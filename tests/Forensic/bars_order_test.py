"""
Orden de las velas (bug de TimescaleDB: ORDER BY time desordenado con plan genérico + fragmentos parcialmente
comprimidos). Parte 1 sin DB: bars_frame / sorted_records. Parte 2 (--db): la base tiene ordered append apagado y
las lecturas reales (backtest, paper, real, régimen y la última vela del collector) salen en orden 10 veces seguidas
sobre la MISMA conexión (desde la 6.ª ejecución asyncpg usa el plan genérico, donde aparecía el bug). Solo lectura.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/bars_order_test.py [--db]
"""
import asyncio
import logging
import os
import random
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from collectors.bars import bars_frame, sorted_records  # noqa: E402

fails = 0
RUNS = 10


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.msgs = []

    def emit(self, record):
        self.msgs.append(record.getMessage())


cap = Capture()
logging.getLogger('collectors.bars').addHandler(cap)
logging.getLogger('collectors.bars').setLevel(logging.WARNING)


def part1():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [(t0 + timedelta(hours=i), 1.0 + i, 2.0 + i, 0.5 + i, 1.5 + i, 10.0 * i) for i in range(50)]

    cap.msgs.clear()
    df = bars_frame(rows, 'asc')
    check('ascendente: igual, sin aviso', list(df['time']) == [r[0] for r in rows] and cap.msgs == [], cap.msgs)
    check('precios en float', all(df[c].dtype == float for c in ('open', 'high', 'low', 'close', 'volume')))

    cap.msgs.clear()
    df = bars_frame(list(reversed(rows)), 'desc')
    check('DESC LIMIT (al revés a propósito): se invierte sin aviso', list(df['time']) == [r[0] for r in rows]
          and cap.msgs == [], cap.msgs)

    shuffled = rows[:]
    random.Random(1).shuffle(shuffled)
    cap.msgs.clear()
    df = bars_frame(shuffled, 'mezcla')
    check('desordenadas: se ordenan y se avisa', list(df['time']) == [r[0] for r in rows]
          and any('fuera de orden' in m for m in cap.msgs), cap.msgs)
    check('cada fila conserva sus precios', all(df.loc[i, 'open'] == 1.0 + i for i in range(50)))

    dup = rows[:10] + [(rows[5][0], 9, 9, 9, 9, 9)] + rows[10:]
    cap.msgs.clear()
    df = bars_frame(dup, 'repetida')
    check('hora repetida: queda una (la última leída) y se avisa', len(df) == 50 and df.loc[5, 'open'] == 9.0
          and any('repetida' in m for m in cap.msgs), cap.msgs)

    check('sin filas: DataFrame vacío con columnas', list(bars_frame([], 'vacío').columns) ==
          ['time', 'open', 'high', 'low', 'close', 'volume'])

    recs = [dict(time=r[0], open=r[1], high=r[2], low=r[3], close=r[4]) for r in rows]
    cap.msgs.clear()
    check('1m en orden: la misma lista, sin aviso', sorted_records(recs, 'm1') == recs and cap.msgs == [])
    mixed = recs[:]
    random.Random(2).shuffle(mixed)
    out = sorted_records(mixed + [recs[3]], 'm1')
    check('1m desordenadas/repetidas: ordenadas, únicas y con aviso', out == recs
          and any('fuera de orden' in m for m in cap.msgs), cap.msgs)


async def part2():
    import asyncpg
    from api.v1.backtest import load_ohlcv
    from collectors.broker_resolver import resolve_live_broker
    from db import DB_DSN

    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=1)  # una sola conexión: fuerza el plan genérico
    try:
        async with pool.acquire() as c:
            setting = await c.fetchval("SHOW timescaledb.enable_ordered_append")
            partial = await c.fetchval(
                "SELECT count(*) FROM timescaledb_information.chunks ch "
                "JOIN _timescaledb_catalog.chunk k ON k.schema_name = ch.chunk_schema AND k.table_name = ch.chunk_name "
                "WHERE ch.hypertable_name = 'ohlcv_data' AND k.status & 8 = 8")
        check('base: timescaledb.enable_ordered_append = off (conexión nueva)', setting == 'off', setting)
        print(f'INFO fragmentos parcialmente comprimidos: {partial} (0 tras la recompresión)')

        now = datetime.now(timezone.utc)
        cases = [('BTCUSDT', '60', 760), ('ETHUSDT', '240', 760), ('SOLUSDT', 'D', 760), ('DOGEUSDT', '15', 400),
                 ('BTCUSDT', '1', 45)]
        for sym, iv, days in cases:
            broker = await resolve_live_broker(pool, sym, iv, require_fresh=False)
            if broker is None:
                print(f'SKIP {sym}/{iv}: sin datos')
                continue
            bad, sizes, ms = 0, set(), []
            for _ in range(RUNS):
                t = time.perf_counter()
                df = await load_ohlcv(pool, sym, iv, broker, now - timedelta(days=days), now)
                ms.append((time.perf_counter() - t) * 1000)
                bad += int(not df['time'].is_monotonic_increasing or df['time'].duplicated().any())
                sizes.add(len(df))
            check(f'backtest {sym}/{iv}: {RUNS} lecturas en orden y del mismo tamaño', bad == 0 and len(sizes) == 1,
                  dict(bad=bad, sizes=sizes))
            print(f'INFO   {sym}/{iv}: {sizes.pop()} velas, mediana {statistics.median(ms):.0f} ms')

            # Lecturas en vivo (DESC LIMIT): las crudas deben venir en orden inverso exacto y ser las ÚLTIMAS 500
            async with pool.acquire() as c:
                last = await c.fetchval("SELECT max(time) FROM ohlcv_data WHERE broker=$1 AND symbol=$2 AND interval=$3",
                                        broker, sym, iv)
                bad, ms = 0, []
                q = ("SELECT time, open, high, low, close, volume FROM ohlcv_data "
                     "WHERE broker = $1 AND symbol = $2 AND interval = $3 ORDER BY time DESC LIMIT 500")
                for _ in range(RUNS):
                    t = time.perf_counter()
                    rows = await c.fetch(q, broker, sym, iv)
                    ms.append((time.perf_counter() - t) * 1000)
                    times = [r['time'] for r in rows]
                    bad += int(any(a <= b for a, b in zip(times, times[1:])) or times[0] != last)
                check(f'vivo {sym}/{iv}: {RUNS} lecturas DESC LIMIT 500 en orden y empezando en la última vela',
                      bad == 0, bad)
                print(f'INFO   DESC LIMIT 500 mediana {statistics.median(ms):.0f} ms')
                ms, badl = [], 0
                for _ in range(RUNS):
                    t = time.perf_counter()
                    v = await c.fetchval("SELECT time FROM ohlcv_data WHERE broker = $1 AND symbol = $2 "
                                         "AND interval = $3 ORDER BY time DESC LIMIT 1", broker, sym, iv)
                    ms.append((time.perf_counter() - t) * 1000)
                    badl += int(v != last)
                check(f'collector {sym}/{iv}: la última vela es max(time) {RUNS} veces', badl == 0, badl)
                print(f'INFO   DESC LIMIT 1 mediana {statistics.median(ms):.0f} ms')
    finally:
        await pool.close()

    # Las funciones reales de paper / real / régimen (pool propio de 1 conexión, 10 llamadas)
    from collectors.regime_detector import RegimeDetector
    from trading.paper_trader import PaperTrader
    from trading.real_trader import RealTrader
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=1)
    try:
        for name, obj, call in (
                ('paper', PaperTrader.__new__(PaperTrader), lambda o: o.get_bars('BTCUSDT', '60')),
                ('real', RealTrader.__new__(RealTrader), lambda o: o.get_bars('BTCUSDT', '60')),
                ('régimen', RegimeDetector.__new__(RegimeDetector), lambda o: o.get_bars('BTCUSDT'))):
            obj.pool = pool
            cap.msgs.clear()
            res = [await call(obj) for _ in range(RUNS)]
            ok = all(len(d) > 0 and d['time'].is_monotonic_increasing and not d['time'].duplicated().any() for d in res)
            check(f'{name}.get_bars: {RUNS} lecturas ascendentes, sin repetidas y sin avisos', ok and cap.msgs == [],
                  cap.msgs[:2])
    finally:
        await pool.close()


part1()
if '--db' in sys.argv:
    asyncio.run(part2())
print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

"""
C6-05: la consulta de lotes comprimidos solapados (database/sql/ohlcv_overlap_batches.sql), la misma que usa el comando
`ohlcv:overlap-check`, contra PostgreSQL de pruebas (C5-04; si no, SKIP) sobre una tabla que imita un fragmento
comprimido de TimescaleDB (broker, symbol, interval = segmentby; _ts_meta_min_1/_ts_meta_max_1 = rango de cada lote).
O1 lotes contiguos sin pisarse -> sin solapes            O2 solape parcial -> 1
O3 otro broker con los mismos tiempos -> no es solape   O4 otra temporalidad con los mismos tiempos -> no es solape
O5 lote contenido dentro de otro -> 1                    O6 tras reparar un hueco (lote nuevo dentro del rango) -> 1
O7 varios lotes solapados -> los cuenta todos y da desde cuándo
O9 un lote que empieza en el minuto en que termina el anterior (la vela queda en dos lotes) -> 1
Todo en una transacción que se revierte.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/ohlcv_overlap_check_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tests/Forensic/ (C5-04: barrera de base)
from test_db import require_test_db, test_dsn  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / 'database' / 'sql' / 'ohlcv_overlap_batches.sql').read_text(encoding='utf-8')
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


check('S1: la consulta agrupa por la serie completa de la compresión (broker, symbol, interval)',
      'PARTITION BY broker, symbol, "interval"' in SQL and 'GROUP BY broker, symbol, "interval"' in SQL)
check('S2: la consulta solo lee (sin escrituras ni reparación)',
      not any(w in SQL.lower() for w in ('insert', 'update ', 'delete', 'decompress_chunk', 'compress_chunk(', 'alter', 'drop')))

T0 = datetime(2026, 10, 8, tzinfo=timezone.utc)


def h(n):
    return T0 + timedelta(hours=n)


if require_test_db('B'):
    import asyncpg

    async def main():
        c = await asyncpg.connect(test_dsn())
        tr = c.transaction()
        await tr.start()
        try:
            await c.execute("""CREATE TEMP TABLE fake_comp (broker text, symbol text, "interval" text,
                               _ts_meta_min_1 timestamptz, _ts_meta_max_1 timestamptz)""")
            rows = [
                ('bybit', 'AAA', '1', h(0), h(1)), ('bybit', 'AAA', '1', h(1.01), h(2)), ('bybit', 'AAA', '1', h(2.01), h(3)),   # O1
                ('bybit', 'BBB', '1', h(0), h(2)), ('bybit', 'BBB', '1', h(1.5), h(3)),                                       # O2
                ('binance', 'BBB', '1', h(0.5), h(2.5)),                                                                     # O3
                ('bybit', 'AAA', '5', h(0), h(3)),                                                                           # O4
                ('bybit', 'CCC', '1', h(0), h(10)), ('bybit', 'CCC', '1', h(3), h(4)),                                       # O5
                ('bybit', 'DDD', '1', h(0), h(1)), ('bybit', 'DDD', '1', h(1.01), h(2)), ('bybit', 'DDD', '1', h(0.4), h(0.6)),  # O6
                ('bybit', 'EEE', '1', h(0), h(5)), ('bybit', 'EEE', '1', h(1), h(2)), ('bybit', 'EEE', '1', h(3), h(6)),     # O7
                ('bybit', 'FFF', '1', h(0), h(1)), ('bybit', 'FFF', '1', h(1), h(2)),                                       # O9
            ]
            await c.executemany('INSERT INTO fake_comp VALUES ($1, $2, $3, $4, $5)', rows)
            got = await c.fetch(SQL.replace('{comp}', 'pg_temp.fake_comp'))
            res = {(r['broker'], r['symbol'], r['interval']): (r['lotes'], r['desde']) for r in got}
            check('O1: lotes contiguos sin pisarse -> sin solapes', ('bybit', 'AAA', '1') not in res, res)
            check('O2: solape parcial -> 1 lote', res.get(('bybit', 'BBB', '1'), (0,))[0] == 1, res)
            check('O3: otro broker con los mismos tiempos -> no es solape (falso positivo evitado)', ('binance', 'BBB', '1') not in res, res)
            check('O4: otra temporalidad con los mismos tiempos -> no es solape', ('bybit', 'AAA', '5') not in res, res)
            check('O5: lote contenido dentro de otro -> 1', res.get(('bybit', 'CCC', '1'), (0,))[0] == 1, res)
            check('O6: tras reparar un hueco (lote nuevo dentro del rango) -> 1', res.get(('bybit', 'DDD', '1'), (0,))[0] == 1, res)
            check('O7: varios solapados -> los cuenta todos y da desde cuándo', res.get(('bybit', 'EEE', '1')) == (2, h(1)), res)
            check('O9: un lote que empieza en el mismo minuto en que termina el anterior (vela en dos lotes) -> 1',
                  res.get(('bybit', 'FFF', '1'), (0,))[0] == 1, res)
            check('O8: solo esas 5 series', sorted(k[1] for k in res) == ['BBB', 'CCC', 'DDD', 'EEE', 'FFF'], sorted(res))
        finally:
            await tr.rollback()
            await c.close()

    asyncio.run(main())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

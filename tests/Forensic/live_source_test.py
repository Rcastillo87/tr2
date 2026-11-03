"""
C-11: en vivo (Paper, Real, régimen) la fuente de velas es SOLO el mercado que se opera (Bybit perpetuos). Antes se
elegía la fuente con la vela más reciente entre todas las de ohlcv_data; sin exigir vela fresca (SL/TP, break-even y
funding de posiciones abiertas) podía tomar binance_vision (spot importado, meses atrasado) y dejar el SL/TP sin evaluar
y sin aviso. El backtest conserva su regla (mayor cobertura; Bybit desempata).
Sin base de datos: pool simulado con la última vela por (broker, symbol, interval).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/live_source_test.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/

import collectors.broker_resolver as br  # noqa: E402

fails = 0
NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
SEP30 = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)   # última vela real de binance_vision (lectura 03-nov)


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Pool:
    """last[(broker, symbol, interval)] = última vela. Acepta la consulta nueva (fetchval) y la anterior (fetch)."""
    def __init__(self, last):
        self.last, self.queries, self.read_from = last, 0, []

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self):
                return Conn(pool)

            async def __aexit__(self, *e):
                return False
        return _C()

    async def fetch(self, sql, *a):   # list_brokers del código anterior usa pool.acquire; por si acaso
        return await Conn(self).fetch(sql, *a)


class Conn:
    def __init__(self, pool):
        self.p = pool

    async def fetchval(self, sql, broker, symbol, interval):
        self.p.queries += 1
        return self.p.last.get((broker, symbol, interval))

    async def fetchrow(self, sql, broker, *a):   # lectura de velas de 1m (extremos desde la entrada)
        self.p.read_from.append(broker)
        return {'hi': None, 'lo': None}

    async def fetch(self, sql, *a):
        self.p.queries += 1
        if 'RECURSIVE' in sql:
            return [{'broker': b} for b in sorted({k[0] for k in self.p.last})]
        brokers, symbol, interval = a
        return [{'broker': b, 'last_bar': self.p.last.get((b, symbol, interval))} for b in brokers]


async def resolve(last, symbol, interval, fresh=True):
    if hasattr(br, '_broker_cache'):
        br._broker_cache = (0.0, [])   # código anterior: cache de brokers por proceso
    pool = Pool(last)
    return await br.resolve_live_broker(pool, symbol, interval, require_fresh=fresh), pool.queries


async def main():
    logging.disable(logging.CRITICAL)
    xrp = {('bybit', 'XRPUSDT', '1'): NOW - timedelta(minutes=1), ('binance_vision', 'XRPUSDT', '1'): SEP30,
           ('bybit', 'XRPUSDT', '60'): NOW - timedelta(hours=1), ('binance_vision', 'XRPUSDT', '60'): SEP30}
    b, q = await resolve(xrp, 'XRPUSDT', '60')
    check('L1 caso normal (Bybit al día): Bybit', b == 'bybit', b)
    check('L2 una sola consulta por resolución (antes: lista de brokers + una subconsulta por fuente)', q == 1, q)

    no_bybit_1m = {k: v for k, v in xrp.items() if k != ('bybit', 'XRPUSDT', '1')}
    b, _ = await resolve(no_bybit_1m, 'XRPUSDT', '1', fresh=False)
    check('L3 sin 1m de Bybit (SL/TP de posiciones abiertas): ninguna fuente, NO binance_vision', b is None, b)

    stale = dict(xrp)
    stale[('bybit', 'XRPUSDT', '1')] = SEP30 - timedelta(days=3)   # Bybit más vieja que binance_vision
    b, _ = await resolve(stale, 'XRPUSDT', '1', fresh=False)
    check('L4 Bybit más atrasada que binance_vision (sin exigir fresca): sigue siendo Bybit', b == 'bybit', b)
    b, _ = await resolve(stale, 'XRPUSDT', '1', fresh=True)
    check('L5 Bybit atrasada (exigiendo fresca): ninguna fuente, no se opera', b is None, b)

    edge = {('bybit', 'BTCUSDT', '60'): NOW - timedelta(hours=4)}
    b, _ = await resolve(edge, 'BTCUSDT', '60')
    check('L5b límite: H1 con 4 h de atraso (> 3 velas) no se opera', b is None, b)
    edge = {('bybit', 'BTCUSDT', '60'): NOW - timedelta(hours=2, minutes=50)}
    b, _ = await resolve(edge, 'BTCUSDT', '60')
    check('L5c límite: H1 con 2 h 50 min de atraso (< 3 velas) sí se opera', b == 'bybit', b)

    other = dict(xrp)
    other[('otra', 'XRPUSDT', '60')] = NOW   # una fuente nueva con la vela más reciente
    b, _ = await resolve(other, 'XRPUSDT', '60')
    check('L6 otra fuente con la vela más reciente: en vivo se usa igual Bybit', b == 'bybit', b)

    naive = {('bybit', 'BTCUSDT', '60'): (NOW - timedelta(hours=1)).replace(tzinfo=None)}
    b, _ = await resolve(naive, 'BTCUSDT', '60')
    check('L7 hora sin zona horaria desde la base: se trata como UTC', b == 'bybit', b)
    b, _ = await resolve({}, 'BTCUSDT', '60')
    check('L8 sin velas: ninguna fuente', b is None, b)

    # Real: break-even usa los extremos de 1m desde la entrada
    import trading.real_trader as rt
    trader = rt.RealTrader.__new__(rt.RealTrader)
    trader.pool = Pool(no_bybit_1m)
    if hasattr(br, '_broker_cache'):
        br._broker_cache = (0.0, [])
    hi, lo = await trader._minute_extremes_since_entry(
        {'symbol': 'XRPUSDT', 'entry_time': NOW - timedelta(hours=2)})
    check('R1 Real (break-even) sin 1m de Bybit: no lee velas de binance_vision',
          (hi, lo) == (None, None) and 'binance_vision' not in trader.pool.read_from, trader.pool.read_from)

    # Backtest: su regla no cambia (mayor cobertura; con empate, Bybit)
    t0 = datetime(2024, 6, 1, tzinfo=timezone.utc)
    cov = lambda broker, bars: br.SourceCoverage(broker, 'BTCUSDT', '60', None, None, t0,  # noqa: E731
                                                 t0 + timedelta(hours=bars - 1), bars)
    pick = br.pick_best_source([cov('bybit', 10000), cov('binance_vision', 20000)])
    check('B1 backtest: binance_vision con más historia sigue pudiendo elegirse', pick.broker == 'binance_vision', pick.broker)
    pick = br.pick_best_source([cov('binance_vision', 20000), cov('bybit', 20000)])
    check('B2 backtest: con empate gana Bybit', pick.broker == 'bybit', pick.broker)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

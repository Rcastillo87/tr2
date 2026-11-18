"""
R-06 (p67): /backtest/run hace la simulación (CPU) en un hilo y de a una. El event loop del motor (único proceso:
ticks Real, circuit breaker, conciliación, Paper) sigue atendiendo mientras corre. Producción 13-nov: un backtest de 24
meses congelaba el proceso 1,64 s; en un hilo, 0,01 s. Sin DB: datos sintéticos (arnés de end_of_data_test) y una
simulación que gasta ~0,8 s de CPU en Python puro (sostiene el GIL como el motor real).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/backtest_offloop_test.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import numpy as np  # noqa: E402
from fastapi import HTTPException  # noqa: E402

import end_of_data_test as eod  # noqa: E402  (velas sintéticas y estrategia de prueba)
import api.v1.backtest as api  # noqa: E402
from collectors.funding_collector import FundingData  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


BURN = 0.8
state = {'now': 0, 'max': 0, 'runs': 0}
RealEngine = api.BacktestEngine


class SlowEngine(RealEngine):
    def run(self):
        state['now'] += 1
        state['max'] = max(state['max'], state['now'])
        state['runs'] += 1
        try:
            t, x = time.perf_counter(), 0
            while time.perf_counter() - t < BURN:   # CPU en Python puro
                x += 1
            return super().run()
        finally:
            state['now'] -= 1


df = eod.bars(sig={4: 1})


async def _load(pool, symbol, interval, start, end, **k):
    fd = FundingData(symbol, np.array([], dtype='datetime64[ns]'), np.array([], dtype=float), start, end)
    return api.BacktestData(df=df, macro_df=None, minute_df=None, warnings=[], coverage={}, funding=fd)


class _Pool:
    async def close(self):
        pass


async def _pool():
    return _Pool()


api.load_backtest_data, api.get_pool = _load, _pool


def req(code=eod.CODE):
    return api.BacktestRequest(strategy='S', strategy_code=code, symbol='BTCUSDT', interval='60', sl_pct=5.0,
                               tp_pct=10.0, be_pct=50.0, max_duration=0, regime_filter=False, start_date='2026-03-02',
                               end_date='2026-03-02', walk_forward=False, slippage_pct=0.05, commission_pct=0.055)


async def probe(stop, gaps):
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(0.02)
        now = time.perf_counter()
        gaps.append(now - last - 0.02)
        last = now


async def with_probe(coro):
    stop, gaps = asyncio.Event(), []
    task = asyncio.create_task(probe(stop, gaps))
    await asyncio.sleep(0.05)
    try:
        out = await coro
    finally:
        stop.set()
        await task
    return out, max(gaps)


# Referencia: el mismo backtest con el motor normal (resultado que debe repetirse)
ref = asyncio.run(api.run_backtest(req()))['result']

api.BacktestEngine = SlowEngine
out, gap = asyncio.run(with_probe(api.run_backtest(req())))
r = out['result']
check(f'O1 mientras simula (~{BURN} s de CPU) el event loop no se congela (< 0,25 s seguidos)', gap < 0.25, f'{gap:.2f} s')
check('O2 el resultado es idéntico al del motor normal (trades y métricas)',
      r['trades'] == ref['trades'] and r['metrics'] == ref['metrics'] and r['ready_for_paper'] == ref['ready_for_paper'],
      (len(r['trades']), len(ref['trades'])))


async def two():
    return await asyncio.gather(api.run_backtest(req()), api.run_backtest(req()))

state.update(max=0, runs=0)
t = time.perf_counter()
(a, b), gap2 = asyncio.run(with_probe(two()))
dur = time.perf_counter() - t
check('O3 dos backtests a la vez: corren de a uno (nunca 2 simulaciones simultáneas)', state['max'] == 1 and state['runs'] == 2,
      dict(state))
check('O4 los dos terminan bien y el loop sigue libre mientras esperan su turno', a['status'] == b['status'] == 'ok'
      and gap2 < 0.25 and dur >= 2 * BURN * 0.95, f'gap {gap2:.2f} s, total {dur:.2f} s')

api.BacktestEngine = RealEngine
try:
    asyncio.run(api.run_backtest(req(code='')))
    check('O5 un error dentro del hilo (estrategia sin código) sigue respondiendo 400', False, 'no lanzó')
except HTTPException as e:
    check('O5 un error dentro del hilo (estrategia sin código) sigue respondiendo 400', e.status_code == 400, e.status_code)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

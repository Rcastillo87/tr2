"""
REAL-10: el trailing fijo se activa en el mismo punto en backtest, Paper y Real (mínimo compartido de 0,3 % con buffer 0).
REAL-11: el tamaño mínimo y el paso de la moneda son los reales de Bybit (caché 6 h, último dato real si Bybit falla) y,
sin ningún dato, no se envía la orden (antes se inventaba 0.001 / 0.001).
Sin red ni base de datos: Bybit simulado.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_lot_trailing_test.py
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/
logging.disable(logging.CRITICAL)

import pandas as pd  # noqa: E402

import real_parity_test as rp  # noqa: E402  (pool/cliente simulados; anula las esperas)
import trading.real_trader as rt  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.base_strategy import calculate_trailing_sl_standalone as trail  # noqa: E402

fails = 0
CODE = "class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 0\n        return df\n"


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


# ─────────────── REAL-10: mismo punto de activación ───────────────
def trailing_cases():
    df = pd.DataFrame({'time': [pd.Timestamp('2026-01-01')], 'open': [100.0], 'high': [100.0], 'low': [100.0],
                       'close': [100.0], 'volume': [1.0]})
    for buf in (0.0, 0.5, 1.0):
        eff = buf if buf > 0 else 0.3
        s = rt.build_strategy({'symbol': 'BTCUSDT', 'interval': '60', 'trailing_mode': 'fixed',
                               'trailing_distance_pct': 1.0, 'trailing_activation_buffer_pct': buf, 'strategy_code': CODE})
        eng = BacktestEngine(s, df)._trail_buf
        for side in ('long', 'short'):
            sign = 1 if side == 'long' else -1
            _, active = rt.compute_native_trailing_params(100.0, side, 1.0,
                                                          buffer_pct=((buf if buf > 0 else rt.NATIVE_TRAILING_MIN_BUFFER_PCT) / 100))
            sl0 = 99.0 if side == 'long' else 101.0
            below = trail('fixed', 1.0, [], 100.0, side, 100.0 + sign * (eff - 0.05), sl0, activation_buffer_pct=buf)
            above = trail('fixed', 1.0, [], 100.0, side, 100.0 + sign * (eff + 0.05), sl0, activation_buffer_pct=buf)
            ok = (abs(active - (100.0 + sign * eff)) < 1e-9 and abs(eng - eff) < 1e-12
                  and below == sl0 and above != sl0)
            check(f'T buffer {buf} {side}: Real activa en {100 + sign * eff:.2f}; backtest/Paper igual', ok,
                  (active, eng, below, above))
    check('T sin números sueltos: el 0,3 % de Real es la constante compartida',
          rt.compute_native_trailing_params.__defaults__[0] == rt.NATIVE_TRAILING_MIN_BUFFER_PCT / 100)


# ─────────────── REAL-11: lote real ───────────────
class Http:
    """httpx.AsyncClient simulado para instruments-info: responde la cola `answers` (dict o Exception)."""
    answers, calls = [], 0

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *e):
        return False

    async def get(self, url, params=None):
        Http.calls += 1
        a = Http.answers.pop(0) if len(Http.answers) > 1 else Http.answers[0]
        if isinstance(a, Exception):
            raise a

        class R:
            def json(self_):
                return a
        return R()


def lot(min_qty, step):
    return {'retCode': 0, 'result': {'list': [{'lotSizeFilter': {'minOrderQty': str(min_qty), 'qtyStep': str(step)}}]}}


async def lot_cases():
    rt.httpx.AsyncClient = Http
    rt._LOT_CACHE.clear()
    clock = [1_000_000.0]
    rt.time.time = lambda: clock[0]
    c = rt.BybitClient('k', 's', 'demo')

    Http.answers, Http.calls = [lot(1, 1)], 0
    r1 = await c.get_lot_size('DOGEUSDT')
    clock[0] += 3600
    r2 = await c.get_lot_size('DOGEUSDT')
    check('L1 lote real de Bybit y caché: una sola consulta en 1 h', r1 == (1.0, 1.0) and r2 == r1 and Http.calls == 1,
          (r1, r2, Http.calls))

    clock[0] += 6 * 3600
    Http.answers = [RuntimeError('caída')]
    r3 = await c.get_lot_size('DOGEUSDT')
    check('L2 caché vencida y Bybit cae: usa el último dato real', r3 == (1.0, 1.0) and Http.calls == 2, (r3, Http.calls))

    Http.answers = [{'retCode': 10002, 'retMsg': 'timestamp'}]
    r4 = await c.get_lot_size('NEARUSDT')
    check('L3 sin dato previo y Bybit falla: None (no inventa 0.001)', r4 is None, r4)

    Http.answers = [lot(0, 0)]
    r5 = await c.get_lot_size('LINKUSDT')
    check('L4 lote inválido (0): se trata como falla', r5 is None, r5)

    Http.answers = [{'retCode': 0, 'result': {'list': []}}]
    r6 = await c.get_lot_size('ENAUSDT')
    check('L5 moneda sin datos: None', r6 is None, r6)

    check('L6 get_min_qty (solo scripts demo) conserva el respaldo', await c.get_min_qty('ENAUSDT') == (0.001, 0.001))

    demo = rt.BybitClient('k', 's', 'demo')
    real = rt.BybitClient('k', 's', 'real')
    rt._LOT_CACHE.clear()
    Http.answers, Http.calls = [lot(0.1, 0.1), lot(1, 1)], 0
    a, b = await demo.get_lot_size('NEARUSDT'), await real.get_lot_size('NEARUSDT')
    check('L7 caché separada por entorno (demo / real)', a == (0.1, 0.1) and b == (1.0, 1.0) and Http.calls == 2, (a, b))


def rounding_cases():
    cases = [((0.3, 0.1), 0.3), ((1234.56, 1), 1234), ((12345, 100), 12300), ((0.0129, 0.001), 0.012),
             ((5.0, 1), 5), ((0.7, 0.1), 0.7), ((2.675, 0.01), 2.67)]
    bad = [(args, exp, rt.floor_to_step(*args)) for args, exp in cases if abs(rt.floor_to_step(*args) - exp) > 1e-12]
    check('R1 redondeo al paso sin perder un paso por coma flotante (0.3 / 0.1, 0.7 / 0.1 …)', not bad, bad)


class LotClient(rp.FakeClient):
    def __init__(self, lot_size, price=100.0):
        super().__init__(price=price, fill_on_check=2)
        self._lot = lot_size

    async def get_lot_size(self, symbol):
        return self._lot


async def open_cases():
    strat = rt.build_strategy({**rp.P, 'symbol': 'DOGEUSDT', 'interval': '60'})
    sub = {'symbol': 'DOGEUSDT', 'interval': '60', 'broker_account_id': 7, 'user_id': 1, 'subscription_id': 1,
           'paper_strategy_config_id': 9, 'strategy': 'T', 'broker': 'bybit',
           'config_params': {**rp.P, 'risk_per_trade_pct': 1.0, 'max_leverage': 5}}
    s = {'exec': []}
    c = LotClient(None, price=0.2)
    ok = await rt.RealTrader(rp.FakePool(s)).open_trade(sub, strat, 'long', 0.2, 'RANGING', c)
    ev = [(a[2], json.loads(a[3])) for sql, a in s['exec'] if 'INSERT INTO broker_events' in sql]
    check('O1 sin lote de Bybit: no envía la orden y avisa (open_rejected con el motivo)',
          not ok and not c.orders and [e[0] for e in ev] == ['open_rejected'] and 'tamaño mínimo' in ev[0][1].get('reason', ''),
          (ok, c.orders, ev))
    s = {'exec': []}
    c = LotClient((1.0, 1.0), price=0.2)
    ok = await rt.RealTrader(rp.FakePool(s)).open_trade(sub, strat, 'long', 0.2, 'RANGING', c)
    qty = c.orders[0][1] if c.orders else None
    check('O2 DOGE (paso 1): la orden sale con cantidad entera', ok and qty is not None and float(qty).is_integer(), qty)

    # O3. Apertura real con trailing fijo: el activePrice que se envía a Bybit usa el mismo mínimo que el backtest
    for buf, eff in ((0.0, 0.3), (0.8, 0.8)):
        params = {**rp.P, 'trailing_mode': 'fixed', 'trailing_distance_pct': 1.0, 'trailing_activation_buffer_pct': buf}
        st = rt.build_strategy({**params, 'symbol': 'BTCUSDT', 'interval': '60'})
        sb = {**sub, 'symbol': 'BTCUSDT', 'config_params': {**params, 'risk_per_trade_pct': 1.0}}
        c = LotClient((0.001, 0.001), price=100.0)
        ok = await rt.RealTrader(rp.FakePool({'exec': []})).open_trade(sb, st, 'long', 100.0, 'RANGING', c)
        sent = [k.get('active_price') for _, _, k in c.stops if k.get('active_price')]
        fill = 100.2   # avgPrice de la posición en el cliente simulado (rp.FakeClient)
        check(f'O3 apertura con trailing fijo y buffer {buf}: activePrice = fill × (1 + {eff} %)',
              ok and sent and abs(sent[0] - round(fill * (1 + eff / 100), 8)) < 1e-6, (sent, fill))


async def main():
    trailing_cases()
    await lot_cases()
    rounding_cases()
    await open_cases()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

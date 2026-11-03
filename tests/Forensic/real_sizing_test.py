"""
REAL-07: el tamaño de Real usa la MISMA regla que el backtest: riesgo % del saldo / distancia al SL, con tope de nocional
saldo × max_leverage (max_leverage limita el tamaño; el apalancamiento de la cuenta se configura en Bybit).
Sin base de datos ni Bybit: pool y cliente simulados, sin órdenes reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_sizing_test.py
"""
import asyncio
import math
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import pandas as pd  # noqa: E402

import real_parity_test as rp  # noqa: E402  (pool/cliente simulados; anula las esperas)
import trading.real_trader as rt_mod  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0
STEP = 0.001


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Client(rp.FakeClient):
    def __init__(self, balance, price):
        super().__init__(price=price, fill_on_check=2)
        self._bal = balance

    async def get_balance(self):
        return self._bal


def engine_size(params, balance, risk, price, sl_pct, side):
    """Tamaño del motor de backtest con el mismo saldo, riesgo, precio y SL, redondeado al paso de Bybit."""
    s = rt_mod.build_strategy({**params, 'symbol': 'BTCUSDT', 'interval': '60'})
    df = pd.DataFrame({'time': [pd.Timestamp('2026-01-01')], 'open': [price], 'high': [price], 'low': [price],
                       'close': [price], 'volume': [1.0]})
    e = BacktestEngine(s, df, initial_balance=balance, risk_per_trade_pct=risk)
    sl = round(price * (1 - sl_pct / 100) if side == 'long' else price * (1 + sl_pct / 100), 8)
    raw = e._position_size(price, sl)
    decimals = max(0, -int(math.floor(math.log10(STEP))))
    return round(math.floor(raw / STEP) * STEP, decimals)


async def real_size(params, balance, risk, price, side):
    sub = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 1, 'user_id': 1, 'subscription_id': 1,
           'paper_strategy_config_id': 9, 'strategy': 'T', 'broker': 'bybit',
           'config_params': {**params, 'risk_per_trade_pct': risk}}
    strat = rt_mod.build_strategy({**params, 'symbol': 'BTCUSDT', 'interval': '60'})
    c = Client(balance, price)
    try:
        ok = await RealTrader(rp.FakePool({'exec': []})).open_trade(sub, strat, side, price, 'RANGING', c)
    except Exception as e:  # noqa: BLE001 - una excepción es un fallo de la prueba, no un crash
        return f'EXCEPCIÓN {type(e).__name__}: {e}'
    return c.orders[0][1] if ok and c.orders else 0.0


async def main():
    cases = [
        # (etiqueta, max_leverage, saldo, riesgo %, precio, sl %, lado)
        ('riesgo manda (tope holgado)', 1.0, 1000.0, 1.0, 100.0, 2.0, 'long'),
        ('tope 1x manda (SL muy ajustado)', 1.0, 1000.0, 1.0, 100.0, 0.5, 'long'),
        ('tope 3x manda', 3.0, 1000.0, 2.0, 100.0, 0.5, 'short'),
        ('tope 0,5x manda', 0.5, 1000.0, 1.0, 100.0, 1.5, 'long'),
        ('sin max_leverage en la config (default 1x)', None, 1000.0, 1.0, 100.0, 0.5, 'long'),
        ('max_leverage = 0 (el motor lo trata como 1x)', 0, 1000.0, 1.0, 100.0, 0.5, 'long'),
        ('max_leverage = null (el motor lo trata como 1x)', 'null', 1000.0, 1.0, 100.0, 0.5, 'long'),
        ('max_leverage en texto "2"', '2', 1000.0, 1.0, 100.0, 0.25, 'short'),
    ]
    for label, lev, bal, risk, price, sl_pct, side in cases:
        params = dict(rp.P, sl_pct=sl_pct)
        if lev == 'null':
            params['max_leverage'] = None
        elif lev is not None:
            params['max_leverage'] = lev
        exp = engine_size(params, bal, risk, price, sl_pct, side)
        got = await real_size(params, bal, risk, price, side)
        check(f'{label}: Real = motor ({exp})', isinstance(got, float) and abs(got - exp) < 1e-9, got)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

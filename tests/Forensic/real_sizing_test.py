"""
REAL-07: el tamaño de Real usa la MISMA regla que el backtest: riesgo % del saldo / distancia al SL, con tope de nocional
saldo × max_leverage (max_leverage limita el tamaño; el apalancamiento de la cuenta se configura en Bybit).
Sin base de datos ni Bybit: pool y cliente simulados, sin órdenes reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_sizing_test.py
"""
import asyncio
import json
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

    # C5-19 (p97): el precio se movió más de 0,5 % entre la señal y el envío: el tamaño se recalcula con el último precio
    class Moving(Client):
        def __init__(self, balance, prices):
            super().__init__(balance, prices[0])
            self.prices = list(prices)

        async def get_market_price(self, symbol):
            return self.prices.pop(0) if len(self.prices) > 1 else self.prices[0]
    params = dict(rp.P, sl_pct=2.0, max_leverage=5)
    sub = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 1, 'user_id': 1, 'subscription_id': 1,
           'paper_strategy_config_id': 9, 'strategy': 'T', 'broker': 'bybit', 'config_params': {**params, 'risk_per_trade_pct': 1.0}}
    strat = rt_mod.build_strategy({**params, 'symbol': 'BTCUSDT', 'interval': '60'})
    s = {'exec': []}
    c = Moving(1000.0, [100.0, 102.0])
    ok = await RealTrader(rp.FakePool(s)).open_trade(sub, strat, 'long', 100.0, 'RANGING', c)
    sent = c.orders[0][1] if c.orders else None
    exp = round(math.floor((1000 * 0.01 / (102.0 * 0.02)) / STEP) * STEP, 3)
    check('Z1: precio 100 → 102 (2 %): se envía el tamaño recalculado con 102 (riesgo = 1 %)',
          ok and sent is not None and abs(sent - exp) < 1e-9 and abs(sent - 5.0) > 1e-9, (sent, exp))
    upd = [a for q, a in s['exec'] if 'SET sl=$1, tp=$2, entry_price_signal=$3, size=$5' in q]
    check('Z2: la fila guarda el tamaño enviado', upd and abs(upd[-1][4] - sent) < 1e-9, upd[-1] if upd else '')
    audit = json.loads(s.get('audit') or '[]') if isinstance(s.get('audit'), str) else (s.get('audit') or [])
    opened = [e for e in audit if e.get('action') == 'opened']
    check('Z3: el historial guarda el riesgo previsto y el real (con el fill y el SL final)',
          opened and opened[-1]['data'].get('risk_planned_pct') == 1.0 and opened[-1]['data'].get('risk_real_pct') is not None,
          opened[-1]['data'] if opened else audit)
    s = {'exec': []}
    c = Moving(1000.0, [100.0, 100.3])
    await RealTrader(rp.FakePool(s)).open_trade(sub, strat, 'long', 100.0, 'RANGING', c)
    check('Z4: movimiento de 0,3 % (< 0,5 %): el tamaño no cambia (5.0)', c.orders and abs(c.orders[0][1] - 5.0) < 1e-9,
          c.orders[0][1] if c.orders else '')

    # C5-20 (p98): riesgo propio de la suscripción (risk_override_pct). Válido (0 < r ≤ 100) manda sobre la
    # configuración; inválido no abre, no envía nada a Bybit y avisa open_rejected con el motivo.
    async def with_override(override, cfg_risk=1.0):
        sub_o = dict(sub, risk_override_pct=override, config_params={**params, 'risk_per_trade_pct': cfg_risk})
        st = {'exec': []}
        c = Client(1000.0, 100.0)
        ok = await RealTrader(rp.FakePool(st)).open_trade(sub_o, strat, 'long', 100.0, 'RANGING', c)
        ev = [a for q, a in st['exec'] if 'INSERT INTO broker_events' in q]
        return ok, (c.orders[0][1] if c.orders else None), ev, c
    ok, sent, ev, _ = await with_override('2.00')
    check('V1: riesgo propio 2 % (texto, como lo entrega Laravel) manda sobre el 1 % de la configuración: tamaño doble',
          ok and sent is not None and abs(sent - 10.0) < 1e-9 and not ev, (ok, sent, ev))
    ok, sent, ev, _ = await with_override(None, 1.5)
    check('V2: sin riesgo propio usa el de la configuración (1,5 %)', ok and sent is not None and abs(sent - 7.5) < 1e-9,
          (ok, sent))
    for tag, bad in (('V3', '0'), ('V4', -1), ('V5', 150), ('V6', 'abc'), ('V7', float('nan')), ('V8', float('inf'))):
        ok, sent, ev, c = await with_override(bad)
        reasons = [json.loads(a[3]).get('reason', '') for a in ev if a[2] == 'open_rejected']
        check(f'{tag}: riesgo propio {bad!r}: no abre, nada a Bybit y aviso open_rejected con el motivo',
              ok is False and not c.orders and reasons and 'riesgo propio de la suscripción inválido' in reasons[0],
              (ok, c.orders, reasons))
    ok, sent, ev, c = await with_override(None, 0)
    reasons = [json.loads(a[3]).get('reason', '') for a in ev if a[2] == 'open_rejected']
    check('V9: sin riesgo propio y riesgo de la configuración 0: no abre y avisa', ok is False and not c.orders
          and reasons and 'riesgo de la configuración inválido' in reasons[0], (ok, reasons))
    ok, sent, ev, c = await with_override('100')
    check('V10: el borde 100 % es válido (lo frena max_leverage, como hoy)', ok and sent is not None and not ev, (ok, sent))
    r, err = RealTrader.subscription_risk({'risk_override_pct': '', 'config_params': '{"risk_per_trade_pct": 0.5}'})
    check('V11: riesgo propio vacío = sin riesgo propio; configuración en texto JSON', r == 0.5 and err is None, (r, err))
    r, err = RealTrader.subscription_risk({'config_params': {}})
    check('V12: configuración sin la clave: 1 % por defecto (como antes)', r == 1.0 and err is None, (r, err))
    r, err = RealTrader.subscription_risk({'config_params': '{roto'})
    check('V13: configuración ilegible: no abre (antes: excepción)', r is None and err and 'ilegible' in err, (r, err))

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

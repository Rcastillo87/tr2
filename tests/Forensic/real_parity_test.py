"""
Paridad Real vs backtest/paper (sin DB ni Bybit: pool y cliente simulados, sin órdenes reales).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_parity_test.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # ejecutar desde python-engine/

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

_real_sleep = asyncio.sleep


async def _no_sleep(*_a, **_k):
    await _real_sleep(0)

asyncio.sleep = _no_sleep  # los esperas de confirmación no hacen falta en el test


async def _live_broker(*_a, **_k):
    return 'bybit'


rt_mod.resolve_live_broker = _live_broker  # fuente de velas fija (sin DB)

CODE = "class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 0\n        return df\n"
P = dict(sl_pct=1.0, tp_pct=4.0, be_pct=1.5, max_duration=5, regime_filter=False, commission_pct=0.055,
         strategy_code=CODE)
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class FakeConn:
    def __init__(self, s):
        self.s = s

    def transaction(self):
        class _T:
            async def __aenter__(self_):
                return self_

            async def __aexit__(self_, *e):
                return False
        return _T()

    async def execute(self, sql, *a):
        self.s['exec'].append((sql, a))
        if 'SET audit_log' in sql:
            self.s['audit'] = a[0]
        return "UPDATE 1"

    async def fetchval(self, sql, *a):
        if 'audit_log' in sql:
            return self.s.get('audit')
        if 'INSERT INTO real_trades' in sql:
            self.s['insert'] = a
            return 77
        return None

    async def fetchrow(self, sql, *a):
        if 'max(high)' in sql:
            return self.s.get('extremes')
        return None

    async def fetch(self, sql, *a):
        return []


class FakePool:
    def __init__(self, s):
        self.s = s

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return FakeConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


class FakeClient:
    def __init__(self, position=None, order_status='Filled', history=None, price=100.0, fill_on_check=None):
        self.position, self.order_status, self.history, self.price = position, order_status, history or [], price
        self.stops, self.orders, self.checks, self.fill_on_check = [], [], 0, fill_on_check

    async def get_open_position(self, symbol):
        self.checks += 1
        if self.fill_on_check is not None:
            return {'size': '1', 'avgPrice': '100.2'} if self.checks >= self.fill_on_check else None
        return self.position

    async def set_trading_stop(self, symbol, sl, tp=None, **k):
        self.stops.append((sl, tp, k))
        return True

    async def place_market_order(self, symbol, side, qty, sl=None, tp=None):
        self.orders.append((side, qty, sl, tp))
        return {'orderId': 'X1'}

    async def get_order(self, symbol, order_id):
        return {'orderStatus': self.order_status, 'avgPrice': str(self.price)}

    async def get_market_price(self, symbol):
        return self.price

    async def get_balance(self):
        return 1000.0

    async def get_min_qty(self, symbol):
        return 0.001, 0.001

    async def get_closed_pnl_history(self, symbol, entry, since, limit=20):
        return self.history

    async def get_native_trailing_level(self, symbol):
        return None


def trade(params=P, hours_ago=1.0, sl=99.0, tp=104.0, be_level=101.5, be_activated=False, trailing=False,
          vol_widened=False):
    return {'id': 5, 'subscription_id': 1, 'strategy': 'T', 'symbol': 'BTCUSDT', 'interval': '60', 'side': 'long',
            'entry_price': 100.0, 'sl': sl, 'tp': tp, 'tp2': None, 'tp3': None, 'tp4': None,
            'be_level': be_level, 'be_activated': be_activated, 'size': 1.0, 'original_size': 1.0,
            'realized_pnl_partial': 0, 'entry_time': datetime.now(timezone.utc) - timedelta(hours=hours_ago),
            'updated_at': None, 'order_id': 'A', 'balance_before': 1000.0, 'status': 'open',
            'trailing_applied': trailing, 'original_sl': 99.0, 'config_snapshot': dict(params),
            'vol_widened': vol_widened}


def position(sl=99.0, tp=104.0):
    return {'size': '1', 'avgPrice': '100', 'stopLoss': str(sl), 'takeProfit': str(tp)}


def bars(atr_spike=False):
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    n = 120
    t = [now - timedelta(hours=n - k) for k in range(n)] + [now]  # la última está en formación
    rng = np.full(n + 1, 1.0)
    if atr_spike:
        rng[-6:-1] = 12.0   # velas CERRADAS con rango enorme
    rng[-1] = 0.1          # la vela en formación no debe contar
    c = np.full(n + 1, 100.0)
    return pd.DataFrame({'time': t, 'open': c, 'high': c + rng / 2, 'low': c - rng / 2, 'close': c, 'volume': 1.0})


async def monitor(tr, client, price, df=None, audit=None, extremes=None):
    s = {'exec': [], 'audit': audit, 'extremes': extremes}
    trader = RealTrader(FakePool(s))
    if df is not None:
        async def _bars(symbol, interval, broker=None):
            return df
        trader.get_bars = _bars
    out = await trader._monitor_single_trade(tr, client, {'BTCUSDT': price}, 1)
    return out, s


def closes(s):
    return [a for sql, a in s['exec'] if "status = 'closed'" in sql or "status='closed'" in sql]


async def main():
    # 1. BE nunca baja un SL que ya subió el trailing
    c = FakeClient(position(sl=100.8))
    out, s = await monitor(trade(sl=100.8, trailing=True), c, 101.6)
    check('BE no baja un SL ya subido (sin trading-stop)', not c.stops and out['be_activated'] == 1, c.stops)

    # 2. BE normal mueve SL a la entrada
    c = FakeClient(position())
    out, s = await monitor(trade(), c, 101.6)
    check('BE mueve SL a la entrada', c.stops and c.stops[0][0] == 100.0, c.stops)

    # 2b. Mecha de 1m tocó el BE (101.6) entre ciclos; precio actual 100.5 (> entrada): se activa
    c = FakeClient(position())
    out, s = await monitor(trade(), c, 100.5, extremes={'hi': 101.6, 'lo': 99.8})
    check('BE por mecha de 1m entre ciclos', c.stops and c.stops[0][0] == 100.0 and out['be_activated'] == 1, c.stops)

    # 2c. Mecha tocó el BE pero el precio ya está por debajo de la entrada: no se mueve (Bybit lo rechazaría)
    c = FakeClient(position())
    out, s = await monitor(trade(), c, 99.7, extremes={'hi': 101.6, 'lo': 99.5})
    check('BE alcanzado con precio bajo la entrada: SL no se mueve', not c.stops and out['be_activated'] == 0, c.stops)

    # 3. SL del exchange distinto al de DB (trading-stop fallido) -> se alinea
    c = FakeClient(position(sl=95.0, tp=110.0))
    out, s = await monitor(trade(), c, 100.2)
    check('SL/TP de Bybit alineados a la DB', c.stops and c.stops[0][:2] == (99.0, 104.0), c.stops)

    # 4. Trailing ATR soportado y con ATR de velas CERRADAS
    pa = dict(P, trailing_mode='atr', trailing_atr_mult=2.0, be_pct=50)
    c = FakeClient(position())
    out, s = await monitor(trade(pa, be_level=150), c, 103.0, df=bars())
    # ATR cerrado = 1.0 -> SL = 103 - 2*1 = 101
    check('trailing ATR con ATR de vela cerrada', c.stops and abs(c.stops[0][0] - 101.0) < 1e-6, c.stops)

    # 5. Volatilidad 'widen' una sola vez por trade
    pv = dict(P, volatility_protection_mode='widen', volatility_atr_multiplier=1.5, volatility_widen_pct=1.0, be_pct=50)
    c = FakeClient(position())
    out, s = await monitor(trade(pv, be_level=150), c, 100.1, df=bars(atr_spike=True))
    widened = c.stops[0][0] if c.stops else None
    check('widen aplicado la primera vez', widened is not None and abs(widened - 99.0 * 0.99) < 1e-6, c.stops)
    c2 = FakeClient(position(sl=widened or 0))
    marked = any('vol_widened=true' in sql for sql, a in s['exec'])
    check('widen persistido en vol_widened', marked)
    out, s2 = await monitor(trade(pv, sl=widened or 0, be_level=150, vol_widened=True), c2, 100.1,
                            df=bars(atr_spike=True))
    check('widen NO se repite en el ciclo siguiente', not c2.stops, c2.stops)
    check('audit_log guardado como lista (no string)', isinstance(s['audit'], list), type(s['audit']).__name__)

    # 6. Duración máxima en velas (5 x H1)
    c = FakeClient(position())
    out, s = await monitor(trade(hours_ago=4.9), c, 100.1)
    check('no cierra antes de 5 velas', not c.orders)
    c = FakeClient(position())
    out, s = await monitor(trade(hours_ago=5.0), c, 100.1)
    cl = closes(s)
    check('time_exit a las 5 velas', c.orders and cl and cl[0][2] == 'time_exit', cl[0][:3] if cl else c.orders)
    if cl:
        # cierre al 100.1 (get_order avgPrice=price): comisión entrada + salida
        exp = (100.0 + 100.0) * 1.0 * 0.00055
        check('comisión entrada + salida', abs(cl[0][7] - round(exp, 6)) < 1e-6, cl[0][7])

    # 7. max_duration_profit: en pérdida no cierra
    pp = dict(P, max_duration_profit=True)
    c = FakeClient(position())
    out, s = await monitor(trade(pp, hours_ago=6), c, 99.5)
    check('max_duration_profit: en pérdida sigue abierta', not c.orders)

    # 8. Cierre detectado en Bybit: costos desde closedPnl (sin doble comisión)
    hist = [{'closedSize': '0.6', 'cumEntryValue': '60', 'cumExitValue': '59.4', 'closedPnl': '-0.666'},
            {'closedSize': '0.4', 'cumEntryValue': '40', 'cumExitValue': '39.6', 'closedPnl': '-0.444'}]
    c = FakeClient(position=None, history=hist)
    out, s = await monitor(trade(), c, 99.0)
    cl = closes(s)
    ok = bool(cl) and abs(cl[0][0] - 99.0) < 1e-9 and abs(cl[0][4] - (-1.11)) < 1e-6 and abs(cl[0][5] - 0.11) < 1e-6
    check('cierre en Bybit: neto=closedPnl, comisión=bruto-neto', ok, cl[0][:6] if cl else 'sin cierre')
    check('motivo stop_loss por precio de salida', bool(cl) and cl[0][1] == 'stop_loss', cl[0][1] if cl else '')

    # 9. Apertura: SL de la señal sobre el precio promedio, y sin reenvío ciego
    sub = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 1, 'user_id': 1, 'subscription_id': 1,
           'paper_strategy_config_id': 9, 'strategy': 'T', 'broker': 'bybit', 'config_params': dict(P)}
    strat = rt_mod.build_strategy({**P, 'symbol': 'BTCUSDT', 'interval': '60'})
    s = {'exec': []}
    trader = RealTrader(FakePool(s))
    c = FakeClient(fill_on_check=4)  # se confirma en la 1ª verificación posterior
    ok = await trader.open_trade(sub, strat, 'long', 100.0, 'RANGING', c, signal_sl_pct=2.0)
    final = [a for sql, a in s['exec'] if "SET status = 'open'" in sql]
    check('una sola orden enviada aunque la confirmación tarde', ok and len(c.orders) == 1, len(c.orders))
    check('SL de la señal (2%) sobre el precio promedio', final and abs(final[0][3] - round(100.2 * 0.98, 8)) < 1e-9,
          final[0][3] if final else '')
    check('snapshot guarda signal_sl_pct', s.get('insert') and s['insert'][-1].get('signal_sl_pct') == 2.0)

    s = {'exec': []}
    trader = RealTrader(FakePool(s))
    c = FakeClient(fill_on_check=99, order_status='Rejected')
    ok = await trader.open_trade(sub, strat, 'long', 100.0, 'RANGING', c)
    failed = [a for sql, a in s['exec'] if "status='failed'" in sql]
    check('orden rechazada -> failed, sin reenvío', not ok and len(c.orders) == 1 and failed, (len(c.orders), failed))

    # 10. Snapshot sin código: no tumba el monitor
    bad = {k: v for k, v in P.items() if k != 'strategy_code'}
    out, s = await monitor(trade(bad), FakeClient(position()), 100.0)
    check('snapshot sin código: error controlado', out['errors'] == 1, out)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')


if __name__ == '__main__':
    asyncio.run(main())

"""
Paridad Paper vs motor V3 (sin DB: pool en memoria, no toca producción).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/paper_parity_test.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # ejecutar desde python-engine/

import pandas as pd  # noqa: E402

import trading.paper_trader as pt_mod  # noqa: E402
from trading.paper_trader import PaperTrader  # noqa: E402

NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
P = dict(symbol='BTCUSDT', interval='60', sl_pct=1.0, tp_pct=2.0, be_pct=1.5, max_duration=5,
         regime_filter=False, commission_pct=0.0, slippage_pct=0.0,
         strategy_code="class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 0\n        return df\n")
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class FakeConn:
    def __init__(self, store):
        self.s = store

    async def fetch(self, sql, *a):
        if "interval = '1'" in sql:  # (symbol, desde, hasta, broker)
            return [b for b in self.s['minutes'] if a[1] < b['time'] <= a[2]]
        if 'FROM paper_trades' in sql:
            return [self.s['trade']] if self.s.get('trade') else []
        return []

    async def fetchrow(self, sql, *a):
        return None

    async def execute(self, sql, *a):
        self.s['exec'].append((sql, a))


class FakePool:
    def __init__(self, store):
        self.store = store

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return FakeConn(pool.store)

            async def __aexit__(self, *exc):
                return False
        return _Ctx()


async def _broker(*a, **k):
    return 'bybit'


async def _price(symbol):
    return 100.0


pt_mod.resolve_live_broker = _broker
pt_mod.get_current_price = _price


def minute(t, high=100.4, low=99.6, close=100.0):
    return {'time': t, 'open': 100.0, 'high': high, 'low': low, 'close': close}


def trade(params, hours_ago=1.0, entry=100.0):
    et = NOW - timedelta(hours=hours_ago)
    return {'id': 1, 'strategy': 'T', 'paper_strategy_config_id': 9, 'config_snapshot': json.dumps(params),
            'symbol': 'BTCUSDT', 'interval': '60', 'side': 'long', 'entry_price': entry,
            'sl': entry * 0.99, 'tp': entry * 1.02, 'tp2': None, 'tp3': None, 'tp4': None,
            'be_level': entry * 1.015, 'be_activated': False, 'trailing_applied': False, 'size': 1.0,
            'entry_time': et, 'regime': 'RANGING', 'max_profit_pct': 0, 'max_loss_pct': 0,
            'last_monitored_at': None}


async def run_monitor(params, minutes, hours_ago=1.0):
    store = {'minutes': minutes, 'trade': trade(params, hours_ago), 'exec': []}
    trader = PaperTrader(FakePool(store), {}, {})
    res = await trader.monitor_open_trades()
    closes = [a for sql, a in store['exec'] if "status = 'closed'" in sql]
    return res, closes, store


async def main():
    base_t = NOW - timedelta(minutes=50)

    # 1. SL vigente antes que BE en la misma vela de 1m
    m = [minute(base_t, high=101.6, low=98.9)]
    _, closes, _ = await run_monitor(P, m)
    check('SL vigente antes que break-even (cierre con pérdida)',
          len(closes) == 1 and closes[0][3] == 'stop_loss' and closes[0][1] < 0,
          closes[0][1:4] if closes else 'sin cierre')

    # 2. BE en una vela y SL en la siguiente -> cierra en entrada (0)
    m = [minute(base_t, high=101.6), minute(base_t + timedelta(minutes=1), low=99.5)]
    _, closes, _ = await run_monitor(P, m)
    check('BE activado y luego tocado -> cierre en entrada',
          len(closes) == 1 and abs(closes[0][0] - 100.0) < 1e-9, closes[0][:4] if closes else 'sin cierre')

    # 3. La vela de 1m en formación NO se procesa (el checkpoint no la salta)
    forming = datetime.now(timezone.utc).replace(second=0, microsecond=0)  # minuto en curso (abierto)
    m = [minute(forming, low=98.0)]
    _, closes, store = await run_monitor(P, m)
    upd = [a for sql, a in store['exec'] if 'last_monitored_at' in sql]
    check('vela de 1m en formación ignorada', not closes and upd and upd[0][5] != m[0]['time'].replace(tzinfo=None),
          'cerró' if closes else '')

    # 4. Duración máxima en velas: 5 velas de 60m
    _, closes, _ = await run_monitor(P, [minute(base_t)], hours_ago=4.9)
    check('no cierra antes de 5 velas (4.9h)', not closes)
    _, closes, _ = await run_monitor(P, [minute(base_t)], hours_ago=5.0)
    check('time_exit al cumplir 5 velas', len(closes) == 1 and closes[0][3] == 'time_exit',
          closes[0][3] if closes else 'sin cierre')

    # 5. max_duration_profit: en pérdida no cierra, en ganancia cierra
    P2 = dict(P, max_duration_profit=True)
    _, closes, _ = await run_monitor(P2, [minute(base_t, close=99.8)], hours_ago=6)
    check('max_duration_profit: en pérdida sigue abierta', not closes)
    _, closes, _ = await run_monitor(P2, [minute(base_t, close=100.3)], hours_ago=6)
    check('max_duration_profit: en ganancia -> time_exit_profit',
          len(closes) == 1 and closes[0][3] == 'time_exit_profit', closes[0][3] if closes else 'sin cierre')

    # 6. Slippage en la salida con el snapshot
    P3 = dict(P, slippage_pct=0.05)
    _, closes, _ = await run_monitor(P3, [minute(base_t, low=98.9)])
    check('salida con slippage en contra', len(closes) == 1 and abs(closes[0][0] - 99.0 * 0.9995) < 1e-9,
          closes[0][0] if closes else 'sin cierre')

    # 7. Apertura: slippage + SL de la señal
    store = {'minutes': [], 'exec': []}
    cfg = {'id': 9, 'display_name': 'T', 'symbol': 'BTCUSDT', 'interval': '60', 'params': json.dumps(P3)}
    trader = PaperTrader(FakePool(store), {}, {9: cfg})
    s = pt_mod.build_strategy(trader._get_params_for(9))
    await trader.open_trade(9, s, 'long', 100.0, 'RANGING', signal_sl_pct=2.0)
    ins = [a for sql, a in store['exec'] if 'INSERT INTO paper_trades' in sql][0]
    check('entrada con slippage en contra', abs(ins[5] - 100.05) < 1e-9, ins[5])
    check('SL de la señal (2%) sobre el precio ejecutado', abs(ins[6] - round(100.05 * 0.98, 8)) < 1e-9, ins[6])

    # 8. Velas cerradas por tiempo
    df = pd.DataFrame({'time': [NOW - timedelta(hours=2), NOW - timedelta(hours=1), NOW - timedelta(minutes=10)]})
    closed = PaperTrader._closed_bars(df, '60', NOW)
    check('_closed_bars excluye la vela en formación', len(closed) == 2, len(closed))
    df2 = df.iloc[:2]
    check('_closed_bars conserva todo si no hay vela en formación', len(PaperTrader._closed_bars(df2, '60', NOW)) == 2)

    # 9. Snapshot sin strategy_code: el monitor no se cae (se omite ese trade)
    bad = {k: v for k, v in P.items() if k != 'strategy_code'}
    try:
        res, closes, _ = await run_monitor(bad, [minute(base_t, low=98.0)])
        check('snapshot sin código no tumba el monitor', res['checked'] == 1 and not closes, res)
    except Exception as e:
        check('snapshot sin código no tumba el monitor', False, repr(e))

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')


if __name__ == '__main__':
    asyncio.run(main())

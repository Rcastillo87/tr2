"""
D-40 (dueño, 19-nov): el cierre en el stop que el break-even dejó en el precio de entrada se llama «break_even» en
backtest, Paper y Real (antes «stop_loss»). Solo cambia el nombre: precio y resultado iguales.
Caso real: ETH #100 (short 1780,28; BE a 17:06, SL → 1780,28; Bybit cerró por StopLoss a 1780,35; −0,08 % por costos).
Sin base ni Bybit: motor real con velas sintéticas, dobles de minute_gap_test (Paper) y de real_parity_test (Real).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/break_even_reason_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import pandas as pd  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


try:
    from backtesting.exit_reasons import stop_exit_reason
except ImportError:
    stop_exit_reason = None

# 1. Regla común
check('R0 existe la regla común stop_exit_reason', stop_exit_reason is not None)
if stop_exit_reason:
    cases = [(('long', 100.0, 100.0, True, False), 'break_even', 'largo, BE en la entrada'),
             (('short', 1780.28, 1780.28, True, False), 'break_even', 'corto, ETH #100'),
             (('long', 100.2, 100.0, True, False), 'break_even', 'largo, stop por encima de la entrada'),
             (('long', 99.0, 100.0, False, False), 'stop_loss', 'sin BE: stop original'),
             (('long', 98.5, 100.0, True, False), 'stop_loss', 'BE y luego la volatilidad alejó el stop (pérdida real)'),
             (('short', 1790.0, 1780.28, True, False), 'stop_loss', 'corto con el stop alejado tras el BE'),
             (('long', 101.0, 100.0, True, True), 'trailing_stop', 'el trailing manda'),
             (('short', 1800.0, 1780.0, False, True), 'trailing_stop', 'trailing sin BE')]
    for args, want, name in cases:
        got = stop_exit_reason(*args)
        check(f'R1 {name} -> {want}', got == want, got)


# 2. Motor del backtest (velas de 1 h, sin 1 m)
def engine_case(path, own_trailing=False):
    from backtesting.engine import BacktestEngine
    from backtesting.strategies.loader import build_strategy
    code = ("class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 0\n"
            "        df.loc[df.index[60], 'signal'] = 1\n        return df\n")
    if own_trailing:   # trailing propio de la estrategia (no mueve nada): fuerza el camino minuto a minuto (_step)
        code += "    def calculate_trailing_sl(self, entry, side, extreme, current_sl, current_atr=None):\n        return current_sl\n"
    st = build_strategy({'strategy_code': code, 'sl_pct': 1.0, 'tp_pct': 5.0, 'be_pct': 1.5, 'max_duration': 0,
                         'regime_filter': False, 'commission_pct': 0.0, 'slippage_pct': 0.0})
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [dict(time=t0 + timedelta(hours=i), open=100.0, high=100.2, low=99.8, close=100.0, volume=1.0) for i in range(62)]
    for k, (h, lo) in enumerate(path):
        rows.append(dict(time=t0 + timedelta(hours=62 + k), open=100.0, high=h, low=lo, close=(h + lo) / 2, volume=1.0))
    rows += [dict(time=t0 + timedelta(hours=62 + len(path) + i), open=100.0, high=100.1, low=99.95, close=100.0, volume=1.0)
             for i in range(3)]
    r = BacktestEngine(strategy=st, df=pd.DataFrame(rows), initial_balance=10000.0, risk_per_trade_pct=1.0).run()
    return [t for t in r['trades'] if t['exit_reason'] != 'end_of_data'], r['metrics']


tr, met = engine_case([(101.6, 100.1), (100.3, 99.9)])      # sube al BE (101,5) y vuelve a la entrada
check('E1 backtest: sube al BE y vuelve a la entrada -> break_even, cierre a la entrada (100)',
      len(tr) == 1 and tr[0]['exit_reason'] == 'break_even' and abs(tr[0]['exit_price'] - 100.0) < 0.2,
      [(t['exit_reason'], t['exit_price']) for t in tr])
if tr:
    size, entry = tr[0]['size'], tr[0]['entry_price']
    peak = 10000.0 + (100.85 - entry) * size          # cierre de la vela que tocó el BE (101,6 + 100,1) / 2
    want = round((peak - 10000.0) / peak * 100, 2)     # el piso es el stop en la entrada, no el mínimo 99,9 de la vela
    check('E3 drawdown flotante (p75): la salida en break-even también corta la caída en el nivel del stop',
          met.get('max_drawdown_floating_pct') == want, (met.get('max_drawdown_floating_pct'), want))
tr, met = engine_case([(101.6, 100.1), (100.3, 99.9)], own_trailing=True)
check('E4 backtest con trailing propio de la estrategia (camino vela a vela): también break_even',
      len(tr) == 1 and tr[0]['exit_reason'] == 'break_even', [(t['exit_reason'], t['exit_price']) for t in tr])
tr, met = engine_case([(100.3, 98.8)])                     # baja directo al SL (99)
check('E2 backtest: sin BE toca el SL -> stop_loss', len(tr) == 1 and tr[0]['exit_reason'] == 'stop_loss',
      [(t['exit_reason'], t['exit_price']) for t in tr])


# 3. Paper (monitor con 1 m)
async def paper_cases():
    import minute_gap_test as mg
    UTC = timezone.utc
    t0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    mins = mg.minutes(t0 + timedelta(minutes=1), t0 + timedelta(minutes=30))
    mins[4] = mg.mm(t0 + timedelta(minutes=5), high=101.7, low=100.6)        # minuto 5: llega al BE (101,5)
    mins[10] = mg.mm(t0 + timedelta(minutes=11), high=100.1, low=99.95)      # minuto 11: vuelve a la entrada
    s = mg.store(mins)
    await mg.monitor(s, t0 + timedelta(minutes=31))
    t = s['trade']
    check('P1 Paper: BE activado y vuelve a la entrada -> break_even a 100',
          t['status'] == 'closed' and t.get('exit_reason') == 'break_even' and abs((t.get('exit_price') or 0) - 100.0) < 1e-9,
          (t['status'], t.get('exit_reason'), t.get('exit_price')))
    mins = mg.minutes(t0 + timedelta(minutes=1), t0 + timedelta(minutes=30), touch={t0 + timedelta(minutes=8): 98.9})
    s = mg.store(mins)
    await mg.monitor(s, t0 + timedelta(minutes=31))
    check('P2 Paper: sin BE toca el SL (99) -> stop_loss', s['trade'].get('exit_reason') == 'stop_loss',
          (s['trade']['status'], s['trade'].get('exit_reason')))


# 4. Real: orden de cierre de Bybit y regla por precio
def real_cases():
    import trading.real_trader as rt
    eth = {'side': 'short', 'sl': 1780.28, 'entry_price': 1780.28, 'be_activated': True, 'trailing_applied': False}
    order = {'stopOrderType': 'StopLoss', 'createType': 'CreateByStopLoss'}
    got = rt.close_trigger_reason(order, False, eth)
    check('Q1 Real: ETH #100 (StopLoss de Bybit con el BE activado) -> break_even', got == 'break_even', got)
    got = rt.close_trigger_reason(order, False, dict(eth, be_activated=False, sl=1806.98))
    check('Q2 Real: StopLoss sin BE -> stop_loss', got == 'stop_loss', got)
    got = rt.close_trigger_reason(order, True, dict(eth, trailing_applied=True))
    check('Q3 Real: StopLoss con el trailing del bot -> trailing_stop', got == 'trailing_stop', got)
    got = rt.close_trigger_reason({'stopOrderType': 'TakeProfit'}, False, eth)
    check('Q4 Real: TakeProfit no cambia', got == 'take_profit_1', got)
    got = rt.close_trigger_reason(order, True)
    check('Q5 Real: llamada sin la operación (compatibilidad): StopLoss + trailing -> trailing_stop', got == 'trailing_stop', got)
    src = open(os.path.join(os.getcwd(), 'trading', 'real_trader.py'), encoding='utf-8').read()
    check('Q6 Real: el cierre por Bybit pasa la operación y la regla por precio usa la regla común',
          "close_trigger_reason(order, bool(trade.get('trailing_applied')), trade)" in src
          and "sl_label = stop_exit_reason(trade['side'], sl, float(trade['entry_price'])" in src)
    api = open(os.path.join(os.getcwd(), 'api', 'v1', 'real_trading.py'), encoding='utf-8').read()
    check('Q7 reclasificación (real:reclassify-exits) con la misma regla',
          "close_trigger_reason(order, bool(r['trailing_applied']), dict(r))" in api and 'sl, be_activated' in api)


async def main():
    await paper_cases()
    real_cases()
    php = open(os.path.join(os.getcwd(), '..', 'app', 'Services', 'BrokerEventMessages.php'), encoding='utf-8').read()
    check('L1 aviso de cierre: «break-even» en palabras', "'break_even' => 'break-even'" in php)
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

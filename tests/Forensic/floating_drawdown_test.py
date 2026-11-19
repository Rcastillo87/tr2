"""
Fase 12 · 4A (D-38): drawdown FLOTANTE además del de cierres. Mayor caída desde el máximo del capital (saldo + PnL
bruto abierto al cierre de cada vela) hasta el peor punto con la posición abierta. Una salida no se «vive» más allá de
su nivel; con 1m, solo los minutos hasta el que la disparó. La posición que queda abierta al final no cuenta (D-35).
Sin DB. Uso: cd python-engine && venv/bin/python ../tests/Forensic/floating_drawdown_test.py
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import pandas as pd  # noqa: E402

import end_of_data_test as eod  # noqa: E402  (velas H1 sintéticas y estrategia de prueba)
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


P = dict(eod.P, sl_pct=50.0, tp_pct=2.0, be_pct=90.0, slippage_pct=0.0, commission_pct=0.0)


def run(df, params=P, minute_df=None):
    return BacktestEngine(build_strategy(params), df, initial_balance=10000.0, risk_per_trade_pct=1.0,
                          minute_df=minute_df).run()


def entry_size(r):
    t = r['trades'][0]
    return t['entry_price'], t['size']


# A. Long que baja a 92 dentro de una vela, se recupera y sale por TP: cierre 0 %, flotante = caída al peor punto
df = eod.bars(n=12, sig={2: 1})
df.loc[5, 'low'] = 92.0
df.loc[8, 'high'] = 110.0          # TP 2 %
r = run(df)
m = r['metrics']
check('A0 una operación ganadora por TP', len(r['trades']) == 1 and r['trades'][0]['exit_reason'].startswith('take_profit'),
      [t['exit_reason'] for t in r['trades']])
e, size = entry_size(r)
peak = 10000.0 + max(0.0, (df.loc[3:4, 'close'].max() - e) * size)
want = round((peak - (10000.0 + (92.0 - e) * size)) / peak * 100, 2)
check('A1 drawdown de cierres 0 % (ganó)', m['max_drawdown_pct'] == 0.0, m['max_drawdown_pct'])
check('A2 drawdown flotante = caída al peor punto desde el máximo previo', m.get('max_drawdown_floating_pct') == want,
      (m.get('max_drawdown_floating_pct'), want))

# B. Salida por SL: no se cuenta más abajo que el nivel de salida aunque el low de la vela siga
P_sl = dict(P, sl_pct=3.0)
df = eod.bars(n=12, sig={2: 1})
df.loc[6, 'low'] = 80.0            # el SL (≈ 97,1) se toca en esta vela; el low sigue hasta 80
r = run(df, P_sl)
m = r['metrics']
t = r['trades'][0]
check('B0 sale por stop_loss', t['exit_reason'] == 'stop_loss', t['exit_reason'])
bound = round((10000.0 - (10000.0 + (t['exit_level'] - t['entry_price']) * t['size'])) / 10000.0 * 100, 2) + 0.05
check('B1 flotante ≥ cierres y acotado por el nivel del SL (no por el low 80)',
      m['max_drawdown_floating_pct'] >= m['max_drawdown_pct'] and m['max_drawdown_floating_pct'] <= max(bound, m['max_drawdown_pct']),
      (m['max_drawdown_floating_pct'], m['max_drawdown_pct'], bound))

# C. D-35: la posición que queda abierta al final, aunque caiga mucho, no cuenta
df = eod.bars(n=12, sig={4: 1})
df.loc[9, 'low'] = 60.0
r = run(df)
check('C1 posición abierta al final con caída grande -> flotante 0 % (no cuenta)',
      r['metrics']['max_drawdown_floating_pct'] == 0.0 and r['closed_at_end'] == 1, r['metrics']['max_drawdown_floating_pct'])

# D. Con 1m: la caída en un minuto POSTERIOR a la salida por TP no cuenta; la anterior sí
df = eod.bars(n=12, sig={2: 1})
rows = []
for h in range(12):
    base = df.loc[h, 'open']
    for mi in range(60):
        rows.append((df.loc[h, 'time'] + timedelta(minutes=mi), base, base + 0.05, base - 0.05, base + 0.01, 1.0))
md = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
k_drop, k_tp, k_late = 5 * 60 + 10, 7 * 60 + 20, 7 * 60 + 40
md.loc[k_drop, 'low'] = 96.0       # antes de la salida: cuenta
md.loc[k_tp, 'high'] = 110.0       # TP en la vela 7, minuto 20
md.loc[k_late, 'low'] = 85.0       # misma vela, después de la salida: NO cuenta
df.loc[5, 'low'] = 96.0
df.loc[7, ['high', 'low']] = [110.0, 85.0]
r1 = run(df, P, minute_df=md)
e, size = entry_size(r1)
peak = max([10000.0] + [10000.0 + (df.loc[j, 'close'] - e) * size for j in range(2, 5)])
want = round((peak - (10000.0 + (96.0 - e) * size)) / peak * 100, 2)
check('D1 con 1m: cuenta la caída a 96 antes del TP y no la de 85 después', r1['metrics']['max_drawdown_floating_pct'] == want,
      (r1['metrics']['max_drawdown_floating_pct'], want))
r2 = run(df, P)
check('D2 sin 1m (vela completa): no se sabe el orden y cuenta el low de la vela (más conservador)',
      r2['metrics']['max_drawdown_floating_pct'] > r1['metrics']['max_drawdown_floating_pct'],
      (r2['metrics']['max_drawdown_floating_pct'], r1['metrics']['max_drawdown_floating_pct']))

# E. Short: el peor punto es el high
df = eod.bars(n=12, sig={2: -1})
df.loc[5, 'high'] = 106.0
df.loc[8, 'low'] = 90.0
r = run(df)
e, size = entry_size(r)
check('E1 short: flotante por el high de la vela', r['metrics']['max_drawdown_floating_pct'] > 0
      and r['trades'][0]['exit_reason'].startswith('take_profit'), (r['metrics']['max_drawdown_floating_pct'], r['trades'][0]['exit_reason']))

# G. Salida por señal opuesta (al open): la caída previa también entra al total
P_op = dict(P, exit_on_opposite=True)
df = eod.bars(n=12, sig={2: 1, 7: -1})
df.loc[5, 'low'] = 93.0
r = run(df, P_op)
check('G1 salida por señal opuesta: la caída a 93 cuenta', r['trades'] and r['trades'][0]['exit_reason'] == 'opposite_signal'
      and r['metrics']['max_drawdown_floating_pct'] > r['metrics']['max_drawdown_pct'],
      ([t['exit_reason'] for t in r['trades']], r['metrics']['max_drawdown_floating_pct'], r['metrics']['max_drawdown_pct']))

# F. Sin operaciones: 0
r = run(eod.bars(n=12))
check('F1 sin operaciones: flotante 0 %', r['metrics']['max_drawdown_floating_pct'] == 0.0)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

"""
Hora de salida del backtest (NUEVO-02): con 1m, una salida por SL/TP/trailing guarda el MINUTO del evento (como Paper,
p19), no la apertura de la vela grande. Sin 1m o con la vela incompleta (respaldo), la apertura de la vela (momento
desconocido, igual que Paper); salidas al cierre, el cierre de la vela. Ninguna métrica cambia. Sin base de datos.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/exit_time_test.py
Antes del parche: FALLAN los casos con 1m.
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import pandas as pd  # noqa: E402

import minute_coverage_test as mc  # noqa: E402   (velas H1 + 1m sintéticos, estrategia con señal guionada)
from backtesting.metrics import calculate_metrics  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


hm = mc.hm
ts = pd.Timestamp

# 1. SL tocado en el minuto 10:47 de la vela 10:00 (con 1m)
hours, mins = mc.data(minute_low={hm(10, 47): 98.9})
r, _ = mc.run(hours, mins)
t = r['trades'][0] if r['trades'] else {}
check('1m: stop_loss con exit_time = minuto del evento (10:47), no la vela (10:00)',
      t.get('exit_reason') == 'stop_loss' and ts(t['exit_time']) == ts(hm(10, 47)), (t.get('exit_reason'), t.get('exit_time')))
check('exit_time con zona UTC, como entry_time', ts(t['exit_time']).tzinfo is not None and ts(t['entry_time']).tzinfo is not None,
      (t.get('exit_time'), t.get('entry_time')))

# 2. TP en la vela siguiente (11:05)
hours, mins = mc.data(minute_high={hm(11, 5): 102.5})
r, _ = mc.run(hours, mins)
t = r['trades'][0] if r['trades'] else {}
check('1m: take_profit en la vela siguiente con exit_time 11:05',
      t.get('exit_reason') == 'take_profit_1' and ts(t['exit_time']) == ts(hm(11, 5)), (t.get('exit_reason'), t.get('exit_time')))

# 3. Sin 1m: apertura de la vela (momento exacto desconocido), como antes
hours, _ = mc.data(bar_low={10: 98.5})
r, _ = mc.run(hours, None)
t = r['trades'][0] if r['trades'] else {}
check('sin 1m: exit_time = apertura de la vela (sin cambios)', ts(t.get('exit_time')) == ts(hm(10, 0)), t.get('exit_time'))

# 4. Vela con minutos faltantes (respaldo NUEVO-01): apertura de la vela, igual que Paper
gap = {hm(10, 40 + k) for k in range(5)}
hours, mins = mc.data(skip=gap, bar_low={10: 98.5})
r, _ = mc.run(hours, mins)
t = r['trades'][0] if r['trades'] else {}
check('vela incompleta (respaldo): exit_time = apertura de la vela', ts(t.get('exit_time')) == ts(hm(10, 0)), t.get('exit_time'))

# 5. Salida al cierre (tiempo máximo): cierre de la vela
hours, mins = mc.data()
r, _ = mc.run(hours, mins, params=dict(mc.P, max_duration=2))
t = r['trades'][0] if r['trades'] else {}
check('time_exit: exit_time = cierre de la vela (sin cambios)',
      t.get('exit_reason') == 'time_exit' and ts(t['exit_time']) == ts(hm(12, 0)), (t.get('exit_reason'), t.get('exit_time')))

# 6. Ninguna métrica cambia: con la hora de la vela (código anterior) las métricas son idénticas
hours, mins = mc.data(n=60, minute_low={hm(10, 47): 98.9})
hours.loc[30, 'sig'] = -1
r, _ = mc.run(hours, mins)
as_bar = [dict(x, exit_time=ts(x['exit_time']).floor('h')) for x in r['trades']]
m_new, m_old = calculate_metrics(r['trades'], 10000.0), calculate_metrics(as_bar, 10000.0)
check('métricas idénticas a las calculadas con la hora de la vela (Sharpe por día incluido)',
      {k: v for k, v in m_new.items() if k != 'equity_curve'} == {k: v for k, v in m_old.items() if k != 'equity_curve'},
      [(k, m_new[k], m_old[k]) for k in m_new if k != 'equity_curve' and m_new[k] != m_old[k]][:3])
check('las salidas por minuto quedan dentro de su vela',
      all(ts(a['exit_time']).floor('h') == ts(b['exit_time']) for a, b in zip(r['trades'], as_bar)))

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

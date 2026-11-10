"""
N-03: atribución de trades a los tramos en muestra / fuera de muestra de la búsqueda de configuraciones.
- En muestra cuenta un trade solo si abre Y cierra antes del corte; el que cruza el corte no cuenta en ninguno de los
  dos tramos y queda en 'cross'. Fuera de muestra (último tramo) cuentan todos los que abren después del corte.
- El PnL se lleva al capital inicial (pnl_pct × INITIAL): la simulación es continua y el tramo posterior no debe
  heredar el tamaño del saldo ganado antes.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/is_oos_attribution_test.py
"""
import inspect
import os
import sys
from datetime import datetime

sys.path.insert(0, os.getcwd())   # python-engine/

import cli.param_search as ps  # noqa: E402

fails = 0
INI = ps.INITIAL


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def T(entry, exit_, pnl, pnl_pct):
    return {'entry_time': datetime(2026, *entry), 'exit_time': datetime(2026, *exit_), 'pnl': pnl, 'pnl_pct': pnl_pct}


LO, SPLIT, END = datetime(2026, 1, 1), datetime(2026, 3, 1), datetime(2026, 4, 1)
# saldo: 10.000 -> +1% (10.100) -> +5% del saldo en el que cruza (10.605) -> +2% fuera (10.817)
trades = [
    T((1, 10), (1, 11), 100.0, 1.0),           # dentro del tramo en muestra
    T((2, 27), (3, 3), 505.0, 5.0),            # abre antes del corte y cierra después: cruza
    T((3, 10), (3, 12), 212.1, 2.0),           # fuera de muestra, con el saldo ya crecido
    T((3, 30), (4, 2), -108.17, -1.0),         # último tramo: cierre end_of_data después del fin, cuenta
]

is_ = ps.segment_stats(trades, LO, SPLIT)
oos = ps.segment_stats(trades, SPLIT, END, last=True) if 'last' in inspect.signature(ps.segment_stats).parameters \
    else ps.segment_stats(trades, SPLIT, END)

check('A1: en muestra cuenta solo el trade que abre y cierra antes del corte (n=1)', is_['n'] == 1, is_)
check('A2: el trade que cruza el corte no suma en muestra (PnL 100, no 605)', abs(is_['pnl'] - 100.0) < 1e-6, is_['pnl'])
check("A3: se informa el cruce (cross=1)", is_.get('cross') == 1, is_.get('cross'))
check('A4: fuera de muestra no incluye el trade que abrió antes del corte (n=2)', oos['n'] == 2, oos)
check('A5: fuera de muestra al capital inicial: +2% y -1% = +100 (no 212.1 - 108.17 = 103.93)',
      abs(oos['pnl'] - 100.0) < 1e-6, oos['pnl'])
check('A6: el último tramo cuenta el cierre posterior al fin (end_of_data), sin cross', oos.get('cross', 0) == 0, oos.get('cross'))
check('A7: PF y drawdown sobre el PnL normalizado (gp=200, gl=100, dd=1%)',
      abs(oos['gp'] - 200.0) < 1e-6 and abs(oos['gl'] - 100.0) < 1e-6 and abs(oos['dd'] - 100 / (INI + 200) * 100) < 1e-6,
      (oos['gp'], oos['gl'], oos['dd']))

v = ps.seg_view(is_)
check("A8: seg_view expone 'cross' (lo guarda la búsqueda con cada tramo)", v.get('cross') == 1, v)
check("A9: seg_sum suma 'cross' de varias monedas", ps.seg_sum([is_, is_]).get('cross') == 2, ps.seg_sum([is_, is_]))

src = inspect.getsource(ps.evaluate)
check('A10: evaluate usa el corte con last=True solo en el último tramo',
      'segment_stats(trades, lo, split)' in src and 'segment_stats(trades, split, end, last=True)' in src)

# Un trade exactamente en el corte: cierra en el corte -> cruza; abre en el corte -> fuera de muestra
edge = [T((2, 28, 23), (3, 1, 0), 50.0, 0.5), T((3, 1, 0), (3, 1, 5), 30.0, 0.3)]
a, b = ps.segment_stats(edge, LO, SPLIT), ps.segment_stats(edge, SPLIT, END, last=True)
check('A11: cierra justo en el corte -> cruza; abre justo en el corte -> fuera de muestra',
      a['n'] == 0 and a.get('cross') == 1 and b['n'] == 1, (a, b))

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

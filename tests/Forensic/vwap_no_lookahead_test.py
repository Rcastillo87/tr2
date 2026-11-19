"""
R-21 (p80): VWAP Tendencia calculaba la banda de desviación con todas las velas del día; en el backtest eso mira velas
futuras. El arreglo (ops/datafix/2026_11_19_r21_vwap_std.py) usa solo las velas del día hasta cada vela.
Comprueba, con el código de la estrategia tal como estaba el 19-nov (fixtures/vwap_tendencia_19nov.py) y velas
sintéticas:
  · el código viejo en el backtest (todo el rango) da señales que en vivo (ventana hasta la vela) no existían;
  · el código nuevo en el backtest da EXACTAMENTE la señal que ve Paper/Real en cada vela (con el código viejo o el nuevo);
  · el parche cambia una sola línea, conserva sangría y fin de línea (\\n o \\r\\n) y es idempotente.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/vwap_no_lookahead_test.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
HERE = os.path.dirname(os.path.abspath(__file__))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


spec = importlib.util.spec_from_file_location('r21', os.path.join(HERE, '..', '..', 'ops', 'datafix', '2026_11_19_r21_vwap_std.py'))
r21 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r21)
OLD = open(os.path.join(HERE, 'fixtures', 'vwap_tendencia_19nov.py'), encoding='utf-8').read()

# 1. El parche
new = r21.patch_code(OLD)
diff = [(a, b) for a, b in zip(OLD.splitlines(), new.splitlines()) if a != b]
check('C1 cambia solo la línea de vwap_std_dev (más un comentario), con la misma sangría',
      len(new.splitlines()) == len(OLD.splitlines()) + 1 and r21.NEW_LINE in new and r21.OLD_LINE not in new
      and "        df['vwap_std_dev'] = df.groupby('date')['typical'].transform(lambda s: s.expanding().std())" in new.splitlines())
crlf = OLD.replace('\n', '\r\n')
new_crlf = r21.patch_code(crlf)
check('C2 código guardado con \\r\\n: conserva el fin de línea en las líneas nuevas',
      new_crlf == new.replace('\n', '\r\n'), new_crlf.count('\r\n') - crlf.count('\r\n'))
try:
    r21.patch_code(new)
    check('C3 sobre código ya corregido no aplica dos veces (error explícito)', False)
except ValueError:
    check('C3 sobre código ya corregido no aplica dos veces (error explícito)', r21.is_patched(new) and not r21.is_patched(OLD))
compile(new, 'vwap', 'exec')

# 2. Velas sintéticas H1, 40 días, con tendencia y volumen variables
rng = np.random.default_rng(21)
n = 24 * 40
t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
ret = rng.normal(0, 0.006, n) + np.sin(np.arange(n) / 37) * 0.002
close = 100 * np.exp(np.cumsum(ret))
open_ = np.r_[close[0], close[:-1]]
high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.004, n))
low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.004, n))
df = pd.DataFrame({'time': [t0 + timedelta(hours=i) for i in range(n)], 'open': open_, 'high': high, 'low': low,
                   'close': close, 'volume': rng.uniform(50, 500, n)})
params = {'symbol': 'TESTUSDT', 'interval': '60', 'mode': 'trend_follow', 'vwap_std_filter': 0.6, 'ema_trend_period': 50}

WINDOW, LAST = 200, 24 * 12
r_old = r21.live_parity(OLD, OLD, params, df, LAST, window=WINDOW)
check('V1 el código viejo en el backtest NO coincide con lo que ve Paper (mira el futuro)',
      len(r_old['mismatches']) > 0, (len(r_old['mismatches']), r_old['ghost_old']))
r_new = r21.live_parity(OLD, new, params, df, LAST, window=WINDOW)
check('V2 el código nuevo en el backtest da en cada vela la señal de Paper/Real (código viejo en vivo)',
      r_new['mismatches'] == [] and r_new['checked'] == LAST and r_new['live_signals'] > 0, r_new)
r_new2 = r21.live_parity(new, new, params, df, LAST, window=WINDOW)
check('V3 Paper/Real con el código nuevo ven lo mismo que con el viejo (en vivo no cambia nada)',
      r_new2['mismatches'] == [] and r_new2['live_signals'] == r_new['live_signals'], r_new2['live_signals'])
check('V4 hay señales del backtest viejo que en vivo no existían (el caso de LINK, ENA, SOL…)', r_old['ghost_old'] > 0,
      r_old['ghost_old'])

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

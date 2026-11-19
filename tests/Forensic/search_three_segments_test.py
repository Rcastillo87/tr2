"""
Fase 12 · 1A (D-38): la búsqueda del módulo Estrategias usa tres tramos.
  60 % ELEGIR · 20 % VALIDAR (la configuración se acepta solo si también gana aquí) · 20 % PRUEBA FINAL (solo informa).
Ningún trade cuenta en dos tramos; la prueba final nunca cambia qué se acepta; las búsquedas v3 (dos tramos) se siguen
leyendo; los modos de consola conservan sus dos tramos. Sin DB: datos sintéticos y el motor real.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/search_three_segments_test.py
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())

import cli.param_search as ps  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def seg(pnl, n=20):
    gp, gl = (pnl, 0.0) if pnl > 0 else (0.0, -pnl)
    return dict(n=n, gp=gp + 50, gl=gl + 50, pnl=pnl, dd=3.0)


def full(n=60, pf=1.5, ret=5.0):
    return dict(n=n, wins=n // 2, wr=50.0, sharpe=1.0, pf=pf, ret=ret, dd=5.0, gp=100.0, gl=60.0, m=[0.5] * 24, m1=True)


# 1. Cortes 60 / 80 %
cuts = getattr(ps, 'segment_cuts', None)
check('C0 existen segment_cuts y evaluate_segments', cuts is not None and hasattr(ps, 'evaluate_segments'))
if cuts:
    s, e = ps.naive_utc('2024-11-01'), ps.naive_utc('2026-11-01')
    c1, c2 = cuts(s, e)
    check('C1 24 meses: elegir hasta el 60 % (≈ 14,4 meses) y validar hasta el 80 % (≈ 19,2 meses)',
          abs((c1 - s) / (e - s) - 0.6) < 1e-9 and abs((c2 - s) / (e - s) - 0.8) < 1e-9, (c1, c2))

# 2. Motor real con datos sintéticos: tres tramos sin solapes
start, end = ps.synthetic_data(['XAUSDT'], ['60'], 8)
end_n = ps.naive_utc(end)
code = ("class T(BaseStrategy):\n    def generate_signals(self, df):\n        import numpy as np\n        df = df.copy()\n"
        "        x = np.random.default_rng(3).random(len(df))\n        df['signal'] = 0\n        df.loc[x < 0.04, 'signal'] = 1\n"
        "        df.loc[x > 0.96, 'signal'] = -1\n        return df\n")
configs = ps.sample_configs(4, 5, 'cons')
if cuts:
    c1, c2 = cuts(start, end)
    out = ps.evaluate_segments('t', code, {}, 'XAUSDT', '60', configs, start, [c1, c2], end_n)
    check('M1 cada configuración trae 3 tramos y las métricas completas',
          out and all(len(segs) == 3 and 'n' in f for _, segs, f in out), [len(x[1]) for x in (out or [])])
    ok = True
    for _, (a, b, c), f in out:
        counted = a['n'] + b['n'] + c['n'] + a['cross'] + b['cross']
        ok &= counted == f['n']   # ningún trade en dos tramos; los que cruzan un corte van aparte
    check('M2 elegir + validar + prueba final + los que cruzan un corte = operaciones del periodo (ninguna se cuenta dos veces)',
          ok, [(s_[0]['n'], s_[1]['n'], s_[2]['n'], s_[0]['cross'], s_[1]['cross'], f['n']) for _, s_, f in out])
    crossed = sum(s_[0]['cross'] + s_[1]['cross'] for _, s_, _ in out)
    check('M4 la operación que abre antes de un corte y cierra después no cuenta en ningún tramo (N-03): se informa aparte',
          crossed > 0 and all(s_[2]['cross'] == 0 for _, s_, _ in out), crossed)
    two = ps.evaluate('t', code, {}, 'XAUSDT', '60', configs, start, c1, end_n)
    seg2 = ps.evaluate_segments('t', code, {}, 'XAUSDT', '60', configs, start, [c1], end_n)
    check('M3 consola (evaluate, dos tramos) = evaluate_segments con un solo corte',
          [(i, a, b, f) for i, a, b, f in two] == [(i, s_[0], s_[1], f) for i, s_, f in seg2])

# 3. La prueba final solo informa
cfgs = {'60': ps.sample_configs(3, 1, 'gain')}
per = {('60', 0): {'SOL': (seg(100), seg(40), full(), seg(-30))},     # pasa la validación, pierde en la prueba final
       ('60', 1): {'SOL': (seg(100), seg(-10), full(), seg(90))},     # pierde la validación, gana la prueba final
       ('60', 2): {'SOL': (seg(100), seg(40), full(), seg(25))}}
rows, near = ps.symbol_mode_rows(per, cfgs, 'gain', ['SOL'])
ids = sorted(r['id'] for r in rows)
check('P1 por moneda: se aceptan las que pasan la validación, gane o pierda la prueba final', ids == ['SOL-60-0', 'SOL-60-2'], ids)
check('P2 la prueba final NO rescata a la que perdió la validación', [n['id'] for n in near['SOL']] == ['SOL-60-1']
      and 'validación' in near['SOL'][0]['why'], [(n['id'], n['why']) for n in near['SOL']])
r0 = next((r for r in rows if r['id'] == 'SOL-60-0'), {})
check('P3 cada fila trae la prueba final (retorno y operaciones)', r0.get('test', {}).get('ret') == round(-30 / ps.INITIAL * 100, 2)
      and r0['test']['n'] == 20, r0.get('test'))

syms = ['BTC', 'ETH', 'SOL', 'XRP']
per = {('60', 0): {'BTC': (seg(100), seg(40), full(), seg(10)), 'ETH': (seg(60), seg(20), full(), seg(-50)),
                   'SOL': (seg(50), seg(10), full(), seg(5)), 'XRP': (seg(-200), seg(-100), full(ret=-3), seg(-80))}}
rows, near, need = ps.interval_mode_rows(per, cfgs, 'gain', syms)
exp = round((10 - 50 + 5 - 80) / (ps.INITIAL * 4) * 100, 2)
check('P4 por temporalidad: prueba final promediada sobre TODAS las monedas (también la perdedora)',
      rows and rows[0].get('test', {}).get('ret') == exp, (rows[0].get('test') if rows else None, exp))

# 4. Búsquedas v3 guardadas (tres elementos por moneda): sin prueba final y sin romper
per3 = {('60', 0): {'SOL': (seg(100), seg(40), full())}}
rows, _ = ps.symbol_mode_rows(per3, cfgs, 'gain', ['SOL'])
check('V1 tuplas v3 (sin prueba final): misma fila de siempre, sin clave test', rows and 'test' not in rows[0], rows[0].keys() if rows else None)
try:
    json.dumps(rows)
    check('V2 filas serializables a JSON', True)
except (TypeError, ValueError) as e:
    check('V2 filas serializables a JSON', False, str(e))

# 5. El modo --run-id usa los tres tramos y lo deja escrito en el resultado
src = open(os.path.join(os.getcwd(), 'cli', 'param_search.py'), encoding='utf-8').read()
check('R1 --run-id: corta en elegir | validar | prueba final', 'split, test_start = segment_cuts(start, end)' in src
      and 'evaluate_segments(name, code, scfg, sym, iv, configs[iv], start, [split, test_start], end_n, tick=tick)' in src)
check('R2 resultado v4 con el corte de la prueba final y cuántas ganan en ella', 'version=4' in src
      and "test=f\"{test_start:%Y-%m-%d}\"" in src and 'test_ok=' in src)

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

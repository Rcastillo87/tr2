"""
Búsqueda v3 (módulo Estrategias): enfoques, regla "gana en los dos tramos", modo por moneda y por temporalidad (≥ 3/4,
métricas de TODAS las monedas) y una corrida real del motor con datos sintéticos. Sin DB.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/param_search_v3_test.py
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


# 1. Espacios por enfoque
for focus in ps.FOCUSES:
    cs = ps.sample_configs(40, 7, focus)
    sp = ps.SPACES[focus]
    ok_sltp = all((c['sl_pct'], c['tp_pct']) in sp['sltp'] for c in cs)
    ok_dur = all(c['max_duration'] in sp['duration'] for c in cs)
    distinct = len({json.dumps(c, sort_keys=True) for c in cs}) == len(cs)
    check(f'espacio {focus}: 40 configuraciones distintas dentro de su SL/TP y duración', len(cs) == 40 and ok_sltp and ok_dur and distinct)
cs = ps.sample_configs(40, 7, 'wr')
check('win rate: prueba TP menores que el SL y break-even temprano',
      any(c['tp_pct'] < c['sl_pct'] for c in cs) and any(c['be_pct'] < c['tp_pct'] for c in cs))
check('consola (sin enfoque): mismo espacio de siempre', ps.sample_configs(20, 7) == ps.sample_configs(20, 7, None)
      and all((c['sl_pct'], c['tp_pct']) in ps.SLTP for c in ps.sample_configs(20, 7)))

# 2. Regla de aceptación
check('gana en los dos tramos con 60 operaciones -> acepta', ps.accept(seg(100), seg(50), full(), 'gain') is None)
check('pocas operaciones -> rechaza', 'operaciones' in (ps.accept(seg(100), seg(50), full(n=20), 'gain') or ''))
check('pierde en muestra -> rechaza', 'primeros' in (ps.accept(seg(-10), seg(50), full(), 'gain') or ''))
check('gana en muestra pero pierde al final -> rechaza', 'últimos' in (ps.accept(seg(100), seg(-5), full(), 'gain') or ''))
check('win rate con PF 1,1 -> rechaza', 'profit factor' in (ps.accept(seg(100), seg(50), full(pf=1.1), 'wr') or ''))
check('ganancia con PF 1,1 -> acepta (el PF mínimo es solo del enfoque win rate)', ps.accept(seg(100), seg(50), full(pf=1.1), 'gain') is None)

# 3. Modo por moneda: cada moneda por separado
cfgs = {'60': ps.sample_configs(2, 1, 'gain')}
per = {('60', 0): {'SOL': (seg(100), seg(40), full()), 'ENA': (seg(80), seg(-20), full())},
       ('60', 1): {'SOL': (seg(-5), seg(10), full()), 'ENA': (seg(30), seg(15), full())}}
rows, near = ps.symbol_mode_rows(per, cfgs, 'gain', ['SOL', 'ENA', 'HYPE'])
ids = sorted(r['id'] for r in rows)
check('por moneda: una fila por (configuración, moneda) que gana', ids == ['ENA-60-1', 'SOL-60-0'], ids)
check('por moneda: cada fila trae solo su moneda', all(list(r['symbols']) == [r['symbol']] and r['survivors'] == [r['symbol']] for r in rows))
check('por moneda: casi-ganadoras por moneda con el motivo', [n['id'] for n in near['ENA']] == ['ENA-60-0']
      and 'últimos' in near['ENA'][0]['why'] and near['HYPE'] == [], {k: [n['id'] for n in v] for k, v in near.items()})
check('por moneda: tramos de la fila = los de su moneda', rows and all(r['is']['n'] == 20 and r['oos']['ret'] > 0 for r in rows))

# 4. Modo por temporalidad: ≥ 3/4 de las monedas, métricas de TODAS
syms = ['BTC', 'ETH', 'SOL', 'XRP']
per = {('60', 0): {'BTC': (seg(100), seg(40), full()), 'ETH': (seg(60), seg(20), full()), 'SOL': (seg(50), seg(10), full()),
                   'XRP': (seg(-200), seg(-100), full(ret=-3))},
       ('60', 1): {'BTC': (seg(100), seg(40), full()), 'ETH': (seg(60), seg(20), full()), 'SOL': (seg(-5), seg(10), full()),
                   'XRP': (seg(-200), seg(-100), full())}}
rows, near, need = ps.interval_mode_rows(per, cfgs, 'gain', syms)
check('por temporalidad: necesita 3 de 4', need == 3, need)
check('por temporalidad: gana en 3 de 4 -> se acepta', [r['id'] for r in rows] == ['60-0'], [r['id'] for r in rows])
r = rows[0] if rows else {}
check('por temporalidad: la perdedora NO se descarta (sus métricas cuentan)', sorted(r.get('symbols', {})) == syms
      and r.get('discarded') == ['XRP'] and r['symbols']['XRP']['role'] == 'lose')
exp_is = round((100 + 60 + 50 - 200) / (ps.INITIAL * 4) * 100, 2)
check('por temporalidad: tramo en muestra promediado sobre las 4 monedas', r.get('is', {}).get('ret') == exp_is, (r.get('is'), exp_is))
check('por temporalidad: 2 de 4 -> casi-ganadora con el motivo', near and near[0]['id'] == '60-1' and '2 de 4' in near[0]['why'], [n['why'] for n in near])
per_missing = {('60', 0): {'BTC': (seg(100), seg(40), full())}}
check('por temporalidad: sin datos en alguna moneda no se juzga', ps.interval_mode_rows(per_missing, cfgs, 'gain', syms)[0] == [])

# 5. Corrida real del motor (sintético) y resultados serializables
start, end = ps.synthetic_data(['XAUSDT', 'XBUSDT'], ['60'], 8)
code = ("class T(BaseStrategy):\n    def generate_signals(self, df):\n        import numpy as np\n        df = df.copy()\n"
        "        x = np.random.default_rng(3).random(len(df))\n        df['signal'] = 0\n        df.loc[x < 0.04, 'signal'] = 1\n"
        "        df.loc[x > 0.96, 'signal'] = -1\n        return df\n")
end_n = ps.naive_utc(end)
split = ps.naive_utc(start) + (end_n - ps.naive_utc(start)) * 2 / 3
configs = {'60': ps.sample_configs(6, 5, 'cons')}
per_cfg = {}
for sym in ('XAUSDT', 'XBUSDT'):
    for i, is_, oos, f in ps.evaluate('t', code, {}, sym, '60', configs['60'], start, split, end_n):
        per_cfg.setdefault(('60', i), {})[sym] = (is_, oos, f)
check('motor: 6 configuraciones × 2 monedas evaluadas', len(per_cfg) == 6 and all(len(v) == 2 for v in per_cfg.values()))
r1, n1 = ps.symbol_mode_rows(per_cfg, configs, 'cons', ['XAUSDT', 'XBUSDT'])
r2, n2, _ = ps.interval_mode_rows(per_cfg, configs, 'cons', ['XAUSDT', 'XBUSDT'])
try:
    json.dumps(dict(rows=r1 + r2, near=n1, near2=n2))
    ok = True
except (TypeError, ValueError) as e:
    ok = str(e)
check('resultados v3 serializables a JSON', ok is True, ok)
check('cada fila trae lo que usa Laravel (summarize, notificación)', all(
    {'id', 'interval', 'cfg', 'symbols', 'survivors', 'discarded', 'is', 'oos', 'ret_total', 'consist'} <= set(r) for r in r1 + r2))
check('métricas por moneda con las claves de summarize', all(
    {'n', 'wins', 'wr', 'sharpe', 'pf', 'ret', 'dd', 'gp', 'gl', 'm'} <= set(v) for r in r1 + r2 for v in r['symbols'].values()))

# 6. Filtros en la búsqueda (auditoría de filtros): régimen solo si la estrategia limita regímenes; nivel de volumen
check('régimen útil: estrategia con los 3 regímenes -> no', ps.regime_useful(code) is False)
code_rng = code.replace("    def generate_signals", "    allowed_regimes = ['RANGING']\n    def generate_signals")
check('régimen útil: estrategia solo lateral -> sí', ps.regime_useful(code_rng) is True)
cs = ps.sample_configs(60, 9, 'cons', regime=False)
check('sin régimen útil: nunca se prueba el filtro de régimen', not any(c['regime_filter'] for c in cs))
check('volumen: se prueban los 4 niveles', {c['volume_filter_mult'] for c in cs if c['volume_filter']} == set(ps.VOLUME_MULTS))
check('volumen apagado: nivel fijo (sin duplicados que no cambian nada)',
      all(c['volume_filter_mult'] == 1.2 for c in cs if not c['volume_filter']))
base = dict(ps.sample_configs(1, 5, 'gain')[0], volume_filter=True, macro_trend_filter=False, trailing_mode=None)
pair = [dict(base, volume_filter_mult=0.8), dict(base, volume_filter_mult=1.5)]
ps.SIGNAL_CACHE.clear()
res = ps.evaluate('t', code, {}, 'XAUSDT', '60', pair, start, split, end_n)
check('caché de señales distingue el nivel de volumen (×0,8 ≠ ×1,5)', res[0][3]['n'] != res[1][3]['n'],
      (res[0][3]['n'], res[1][3]['n']))

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

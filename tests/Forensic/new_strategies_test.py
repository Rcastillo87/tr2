"""
Estrategias BNF (sobreventa) y Ruptura de triángulos (docs/estrategias): señales esperadas en series sintéticas,
sin mirar al futuro (la señal de la vela t es la misma con datos hasta t que con toda la serie), Paper (500 velas)
= backtest, SL por swing del triángulo, parámetros inválidos.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/new_strategies_test.py
"""
import os, sys, time, json
sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd
from backtesting.strategies.loader import build_strategy
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs', 'estrategias') + os.sep
fails = 0
def check(name, ok, d=''):
    global fails; fails += 0 if ok else 1; print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {d}' if d != '' else ''))

def frame(close, interval_h=4, vol=None, start='2025-01-01'):
    close = np.asarray(close, float); n = len(close)
    rng = np.random.default_rng(1)
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close) * (1 + rng.uniform(0, 0.002, n)); lo = np.minimum(op, close) * (1 - rng.uniform(0, 0.002, n))
    return pd.DataFrame({'time': pd.date_range(start, periods=n, freq=f'{interval_h}h'), 'open': op, 'high': hi, 'low': lo,
                         'close': close, 'volume': vol if vol is not None else rng.uniform(900, 1100, n)})

def prefix_invariant(strat_params, df, idxs):
    full = build_strategy(strat_params).generate_signals(build_strategy(strat_params).prepare(df))['signal'].to_numpy()
    bad = [t for t in idxs if build_strategy(strat_params).generate_signals(build_strategy(strat_params).prepare(df.iloc[:t+1]))['signal'].iloc[-1] != full[t]]
    return full, bad

def window500(strat_params, df, idxs):
    full = build_strategy(strat_params).generate_signals(build_strategy(strat_params).prepare(df))['signal'].to_numpy()
    return [t for t in idxs if build_strategy(strat_params).generate_signals(build_strategy(strat_params).prepare(df.iloc[max(0,t-499):t+1]))['signal'].iloc[-1] != full[t]]

# ---------------- BNF ----------------
bnf = open(D + 'bnf_sobreventa.py').read()
P = dict(json.load(open(D + 'bnf_sobreventa.config.json')), strategy_code=bnf, interval='240')
rng = np.random.default_rng(7)
c = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.006, 900)))
crash_at = 600
c[crash_at:crash_at+5] = c[crash_at-1] * np.array([0.97, 0.93, 0.89, 0.86, 0.84])     # pánico: -16 % en 5 velas
c[crash_at+5:] = c[crash_at+4] * np.exp(np.cumsum(rng.normal(0.004, 0.004, 900-crash_at-5)))   # rebote
df = frame(c)
s = build_strategy(P); out = s.generate_signals(s.prepare(df))
e = np.nonzero(out['signal'].to_numpy() == 1)[0]; x = np.nonzero(out['signal'].to_numpy() == -1)[0]
ec = e[(e >= crash_at) & (e <= crash_at + 10)]
check('B1: el pánico dispara UNA entrada (flanco) en la caída', len(ec) == 1 and ec[0] <= crash_at + 5, list(e))
xc = x[x > (ec[0] if len(ec) else 10**9)]
check('B2: hay salida -1 después de la entrada del pánico, dentro de exit_window', len(xc) > 0 and xc[0] - ec[0] <= P['exit_window'], (list(xc[:3]), list(ec)))
calm = frame(100 * np.exp(np.cumsum(rng.normal(0, 0.003, 900))))
s = build_strategy(P); check('B3: mercado tranquilo -> sin señales', (s.generate_signals(s.prepare(calm))['signal'] != 0).sum() == 0)
slow = 100 * np.exp(np.linspace(0, -0.35, 900))      # cae 30 % pero lento: desviación sí, velocidad no
s = build_strategy(P); o = s.generate_signals(s.prepare(frame(slow)))
check('B4: caída lenta (sin velocidad) -> sin entrada', (o['signal'] == 1).sum() == 0, int((o['signal'] == 1).sum()))
s = build_strategy(dict(P, interval='60')); o = s.generate_signals(s.prepare(frame(c, 1)))
check('B5: en 1h (media > 500 velas) no da señales', (o['signal'] != 0).sum() == 0 and s.ma_bars() is None)
full, bad = prefix_invariant(P, df, list(range(560, 700)))
check('B6: sin mirar al futuro: la señal en t es la misma con datos hasta t que con toda la serie', bad == [], bad[:5])
check('B7: Paper (últimas 500 velas) = backtest en cada vela', window500(P, df, list(range(560, 900, 3))) == [])
try:
    build_strategy(dict(P, exit_reversion=1.5)); check('B8: parámetros inválidos -> error claro', False)
except ValueError as ex:
    check('B8: parámetros inválidos -> error claro', 'BNF' in str(ex))

# ---------------- Triángulo ----------------
tri = open(D + 'triangulo_ruptura.py').read()
T = dict(json.load(open(D + 'triangulo_ruptura.config.json')), strategy_code=tri, interval='240')
def ascending(n_pre=300, bars=60, top=110.0, base0=100.0, breakout_dir=1, seed=3):
    r = np.random.default_rng(seed)
    pre = 105 * np.exp(np.cumsum(r.normal(0, 0.004, n_pre)))
    pre = pre / pre[-1] * 104
    seg = []
    for i in range(bars):
        lowline = base0 + (top - 1 - base0) * i / bars
        ph = (i % 12) / 12.0
        seg.append(lowline + (top - lowline) * (0.5 + 0.48 * np.sin(2 * np.pi * ph)))
    seg = np.array(seg)
    post = top * (1.02 + 0.002 * np.arange(40)) if breakout_dir == 1 else (base0 + (top - base0) * 0.9) * (0.96 - 0.002 * np.arange(40))
    c = np.r_[pre, seg, post]
    vol = np.r_[r.uniform(900, 1100, n_pre), np.linspace(1200, 500, bars), np.full(40, 2500.0)]
    d = frame(c, 4, vol)
    # techo plano real y mínimos crecientes: forzar extremos de las velas de la figura
    a = n_pre
    for i in range(bars):
        lowline = base0 + (top - 1 - base0) * i / bars
        d.loc[a + i, 'high'] = min(d.loc[a + i, 'high'], top)
        d.loc[a + i, 'low'] = max(d.loc[a + i, 'low'], lowline)
    return d, a + bars
d, brk_bar = ascending()
s = build_strategy(T); o = s.generate_signals(s.prepare(d))
sigs = np.nonzero(o['signal'].to_numpy() != 0)[0]
check('T1: triángulo ascendente con ruptura al alza y volumen -> UN largo, en la vela de ruptura', len(sigs) == 1 and sigs[0] == brk_bar and o['signal'].iloc[brk_bar] == 1 and o['tri_kind'].iloc[brk_bar] == 'asc', (list(sigs[:3]), brk_bar, o['tri_kind'].iloc[brk_bar] if len(o) > brk_bar else None))
check('T2: antes de la ruptura no hay señales', (o['signal'].iloc[:brk_bar] != 0).sum() == 0)
dn, b2 = ascending(breakout_dir=-1)
o2 = build_strategy(dict(T, bias=True)).generate_signals(build_strategy(T).prepare(dn))
check('T3: bias=true: ascendente que rompe a la baja -> sin corto', (o2['signal'] == -1).sum() == 0)
d_novol, _ = ascending(); d_novol.loc[brk_bar:, 'volume'] = 600.0
o3 = build_strategy(T).generate_signals(d_novol)
check('T4: ruptura sin volumen -> sin señal', (o3['signal'] != 0).sum() == 0)
calm = frame(100 * np.exp(np.cumsum(np.random.default_rng(11).normal(0, 0.006, 1500))))
o4 = build_strategy(T).generate_signals(calm)
check('T5: paseo aleatorio largo -> pocas señales (no dispara en cualquier lado)', (o4['signal'] != 0).sum() <= 8, int((o4['signal'] != 0).sum()))
full, bad = prefix_invariant(T, d, list(range(brk_bar - 30, brk_bar + 30)))
check('T6: sin mirar al futuro (prefijo = serie completa)', bad == [], bad[:5])
check('T7: Paper (últimas 500 velas) = backtest', window500(T, calm, list(range(500, 1500, 7))) == [] and window500(T, d, [brk_bar]) == [])
# retest
dr, b = ascending(); top = 110.0
dr.loc[b, ['close', 'high']] = [top * 1.02, top * 1.025]; dr.loc[b, 'volume'] = 2500.0
for j, (o_, c_) in enumerate([(top*1.02, top*1.012), (top*1.012, top*1.004), (top*1.0005, top*1.012)], start=1):
    dr.loc[b + j, ['open', 'close', 'high', 'low', 'volume']] = [o_, c_, max(o_, c_) * 1.001, min(o_, c_) * 0.998 if j < 3 else top * 0.999, 1500.0]
o5 = build_strategy(dict(T, entry_mode='retest')).generate_signals(dr)
s5 = np.nonzero(o5['signal'].to_numpy() != 0)[0]
check('T8: modo retest: sin señal en la ruptura; largo en la vela de rechazo sobre el techo, SL bajo el mínimo del pullback', o5['signal'].iloc[b] == 0 and len(s5) >= 1 and s5[0] == b + 3 and o5['signal'].iloc[b + 3] == 1 and dr['close'].iloc[b+3] * (1 - o5['signal_sl_pct'].iloc[b+3] / 100) < dr['low'].iloc[b+1:b+4].min(), (list(s5[:3]), b, o5['signal_sl_pct'].iloc[b+3] if len(o5) > b+3 else None))
full, bad = prefix_invariant(dict(T, entry_mode='retest'), dr, list(range(b - 5, b + 10)))
check('T9: retest sin mirar al futuro', bad == [], bad[:5])
sl_b = o['signal_sl_pct'].iloc[brk_bar]
lows_fig = d['low'].iloc[brk_bar-60:brk_bar].to_numpy()
check('T12: SL por swing: en la ruptura, entre min y max, por debajo del último mínimo de la figura', 0.8 <= sl_b <= 6.0
      and d['close'].iloc[brk_bar] * (1 - sl_b / 100) < lows_fig[-8:].min() and d["close"].iloc[brk_bar] * (1 - sl_b / 100) > lows_fig[-8:].min() * (1 - 0.003), round(float(sl_b), 3))
ofx = build_strategy(dict(T, sl_mode='fixed')).generate_signals(d)
check('T13: sl_mode=fixed -> sin SL por señal (el motor usa sl_pct); mismas señales', ofx['signal_sl_pct'].isna().all()
      and (ofx['signal'].to_numpy() == o['signal'].to_numpy()).all())
check('T14: SL por swing solo en velas con señal', o['signal_sl_pct'].notna().sum() == (o['signal'] != 0).sum())
t0 = time.time(); build_strategy(T).generate_signals(frame(100 * np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.006, 4400)))))
el = time.time() - t0
check(f'T10: velocidad: 24 meses de 4h (4.400 velas) en {el:.2f}s (< 5 s)', el < 5)
try:
    build_strategy(dict(T, min_touches=5, max_pivots=4)); check('T11: parámetros inválidos -> error claro', False)
except ValueError as ex:
    check('T11: parámetros inválidos -> error claro', 'Triángulo' in str(ex))
calm2 = frame(100 * np.exp(np.cumsum(np.random.default_rng(11).normal(0, 0.006, 6000))))
loose = dict(T, breakout_vol_mult=0, vol_contraction=0)
n_loose = int((build_strategy(loose).generate_signals(calm2)['signal'] != 0).sum())
print(f'     info: paseo aleatorio de 6.000 velas sin filtros de volumen -> {n_loose} rupturas detectadas')
sb = build_strategy(dict(P, allow_short=True))
check('B9: BNF es solo largos aunque la configuración diga allow_short=true', not sb.allows_side('short') and sb.allows_side('long'))
sys.stdout.flush()
print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

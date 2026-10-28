"""
Equivalencia del motor optimizado (backtesting/engine.py) con la referencia congelada (reference/engine_v3_ref.py):
mismos trades (todos los campos, igualdad exacta), métricas y curva de capital, con la combinatoria de la UI.
  cd python-engine && venv/bin/python ../tests/Forensic/engine_speed_parity_test.py            # sintético
  cd python-engine && venv/bin/python ../tests/Forensic/engine_speed_parity_test.py --real     # + datos reales y estrategias de la DB
"""
import asyncio
import importlib.util
import itertools
import os
import random
import sys
import time
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())  # python-engine/

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import BacktestRequest, load_strategy  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from collectors.funding_collector import FundingData  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'engine_v3_ref', Path(__file__).resolve().parent / 'reference' / 'engine_v3_ref.py')
ref_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref_mod)
RefEngine = ref_mod.BacktestEngine

fails = 0
T_REF = T_NEW = 0.0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


RAND = """class T(BaseStrategy):
    def generate_signals(self, df):
        import numpy as np
        df = df.copy()
        x = np.random.default_rng(SEED).random(len(df))
        df['signal'] = 0
        df.loc[x < P, 'signal'] = 1
        df.loc[x > 1 - P, 'signal'] = -1
        if SLSIG:
            df['signal_sl_pct'] = np.where(x < 0.5, 0.8 + x, np.nan)
        return df
"""
OWN_TRAIL = RAND + """
    def calculate_trailing_sl(self, entry_price, side, current_price, current_sl, current_atr=None):
        if side == 'long':
            return max(current_sl, round(current_price * 0.985, 8)) if current_price > entry_price * 1.004 else current_sl
        return min(current_sl, round(current_price * 1.015, 8)) if current_price < entry_price * 0.996 else current_sl
"""


def synthetic(days=150, seed=5):
    rng = np.random.default_rng(seed)
    n = days * 1440
    vol = np.repeat(rng.choice([0.0005, 0.001, 0.002], size=n // 1440 + 1), 1440)[:n]
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1, n) * vol))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0, 1, n)) * vol * close * 0.6
    t = pd.date_range(datetime(2025, 1, 1, tzinfo=timezone.utc), periods=n, freq='1min')
    m = pd.DataFrame({'time': t, 'open': open_, 'high': np.maximum(open_, close) + wick,
                      'low': np.minimum(open_, close) - wick, 'close': close, 'volume': rng.gamma(2.0, 50, n)})

    def rs(iv):
        rule = '1D' if iv == 'D' else f'{iv}min'
        return (m.set_index('time').resample(rule, label='left', closed='left')
                .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
                .dropna().reset_index())
    ft = pd.date_range(t[0], t[-1], freq='8h')
    fund = FundingData('X', ft.tz_convert(None).to_numpy(dtype='datetime64[ns]'),
                       rng.normal(0.00005, 0.0002, len(ft)), None, None)
    return m, rs, fund, t[0] + timedelta(days=30)


def configs(k, seed):
    space = dict(
        sltp=[(1.0, 2.0), (1.5, 3.0), (0.8, 4.0), (2.5, 2.0)],
        trailing=[None, ('fixed', 1.0, 0.0), ('fixed', 1.5, 0.5), ('atr', 2.0, 0.0), ('atr', 3.0, 1.0),
                  ('stepped', 0, 0.0), ('stepped', 0, 0.6)],
        be=[99.0, 0.5, 1.0], dur=[0, 12, 40], dur_profit=[False, True],
        opposite=[(False, False), (True, False), (False, True)], short=[True, False],
        vol=[None, 'close', 'widen'], regime=[False, True])
    rng = random.Random(seed)
    keys = list(space)
    out = []
    for _ in range(k):
        c = {key: rng.choice(space[key]) for key in keys}
        tr = c['trailing']
        out.append(dict(sl_pct=c['sltp'][0], tp_pct=c['sltp'][1], be_pct=c['be'], max_duration=c['dur'],
                        max_duration_profit=c['dur_profit'], close_on_opposite=c['opposite'][0],
                        exit_on_opposite=c['opposite'][1], allow_short=c['short'],
                        volatility_protection_mode=c['vol'], volatility_atr_multiplier=1.3, volatility_widen_pct=1.0,
                        regime_filter=c['regime'],
                        trailing_mode=tr[0] if tr else None,
                        trailing_distance_pct=tr[1] if tr and tr[0] == 'fixed' else 1.0,
                        trailing_atr_mult=tr[1] if tr and tr[0] == 'atr' else 2.0,
                        trailing_activation_buffer_pct=tr[2] if tr else 0.0,
                        trailing_steps=[[0.8, 0.1], [1.6, 0.9], [2.5, 1.8]] if tr and tr[0] == 'stepped' else []))
    return out


def same(a, b):
    """Igualdad exacta de dos resultados (los backtest_id llevan la hora: se excluyen)."""
    if len(a['trades']) != len(b['trades']):
        return f"{len(a['trades'])} vs {len(b['trades'])} trades"
    for k, (x, y) in enumerate(zip(a['trades'], b['trades'])):
        if x != y:
            diff = {f: (x.get(f), y.get(f)) for f in set(x) | set(y) if x.get(f) != y.get(f)}
            return f"trade {k}: {diff}"
    if a['metrics'] != b['metrics']:
        return 'métricas distintas'
    return ''


def compare(label, make, df, minute_df, funding, trade_from):
    global T_REF, T_NEW
    t = time.time()
    r1 = RefEngine(strategy=make(), df=df, initial_balance=10000.0, risk_per_trade_pct=1.0, minute_df=minute_df,
                   trade_from=trade_from, funding=funding).run()
    T_REF += time.time() - t
    t = time.time()
    r2 = BacktestEngine(strategy=make(), df=df, initial_balance=10000.0, risk_per_trade_pct=1.0, minute_df=minute_df,
                        trade_from=trade_from, funding=funding).run()
    T_NEW += time.time() - t
    d = same(r1, r2)
    return d, len(r1['trades'])


def maker(code, iv, cfg, scfg=None, symbol='X', macro_df=None, signals=None):
    def make():
        req = BacktestRequest(strategy='t', strategy_code=code, strategy_config=scfg or {}, symbol=symbol, interval=iv,
                              initial_balance=10000.0, risk_per_trade_pct=1.0, commission_pct=0.055,
                              slippage_pct=0.05, **cfg)
        s = load_strategy(req)
        s.slippage_pct = 0.05
        if macro_df is not None:
            s.macro_df = macro_df
        if signals is not None:
            s.compute_signals = lambda _df, c=signals: c.copy()
        return s
    return make


def synthetic_suite():
    m, rs, fund, start = synthetic()
    cases = [('60', True, True), ('240', True, False), ('60', False, True), ('15', False, False), ('D', True, True)]
    total_trades = 0
    for iv, with_1m, with_fund in cases:
        df = rs(iv)
        mdf = m[m['time'] >= start].reset_index(drop=True) if with_1m else None
        bad = []
        n_cfg = 0
        for j, cfg in enumerate(configs(36, seed=zlib.crc32(iv.encode()) % 1000)):
            code = (RAND.replace('SEED', str(j)).replace('P', '0.04' if iv in ('15', '60') else '0.12')
                    .replace('SLSIG', 'True' if j % 3 == 0 else 'False'))
            d, nt = compare(f'{iv}-{j}', maker(code, iv, cfg), df, mdf, fund if with_fund else None, start)
            total_trades += nt
            n_cfg += 1
            if d:
                bad.append(f"cfg {j} {cfg['trailing_mode']}: {d}")
        check(f"sintético {iv} {'con' if with_1m else 'sin'} 1m {'con' if with_fund else 'sin'} funding: "
              f"{n_cfg} configuraciones idénticas", not bad, bad[:2] if bad else '')
    # Estrategia con trailing propio: el motor nuevo usa su método (no el cálculo en línea)
    df, mdf = rs('60'), m[m['time'] >= start].reset_index(drop=True)
    bad = []
    for j, cfg in enumerate(configs(10, seed=99)):
        cfg = dict(cfg, trailing_mode='fixed')
        code = OWN_TRAIL.replace('SEED', str(j)).replace('P', '0.04').replace('SLSIG', 'False')
        d, nt = compare(f'own-{j}', maker(code, '60', cfg), df, mdf, fund, start)
        total_trades += nt
        if d:
            bad.append(d)
    check('estrategia con trailing propio: 10 configuraciones idénticas', not bad, bad[:1] if bad else '')
    check(f'se compararon suficientes trades ({total_trades})', total_trades > 20000, total_trades)


def real_suite():
    import cli.param_search as ps
    start, end = ps.ui_period(24)
    strategies = asyncio.run(ps.strategies_from_db())
    for iv in ('60', '240'):
        asyncio.run(ps.load_data(['BTCUSDT'], [iv], start, end, log=lambda *_: None))
        data = ps.DATA[('BTCUSDT', iv)]
        for name, code, scfg in strategies:
            bad, nt_all = [], 0
            for j, cfg in enumerate(ps.sample_configs(8, 3)):
                cfg = dict(cfg, **ps.UI_FIXED)
                mk = maker(code, iv, cfg, scfg, 'BTCUSDT', data.macro_df if cfg['macro_trend_filter'] else None)
                sig = mk().compute_signals(data.df)
                d, nt = compare(f'{name}-{j}', maker(code, iv, cfg, scfg, 'BTCUSDT',
                                                     data.macro_df if cfg['macro_trend_filter'] else None, sig),
                                data.df, data.minute_df, data.funding, start)
                nt_all += nt
                if d:
                    bad.append(f"cfg {j}: {d}")
            check(f"real BTCUSDT {iv} · {name}: 8 configuraciones idénticas ({nt_all} trades)", not bad, bad[:1] if bad else '')
        ps.drop_data(['BTCUSDT'])


if __name__ == '__main__':
    synthetic_suite()
    if '--real' in sys.argv:
        real_suite()
    print(f"\nTiempo de motor: referencia {T_REF:.1f}s · optimizado {T_NEW:.1f}s · "
          f"{T_REF / T_NEW if T_NEW else 0:.1f}x más rápido")
    print('RESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)

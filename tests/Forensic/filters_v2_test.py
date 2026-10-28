"""
Filtros de apertura v2: regímenes permitidos elegidos en la UI y tendencia de BTC para altcoins. Sin DB.
  - allowed_regimes: None = los de la estrategia; lista = pisa los de la clase; [] = no opera.
  - Con los 3 regímenes y ambiguo = lateral el filtro de régimen no cambia nada (el motivo del aviso en pantalla).
  - Tendencia de BTC: bloquea largos con BTC bajista y cortos con BTC alcista, sin mirar al futuro; en BTC no aplica;
    sin velas de BTC no opera (pesimista). Paper y real usan el mismo compute_signals.
  - BacktestRequest acepta los campos nuevos y llegan a la estrategia (regla 3: nada quemado).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/filters_v2_test.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import cli.param_search as ps  # noqa: E402
from api.v1.backtest import BacktestRequest, load_strategy  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.base_strategy import macro_trend_series  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


CODE = ("class T(BaseStrategy):\n    def generate_signals(self, df):\n        import numpy as np\n        df = df.copy()\n"
        "        x = np.random.default_rng(3).random(len(df))\n        df['signal'] = 0\n        df.loc[x < 0.05, 'signal'] = 1\n"
        "        df.loc[x > 0.95, 'signal'] = -1\n        return df\n")
CODE_RANGING = CODE.replace("    def generate_signals", "    allowed_regimes = ['RANGING']\n    def generate_signals")


def strat(symbol='XAUSDT', code=CODE, **kw):
    req = BacktestRequest(strategy='t', strategy_code=code, symbol=symbol, interval='60', **kw)
    s = load_strategy(req)
    s.slippage_pct = 0.05
    return s


# 1) Regímenes permitidos
check('sin allowed_regimes: los de la estrategia (los 3)', strat().allowed_regimes == ['TRENDING', 'RANGING', 'VOLATILE'])
check('sin allowed_regimes: estrategia solo lateral -> RANGING', strat(code=CODE_RANGING).allowed_regimes == ['RANGING'])
s = strat(code=CODE_RANGING, regime_filter=True, allowed_regimes=['VOLATILE', 'TRENDING'])
check('la UI pisa los de la clase (orden canónico)', s.allowed_regimes == ['TRENDING', 'VOLATILE'], s.allowed_regimes)
check('should_operate respeta la elección', s.should_operate('TRENDING') and not s.should_operate('RANGING'))
s = strat(regime_filter=True, allowed_regimes=[])
check('lista vacía: no opera en ningún régimen', not any(s.should_operate(r) for r in ('TRENDING', 'RANGING', 'VOLATILE')))
check('régimen apagado: opera aunque la lista esté vacía', strat(regime_filter=False, allowed_regimes=[]).should_operate('RANGING'))
check('valores desconocidos se descartan', strat(allowed_regimes=['RANGING', 'X']).allowed_regimes == ['RANGING'])

start, end = ps.synthetic_data(['XAUSDT', 'BTCUSDT'], ['60'], 6)
data, btc = ps.DATA[('XAUSDT', '60')], ps.DATA[('BTCUSDT', '60')]


def run(s, d=data):
    return BacktestEngine(strategy=s, df=d.df, initial_balance=10000, risk_per_trade_pct=1.0, minute_df=d.minute_df,
                          trade_from=start).run()['trades']


base = run(strat(regime_filter=False))
same = run(strat(regime_filter=True, regime_ambiguous_as='RANGING'))
check('3 regímenes + ambiguo lateral = sin efecto (por eso el aviso)',
      [(t['entry_time'], t['side']) for t in base] == [(t['entry_time'], t['side']) for t in same], (len(base), len(same)))
only = run(strat(regime_filter=True, allowed_regimes=['RANGING']))
check('solo lateral: menos operaciones y todas en lateral', 0 < len(only) < len(base) and all(t['regime'] == 'RANGING' for t in only),
      (len(base), len(only), {t['regime'] for t in only}))

# 2) Tendencia de BTC
s = strat(btc_trend_filter=True)
s.btc_macro_df = btc.macro_df
out = s.compute_signals(data.df)
raw = strat().compute_signals(data.df)
trend = macro_trend_series(data.df['time'], '60', btc.macro_df)
sig_raw, sig = raw['signal'].to_numpy(), out['signal'].to_numpy()
exp = np.where(((sig_raw == 1) & (trend != 1)) | ((sig_raw == -1) & (trend != -1)), 0, sig_raw)
check('BTC: bloquea largos con BTC bajista y cortos con BTC alcista (exacto)', np.array_equal(sig, exp),
      int((sig != exp).sum()))
check('BTC: bloquea algo y deja algo', 0 < int((sig != 0).sum()) < int((sig_raw != 0).sum()),
      (int((sig_raw != 0).sum()), int((sig != 0).sum())))
s2 = strat(btc_trend_filter=True)
s2.btc_macro_df = None
check('BTC sin velas de BTC: no opera (pesimista)', int((s2.compute_signals(data.df)['signal'] != 0).sum()) == 0)
s3 = strat(symbol='BTCUSDT', btc_trend_filter=True)
check('BTC en BTCUSDT: no aplica', not s3.btc_filter_applies() and
      np.array_equal(s3.compute_signals(btc.df)['signal'].to_numpy(), strat(symbol='BTCUSDT').compute_signals(btc.df)['signal'].to_numpy()))
check('BTC apagado: no cambia nada', np.array_equal(strat().compute_signals(data.df)['signal'].to_numpy(), sig_raw))
# sin mirar al futuro: la decisión de la vela i solo usa velas H4 de BTC cerradas antes de su cierre
cut = data.df['time'].iloc[len(data.df) // 2]
m_past = btc.macro_df[pd.to_datetime(btc.macro_df['time']) + pd.Timedelta(hours=4) <= cut + pd.Timedelta(hours=1)]
t_full = macro_trend_series(data.df['time'][data.df['time'] <= cut], '60', btc.macro_df)
t_past = macro_trend_series(data.df['time'][data.df['time'] <= cut], '60', m_past)
check('BTC sin mirar al futuro: mismas decisiones sin las velas H4 posteriores', np.array_equal(t_full, t_past))
trades_btc = run(s)
check('BTC en el motor: corre y opera menos', 0 < len(trades_btc) < len(base), (len(base), len(trades_btc)))

# 3) Campos nuevos en el request (los manda Laravel)
fields = BacktestRequest.model_fields
check('BacktestRequest tiene btc_trend_filter y allowed_regimes', 'btc_trend_filter' in fields and 'allowed_regimes' in fields)
s = strat(btc_trend_filter=True, allowed_regimes=['TRENDING'])
check('llegan a la estrategia', s.btc_trend_filter is True and s.allowed_regimes == ['TRENDING'])

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

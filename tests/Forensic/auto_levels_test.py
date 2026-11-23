"""
D-45 (p92): SL, TP y break-even automáticos por ATR, opcionales, iguales en backtest, Paper y Real.

A. Cálculo (backtesting/auto_levels.py): fórmula, topes, «veces el SL», orden automático → estrategia → fijo, sin ATR,
   interruptor general (D-49), sin mirar el futuro.
B. Backtest: en modo fijo nada cambia; en automático la operación abre con los % de la vela de la señal.
C. Paper y Real: los mismos niveles que el backtest para la misma vela y el mismo precio; el snapshot de Real los
   guarda y la recuperación (adopción) los usa.
D. Estático: los tres motores llaman with_levels tras compute_signals y leen los tres %; validación de los campos.
E. La regresión ve los fallos: toda prueba de la lista oficial termina con código distinto de 0 si falla.
"""
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


try:
    from backtesting import auto_levels as al
except ImportError as e:
    check('existe backtesting/auto_levels.py', False, e)
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402
from indicators.regime_indicators import calculate_atr  # noqa: E402

CODE = """class T(BaseStrategy):
    def generate_signals(self, df):
        df['signal'] = 0
        df.loc[df.index.isin(self.fire), 'signal'] = 1
        if self.own_sl is not None:
            df['signal_sl_pct'] = self.own_sl
        return df
"""
BASE = dict(symbol='BTCUSDT', interval='240', sl_pct=1.0, tp_pct=2.0, be_pct=1.5, max_duration=0, regime_filter=False,
            commission_pct=0.0, slippage_pct=0.0, strategy_code=CODE)


def strat(own_sl=None, fire=(), **kw):
    s = build_strategy({**BASE, **kw})
    s.fire, s.own_sl = set(fire), own_sl
    return s


def frame(n=120, seed=7, start='2026-01-01'):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    high = close * (1 + rng.uniform(0.001, 0.02, n))
    low = close * (1 - rng.uniform(0.001, 0.02, n))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({'time': pd.date_range(start, periods=n, freq='4h', tz='UTC'), 'open': open_, 'high': high,
                         'low': low, 'close': close, 'volume': 1.0})


df = frame()
atr = calculate_atr(df, 14).to_numpy()
AUTO = dict(sl_tp_mode='atr', sl_atr_mult=2.0, tp_r_mult=3.0, be_r_mult=1.0, sl_min_pct=0.5, sl_max_pct=5.0)

# ── A. Cálculo ──
s_fixed = strat()
check('A1: modo fijo (default): el df no cambia (mismo objeto, sin columnas nuevas)',
      s_fixed.sl_tp_mode == 'fixed' and al.apply(df, s_fixed) is df)
s = strat(**AUTO)
out = s.with_levels(s.compute_signals(df.copy()))
i = 60
exp_sl = round(min(max(2.0 * atr[i] / df['close'][i] * 100, 0.5), 5.0), 6)
check('A2: SL % = 2 × ATR(14) / cierre, en la vela de la señal', abs(out['signal_sl_pct'][i] - exp_sl) < 1e-12,
      (out['signal_sl_pct'][i], exp_sl))
check('A3: TP = 3 × SL y break-even = 1 × SL («veces el SL»)',
      abs(out['signal_tp_pct'][i] - round(exp_sl * 3, 6)) < 1e-12 and abs(out['signal_be_pct'][i] - exp_sl) < 1e-12)
s_lo = strat(**dict(AUTO, sl_min_pct=4.0, sl_max_pct=4.5))
o2 = s_lo.with_levels(s_lo.compute_signals(df.copy()))
check('A4: topes: con mínimo 4 % y máximo 4,5 % todos los SL quedan dentro', o2['signal_sl_pct'][14:].between(4.0, 4.5).all())
s_sw = strat(**dict(AUTO, sl_min_pct=4.5, sl_max_pct=4.0))
o3 = s_sw.with_levels(s_sw.compute_signals(df.copy()))
check('A5: mínimo y máximo invertidos: se ordenan (no rompe)', o3['signal_sl_pct'][14:].between(4.0, 4.5).all())
check('A6: sin 14 velas no hay ATR: la vela queda sin niveles automáticos (fijo)',
      out['signal_sl_pct'][:14].isna().all() and out['signal_tp_pct'][:14].isna().all())
s_own = strat(own_sl=1.7, **AUTO)
o4 = s_own.with_levels(s_own.compute_signals(df.copy()))
check('A7: orden automático → estrategia: con ATR manda el automático; sin ATR, el SL de la estrategia (1,7)',
      abs(o4['signal_sl_pct'][i] - exp_sl) < 1e-12 and (o4['signal_sl_pct'][:14] == 1.7).all()
      and o4['signal_tp_pct'][:14].isna().all())
os.environ['SLTP_AUTO_ENABLED'] = 'false'
o5 = s.with_levels(s.compute_signals(df.copy()))
check('A8: interruptor general SLTP_AUTO_ENABLED=false (D-49): sin niveles automáticos aunque la config diga «atr»',
      'signal_tp_pct' not in o5.columns and not al.is_auto(s))
os.environ['SLTP_AUTO_ENABLED'] = 'true'
part = s.with_levels(s.compute_signals(df.iloc[:i + 1].copy()))
check('A9: no mira el futuro: los niveles de la vela 60 con las velas hasta la 60 = con todas',
      all(abs(part[c].iloc[-1] - out[c][i]) < 1e-12 for c in al.LEVEL_COLS))
check('A10: row_levels lee los tres % de una vela; vela sin niveles = None',
      al.row_levels(out.iloc[i]) == {'sl': out['signal_sl_pct'][i], 'tp': out['signal_tp_pct'][i], 'be': out['signal_be_pct'][i]}
      and al.row_levels(s_fixed.compute_signals(df.copy()).iloc[i]) == {'sl': None, 'tp': None, 'be': None})

# ── B. Backtest ──
def run(st):
    return BacktestEngine(strategy=st, df=df.copy(), initial_balance=10000, risk_per_trade_pct=1.0).run()['trades']


t_fixed = run(strat(fire=[i]))
t_fixed2 = run(strat(fire=[i], sl_tp_mode='fixed'))
check('B1: modo fijo: mismas operaciones con o sin la clave (como antes)', t_fixed == t_fixed2 and len(t_fixed) == 1)
e = t_fixed[0]['entry_price']
check('B2: modo fijo: SL 1 % y TP 2 % del precio de entrada',
      abs(t_fixed[0]['tp1'] - e * 1.02) < 1e-6 and abs(t_fixed[0]['sl'] - e * 0.99) < 1e-6, (t_fixed[0]['sl'], t_fixed[0]['tp1']))
far = dict(AUTO, be_r_mult=20.0)   # break-even lejos: el SL no se mueve y se ve el inicial
t_auto = run(strat(fire=[i], **far))
ea = t_auto[0]['entry_price']
sl_a, tp_a = exp_sl, round(exp_sl * 3, 6)
check('B3: automático: abre con el SL y el TP de la vela de la señal (aplicados al precio de entrada)',
      abs(t_auto[0]['tp1'] - round(ea * (1 + tp_a / 100), 8)) < 1e-9 and abs(t_auto[0]['sl'] - round(ea * (1 - sl_a / 100), 8)) < 1e-9,
      (t_auto[0]['sl'], t_auto[0]['tp1']))
check('B4: automático: el tamaño se ajusta al SL (mismo riesgo en USDT)',
      abs(t_auto[0]['size'] * (ea - t_auto[0]['sl']) - 100) < 1e-4 * 100, t_auto[0]['size'] * (ea - t_auto[0]['sl']))
os.environ['SLTP_AUTO_ENABLED'] = 'off'
t_off = run(strat(fire=[i], **far))
os.environ['SLTP_AUTO_ENABLED'] = 'true'
check('B5: con el interruptor apagado el backtest vuelve exacto al fijo', t_off == t_fixed, (len(t_off),))

# ── C. Paper y Real: mismos niveles ──
from trading.paper_trader import PaperTrader, snapshot_with_levels  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

lv = al.row_levels(out.iloc[i])
st = strat(**far)
sl_r, tp_r, be_r = RealTrader._levels(st, ea, 'long', lv['sl'], lv['tp'], lv['be'])
check('C1: Real: con el mismo precio, SL y TP iguales a los del backtest',
      abs(sl_r - t_auto[0]['sl']) < 1e-9 and abs(tp_r - t_auto[0]['tp1']) < 1e-9, (sl_r, tp_r))
snap = {'sl_pct': 1.0, 'signal_sl_pct': lv['sl'], 'signal_tp_pct': lv['tp'], 'signal_be_pct': lv['be']}
check('C2: Real: la recuperación (adopción) toma los % del snapshot; sin ellos, el SL fijo y TP/BE fijos',
      RealTrader._effective_levels(st, snap) == (lv['sl'], lv['tp'], lv['be'])
      and RealTrader._effective_levels(st, {}) == (1.0, None, None))
check('C3: Real sin % de la señal: SL/TP/BE fijos de la config (como antes)',
      RealTrader._levels(st, 100.0, 'long', 1.0) == (99.0, 102.0, round(100 * (1 + 1.5 / 100), 8)))
check('C4: Paper: el snapshot guarda los % de la señal solo si los hubo',
      snapshot_with_levels({'a': 1}, None, None, None) == {'a': 1}
      and snapshot_with_levels({'a': 1}, 2.0, 6.0, 2.0) == {'a': 1, 'signal_sl_pct': 2.0, 'signal_tp_pct': 6.0, 'signal_be_pct': 2.0})


class PConn:
    def __init__(self, sink):
        self.sink = sink

    async def execute(self, sql, *a):
        self.sink.append(a)


class PPool:
    def __init__(self):
        self.sink = []

    def acquire(self):
        pool = self

        class Ctx:
            async def __aenter__(self):
                return PConn(pool.sink)

            async def __aexit__(self, *x):
                return False
        return Ctx()


async def paper_open():
    params = {**BASE, **far}
    pt = PaperTrader(PPool(), {}, {})
    pt.config_map = {9: {'id': 9, 'display_name': 'T', 'symbol': 'BTCUSDT', 'interval': '240', 'params': params}}
    pt._get_params_for = lambda cid: params
    await pt.open_trade(9, st, 'long', ea, 'TRENDING', lv['sl'], lv['tp'], lv['be'])
    return pt.pool.sink[0]


row = asyncio.run(paper_open())
check('C5: Paper: abre con el mismo SL y TP que el backtest (precio de entrada sin deslizamiento)',
      abs(row[6] - t_auto[0]['sl']) < 1e-9 and abs(row[7] - t_auto[0]['tp1']) < 1e-9, (row[6], row[7]))

# ── D. Estático ──
src = {n: (ROOT / 'python-engine' / p).read_text(encoding='utf-8') for n, p in (
    ('engine', 'backtesting/engine.py'), ('paper', 'trading/paper_trader.py'), ('real', 'trading/real_trader.py'),
    ('api', 'api/v1/real_trading.py'))}
check('D1: backtest, Paper y Real calculan con with_levels(compute_signals(...)) (un solo cálculo)',
      all(re.search(r'with_levels\(\w+\.compute_signals\(', src[k]) for k in ('engine', 'paper', 'real')))
check('D2: Paper y Real abren con los tres % de la vela (row_levels) y Real los guarda en el snapshot',
      "lv['sl'], lv['tp'], lv['be']" in src['paper'] and "lv['sl'], lv['tp'], lv['be']" in src['real']
      and "'signal_tp_pct': signal_tp_pct" in src['real'] and "'signal_be_pct': signal_be_pct" in src['real'])
check('D3: la adopción de la conciliación usa los % del snapshot', '*trader._effective_levels(strategy, params)' in src['api'])
from api.v1.backtest import BacktestRequest  # noqa: E402


def rejects(cfg):
    try:
        BacktestRequest(strategy='x', strategy_code='c', symbol='BTCUSDT', interval='60', strategy_config=cfg)
        return False
    except Exception:   # noqa: BLE001
        return True


check('D4: validación (Laravel y Python): modo desconocido, mínimo > máximo y multiplicadores ≤ 0 se rechazan, '
      'también dentro del JSON de la estrategia',
      rejects({'sl_tp_mode': 'atx'}) and rejects({'sl_min_pct': 6, 'sl_max_pct': 5}) and rejects({'tp_r_mult': 0})
      and not rejects(dict(AUTO)))

# ── E. Códigos de salida de la regresión ──
cert = (ROOT / 'docs' / 'CERTIFICACION_AUDITORIA.md').read_text(encoding='utf-8')
names = re.search(r'^\d+ Python: `([^`]+)`', cert, re.M).group(1).split()
silent = [n for n in names if not re.search(r'sys\.exit\(|raise SystemExit', (ROOT / 'tests' / 'Forensic' / f'{n}.py').read_text(encoding='utf-8'))]
check('E1: toda prueba Python de la regresión termina con código ≠ 0 si falla (paper_parity_test salía 0 con 10 fallos)',
      not silent, silent)

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

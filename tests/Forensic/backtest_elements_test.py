"""
Fase 3 · cada filtro y elemento del backtest hace EXACTAMENTE lo que dice la UI.

Corre el motor real (mismo camino que /v1/backtest/run: BacktestRequest → load_strategy → BacktestEngine con
velas de 1m) en varios escenarios y comprueba, operación por operación, la regla de cada elemento:
costos y llenados, tamaño por riesgo, SL, TP, régimen, caso ambiguo, volumen, tendencia macro, duración,
cierre por tiempo en ganancia, break-even, trailing fijo y ATR (con su activación) y señal opuesta.
Solo lectura: no escribe en la base de datos.

Uso (desde python-engine/):
  venv/bin/python ../tests/Forensic/backtest_elements_test.py                      # datos reales (BTCUSDT H1, 6 meses)
  venv/bin/python ../tests/Forensic/backtest_elements_test.py --strategy all            # las 5 estrategias
  venv/bin/python ../tests/Forensic/backtest_elements_test.py --symbol SOLUSDT --months 12 --strategy "VWAP Reversión"
  venv/bin/python ../tests/Forensic/backtest_elements_test.py --synthetic /ruta/estrategia.py   # sin base de datos
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import WARMUP_BARS, BacktestRequest, load_strategy  # noqa: E402
from backtesting.engine import BacktestEngine, compute_regimes  # noqa: E402
from backtesting.strategies.base_strategy import calculate_trailing_sl_standalone  # noqa: E402

fails = 0
EPS = 1e-9


def check(name: str, ok: bool, detail: str = '') -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + detail if detail else ''}")


def rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


# ─────────────────────────────── datos ───────────────────────────────

def synthetic_data(months: int, seed: int = 7):
    """Paseo aleatorio de 1m con régimenes alternos; las velas de 60m se agregan desde las de 1m."""
    rng = np.random.default_rng(seed)
    n = months * 30 * 24 * 60 + WARMUP_BARS * 60
    vol = np.repeat(rng.choice([0.0004, 0.0009, 0.0018], size=n // 1440 + 1), 1440)[:n]
    drift = np.repeat(rng.normal(0, 0.00004, size=n // 4320 + 1), 4320)[:n]
    close = 30000 * np.exp(np.cumsum(drift + rng.normal(0, 1, n) * vol))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0, 1, n)) * vol * close * 0.6
    high, low = np.maximum(open_, close) + wick, np.minimum(open_, close) - wick
    t = pd.date_range(datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(minutes=n), periods=n,
                      freq='1min', tz='UTC')
    m = pd.DataFrame({'time': t, 'open': open_, 'high': high, 'low': low, 'close': close,
                      'volume': rng.gamma(2.0, 50, n) * (1 + 3 * (vol > 0.001))})
    h = (m.set_index('time').resample('60min', label='left', closed='left')
         .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index())
    start = h['time'].iloc[WARMUP_BARS].to_pydatetime()
    h4 = (h.set_index('time').resample('240min', label='left', closed='left')
          .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index())
    return h, m[m['time'] >= start].reset_index(drop=True), start, h4


async def real_data(symbol: str, interval: str, months: int):
    from api.v1.backtest import interval_delta, load_ohlcv
    from collectors.broker_resolver import resolve_backtest_source
    from db import close_pools, get_pool
    end = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = (end - timedelta(days=31 * months)).replace(day=1)
    pool = await get_pool('backtest')
    try:
        src = await resolve_backtest_source(pool, symbol, interval, start, end)
        if src is None:
            sys.exit(f"Sin velas de {symbol} {interval}")
        df = await load_ohlcv(pool, symbol, interval, src.broker, start - interval_delta(interval) * WARMUP_BARS, end)
        msrc = await resolve_backtest_source(pool, symbol, '1', start, end)
        if msrc is None or not msrc.covers(start, end):
            sys.exit("Las velas de 1m no cubren el rango: la prueba necesita 1m completo")
        mdf = await load_ohlcv(pool, symbol, '1', msrc.broker, start, end)
        h4src = await resolve_backtest_source(pool, symbol, '240', start - timedelta(hours=4 * 300), end)
        h4 = await load_ohlcv(pool, symbol, '240', h4src.broker, start - timedelta(hours=4 * 300), end) if h4src else None
    finally:
        await close_pools()
    return df, mdf, start, h4


def _dsn() -> str:
    return (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
            f"{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")


async def strategy_names() -> list[str]:
    import asyncpg
    c = await asyncpg.connect(_dsn())
    try:
        return [r['name'] for r in await c.fetch("SELECT name FROM strategies ORDER BY id")]
    finally:
        await c.close()


async def strategy_code_from_db(name: str) -> tuple[str, dict]:
    import asyncpg
    c = await asyncpg.connect(_dsn())
    try:
        row = await c.fetchrow("SELECT code, config FROM strategies WHERE name = $1", name)
    finally:
        await c.close()
    if not row:
        sys.exit(f"No existe la estrategia '{name}'")
    cfg = json.loads(row['config']) if isinstance(row['config'], str) else (row['config'] or {})
    return row['code'], cfg


# ─────────────────────────────── motor ───────────────────────────────

BASE = dict(sl_pct=1.5, tp_pct=3.0, be_pct=99.0, max_duration=0, risk_per_trade_pct=1.0, commission_pct=0.055,
            slippage_pct=0.05, regime_filter=False, regime_adx_trending=25.0, regime_adx_ranging=20.0,
            regime_ambiguous_as='RANGING', volume_filter=False, volume_filter_period=20, volume_filter_mult=1.2,
            macro_trend_filter=False, trailing_mode=None, trailing_distance_pct=1.0, trailing_atr_mult=2.0,
            trailing_activation_buffer_pct=0.0, max_duration_profit=False, close_on_opposite=False)


class Runner:
    def __init__(self, code, cfg, symbol, interval, df, mdf, start, h4=None):
        self.code, self.cfg, self.symbol, self.interval = code, cfg, symbol, interval
        self.df, self.mdf, self.start, self.h4 = df, mdf, start, h4
        self.open_by_time = dict(zip(pd.to_datetime(df['time'], utc=True), df['open'].astype(float)))
        self.index_by_time = {t: i for i, t in enumerate(pd.to_datetime(df['time'], utc=True))}

    def run(self, allowed_regimes=None, **over):
        p = dict(BASE, **over)
        req = BacktestRequest(strategy='prueba-elementos', strategy_code=self.code, strategy_config=self.cfg,
                              symbol=self.symbol, interval=self.interval, initial_balance=10000.0, **p)
        s = load_strategy(req)
        s.slippage_pct = float(req.slippage_pct)  # igual que run_backtest
        if hasattr(s, 'macro_df'):                  # velas H4 para la tendencia macro (igual que run_backtest)
            s.macro_df = self.h4
        if allowed_regimes is not None:            # solo para probar el filtro con regímenes restringidos
            s.allowed_regimes = list(allowed_regimes)
        eng = BacktestEngine(strategy=s, df=self.df, initial_balance=10000.0, risk_per_trade_pct=req.risk_per_trade_pct,
                             minute_df=self.mdf, trade_from=self.start)
        res = eng.run()
        return s, res['trades'], p

    @staticmethod
    def reasons(trades):
        out = {}
        for t in trades:
            out[t['exit_reason']] = out.get(t['exit_reason'], 0) + 1
        return out


def ts(x):
    return pd.Timestamp(x).tz_localize('UTC') if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).tz_convert('UTC')


# ─────────────────────────────── pruebas ───────────────────────────────

def test_costs_and_fills(r: Runner):
    s, tr, p = r.run()
    print(f"\n[1] Base: {len(tr)} operaciones · salidas {r.reasons(tr)}")
    check('base: hay operaciones suficientes para probar (≥ 20)', len(tr) >= 20, str(len(tr)))
    slip, com, bal = p['slippage_pct'] / 100, p['commission_pct'] / 100, 10000.0
    bad = {'entrada': 0, 'sl': 0, 'tp': 0, 'salida': 0, 'comision': 0, 'pnl': 0, 'tamano': 0, 'solape': 0}
    prev_exit = None
    for t in tr:
        long = t['side'] == 'long'
        o = r.open_by_time.get(ts(t['entry_time']))
        if o is None or rel(t['entry_price'], o * (1 + slip if long else 1 - slip)) > EPS:
            bad['entrada'] += 1
        e = t['entry_price']
        if rel(t['sl'], e * (1 - p['sl_pct'] / 100) if long else e * (1 + p['sl_pct'] / 100)) > 1e-8:
            bad['sl'] += 1
        if rel(t['tp1'], e * (1 + p['tp_pct'] / 100) if long else e * (1 - p['tp_pct'] / 100)) > 1e-8:
            bad['tp'] += 1
        if rel(t['exit_price'], t['exit_level'] * (1 - slip if long else 1 + slip)) > EPS:
            bad['salida'] += 1
        if abs(t['commission'] - round((e + t['exit_price']) * t['size'] * com, 4)) > 1e-4:
            bad['comision'] += 1
        gross = (t['exit_price'] - e) * t['size'] if long else (e - t['exit_price']) * t['size']
        if abs(t['pnl'] - round(gross - (e + t['exit_price']) * t['size'] * com, 4)) > 2e-4:
            bad['pnl'] += 1
        size = round(min(bal * p['risk_per_trade_pct'] / 100 / abs(e - t['sl']), bal * 1.0 / e), 6)
        if abs(t['size'] - size) > max(2e-6, size * 1e-4):  # el motor redondea a 6 decimales y acumula el PnL sin redondear
            bad['tamano'] += 1
        if prev_exit is not None and ts(t['entry_time']) < ts(prev_exit):
            bad['solape'] += 1
        prev_exit = t['exit_time']
        bal += t['pnl']
    labels = {'entrada': 'entrada = open de la vela ± slippage en contra', 'sl': 'SL = entrada × (1 ∓ SL%)',
              'tp': 'TP = entrada × (1 ± TP%)', 'salida': 'salida = nivel ± slippage en contra',
              'comision': 'comisión = (entrada + salida) × tamaño × comisión%', 'pnl': 'PnL = bruto − comisión',
              'tamano': 'tamaño = balance × riesgo ÷ distancia al SL (tope: balance)', 'solape': 'nunca dos posiciones a la vez'}
    for k, label in labels.items():
        check(label, bad[k] == 0, f"{bad[k]} de {len(tr)} no cumplen" if bad[k] else '')
    sl_hits = [t for t in tr if t['exit_reason'] == 'stop_loss']
    check('SL: sale exactamente en el nivel del SL', all(rel(t['exit_level'], t['sl']) < EPS for t in sl_hits), f"{len(sl_hits)} salidas por SL")
    tp_hits = [t for t in tr if t['exit_reason'] == 'take_profit_1']
    check('TP: sale exactamente en el nivel del TP', all(rel(t['exit_level'], t['tp1']) < EPS for t in tp_hits), f"{len(tp_hits)} salidas por TP")
    capped = sum(1 for t in tr if rel(t['size'] * t['entry_price'], 10000.0) < 0.5)  # aprox: tamaño topado
    losses = [t for t in sl_hits if t['gross_pnl'] < 0]
    if losses:
        b, ok = 10000.0, 0
        balances = {}
        for t in tr:
            balances[id(t)] = b
            b += t['pnl']
        for t in losses:
            risk = balances[id(t)] * p['risk_per_trade_pct'] / 100
            full = abs(t['entry_price'] - t['sl']) * t['size']
            ok += full <= risk * (1 + 1e-4) + 1e-6  # tolerancia: redondeo del tamaño a 6 decimales
        check('riesgo: la pérdida bruta al SL (sin slippage) nunca supera el riesgo/trade', ok == len(losses), f"{ok}/{len(losses)}")
    return tr


def test_slippage_commission_zero(r: Runner):
    _, tr, _ = r.run(slippage_pct=0.0, commission_pct=0.0)
    print(f"\n[2] Slippage 0 y comisión 0: {len(tr)} operaciones")
    check('slippage 0: entrada = open exacto', all(rel(t['entry_price'], r.open_by_time[ts(t['entry_time'])]) < EPS for t in tr))
    check('comisión 0: ninguna operación paga comisión', all(t['commission'] == 0 for t in tr))


def test_regime(r: Runner):
    s, tr, p = r.run(regime_filter=True)
    allowed = set(getattr(s, 'allowed_regimes', []))
    print(f"\n[3] Régimen ON (permitidos {sorted(allowed)}): {len(tr)} operaciones")
    check('régimen: toda operación abre en un régimen permitido', all(t['regime'] in allowed for t in tr),
          str({t['regime'] for t in tr} - allowed))
    regimes = compute_regimes(r.df, 25.0, 20.0, 'NO_OPERAR')
    blocked = int((regimes == 'NO_OPERAR').sum())
    _, tr2, _ = r.run(regime_filter=True, regime_ambiguous_as='NO_OPERAR')
    check('caso ambiguo "No operar": ninguna operación en velas ambiguas', all(t['regime'] != 'NO_OPERAR' for t in tr2),
          f"{blocked} velas ambiguas; {len(tr2)} operaciones")
    if {'TRENDING', 'RANGING', 'VOLATILE'} <= allowed:
        print("INFO  esta estrategia permite los 3 regímenes: con ella el filtro de régimen solo actúa con 'No operar'")
    # Con regímenes restringidos (solo TENDENCIA) el filtro y sus parámetros deben notarse
    _, only_t, _ = r.run(allowed_regimes=['TRENDING'], regime_filter=True)
    check('régimen restringido a TENDENCIA: todas las operaciones en tendencia', all(t['regime'] == 'TRENDING' for t in only_t),
          f"{len(only_t)} operaciones")
    _, amb_t, _ = r.run(allowed_regimes=['TRENDING'], regime_filter=True, regime_ambiguous_as='TRENDING')
    check('caso ambiguo como Tendencia: suma las velas ambiguas', len(amb_t) > len(only_t) or blocked == 0, f"{len(amb_t)} vs {len(only_t)}")
    _, adx, _ = r.run(allowed_regimes=['TRENDING'], regime_filter=True, regime_adx_trending=40.0)
    check('umbral ADX tendencia más alto: menos operaciones', len(adx) < len(only_t), f"{len(adx)} vs {len(only_t)}")
    _, off, _ = r.run(allowed_regimes=['TRENDING'], regime_filter=False)
    check('régimen OFF: opera en cualquier régimen', len({t['regime'] for t in off}) > 1, str({t['regime'] for t in off}))


def test_volume(r: Runner):
    period, mult = 20, 1.5
    _, tr, _ = r.run(volume_filter=True, volume_filter_period=period, volume_filter_mult=mult)
    vol = r.df['volume'].astype(float)
    ma = vol.rolling(period).mean()
    bad = 0
    for t in tr:
        j = r.index_by_time[ts(t['entry_time'])] - 1   # vela de la señal
        bad += not (vol.iloc[j] >= ma.iloc[j] * mult)
    print(f"\n[4] Volumen ON ({period}, ×{mult}): {len(tr)} operaciones")
    check('volumen: la vela de la señal tiene volumen ≥ promedio × multiplicador', bad == 0, f"{bad} de {len(tr)} no cumplen")
    _, base, _ = r.run()
    check('volumen: filtra (menos operaciones que sin filtro)', len(tr) < len(base), f"{len(tr)} vs {len(base)}")


def test_macro(r: Runner):
    _, on, _ = r.run(macro_trend_filter=True)
    _, off, _ = r.run(macro_trend_filter=False)
    print(f"\n[5] Tendencia macro H4: ON {len(on)} vs OFF {len(off)} operaciones")
    same = [t['entry_time'] for t in on] == [t['entry_time'] for t in off]
    check('tendencia macro H4: activarla cambia las operaciones', not same,
          'mismas operaciones con y sin filtro: no tiene efecto' if same else '')
    if r.h4 is None or not on:
        return
    # Regla: tendencia de la última vela H4 YA CERRADA al cierre de la vela de la señal (EMA50 de cierres H4)
    h4 = r.h4[['time', 'close']].copy()
    h4['time'] = pd.to_datetime(h4['time'], utc=True)
    h4 = h4.sort_values('time').reset_index(drop=True)
    ema = h4['close'].astype(float).ewm(span=50, adjust=False).mean()
    trend = np.array(np.sign(h4['close'].astype(float) - ema), dtype=int)
    trend[:49] = 0
    ready = (h4['time'] + pd.Timedelta(hours=4)).dt.tz_convert(None).to_numpy()
    bad = 0
    for t in on:
        signal_close = ts(t['entry_time'])           # la vela de la señal cierra cuando abre la de entrada
        k = np.searchsorted(ready, signal_close.tz_convert(None).to_datetime64(), side='right') - 1
        tr = trend[k] if k >= 0 else 0
        bad += not ((t['side'] == 'long' and tr == 1) or (t['side'] == 'short' and tr == -1))
    check('tendencia macro H4: largos solo con H4 alcista y cortos solo con H4 bajista (vela H4 ya cerrada)', bad == 0,
          f"{bad} de {len(on)} no cumplen")



def test_duration(r: Runner):
    n = 12
    _, tr, _ = r.run(max_duration=n)
    print(f"\n[6] Duración máxima {n} velas: {len(tr)} operaciones · salidas {r.reasons(tr)}")
    check(f'duración: ninguna operación supera {n} velas', all(t['bars_open'] <= n for t in tr), str(max((t['bars_open'] for t in tr), default=0)))
    te = [t for t in tr if t['exit_reason'] == 'time_exit']
    check('duración: el cierre por tiempo ocurre exactamente en la vela N', bool(te) and all(t['bars_open'] == n for t in te), f"{len(te)} cierres por tiempo")
    _, tp, _ = r.run(max_duration=n, max_duration_profit=True)
    rs = r.reasons(tp)
    print(f"[7] Duración {n} + solo en ganancia: {len(tp)} operaciones · salidas {rs}")
    check('solo en ganancia: no hay cierres por tiempo en pérdida', 'time_exit' not in rs, str(rs.get('time_exit', 0)))
    tep = [t for t in tp if t['exit_reason'] == 'time_exit_profit']
    check('solo en ganancia: cada cierre por tiempo cierra en ganancia (cierre de vela vs entrada)',
          all((t['exit_level'] > t['entry_price']) if t['side'] == 'long' else (t['exit_level'] < t['entry_price']) for t in tep),
          f"{len(tep)} cierres")
    check('solo en ganancia: las perdedoras siguen abiertas más allá de N', any(t['bars_open'] > n for t in tp))


def test_breakeven(r: Runner):
    be = 0.5
    _, tr, _ = r.run(be_pct=be)
    act = [t for t in tr if t['be_activated']]
    stop_be = [t for t in act if t['exit_reason'] == 'stop_loss']
    print(f"\n[8] Break-even {be}%: {len(act)} activados de {len(tr)} · {len(stop_be)} cerrados en BE")
    check('break-even: se activa en algunas operaciones', len(act) > 0)
    check('break-even: tras activarse, el SL queda en el precio de entrada', all(rel(t['exit_level'], t['entry_price']) < EPS for t in stop_be),
          f"{len(stop_be)} salidas")
    _, big, _ = r.run(be_pct=4.0, tp_pct=3.0)
    check('break-even ≥ TP: nunca se activa (por eso el aviso en la UI)', not any(t['be_activated'] for t in big))


def test_trailing(r: Runner):
    dist, act = 1.0, 0.45
    _, tr, _ = r.run(trailing_mode='fixed', trailing_distance_pct=dist, trailing_activation_buffer_pct=act, tp_pct=6.0)
    tt = [t for t in tr if t['exit_reason'] == 'trailing_stop']
    print(f"\n[9] Trailing fijo {dist}% (activación {act}%): {len(tt)} salidas por trailing de {len(tr)}")
    check('trailing fijo: hay salidas por trailing', len(tt) > 0)
    lim = lambda t: t['entry_price'] * (1 + (act - dist) / 100) if t['side'] == 'long' else t['entry_price'] * (1 - (act - dist) / 100)
    check('trailing fijo: el SL nunca se movió antes de la activación (SL ≥ entrada × (1 + act − dist))',
          all((t['exit_level'] >= lim(t) * (1 - 1e-9)) if t['side'] == 'long' else (t['exit_level'] <= lim(t) * (1 + 1e-9)) for t in tt))
    _, tr2, _ = r.run(trailing_mode='fixed', trailing_distance_pct=dist, trailing_activation_buffer_pct=2.0, tp_pct=6.0)
    check('trailing fijo: la activación cambia el resultado', [t['exit_time'] for t in tr2] != [t['exit_time'] for t in tr])

    _, ta, _ = r.run(trailing_mode='atr', trailing_atr_mult=2.0, trailing_activation_buffer_pct=0.3, tp_pct=6.0)
    print(f"[10] Trailing ATR ×2: {r.reasons(ta)}")
    check('trailing ATR: hay salidas por trailing', any(t['exit_reason'] == 'trailing_stop' for t in ta))
    _, tb, _ = r.run(trailing_mode='atr', trailing_atr_mult=4.0, trailing_activation_buffer_pct=0.3, tp_pct=6.0)
    check('trailing ATR: el multiplicador cambia el resultado', [t['exit_time'] for t in ta] != [t['exit_time'] for t in tb])
    # Regla directa: con ganancia 0.6% y activación 0.3%, el trailing ATR debe mover el SL
    moved = calculate_trailing_sl_standalone('atr', 1.0, [], 100.0, 'long', 100.6, 98.5, activation_buffer_pct=0.3,
                                             current_atr=0.1, atr_mult=2.0)
    check('trailing ATR: respeta la "Activación trailing %" de la UI (0.3% → mueve con 0.6% de ganancia)', moved > 98.5,
          f"SL quedó en {moved}: hay un mínimo de activación fijo en el código" if moved <= 98.5 else '')


def test_opposite(r: Runner):
    _, on, _ = r.run(close_on_opposite=True)
    _, off, _ = r.run(close_on_opposite=False)
    print(f"\n[11] Señal opuesta: ON {r.reasons(on).get('opposite_signal', 0)} cierres · OFF {r.reasons(off).get('opposite_signal', 0)}")
    check('señal opuesta ON: hay cierres por señal opuesta', r.reasons(on).get('opposite_signal', 0) > 0)
    check('señal opuesta OFF: ningún cierre por señal opuesta', r.reasons(off).get('opposite_signal', 0) == 0)
    rev = sum(1 for a, b in zip(on, on[1:]) if a['exit_reason'] == 'opposite_signal' and ts(b['entry_time']) == ts(a['exit_time'])
              and b['side'] != a['side'])
    check('señal opuesta: cierra y abre la contraria en la misma vela (si pasa filtros)', rev > 0, f"{rev} reversiones")


def test_risk(r: Runner):
    _, r1, _ = r.run(risk_per_trade_pct=0.5)
    _, r2, _ = r.run(risk_per_trade_pct=1.0)
    print(f"\n[12] Riesgo 0.5% vs 1.0%")
    first = [(a, b) for a, b in zip(r1, r2) if a['entry_time'] == b['entry_time']][:1]
    check('riesgo: duplicar el riesgo duplica el tamaño de la primera operación (sin tope)',
          bool(first) and rel(first[0][1]['size'], 2 * first[0][0]['size']) < 1e-4 or
          (bool(first) and first[0][1]['size'] * first[0][1]['entry_price'] >= 10000 * 0.999),
          f"{first[0][0]['size']} → {first[0][1]['size']}" if first else 'sin operaciones comparables')


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--symbol', default='BTCUSDT')
    ap.add_argument('--interval', default='60')
    ap.add_argument('--months', type=int, default=6)
    ap.add_argument('--strategy', default='VWAP Reversión')
    ap.add_argument('--synthetic', metavar='CODIGO_PY')
    a = ap.parse_args()
    if a.synthetic:
        code, cfg = Path(a.synthetic).read_text(encoding='utf-8'), {}
        df, mdf, start, h4 = synthetic_data(a.months)
        print(f"Datos SINTÉTICOS · {len(df)} velas H1 · {len(mdf)} velas 1m")
        suites = [('sintética', code, cfg)]
    else:
        names = await strategy_names() if a.strategy == 'all' else [a.strategy]
        suites = [(n, *(await strategy_code_from_db(n))) for n in names]
        df, mdf, start, h4 = await real_data(a.symbol, a.interval, a.months)
        print(f"{a.symbol} {a.interval} · {a.months} meses · {len(df)} velas · {len(mdf)} velas 1m")
    for name, code, cfg in suites:
        print(f"\n══════════ Estrategia: {name} ══════════")
        r = Runner(code, cfg, a.symbol, a.interval, df, mdf, start, h4)
        for t in (test_costs_and_fills, test_slippage_commission_zero, test_regime, test_volume, test_macro,
                  test_duration, test_breakeven, test_trailing, test_opposite, test_risk):
            try:
                t(r)
            except Exception as e:  # una prueba rota no oculta las demás
                check(f'{t.__name__} se ejecutó', False, f"{type(e).__name__}: {e}")
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

"""
Búsqueda de configuraciones con validación fuera de muestra (anti-sobreajuste).

Para cada estrategia × intervalo × símbolo prueba combinaciones de SL/TP, break-even, trailing, filtros y duración
con el MOTOR REAL y los MISMOS datos que un backtest de la pantalla (api.v1.backtest.load_backtest_data: fuente,
calentamiento, velas de 1m, tendencia macro H4) y el MISMO periodo que la pantalla ("24 meses" = 24 meses
calendario completos hasta el último mes cerrado). El periodo se separa en dos tramos:
  · EN MUESTRA (primeros 2/3): el único que se usa para ELEGIR configuraciones.
  · FUERA DE MUESTRA (último 1/3): nunca se usa para elegir; solo para comprobar que lo elegido sigue funcionando.
"ROBUSTA" = gana en muestra en la mayoría de los símbolos Y también fuera de muestra.
"VALIDADA" = robusta que además gana en monedas que la búsqueda nunca vio.

Modos (desde python-engine/):
  venv/bin/python cli/param_search.py                       # consola: 5 estrategias · 15m/H1/H4 · BTC ETH SOL LINK
  venv/bin/python cli/param_search.py --strategies "VWAP Reversión" --intervals 60,120 --samples 40
  venv/bin/python cli/param_search.py --validar /tmp/x_robustas.json --symbols otros
  venv/bin/python cli/param_search.py --run-id N            # búsqueda del módulo Estrategias (tabla param_search_runs)
El modo --run-id corre en 1 proceso con prioridad mínima, escribe progreso/latido en la fila y respeta la cancelación.
"""
import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import random
import resource
import sys
import time
import traceback
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import (  # noqa: E402
    BacktestData, BacktestRequest, build_monthly_breakdown, load_backtest_data, load_strategy, parse_range,
)
from backtesting.engine import BacktestEngine  # noqa: E402

INITIAL = 10000.0
RISK_PCT = 1.0
COSTS = dict(commission_pct=0.055, slippage_pct=0.05)  # costos honestos, los mismos de la UI
# Lo que la pantalla de Backtesting envía siempre (sin protección por volatilidad): mismos parámetros "enviados"
UI_FIXED = dict(volatility_protection_mode=None, volatility_atr_multiplier=2.5, volatility_widen_pct=1.0)
ALLOWED_INTERVALS = ('15', '60', '120', '240', 'D')
MAX_VALIDATE = 5          # robustas que se validan en otras monedas (las de mayor retorno)
MIN_TRADES = 30           # operaciones mínimas (24 meses) para que una moneda cuente como sobreviviente
NEAR_MAX = 5              # si nada sobrevive: cuántas "más cercanas" se muestran
HEARTBEAT_EVERY = 3.0     # segundos entre escrituras de progreso / lectura de cancelación

# Espacio de búsqueda (todos son campos de la UI de Backtesting)
SLTP = [(1.0, 2.0), (1.5, 3.0), (2.0, 4.0), (1.5, 4.5), (2.5, 5.0), (3.0, 6.0)]
TRAILING = [None, ('atr', 2.0), ('atr', 3.0), ('fixed', 1.5)]
BASE_KEYS = ('sl_pct', 'tp_pct', 'be_pct', 'trailing_mode', 'trailing_atr_mult', 'trailing_distance_pct',
             'trailing_activation_buffer_pct', 'regime_filter', 'macro_trend_filter', 'volume_filter',
             'volume_filter_period', 'volume_filter_mult', 'max_duration', 'max_duration_profit', 'close_on_opposite',
             'regime_adx_trending', 'regime_adx_ranging', 'regime_ambiguous_as')

DATA: dict = {}           # (símbolo, intervalo) -> BacktestData | None
SIGNAL_CACHE: dict = {}


class Cancelled(Exception):
    pass


def sample_configs(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    seen, out = set(), []
    while len(out) < n and len(seen) < 5000:
        sl, tp = rng.choice(SLTP)
        tr = rng.choice(TRAILING)
        cfg = dict(sl_pct=sl, tp_pct=tp,
                   be_pct=rng.choice([99.0, round(tp * 0.5, 2)]),
                   trailing_mode=tr[0] if tr else None,
                   trailing_atr_mult=tr[1] if tr and tr[0] == 'atr' else 2.0,
                   trailing_distance_pct=tr[1] if tr and tr[0] == 'fixed' else 1.0,
                   trailing_activation_buffer_pct=rng.choice([0.5, 1.0]) if tr else 0.0,
                   regime_filter=rng.random() < 0.5, macro_trend_filter=rng.random() < 0.5,
                   volume_filter=rng.random() < 0.4, volume_filter_period=20, volume_filter_mult=1.2,
                   max_duration=rng.choice([0, 24, 48]), max_duration_profit=False,
                   close_on_opposite=rng.random() < 0.3,
                   regime_adx_trending=25.0, regime_adx_ranging=20.0, regime_ambiguous_as='RANGING')
        key = json.dumps(cfg, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(cfg)
    return out


def ui_period(months: int, today: date | None = None) -> tuple[datetime, datetime]:
    """
    El MISMO periodo que BacktestingController::executeAjax: termina el último día del mes anterior y empieza el
    día 1 de (months - 1) meses antes. Devuelve [inicio, fin) en UTC vía parse_range (igual que /backtest/run).
    """
    today = today or datetime.now(timezone.utc).date()
    end_d = today.replace(day=1) - timedelta(days=1)
    m = end_d.year * 12 + (end_d.month - 1) - (months - 1)
    start_d = date(m // 12, m % 12 + 1, 1)
    return parse_range(start_d.isoformat(), end_d.isoformat())


def dsn() -> str:
    return (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
            f"{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")


def low_priority():
    """Prioridad mínima de CPU y disco: la búsqueda nunca compite con los ticks de paper/real."""
    try:
        os.nice(19 - os.nice(0))
    except Exception:
        pass
    try:
        import subprocess
        subprocess.run(['ionice', '-c3', '-p', str(os.getpid())], check=False, capture_output=True, timeout=5)
    except Exception:
        pass


# ─────────────────────────────── datos ───────────────────────────────

async def load_data(symbols, intervals, start, end, log=print, close=True):
    """
    Carga con el loader de /backtest/run (macro H4 incluida: la usan las configuraciones con ese filtro).
    close=True cierra los pools al terminar (modos de consola: un asyncio.run por carga).
    """
    from db import close_pools, get_pool
    pool = await get_pool('backtest')
    try:
        await _load(pool, symbols, intervals, start, end, log)
    finally:
        if close:
            await close_pools()


async def _load(pool, symbols, intervals, start, end, log):
    for sym in symbols:
        parts = []
        minute_cache: dict = {}   # velas de 1m de la moneda: una carga y un solo DataFrame para todas las temporalidades
        for iv in intervals:
            try:
                DATA[(sym, iv)] = await load_backtest_data(pool, sym, iv, start, end, macro=True, minute_cache=minute_cache)
                d = DATA[(sym, iv)]
                parts.append(f"{iv}={len(d.df)}{'' if d.minute_df is not None or iv == '15' else ' (sin 1m)'}")
            except ValueError:
                DATA[(sym, iv)] = None
                parts.append(f"{iv}=sin datos")
        log(f"  {sym}: " + " · ".join(parts))


def drop_data(symbols):
    for key in [k for k in DATA if k[0] in symbols]:
        DATA.pop(key, None)
    for key in [k for k in SIGNAL_CACHE if k[1] in symbols]:
        SIGNAL_CACHE.pop(key, None)


def synthetic_data(symbols, intervals, months):
    rng = np.random.default_rng(3)
    for k, sym in enumerate(symbols):
        n = (months * 30 + 120) * 1440
        vol = np.repeat(rng.choice([0.0004, 0.0009, 0.0018], size=n // 1440 + 1), 1440)[:n]
        close = 100 * (k + 1) * np.exp(np.cumsum(rng.normal(0, 1, n) * vol))
        open_ = np.concatenate([[close[0]], close[:-1]])
        wick = np.abs(rng.normal(0, 1, n)) * vol * close * 0.6
        t = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq='1min')
        m = pd.DataFrame({'time': t, 'open': open_, 'high': np.maximum(open_, close) + wick,
                          'low': np.minimum(open_, close) - wick, 'close': close, 'volume': rng.gamma(2.0, 50, n)})

        def rs(iv):
            rule = '1D' if iv == 'D' else f'{iv}min'
            return (m.set_index('time').resample(rule, label='left', closed='left')
                    .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
                    .dropna().reset_index())
        start = t[0] + timedelta(days=120)
        h4 = rs('240')
        for iv in intervals:
            DATA[(sym, iv)] = BacktestData(df=rs(iv), macro_df=h4, minute_df=m[m['time'] >= start].reset_index(drop=True),
                                           warnings=[], coverage={})
    return start.to_pydatetime(), t[-1].to_pydatetime()


async def strategies_from_db(names=None, strategy_id=None):
    import asyncpg
    c = await asyncpg.connect(dsn())
    try:
        rows = await c.fetch("SELECT id, name, code, config FROM strategies ORDER BY id")
    finally:
        await c.close()
    out = []
    for r in rows:
        if (names and r['name'] not in names) or (strategy_id is not None and r['id'] != strategy_id):
            continue
        cfg = json.loads(r['config']) if isinstance(r['config'], str) else (r['config'] or {})
        out.append((r['name'], r['code'], cfg))
    return out


async def other_symbols(exclude: set) -> list[str]:
    import asyncpg
    c = await asyncpg.connect(dsn())
    try:
        rows = await c.fetch("SELECT DISTINCT symbol FROM collector_configs WHERE broker = 'bybit' AND active ORDER BY symbol")
    finally:
        await c.close()
    return [r['symbol'] for r in rows if r['symbol'] not in exclude]


# ─────────────────────────────── evaluación ───────────────────────────────

def naive_utc(x) -> pd.Timestamp:
    ts = pd.Timestamp(x)
    return ts.tz_convert(None) if ts.tzinfo is not None else ts


def pf(gp, gl):
    return round(gp / gl, 3) if gl > 0 else (99.0 if gp > 0 else 0.0)


def finite(x, nd=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


def month_keys(start, end) -> list[str]:
    """Meses calendario del rango [start, end): los mismos que build_monthly_breakdown (incluye meses sin operaciones)."""
    return [str(p) for p in pd.period_range(naive_utc(start), naive_utc(end) - timedelta(seconds=1), freq='M')]


def segment_stats(trades, lo, hi):
    pnl = [t['pnl'] for t in trades if lo <= naive_utc(t['entry_time']) < hi]
    gp = sum(p for p in pnl if p > 0)
    gl = -sum(p for p in pnl if p <= 0)
    eq = np.cumsum([0.0] + pnl) + INITIAL
    peak = np.maximum.accumulate(eq)
    dd = float(((peak - eq) / peak).max() * 100) if len(eq) else 0.0
    return dict(n=len(pnl), gp=float(gp), gl=float(gl), pnl=float(sum(pnl)), dd=float(dd))


def evaluate(name, code, scfg, sym, iv, configs, start, split, end, tick=None):
    """
    Un (estrategia, intervalo, símbolo) con varias configuraciones. Por configuración devuelve los tramos en/fuera
    de muestra y las métricas del periodo completo tal como las calcula /backtest/run (las de las estrellas).
    Las señales se calculan una vez por combinación de filtros que las afectan (volumen, macro).
    """
    data = DATA.get((sym, iv))
    if data is None:
        return None
    lo = naive_utc(start)
    out = []
    for i, cfg in enumerate(configs):
        req = BacktestRequest(strategy=name, strategy_code=code, strategy_config=scfg, symbol=sym, interval=iv,
                              initial_balance=INITIAL, risk_per_trade_pct=RISK_PCT, **COSTS, **UI_FIXED, **cfg)
        s = load_strategy(req)
        s.slippage_pct = COSTS['slippage_pct']
        if cfg['macro_trend_filter']:
            s.macro_df = data.macro_df
        key = (name, sym, iv, cfg['volume_filter'], cfg['macro_trend_filter'])
        if key not in SIGNAL_CACHE:
            SIGNAL_CACHE[key] = s.compute_signals(data.df)
        cached = SIGNAL_CACHE[key]
        s.compute_signals = lambda _df, c=cached: c.copy()   # mismas señales: solo cambian SL/TP/gestión
        res = BacktestEngine(strategy=s, df=data.df, initial_balance=INITIAL, risk_per_trade_pct=RISK_PCT,
                             minute_df=data.minute_df, trade_from=start, funding=data.funding).run()
        trades, m = res['trades'], res['metrics']
        by_month = {x['month']: x['total_pnl_pct'] for x in build_monthly_breakdown(trades, INITIAL, start, end)}
        full = dict(n=int(m['total_trades']), wins=int(m['winning_trades']), wr=finite(m['win_rate'], 2),
                    sharpe=finite(m['sharpe_ratio'], 2), pf=finite(m['profit_factor'], 2),
                    ret=finite(m['total_return_pct'], 2), dd=finite(m['max_drawdown_pct'], 2),
                    gp=finite(m.get('gross_profit', 0.0)), gl=finite(m.get('gross_loss', 0.0)),
                    m=[finite(by_month.get(k, 0.0)) for k in month_keys(start, end)], m1=data.minute_df is not None)
        out.append((i, segment_stats(trades, lo, split), segment_stats(trades, split, end), full))
        if tick:
            tick(f"{sym} · {iv}")
    return out


def aggregate(by_sym: dict, symbols: list) -> dict | None:
    """Tramos en/fuera de muestra sumados sobre los símbolos de búsqueda + criterios candidata/robusta."""
    if len(by_sym) < len(symbols):
        return None
    need = math.ceil(len(symbols) * 0.75)
    agg = {}
    for part, k in (('is', 0), ('oos', 1)):
        st = [v[k] for v in by_sym.values()]
        agg[part] = dict(n=sum(x['n'] for x in st), pf=pf(sum(x['gp'] for x in st), sum(x['gl'] for x in st)),
                         ret=round(sum(x['pnl'] for x in st) / (INITIAL * len(st)) * 100, 2),
                         pos=int(sum(x['pnl'] > 0 for x in st)), dd=round(max(x['dd'] for x in st), 1))
    cand = (agg['is']['pf'] >= 1.15 and agg['is']['pos'] >= need and agg['is']['n'] >= 15 * len(symbols)
            and agg['is']['dd'] <= 25)
    robust = cand and agg['oos']['pf'] >= 1.1 and agg['oos']['pos'] >= need and agg['oos']['n'] >= 6 * len(symbols)
    return dict(**agg, candidata=bool(cand), robusta=bool(robust))


def totals(symbols_full: dict) -> tuple[float, float]:
    """Retorno total y consistencia como la pantalla: suma mensual de todas las monedas; % de meses > 0."""
    months = None
    for f in symbols_full.values():
        arr = np.array([x or 0.0 for x in f['m']], dtype=float)
        months = arr if months is None else months + arr
    if months is None or not len(months):
        return 0.0, 0.0
    return round(float(months.sum()), 2), round(float((months > 0).sum() / len(months) * 100), 1)


# ─────────────────────────────── modo --run-id (módulo Estrategias) ───────────────────────────────

class RunReporter:
    """Progreso, latido y cancelación sobre la fila de param_search_runs (escrituras limitadas a 1 cada 3 s)."""

    def __init__(self, conn, run_id: int, loop):
        self.conn, self.run_id, self.loop = conn, run_id, loop
        self.done = self.total = 0
        self.phase, self.note = None, None
        self._last = 0.0

    def q(self, sql, *args):
        return self.loop.run_until_complete(self.conn.fetchrow(sql, *args))

    def set(self, force=False, **cols):
        for k, v in cols.items():
            setattr(self, k, v)
        now = time.time()
        if not force and now - self._last < HEARTBEAT_EVERY:
            return
        self._last = now
        row = self.q("""UPDATE param_search_runs SET phase = $2, progress_done = $3, progress_total = $4,
                        progress_note = $5, heartbeat_at = now(), updated_at = now()
                        WHERE id = $1 RETURNING cancel_requested""",
                     self.run_id, self.phase, self.done, self.total, self.note)
        if row is None or row['cancel_requested']:
            raise Cancelled()

    def tick(self, note):
        self.set(done=self.done + 1, note=note)


def survivor_row(iv: str, i: int, cfg: dict, by_sym: dict) -> dict:
    """
    Regla del usuario: con las monedas de la búsqueda se mira el retorno de cada una (periodo completo);
    se descartan las que pierden o tienen menos de MIN_TRADES operaciones; si no queda ninguna, la configuración
    se descarta. Los tramos en/fuera de muestra se informan (solo las sobrevivientes), no filtran.
    """
    symbols, survivors = {}, []
    for s, (is_, oos, full) in by_sym.items():
        why = None
        if full['n'] == 0:
            why = 'sin operaciones'
        elif (full['ret'] or 0) <= 0:
            why = f"pierde ({full['ret']}%)"
        elif full['n'] < MIN_TRADES:
            why = f"solo {full['n']} operaciones (< {MIN_TRADES})"
        symbols[s] = dict(role='survivor' if why is None else 'discarded', why=why, **full)
        if why is None:
            survivors.append(s)
    seg = {}
    for part, k in (('is', 0), ('oos', 1)):
        st = [by_sym[s][k] for s in survivors]
        gp, gl = sum(x['gp'] for x in st), sum(x['gl'] for x in st)
        seg[part] = dict(n=sum(x['n'] for x in st), pf=pf(gp, gl),
                         ret=round(sum(x['pnl'] for x in st) / (INITIAL * max(1, len(st))) * 100, 2),
                         pos=int(sum(x['pnl'] > 0 for x in st)))
    row = dict(id=f"{iv}-{i}", interval=iv, cfg={k: cfg[k] for k in BASE_KEYS}, survivors=sorted(survivors),
               discarded=sorted(s for s in symbols if s not in survivors), symbols=symbols,
               **{'is': seg['is'], 'oos': seg['oos']}, oos_ok=seg['oos']['ret'] > 0)
    row['ret_total'], row['consist'] = totals({s: symbols[s] for s in survivors})
    return row


def near_misses(per_cfg: dict, configs: dict, k: int = NEAR_MAX) -> list:
    """Si nada sobrevive: las k configuraciones que más se acercaron y por qué quedaron fuera."""
    out = []
    for (iv, i), by_sym in per_cfg.items():
        best_s, best = max(by_sym.items(), key=lambda kv: kv[1][2]['ret'] or -1e9)
        full = best[2]
        if (full['ret'] or 0) > 0:
            why = f"{best_s} gana {full['ret']}% pero con solo {full['n']} operaciones (< {MIN_TRADES})"
        else:
            why = f"pierde en todas las monedas (la mejor: {best_s} {full['ret']}%)"
        out.append(dict(id=f"{iv}-{i}", interval=iv, cfg={kk: configs[iv][i][kk] for kk in BASE_KEYS},
                        best_symbol=best_s, best_ret=full['ret'], best_n=full['n'], why=why,
                        rets={s: v[2]['ret'] for s, v in by_sym.items()}))
    return sorted(out, key=lambda r: -(r['best_ret'] or -1e9))[:k]


def run_mode(run_id: int, max_minutes: float) -> int:
    import asyncpg
    low_priority()
    t0 = time.time()
    loop = asyncio.new_event_loop()
    conn = loop.run_until_complete(asyncpg.connect(dsn()))
    rep = RunReporter(conn, run_id, loop)

    def finish(status, results=None, error=None):
        rep.q("""UPDATE param_search_runs SET status = $2, results = $3::jsonb, error = $4, finished_at = now(),
                 heartbeat_at = now(), updated_at = now(), progress_done = $5, progress_total = $6, phase = $7,
                 progress_note = $8 WHERE id = $1 RETURNING id""",
              run_id, status, json.dumps(results, ensure_ascii=False) if results is not None else None, error,
              rep.done, rep.total, rep.phase, rep.note)

    row = rep.q("""UPDATE param_search_runs SET status = 'running', pid = $2, started_at = now(), heartbeat_at = now(),
                   updated_at = now() WHERE id = $1 AND status = 'queued' RETURNING *""", run_id, os.getpid())
    if row is None:
        print(f"La búsqueda #{run_id} no existe o ya no está en cola.", file=sys.stderr)
        return 2
    try:
        intervals = [str(x) for x in json.loads(row['intervals'])]
        search = [str(x) for x in json.loads(row['search_symbols'])]
        bad = [iv for iv in intervals if iv not in ALLOWED_INTERVALS]
        if bad or not intervals or not search:
            raise ValueError(f"Parámetros inválidos (intervalos {intervals}, monedas {search}).")
        strat = loop.run_until_complete(strategies_from_db(strategy_id=row['strategy_id']))
        if not strat:
            raise ValueError("La estrategia ya no existe.")
        name, code, scfg = strat[0]
        start, end = ui_period(int(row['months']))
        split = naive_utc(start) + (naive_utc(end) - naive_utc(start)) * 2 / 3
        start_n, end_n = naive_utc(start), naive_utc(end)
        samples = int(row['samples'])
        rep.q("""UPDATE param_search_runs SET strategy_code_md5 = $2, period_start = $3, split_date = $4,
                 period_end = $5 WHERE id = $1 RETURNING id""",
              run_id, hashlib.md5((code or '').encode()).hexdigest(), start_n.date(), split.date(), end_n.date())

        deadline = t0 + max_minutes * 60
        configs = {iv: sample_configs(samples, int(row['seed']) + zlib.crc32(f'{name}|{iv}'.encode()) % 1000)
                   for iv in intervals}
        per_cfg: dict = {}          # (iv, i) -> {símbolo: (is, oos, full)}
        rep.set(force=True, phase='busqueda', done=0, total=len(intervals) * len(search) * samples,
                note='Probando combinaciones')

        def tick(note):
            if time.time() > deadline:
                raise TimeoutError(f"superó el tiempo máximo ({max_minutes:.0f} min)")
            rep.tick(note)

        # Una moneda a la vez en memoria (velas de 1m de 24 meses ≈ 300 MB por moneda): sin importar cuántas se elijan
        for sym in search:
            rep.set(force=True, note=f"{sym}: cargando velas")
            loop.run_until_complete(load_data([sym], intervals, start, end, log=lambda *_: None, close=False))
            for iv in intervals:
                out = evaluate(name, code, scfg, sym, iv, configs[iv], start, split, end_n, tick=tick)
                if out is None:
                    rep.set(done=rep.done + samples, note=f"{sym} · {iv}: sin datos")
                    continue
                for i, is_, oos, full in out:
                    per_cfg.setdefault((iv, i), {})[sym] = (is_, oos, full)
            drop_data([sym])

        rows = []
        for (iv, i), by_sym in per_cfg.items():
            r = survivor_row(iv, i, configs[iv][i], by_sym)
            if r['survivors']:
                rows.append(r)
        rows.sort(key=lambda r: (-r['ret_total'], -r['consist']))
        near = [] if rows else near_misses(per_cfg, configs)

        results = dict(version=2, strategy=name, months=month_keys(start, end),
                       period=dict(start=f"{start_n:%Y-%m-%d}", split=f"{split:%Y-%m-%d}", end=f"{end_n:%Y-%m-%d}"),
                       intervals=intervals, search_symbols=search, min_trades=MIN_TRADES,
                       tested=len(per_cfg), candidates=len(rows), survivors=len(rows),
                       oos_ok=sum(1 for r in rows if r['oos_ok']),
                       costs=dict(**COSTS, risk_pct=RISK_PCT, initial_balance=INITIAL),
                       elapsed_s=round(time.time() - t0, 1),
                       peak_mem_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
                       rows=rows, near=near)
        rep.phase, rep.note, rep.done, rep.total = 'fin', 'Terminada', rep.total, rep.total   # 100 %
        finish('done', results)
        print(f"Búsqueda #{run_id}: {len(per_cfg)} configuraciones · {len(rows)} sobreviven "
              f"({results['oos_ok']} también ganan en los últimos meses) · {results['elapsed_s']} s · "
              f"{results['peak_mem_mb']} MB")
        return 0
    except Cancelled:
        finish('cancelled', error='Cancelada por el usuario.')
        print(f"Búsqueda #{run_id} cancelada.")
        return 0
    except Exception as e:
        tb = traceback.format_exc(limit=4)
        finish('failed', error=f"{type(e).__name__}: {e}\n{tb}"[-4000:])
        print(tb, file=sys.stderr)
        return 1
    finally:
        loop.run_until_complete(conn.close())
        try:
            from db import close_pools
            loop.run_until_complete(close_pools())
        except Exception:
            pass
        loop.close()


# ─────────────────────────────── modos de consola ───────────────────────────────

def validate(a) -> int:
    """Valida configuraciones ya elegidas (un *_robustas.json) en otras monedas, con el mismo periodo que la UI."""
    t0 = time.time()
    picks = json.loads(Path(a.validar).read_text(encoding='utf-8'))
    used = set(picks[0].get('simbolos', []))
    symbols = asyncio.run(other_symbols(used)) if a.symbols.strip() == 'otros' else \
        [s.strip() for s in a.symbols.split(',') if s.strip()]
    intervals = sorted({str(p['intervalo']) for p in picks})
    strategies = {n: (code, cfg) for n, code, cfg in asyncio.run(strategies_from_db({p['estrategia'] for p in picks}))}
    start, end = ui_period(a.months)
    start_n, end_n = naive_utc(start), naive_utc(end)
    split = start_n + (end_n - start_n) * 2 / 3
    print(f"Validando {len(picks)} configuraciones en {len(symbols)} monedas: {', '.join(symbols)}")
    print(f"Periodo {start_n:%Y-%m-%d} → {end_n:%Y-%m-%d} ({a.months} meses, igual que la pantalla) · cargando datos…", flush=True)
    asyncio.run(load_data(symbols, intervals, start, end))
    for k, p in enumerate(picks, 1):
        cfg = {kk: p[kk] for kk in BASE_KEYS}
        code, scfg = strategies[p['estrategia']]
        print(f"\n═══ Configuración {k}: {p['estrategia']} · {p['intervalo']} · SL {cfg['sl_pct']} / TP {cfg['tp_pct']} / BE {cfg['be_pct']} "
              f"· trailing {cfg['trailing_mode']} · régimen {cfg['regime_filter']} · macro {cfg['macro_trend_filter']} "
              f"· volumen {cfg['volume_filter']} · dur {cfg['max_duration']} · opuesta {cfg['close_on_opposite']}")
        print(f"  {'Moneda':12} {'Trades':>6} │ {'PF':>6} {'Ret':>8} {'DD':>6} │ {'PF in':>6} {'PF fuera':>8}  datos 1m")
        agg_gp = agg_gl = 0.0
        pos = valid = 0
        for sym in symbols:
            res = evaluate(p['estrategia'], code, scfg, sym, str(p['intervalo']), [cfg], start, split, end_n)
            if not res:
                print(f"  {sym:12} sin datos suficientes")
                continue
            _, is_, oos, f = res[0]
            agg_gp, agg_gl, valid = agg_gp + (f['gp'] or 0), agg_gl + (f['gl'] or 0), valid + 1
            pos += (f['ret'] or 0) > 0
            print(f"  {sym:12} {f['n']:>6} │ {f['pf'] if f['pf'] is not None else '-':>6} {f['ret']:>7}% {f['dd']:>5}% │ "
                  f"{pf(is_['gp'], is_['gl']):>6} {pf(oos['gp'], oos['gl']):>8}  {'sí' if f['m1'] else 'NO (vela grande, SL primero)'}")
        print(f"  → PF conjunto {pf(agg_gp, agg_gl)} · ganan {pos}/{valid} monedas")
    print(f"\nTiempo total: {(time.time() - t0) / 60:.1f} min")
    return 0


def console_search(a) -> int:
    symbols = [s.strip() for s in a.symbols.split(',') if s.strip()]
    intervals = [s.strip() for s in a.intervals.split(',') if s.strip()]
    names = [s.strip() for s in a.strategies.split(',') if s.strip()]
    t0 = time.time()
    if a.synthetic:
        strategies = [('sintética', Path(a.synthetic).read_text(encoding='utf-8'), {})]
        start, end = synthetic_data(symbols, intervals, a.months)
    else:
        strategies = asyncio.run(strategies_from_db(names))
        start, end = ui_period(a.months)
        print(f"Cargando datos ({a.months} meses, igual que la pantalla)…", flush=True)
        asyncio.run(load_data(symbols, intervals, start, end))
    start_n, end_n = naive_utc(start), naive_utc(end)
    split = start_n + (end_n - start_n) * 2 / 3
    print(f"En muestra: {start_n:%Y-%m-%d} → {split:%Y-%m-%d} · Fuera de muestra: {split:%Y-%m-%d} → {end_n:%Y-%m-%d}")
    configs = {(n, iv): sample_configs(a.samples, a.seed + zlib.crc32(f'{n}|{iv}'.encode()) % 1000)
               for n, _, _ in strategies for iv in intervals}
    groups = [(n, code, scfg, iv, sym) for n, code, scfg in strategies for iv in intervals for sym in symbols]
    print(f"{len(strategies)} estrategias × {len(intervals)} intervalos × {len(symbols)} símbolos × {a.samples} configs "
          f"= {len(groups) * a.samples} backtests · 1 proceso\n", flush=True)
    per_cfg = {}
    for k, (n, code, scfg, iv, sym) in enumerate(groups, 1):
        out = evaluate(n, code, scfg, sym, iv, configs[(n, iv)], start, split, end_n)
        for i, is_, oos, _ in (out or []):
            per_cfg.setdefault((n, iv, i), {})[sym] = (is_, oos)
        print(f"  [{k}/{len(groups)}] {n} · {sym} · {iv} · {(time.time() - t0) / 60:.1f} min", flush=True)

    rows = []
    for (n, iv, i), by_sym in per_cfg.items():
        agg = aggregate(by_sym, symbols)
        if agg:
            rows.append(dict(estrategia=n, intervalo=iv, cfg=configs[(n, iv)][i], **agg))
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    out_csv = Path(f'/tmp/tr2_busqueda_{stamp}.csv')
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['estrategia', 'intervalo', 'robusta', 'candidata', 'is_pf', 'is_ret', 'is_pos', 'is_n', 'is_dd',
                    'oos_pf', 'oos_ret', 'oos_pos', 'oos_n', 'oos_dd', 'config'])
        for r in sorted(rows, key=lambda r: (-r['robusta'], -r['is']['pf'])):
            w.writerow([r['estrategia'], r['intervalo'], r['robusta'], r['candidata'],
                        *(r['is'][k] for k in ('pf', 'ret', 'pos', 'n', 'dd')),
                        *(r['oos'][k] for k in ('pf', 'ret', 'pos', 'n', 'dd')), json.dumps(r['cfg'], ensure_ascii=False)])
    cands = sorted([r for r in rows if r['candidata']], key=lambda r: -r['is']['pf'])
    robust = [r for r in cands if r['robusta']]
    print(f"\nProbadas {len(rows)} configuraciones · {len(cands)} candidatas · {len(robust)} ROBUSTAS\n")
    for r in cands[:20]:
        print(f"{'✔ ' if r['robusta'] else '  '}{r['estrategia'][:24]:24} {r['intervalo']:>4} │ PF in {r['is']['pf']:>6} "
              f"{r['is']['ret']:>6}% {r['is']['pos']}/{len(symbols)} │ PF fuera {r['oos']['pf']:>6} {r['oos']['ret']:>6}% "
              f"{r['oos']['pos']}/{len(symbols)} · {r['oos']['n']} trades")
    if robust:
        out_json = Path(f'/tmp/tr2_busqueda_{stamp}_robustas.json')
        out_json.write_text(json.dumps([dict(estrategia=r['estrategia'], intervalo=r['intervalo'], simbolos=symbols,
                                             meses=a.months, **COSTS, riesgo_pct=RISK_PCT, **r['cfg'],
                                             en_muestra=dict(pf=r['is']['pf'], ret=r['is']['ret']),
                                             fuera_de_muestra=dict(pf=r['oos']['pf'], ret=r['oos']['ret']))
                                        for r in robust[:5]], ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"\nTop robustas: {out_json}")
    print(f"Todas: {out_csv}\nTiempo total: {(time.time() - t0) / 60:.1f} min")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', type=int, help='búsqueda del módulo Estrategias (fila de param_search_runs)')
    ap.add_argument('--max-minutes', type=float, default=180.0, help='tope técnico de duración del modo --run-id')
    ap.add_argument('--strategies', default='', help='nombres separados por coma (vacío = todas)')
    ap.add_argument('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT,LINKUSDT')
    ap.add_argument('--intervals', default='15,60,240')
    ap.add_argument('--months', type=int, default=24)
    ap.add_argument('--samples', type=int, default=60, help='configuraciones por estrategia e intervalo')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--synthetic', metavar='CODIGO_PY', help=argparse.SUPPRESS)  # validar la herramienta sin DB
    ap.add_argument('--validar', metavar='JSON', help='evalúa SOLO las configuraciones de ese JSON en --symbols; '
                                                      '"--symbols otros" = monedas que la búsqueda no usó')
    a = ap.parse_args()
    if a.run_id:
        return run_mode(a.run_id, a.max_minutes)
    low_priority()
    if a.validar:
        return validate(a)
    return console_search(a)


if __name__ == '__main__':
    sys.exit(main())

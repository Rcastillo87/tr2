"""
Búsqueda de configuraciones con validación fuera de muestra (anti-sobreajuste).

Para cada estrategia × intervalo × símbolo prueba combinaciones de SL/TP, break-even, trailing, filtros y duración
con el MOTOR REAL (mismo camino que /v1/backtest/run: comisión 0.055 %, slippage 0.05 % por lado, velas de 1m,
tendencia macro H4) sobre `--months` meses, y separa el periodo en dos tramos:
  · EN MUESTRA (primeros 2/3): el único que se usa para ELEGIR configuraciones.
  · FUERA DE MUESTRA (último 1/3): nunca se usa para elegir; solo para comprobar que lo elegido sigue funcionando.
Una configuración es "ROBUSTA" si gana en muestra en la mayoría de los símbolos Y también fuera de muestra.
Solo lectura: no escribe en la base de datos. Corre con prioridad baja (nice) para no afectar al resto del servidor.

Uso (desde python-engine/):
  venv/bin/python cli/param_search.py                                  # 5 estrategias · 15m/H1/H4 · BTC ETH SOL LINK · 24 meses
  venv/bin/python cli/param_search.py --strategies "VWAP Reversión" --intervals 60 --samples 120
  venv/bin/python cli/param_search.py --symbols BTCUSDT,SOLUSDT --months 18 --workers 2
"""
import argparse
import asyncio
import csv
import json
import math
import os
import random
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import WARMUP_BARS, BacktestRequest, load_strategy  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402

INITIAL = 10000.0
COSTS = dict(commission_pct=0.055, slippage_pct=0.05)  # costos honestos, los mismos de la UI

# Espacio de búsqueda (todos son campos de la UI de Backtesting)
SLTP = [(1.0, 2.0), (1.5, 3.0), (2.0, 4.0), (1.5, 4.5), (2.5, 5.0), (3.0, 6.0)]
TRAILING = [None, ('atr', 2.0), ('atr', 3.0), ('fixed', 1.5)]

DATA: dict = {}        # (símbolo, intervalo) -> df principal · (símbolo,'1') -> 1m · (símbolo,'240') -> H4
SIGNAL_CACHE: dict = {}


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


# ─────────────────────────────── datos ───────────────────────────────

async def load_all(symbols, intervals, months):
    from api.v1.backtest import interval_delta, load_ohlcv
    from collectors.broker_resolver import resolve_backtest_source
    from db import close_pools, get_pool
    end = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = (end - timedelta(days=31 * months)).replace(day=1)
    pool = await get_pool('backtest')
    try:
        for sym in symbols:
            for iv in intervals + ['240']:
                frm = start - interval_delta(iv) * (WARMUP_BARS if iv != '240' else 300)
                src = await resolve_backtest_source(pool, sym, iv, frm, end)
                DATA[(sym, iv)] = await load_ohlcv(pool, sym, iv, src.broker, frm, end) if src else None
            msrc = await resolve_backtest_source(pool, sym, '1', start, end)
            DATA[(sym, '1')] = (await load_ohlcv(pool, sym, '1', msrc.broker, start, end)
                                if msrc and msrc.covers(start, end) else None)
            print(f"  {sym}: " + " · ".join(f"{iv}={0 if DATA.get((sym, iv)) is None else len(DATA[(sym, iv)])}"
                                             for iv in intervals + ['240', '1']), flush=True)
    finally:
        await close_pools()
    return start, end


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
        for iv in intervals + ['240']:
            DATA[(sym, iv)] = (m.set_index('time').resample(f'{iv}min', label='left', closed='left')
                               .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
                               .dropna().reset_index())
        start = t[0] + timedelta(days=120)
        DATA[(sym, '1')] = m[m['time'] >= start].reset_index(drop=True)
    return start.to_pydatetime(), t[-1].to_pydatetime()


async def strategies_from_db(names):
    import asyncpg
    dsn = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
           f"{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    c = await asyncpg.connect(dsn)
    try:
        rows = await c.fetch("SELECT name, code, config FROM strategies ORDER BY id")
    finally:
        await c.close()
    out = []
    for r in rows:
        if names and r['name'] not in names:
            continue
        cfg = json.loads(r['config']) if isinstance(r['config'], str) else (r['config'] or {})
        out.append((r['name'], r['code'], cfg))
    return out


# ─────────────────────────────── evaluación ───────────────────────────────

def naive_utc(x) -> pd.Timestamp:
    ts = pd.Timestamp(x)
    return ts.tz_convert(None) if ts.tzinfo is not None else ts


def segment_stats(trades, lo, hi):
    pnl = [t['pnl'] for t in trades if lo <= naive_utc(t['entry_time']) < hi]
    gp = sum(p for p in pnl if p > 0)
    gl = -sum(p for p in pnl if p <= 0)
    eq = np.cumsum([0.0] + pnl) + INITIAL
    peak = np.maximum.accumulate(eq)
    dd = float(((peak - eq) / peak).max() * 100) if len(eq) else 0.0
    return dict(n=len(pnl), gp=float(gp), gl=float(gl), pnl=float(sum(pnl)), dd=float(dd))


def run_group(task):
    """Un (estrategia, intervalo, símbolo) con muchas configuraciones: las señales se calculan una vez por filtro."""
    try:
        os.nice(10)
    except Exception:
        pass
    name, code, scfg, sym, iv, configs, start, split, end = task
    df, mdf, h4 = DATA.get((sym, iv)), DATA.get((sym, '1')), DATA.get((sym, '240'))
    if df is None or len(df) < WARMUP_BARS + 100:
        return name, sym, iv, None
    use_minutes = mdf if iv in ('60', '240', 'D') else None  # como run_backtest: 1m solo para intervalos >= H1
    out = []
    for i, cfg in enumerate(configs):
        req = BacktestRequest(strategy=name, strategy_code=code, strategy_config=scfg, symbol=sym, interval=iv,
                              initial_balance=INITIAL, risk_per_trade_pct=1.0, **COSTS, **cfg)
        s = load_strategy(req)
        s.slippage_pct = COSTS['slippage_pct']
        s.macro_df = h4
        key = (name, sym, iv, cfg['volume_filter'], cfg['macro_trend_filter'])
        if key not in SIGNAL_CACHE:
            SIGNAL_CACHE[key] = s.compute_signals(df)
        cached = SIGNAL_CACHE[key]
        s.compute_signals = lambda _df, c=cached: c.copy()   # mismas señales: solo cambian SL/TP/gestión
        trades = BacktestEngine(strategy=s, df=df, initial_balance=INITIAL, risk_per_trade_pct=1.0,
                                minute_df=use_minutes, trade_from=start).run()['trades']
        lo = naive_utc(start)
        out.append((i, segment_stats(trades, lo, split), segment_stats(trades, split, end)))
    return name, sym, iv, out


async def other_symbols(exclude: set) -> list[str]:
    import asyncpg
    dsn = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
           f"{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    c = await asyncpg.connect(dsn)
    try:
        rows = await c.fetch("SELECT DISTINCT symbol FROM collector_configs WHERE broker = 'bybit' AND active ORDER BY symbol")
    finally:
        await c.close()
    return [r['symbol'] for r in rows if r['symbol'] not in exclude]


def validate(a) -> int:
    """Valida configuraciones ya elegidas en otras monedas (fuera de muestra por activo) y en todo el periodo."""
    t0 = time.time()
    picks = json.loads(Path(a.validar).read_text(encoding='utf-8'))
    used = set(picks[0].get('simbolos', []))
    symbols = asyncio.run(other_symbols(used)) if a.symbols.strip() == 'otros' else \
        [s.strip() for s in a.symbols.split(',') if s.strip()]
    intervals = sorted({str(p['intervalo']) for p in picks})
    strategies = {n: (code, cfg) for n, code, cfg in asyncio.run(strategies_from_db({p['estrategia'] for p in picks}))}
    print(f"Validando {len(picks)} configuraciones en {len(symbols)} monedas que la búsqueda NO usó: {', '.join(symbols)}")
    print(f"Cargando datos ({a.months} meses)…", flush=True)
    start, end = asyncio.run(load_all(symbols, intervals, a.months))
    start_n, end_n = pd.Timestamp(start).tz_convert(None), pd.Timestamp(end).tz_convert(None)
    split_n = start_n + (end_n - start_n) * 2 / 3
    keep = set(BASE_KEYS)
    for k, p in enumerate(picks, 1):
        cfg = {kk: v for kk, v in p.items() if kk in keep}
        code, scfg = strategies[p['estrategia']]
        print(f"\n═══ Configuración {k}: {p['estrategia']} · {p['intervalo']} · SL {cfg['sl_pct']} / TP {cfg['tp_pct']} / BE {cfg['be_pct']} "
              f"· trailing {cfg['trailing_mode']} · régimen {cfg['regime_filter']} · macro {cfg['macro_trend_filter']} "
              f"· volumen {cfg['volume_filter']} · dur {cfg['max_duration']} · opuesta {cfg['close_on_opposite']}")
        print(f"  {'Moneda':12} {'Trades':>6} │ {'PF total':>8} {'Ret total':>9} {'DD':>6} │ {'PF in':>6} {'PF fuera':>8}  datos 1m")
        agg_gp = agg_gl = 0.0
        pos = valid = 0
        for sym in symbols:
            res = run_group((p['estrategia'], code, scfg, sym, str(p['intervalo']), [cfg], start, split_n, end_n))[3]
            if not res:
                print(f"  {sym:12} sin datos suficientes")
                continue
            _, is_, oos = res[0]
            gp, gl = is_['gp'] + oos['gp'], is_['gl'] + oos['gl']
            ret = (is_['pnl'] + oos['pnl']) / INITIAL * 100
            agg_gp, agg_gl, valid = agg_gp + gp, agg_gl + gl, valid + 1
            pos += ret > 0
            print(f"  {sym:12} {is_['n'] + oos['n']:>6} │ {pf(gp, gl):>8} {ret:>8.2f}% {max(is_['dd'], oos['dd']):>5.1f}% │ "
                  f"{pf(is_['gp'], is_['gl']):>6} {pf(oos['gp'], oos['gl']):>8}  {'sí' if DATA.get((sym, '1')) is not None else 'NO (vela grande, SL primero)'}")
        print(f"  → PF conjunto {pf(agg_gp, agg_gl)} · ganan {pos}/{valid} monedas")
    print(f"\nTiempo total: {(time.time() - t0) / 60:.1f} min")
    return 0


BASE_KEYS = ('sl_pct', 'tp_pct', 'be_pct', 'trailing_mode', 'trailing_atr_mult', 'trailing_distance_pct',
             'trailing_activation_buffer_pct', 'regime_filter', 'macro_trend_filter', 'volume_filter',
             'volume_filter_period', 'volume_filter_mult', 'max_duration', 'max_duration_profit', 'close_on_opposite',
             'regime_adx_trending', 'regime_adx_ranging', 'regime_ambiguous_as')


def pf(gp, gl):
    return round(gp / gl, 3) if gl > 0 else (99.0 if gp > 0 else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--strategies', default='', help='nombres separados por coma (vacío = todas)')
    ap.add_argument('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT,LINKUSDT')
    ap.add_argument('--intervals', default='15,60,240')
    ap.add_argument('--months', type=int, default=24)
    ap.add_argument('--samples', type=int, default=60, help='configuraciones por estrategia e intervalo')
    ap.add_argument('--workers', type=int, default=max(1, min(3, (os.cpu_count() or 2) - 1)))
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--synthetic', metavar='CODIGO_PY', help=argparse.SUPPRESS)  # validar la herramienta sin DB
    ap.add_argument('--validar', metavar='JSON', help='evalúa SOLO las configuraciones de ese JSON (el *_robustas.json) '
                                                      'en --symbols; "--symbols otros" = monedas que la búsqueda no usó')
    a = ap.parse_args()
    if a.validar:
        return validate(a)
    symbols = [s.strip() for s in a.symbols.split(',') if s.strip()]
    intervals = [s.strip() for s in a.intervals.split(',') if s.strip()]
    names = [s.strip() for s in a.strategies.split(',') if s.strip()]

    t0 = time.time()
    if a.synthetic:
        strategies = [('sintética', Path(a.synthetic).read_text(encoding='utf-8'), {})]
        start, end = synthetic_data(symbols, intervals, a.months)
    else:
        strategies = asyncio.run(strategies_from_db(names))
        print(f"Cargando datos ({a.months} meses)…", flush=True)
        start, end = asyncio.run(load_all(symbols, intervals, a.months))
    start_n, end_n = pd.Timestamp(start).tz_convert(None), pd.Timestamp(end).tz_convert(None)
    split_n = start_n + (end_n - start_n) * 2 / 3
    print(f"En muestra: {start_n:%Y-%m-%d} → {split_n:%Y-%m-%d} · Fuera de muestra: {split_n:%Y-%m-%d} → {end_n:%Y-%m-%d}")

    configs = {(n, iv): sample_configs(a.samples, a.seed + zlib.crc32(f'{n}|{iv}'.encode()) % 1000) for n, _, _ in strategies for iv in intervals}
    tasks = [(n, code, scfg, sym, iv, configs[(n, iv)], start, split_n, end_n)
             for n, code, scfg in strategies for iv in intervals for sym in symbols]
    total_runs = sum(len(t[5]) for t in tasks)
    print(f"{len(strategies)} estrategias × {len(intervals)} intervalos × {len(symbols)} símbolos × {a.samples} configs "
          f"= {total_runs} backtests · {a.workers} procesos\n", flush=True)

    results = {}   # (estrategia, intervalo, i) -> {símbolo: (is, oos)}
    done = 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(run_group, t) for t in tasks]
        for f in as_completed(futs):
            name, sym, iv, out = f.result()
            done += 1
            if out:
                for i, is_, oos in out:
                    results.setdefault((name, iv, i), {})[sym] = (is_, oos)
            el = time.time() - t0
            print(f"  [{done}/{len(tasks)}] {name} · {sym} · {iv} · {el / 60:.1f} min", flush=True)

    rows = []
    need = math.ceil(len(symbols) * 0.75)
    for (name, iv, i), by_sym in results.items():
        if len(by_sym) < len(symbols):
            continue
        agg = {}
        for part, k in (('is', 0), ('oos', 1)):
            st = [v[k] for v in by_sym.values()]
            agg[part] = dict(n=sum(x['n'] for x in st), pf=pf(sum(x['gp'] for x in st), sum(x['gl'] for x in st)),
                             ret=round(sum(x['pnl'] for x in st) / (INITIAL * len(st)) * 100, 2),
                             pos=sum(x['pnl'] > 0 for x in st), dd=round(max(x['dd'] for x in st), 1))
        months_is, months_oos = a.months * 2 / 3, a.months / 3
        cand = (agg['is']['pf'] >= 1.15 and agg['is']['pos'] >= need and agg['is']['n'] >= 15 * len(symbols)
                and agg['is']['dd'] <= 25)
        robust = cand and agg['oos']['pf'] >= 1.1 and agg['oos']['pos'] >= need and agg['oos']['n'] >= 6 * len(symbols)
        rows.append(dict(estrategia=name, intervalo=iv, cfg=configs[(name, iv)][i], **{f'is_{k}': v for k, v in agg['is'].items()},
                         **{f'oos_{k}': v for k, v in agg['oos'].items()},
                         is_ret_mes=round(agg['is']['ret'] / months_is, 2), oos_ret_mes=round(agg['oos']['ret'] / months_oos, 2),
                         candidata=bool(cand), robusta=bool(robust)))

    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    out_csv = Path(f'/tmp/tr2_busqueda_{stamp}.csv')
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['estrategia', 'intervalo', 'robusta', 'candidata', 'is_pf', 'is_ret', 'is_pos', 'is_n', 'is_dd',
                    'oos_pf', 'oos_ret', 'oos_pos', 'oos_n', 'oos_dd', 'config'])
        for r in sorted(rows, key=lambda r: (-r['robusta'], -r['is_pf'])):
            w.writerow([r['estrategia'], r['intervalo'], r['robusta'], r['candidata'], r['is_pf'], r['is_ret'], r['is_pos'],
                        r['is_n'], r['is_dd'], r['oos_pf'], r['oos_ret'], r['oos_pos'], r['oos_n'], r['oos_dd'],
                        json.dumps(r['cfg'], ensure_ascii=False)])

    cands = sorted([r for r in rows if r['candidata']], key=lambda r: -r['is_pf'])
    robust = [r for r in cands if r['robusta']]
    print(f"\nProbadas {len(rows)} configuraciones · {len(cands)} candidatas (ganan EN MUESTRA en ≥{need}/{len(symbols)} "
          f"símbolos, PF ≥ 1.15) · {len(robust)} ROBUSTAS (siguen ganando FUERA DE MUESTRA)\n")
    hdr = f"{'':2}{'Estrategia':24} {'Int':>4} │ {'PF in':>6} {'Ret in':>7} {'+/'+str(len(symbols)):>4} {'DD':>5} │ {'PF fuera':>8} {'Ret fuera':>9} {'+/'+str(len(symbols)):>4} {'Trades':>6}"
    print(hdr)
    print('─' * len(hdr))
    for r in cands[:20]:
        print(f"{'✔ ' if r['robusta'] else '  '}{r['estrategia'][:24]:24} {r['intervalo']:>4} │ {r['is_pf']:>6} {r['is_ret']:>6}% "
              f"{r['is_pos']:>4} {r['is_dd']:>4}% │ {r['oos_pf']:>8} {r['oos_ret']:>8}% {r['oos_pos']:>4} {r['oos_n']:>6}")
    if robust:
        best = robust[:5]
        out_json = Path(f'/tmp/tr2_busqueda_{stamp}_robustas.json')
        out_json.write_text(json.dumps([dict(estrategia=r['estrategia'], intervalo=r['intervalo'], simbolos=symbols,
                                             meses=a.months, **COSTS, riesgo_pct=1.0, **r['cfg'],
                                             en_muestra=dict(pf=r['is_pf'], ret=r['is_ret']),
                                             fuera_de_muestra=dict(pf=r['oos_pf'], ret=r['oos_ret'])) for r in best],
                                       ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"\nTop robustas (para repetir en la UI de Backtesting): {out_json}")
    print(f"Todas las combinaciones: {out_csv}\nTiempo total: {(time.time() - t0) / 60:.1f} min")
    return 0


if __name__ == '__main__':
    sys.exit(main())

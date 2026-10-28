"""
Auditoría de filtros de apertura y revalidación de lo que corre en paper. Solo lectura (no escribe en la DB).

  1) Revalidación (--revalidate): cada paper activa vuelve a correr su backtest de origen (mismo rango y parámetros)
     con el motor actual y se compara con lo guardado; también compara params de paper vs backtest.
  2) Filtros: base sin filtros y cada filtro encendido por separado. Además de cuántas operaciones cambia, mide la
     CALIDAD de lo que quita: un filtro sirve si las operaciones que bloquea son peores que las que deja, en la
     muestra (primeros 2/3) Y fuera de muestra (último 1/3, el que no se usa para elegir). Quitar operaciones a una
     estrategia perdedora siempre "mejora" el retorno: por eso se juzga por R por operación y PF, no por retorno.
       --mode generic: estrategias de la DB con SL/TP genéricos × monedas × temporalidades.
       --mode paper:   las configuraciones activas de paper, con SUS parámetros (cada filtro sobre su config).
  Filtros EXPERIMENTALES (solo en esta auditoría, no existen en el motor): funding saturado, tendencia de BTC para
  altcoins, ATR mínimo (mercado muerto) y tendencia diaria EMA 50. Todos sin mirar al futuro (dato ya cerrado al
  decidir, cierre de la vela de la señal).

Uso: cd python-engine && nice -n 19 venv/bin/python tools/analysis/filter_audit.py [--mode generic|paper]
     [--revalidate] [--symbols BTCUSDT,ETHUSDT] [--intervals 60,240] [--months 24] [--out /root/patches/audit]
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

import cli.param_search as ps  # noqa: E402
from api.v1.backtest import BacktestRequest, load_strategy, run_backtest  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.base_strategy import macro_trend_series  # noqa: E402
from collectors.broker_resolver import interval_delta  # noqa: E402
from indicators.regime_indicators import calculate_atr  # noqa: E402

RISK_USD = ps.INITIAL * ps.RISK_PCT / 100          # 1 R = lo que se arriesga por operación
FUNDING_CROWD = 0.0003                             # 0,03 % por liquidación = 3× la tasa base de Bybit
ATR_WINDOW, ATR_PCTL = 200, 0.30                   # ATR% por debajo del percentil 30 de 200 velas = mercado muerto
DAILY_EMA = 50

BASE = dict(sl_pct=1.5, tp_pct=3.0, be_pct=99.0, max_duration=48, max_duration_profit=False, close_on_opposite=False,
            trailing_mode=None, regime_filter=False, regime_adx_trending=25.0, regime_adx_ranging=20.0,
            regime_ambiguous_as='RANGING', volume_filter=False, volume_filter_period=20, volume_filter_mult=1.2,
            macro_trend_filter=False, hour_filter=False, weekend_filter=False, allow_short=True)
VARIANTS = {
    'régimen (ambiguo=lateral)': dict(regime_filter=True, regime_ambiguous_as='RANGING'),
    'régimen (ambiguo=no operar)': dict(regime_filter=True, regime_ambiguous_as='NO_OPERAR'),
    'volumen ×1,0': dict(volume_filter=True, volume_filter_mult=1.0),
    'volumen ×1,2': dict(volume_filter=True, volume_filter_mult=1.2),
    'volumen ×1,5': dict(volume_filter=True, volume_filter_mult=1.5),
    'tendencia macro H4': dict(macro_trend_filter=True),
    'horario 7-21 UTC (oculto)': dict(hour_filter=True),
    'sin fin de semana (oculto)': dict(weekend_filter=True),
    'NUEVO funding saturado': dict(x_funding=True),
    'NUEVO tendencia BTC (altcoins)': dict(x_btc=True),
    'NUEVO ATR mínimo': dict(x_atr=True),
    'NUEVO tendencia diaria EMA50': dict(x_daily=True),
}
FIELDS = set(BacktestRequest.model_fields)
BTC_MACRO = {}   # macro H4 de BTC (para el filtro de tendencia BTC en altcoins)


def j(v):
    return v if isinstance(v, dict) else json.loads(v or '{}')


# ─────────────────────────── filtros experimentales (máscaras de bloqueo) ───────────────────────────

def decide_times(df, iv):
    return pd.to_datetime(df['time'], utc=True).dt.tz_convert(None).to_numpy(dtype='datetime64[ns]') + \
        np.timedelta64(int(interval_delta(iv).total_seconds() // 60), 'm')


def block_funding(df, iv, data):
    f = data.funding
    if f is None or not len(f.times):
        return np.ones(len(df), dtype=bool)          # sin funding: no se opera (pesimista)
    idx = np.searchsorted(np.asarray(f.times, dtype='datetime64[ns]'), decide_times(df, iv), side='right') - 1
    rate = np.where(idx >= 0, np.asarray(f.rates, dtype=float)[np.clip(idx, 0, None)], np.nan)
    sig = df['signal'].to_numpy()
    return ((sig == 1) & (rate >= FUNDING_CROWD)) | ((sig == -1) & (rate <= -FUNDING_CROWD)) | np.isnan(rate) & (sig != 0)


def block_trend(df, trend):
    sig = df['signal'].to_numpy()
    return ((sig == 1) & (trend != 1)) | ((sig == -1) & (trend != -1))


def block_btc(df, iv, sym):
    if sym == 'BTCUSDT':
        return np.zeros(len(df), dtype=bool)          # en BTC sería el mismo filtro macro
    return block_trend(df, macro_trend_series(df['time'], iv, BTC_MACRO.get(iv)))


def block_atr(df):
    atrp = (calculate_atr(df) / df['close']).astype(float)
    thr = atrp.rolling(ATR_WINDOW).quantile(ATR_PCTL)
    return ((atrp < thr) | thr.isna()).to_numpy() & (df['signal'].to_numpy() != 0)


def daily_trend(df, iv, macro_df):
    n = len(df)
    if macro_df is None or len(macro_df) < 6 * DAILY_EMA:
        return np.zeros(n, dtype=int)
    m = macro_df[['time', 'close']].copy()
    m['time'] = pd.to_datetime(m['time'], utc=True).dt.tz_convert(None)
    m['day'] = m['time'].dt.floor('D')
    g = m.groupby('day').agg(close=('close', 'last'), bars=('close', 'size')).reset_index()
    g = g[g['bars'] == 6].reset_index(drop=True)      # solo días completos (6 velas H4)
    ema = g['close'].astype(float).ewm(span=DAILY_EMA, adjust=False).mean()
    t = np.sign(g['close'].astype(float) - ema).astype(int).to_numpy()
    t[: DAILY_EMA - 1] = 0
    ready = (g['day'] + pd.Timedelta(days=1)).to_numpy(dtype='datetime64[ns]')
    idx = np.searchsorted(ready, decide_times(df, iv), side='right') - 1
    return np.where(idx >= 0, t[np.clip(idx, 0, None)], 0)


def experimental(s, cfg, data, sym, iv):
    if not any(cfg.get(k) for k in ('x_funding', 'x_btc', 'x_atr', 'x_daily')):
        return
    orig = s.compute_signals

    def wrapped(df):
        out = orig(df).copy()
        if cfg.get('x_funding'):
            mask = block_funding(out, iv, data)
        elif cfg.get('x_btc'):
            mask = block_btc(out, iv, sym)
        elif cfg.get('x_atr'):
            mask = block_atr(out)
        else:
            mask = block_trend(out, daily_trend(out, iv, data.macro_df))
        out.loc[mask, 'signal'] = 0
        return out
    s.compute_signals = wrapped


# ─────────────────────────── corrida y métricas ───────────────────────────

def run_one(name, code, scfg, sym, iv, cfg, data, start, split, end):
    kw = {**ps.COSTS, **ps.UI_FIXED, **{k: v for k, v in cfg.items() if k in FIELDS}}   # la config manda (paper)
    req = BacktestRequest(strategy=name, strategy_code=code, strategy_config=scfg, symbol=sym, interval=iv,
                          initial_balance=ps.INITIAL, risk_per_trade_pct=ps.RISK_PCT, **kw)
    s = load_strategy(req)
    s.slippage_pct = float(kw['slippage_pct'])
    s.hour_filter, s.weekend_filter = bool(cfg.get('hour_filter')), bool(cfg.get('weekend_filter'))
    if cfg.get('macro_trend_filter'):
        s.macro_df = data.macro_df
    experimental(s, cfg, data, sym, iv)
    res = BacktestEngine(strategy=s, df=data.df, initial_balance=ps.INITIAL, risk_per_trade_pct=ps.RISK_PCT,
                         minute_df=data.minute_df, trade_from=start, funding=data.funding).run()
    lo = ps.naive_utc(start)
    trades = {}
    for t in res['trades']:
        et = ps.naive_utc(t['entry_time'])
        if lo <= et < end:
            trades[(str(t['entry_time']), t['side'])] = (t['pnl'], 'oos' if et >= split else 'is')
    return trades


def seg(trades, part=None):
    v = [p for p, s in trades.values() if part is None or s == part]
    gp, gl = sum(x for x in v if x > 0), -sum(x for x in v if x <= 0)
    return dict(n=len(v), wins=sum(x > 0 for x in v), pnl=sum(v), gp=gp, gl=gl)


def pf(s):
    return round(s['gp'] / s['gl'], 2) if s['gl'] > 0 else (99.0 if s['gp'] > 0 else 0.0)


def compare(base, var):
    """Lo que el filtro quitó (operaciones de la base que ya no están) vs lo que dejó, por tramo."""
    removed = {k: v for k, v in base.items() if k not in var}
    kept = {k: v for k, v in base.items() if k in var}
    out = dict(changed=len(set(base) ^ set(var)))
    for part in ('is', 'oos'):
        out[part] = dict(base=seg(base, part), var=seg(var, part), removed=seg(removed, part), kept=seg(kept, part))
    out['full'] = dict(base=seg(base), var=seg(var), removed=seg(removed))
    return out


def combos(name, code, scfg, sym, iv, base_cfg, data, start, split, end):
    base = run_one(name, code, scfg, sym, iv, base_cfg, data, start, split, end)
    res = {}
    for vname, over in VARIANTS.items():
        if all(base_cfg.get(k) == v for k, v in over.items()):
            continue      # la config ya lo trae así (paper): no hay nada que comparar
        res[vname] = compare(base, run_one(name, code, scfg, sym, iv, {**base_cfg, **over}, data, start, split, end))
    return res


# ─────────────────────────── partes ───────────────────────────

async def revalidate(conn, out):
    print('\n== Revalidación de paper ==', flush=True)
    rows = await conn.fetch("SELECT id, display_name, symbol, interval, params, backtest_id FROM paper_strategy_configs "
                            "WHERE active ORDER BY id")
    for r in rows:
        p = j(r['params'])
        b = await conn.fetchrow("SELECT config_params, metrics FROM backtests WHERE id = $1", r['backtest_id'])
        if b is None:
            print(f"#{r['id']} {r['display_name']}: sin backtest de origen")
            continue
        cp = j(b['config_params'])
        diff = {k: (p.get(k), cp.get(k)) for k in sorted(set(p) | set(cp))
                if k in FIELDS and k not in ('symbol', 'interval', 'start_date', 'end_date', 'walk_forward', 'n_windows',
                                             'monthly_breakdown') and p.get(k) != cp.get(k)}
        req = {k: v for k, v in cp.items() if k in FIELDS}
        req.update(symbol=r['symbol'], interval=r['interval'])
        try:
            mm = (await run_backtest(BacktestRequest(**req)))['result']['metrics']
        except Exception as e:  # noqa: BLE001
            print(f"#{r['id']} {r['display_name']}: ERROR {getattr(e, 'detail', e)}")
            continue
        print(f"#{r['id']} {r['display_name']}: trades={mm['total_trades']} wr={mm['win_rate']:.1f}% "
              f"ret={mm['total_return_pct']:.2f}% pf={mm['profit_factor']:.2f} · params distintos: {diff or 'ninguno'}")
        out['revalidation'].append(dict(id=r['id'], metrics={k: mm[k] for k in ('total_trades', 'win_rate',
                                        'total_return_pct', 'profit_factor', 'max_drawdown_pct')}))
    from db import close_pools
    await close_pools()


async def load_targets(conn, mode, symbols, intervals, outdir):
    strats = await conn.fetch("SELECT id, name, code, config FROM strategies WHERE active ORDER BY id")
    with open(outdir / 'strategies_code.txt', 'w') as f:
        for r in strats:
            f.write(f"\n{'=' * 100}\n#{r['id']} {r['name']}  config={json.dumps(j(r['config']), ensure_ascii=False)}\n"
                    f"{'=' * 100}\n{r['code']}\n")
    if mode == 'generic':
        return [dict(label=r['name'], name=r['name'], code=r['code'], scfg=j(r['config']), sym=sym, iv=iv, cfg=BASE)
                for sym in symbols for iv in intervals for r in strats]
    rows = await conn.fetch("SELECT id, display_name, symbol, interval, params FROM paper_strategy_configs WHERE active "
                            "ORDER BY id")
    out = []
    for r in rows:
        p = j(r['params'])
        cfg = {**BASE, **{k: v for k, v in p.items() if k in BASE or k in FIELDS}}
        cfg = {k: v for k, v in cfg.items() if k not in ('symbol', 'interval', 'strategy', 'strategy_code',
                                                         'strategy_config', 'initial_balance', 'risk_per_trade_pct')}
        out.append(dict(label=f"#{r['id']} {r['display_name']}", name=p.get('strategy', r['display_name']),
                        code=p['strategy_code'], scfg=p.get('strategy_config') or {}, sym=r['symbol'],
                        iv=r['interval'], cfg=cfg))
    return out


def audit(targets, months, out):
    start, end = ps.ui_period(months)
    end_n = ps.naive_utc(end)
    split = ps.naive_utc(start) + (end_n - ps.naive_utc(start)) * 2 / 3
    print(f'\n== Filtros: {len(targets)} combinaciones · {start:%Y-%m-%d}..{end:%Y-%m-%d} '
          f'(fuera de muestra desde {split:%Y-%m-%d}) ==', flush=True)
    syms = sorted({t['sym'] for t in targets}, key=lambda s: (s != 'BTCUSDT', s))
    ivs = sorted({t['iv'] for t in targets})
    if 'BTCUSDT' not in syms:      # la tendencia de BTC se necesita aunque BTC no se audite
        asyncio.run(ps.load_data(['BTCUSDT'], ivs, start, end))
        for iv in ivs:
            d = ps.DATA.get(('BTCUSDT', iv))
            BTC_MACRO[iv] = d.macro_df if d is not None else None
        ps.drop_data(['BTCUSDT'])
    for sym in syms:
        t0 = time.time()
        mine = [t for t in targets if t['sym'] == sym]
        asyncio.run(ps.load_data([sym], sorted({t['iv'] for t in mine}), start, end))
        if sym == 'BTCUSDT':
            for iv in ivs:
                d = ps.DATA.get(('BTCUSDT', iv))
                if d is not None:
                    BTC_MACRO[iv] = d.macro_df
        f = next((d.funding for k, d in ps.DATA.items() if k[0] == sym and d is not None), None)
        if f is not None and len(f.rates):
            r = np.abs(np.asarray(f.rates, dtype=float))
            print(f"  {sym}: funding mediana |tasa|={np.median(r) * 100:.4f}% · liquidaciones ≥ 0,03%: "
                  f"{(r >= FUNDING_CROWD).mean() * 100:.1f}%", flush=True)
        for t in mine:
            data = ps.DATA.get((sym, t['iv']))
            if data is None:
                continue
            out['audit'].append(dict(label=t['label'], sym=sym, iv=t['iv'],
                                     variants=combos(t['name'], t['code'], t['scfg'], sym, t['iv'], t['cfg'], data,
                                                     start, split, end_n)))
        ps.drop_data([sym])
        print(f"  {sym}: listo en {time.time() - t0:.0f}s", flush=True)


def agg(items, part, key):
    vals = [v[part][key] for v in items]
    return dict(n=sum(x['n'] for x in vals), wins=sum(x['wins'] for x in vals), pnl=sum(x['pnl'] for x in vals),
                gp=sum(x['gp'] for x in vals), gl=sum(x['gl'] for x in vals))


def part_view(items, part):
    b, v, rem = agg(items, part, 'base'), agg(items, part, 'var'), agg(items, part, 'removed')
    bl, rl = b['n'] - b['wins'], rem['n'] - rem['wins']
    return dict(win_cut=rem['wins'] / b['wins'] * 100 if b['wins'] else 0.0, loss_cut=rl / bl * 100 if bl else 0.0,
                r_base=b['pnl'] / RISK_USD, r_var=v['pnl'] / RISK_USD, pf_base=pf(b), pf_var=pf(v))


def verdict(items):
    """
    SIRVE: en la muestra Y fuera de muestra sube el PF y la ganancia total (en R) no baja.
    MEJORA CALIDAD: sube el PF en ambos tramos pero se gana menos en total (menos operaciones, mejores).
    """
    if all(v['changed'] == 0 for v in items):
        return 'SIN EFECTO'
    pv = [part_view(items, p) for p in ('is', 'oos')]
    if all(x['pf_var'] > x['pf_base'] for x in pv):
        return 'SIRVE' if all(x['r_var'] >= x['r_base'] for x in pv) else 'MEJORA CALIDAD'
    return 'NO APORTA'


def summary(out):
    print('\n== Resumen: qué quita cada filtro ==')
    print('   perdedoras/ganadoras: % de las de la base que el filtro bloquea · R total: ganancia en R (1 R = riesgo por '
          'operación) · [muestra | fuera de muestra]')
    by = {}
    for rec in out['audit']:
        for vname, v in rec['variants'].items():
            by.setdefault((rec['label'], vname), []).append(v)
    cur = None
    for (label, vname), items in by.items():
        if label != cur:
            cur = label
            print(f"\n  {label}  ({sum(rec['label'] == label for rec in out['audit'])} combos)")
        noeff = sum(v['changed'] == 0 for v in items)
        cells = []
        for part in ('is', 'oos'):
            x = part_view(items, part)
            cells.append(f"perd -{x['loss_cut']:3.0f}% gan -{x['win_cut']:3.0f}% R {x['r_base']:+6.1f}→{x['r_var']:+6.1f} "
                         f"PF {x['pf_base']:.2f}→{x['pf_var']:.2f}")
        print(f"    {vname:<31} {verdict(items):<14} sin efecto {noeff:>2}/{len(items)} │ {cells[0]} │ {cells[1]}")


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--mode', choices=('generic', 'paper'), default='paper')
    a.add_argument('--revalidate', action='store_true')
    a.add_argument('--symbols', default='BTCUSDT,ETHUSDT,SOLUSDT,SUIUSDT,XRPUSDT,ZECUSDT')
    a.add_argument('--intervals', default='60,240')
    a.add_argument('--months', type=int, default=24)
    a.add_argument('--out', default='/root/patches/audit')
    a = a.parse_args()
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    out = dict(revalidation=[], audit=[])
    ps.low_priority()

    async def db_part():
        import asyncpg
        from db import DB_DSN
        conn = await asyncpg.connect(DB_DSN)
        try:
            if a.revalidate:
                await revalidate(conn, out)
            return await load_targets(conn, a.mode, a.symbols.split(','), a.intervals.split(','), outdir)
        finally:
            await conn.close()

    t = time.time()
    targets = asyncio.run(db_part())
    audit(targets, a.months, out)
    summary(out)
    (outdir / f'filter_audit_{a.mode}.json').write_text(json.dumps(out, ensure_ascii=False, default=str))
    print(f"\nFIN en {(time.time() - t) / 60:.1f} min · detalle: {outdir}/filter_audit_{a.mode}.json")


if __name__ == '__main__':
    main()

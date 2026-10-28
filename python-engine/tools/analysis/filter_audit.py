"""
Auditoría de filtros de apertura y revalidación de lo que corre en paper. Solo lectura (no escribe en la DB).

  1) Revalidación: cada paper activa vuelve a correr su backtest de origen (mismo rango y parámetros) con el motor
     actual (funding + velas ordenadas) y se compara con lo guardado. También compara params de paper vs backtest.
  2) Filtros: para cada estrategia de la DB × monedas × temporalidades, se corre una base sin filtros y cada filtro
     encendido por separado. Por filtro: cuántas operaciones cambia (0 = "sin efecto"), y el efecto en el periodo
     completo y en el último 1/3 (fuera de muestra, el que no se usa para elegir).

Uso: cd python-engine && nice -n 19 venv/bin/python tools/analysis/filter_audit.py [--symbols BTCUSDT,ETHUSDT]
     [--intervals 60,240] [--months 24] [--out /root/patches/audit]
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

import cli.param_search as ps  # noqa: E402
from api.v1.backtest import BacktestRequest, load_strategy, run_backtest  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402

BASE = dict(sl_pct=1.5, tp_pct=3.0, be_pct=99.0, max_duration=48, max_duration_profit=False, close_on_opposite=False,
            trailing_mode=None, regime_filter=False, regime_adx_trending=25.0, regime_adx_ranging=20.0,
            regime_ambiguous_as='RANGING', volume_filter=False, volume_filter_period=20, volume_filter_mult=1.2,
            macro_trend_filter=False, hour_filter=False, weekend_filter=False, allow_short=True)
VARIANTS = {
    'régimen (ambiguo=lateral)': dict(regime_filter=True),
    'régimen (ambiguo=no operar)': dict(regime_filter=True, regime_ambiguous_as='NO_OPERAR'),
    'volumen ×0,8': dict(volume_filter=True, volume_filter_mult=0.8),
    'volumen ×1,0': dict(volume_filter=True, volume_filter_mult=1.0),
    'volumen ×1,2': dict(volume_filter=True, volume_filter_mult=1.2),
    'volumen ×1,5': dict(volume_filter=True, volume_filter_mult=1.5),
    'tendencia macro H4': dict(macro_trend_filter=True),
    'horario 7-21 UTC (oculto)': dict(hour_filter=True),
    'sin fin de semana (oculto)': dict(weekend_filter=True),
}
FIELDS = set(BacktestRequest.model_fields)


def j(v):
    return v if isinstance(v, dict) else json.loads(v or '{}')


def stats(trades, lo, hi):
    sel = [t for t in trades if lo <= ps.naive_utc(t['entry_time']) < hi]
    gp = sum(t['pnl'] for t in sel if t['pnl'] > 0)
    gl = -sum(t['pnl'] for t in sel if t['pnl'] <= 0)
    return dict(n=len(sel), pnl=round(sum(t['pnl'] for t in sel), 2), gp=gp, gl=gl,
                wins=sum(t['pnl'] > 0 for t in sel))


def run_one(name, code, scfg, sym, iv, cfg, data, start, split, end):
    req = BacktestRequest(strategy=name, strategy_code=code, strategy_config=scfg, symbol=sym, interval=iv,
                          initial_balance=ps.INITIAL, risk_per_trade_pct=ps.RISK_PCT, **ps.COSTS, **ps.UI_FIXED,
                          **{k: v for k, v in cfg.items() if k in FIELDS})
    s = load_strategy(req)
    s.slippage_pct = ps.COSTS['slippage_pct']
    s.hour_filter, s.weekend_filter = cfg['hour_filter'], cfg['weekend_filter']   # no son campos de la UI
    if cfg['macro_trend_filter']:
        s.macro_df = data.macro_df
    res = BacktestEngine(strategy=s, df=data.df, initial_balance=ps.INITIAL, risk_per_trade_pct=ps.RISK_PCT,
                         minute_df=data.minute_df, trade_from=start, funding=data.funding).run()
    trades = res['trades']
    lo = ps.naive_utc(start)
    return dict(keys={(str(t['entry_time']), t['side']) for t in trades}, full=stats(trades, lo, end),
                oos=stats(trades, split, end), dd=float(res['metrics'].get('max_drawdown_pct') or 0),
                funding=round(sum(float(t.get('funding') or 0) for t in trades), 2))


def pf(s):
    return round(s['gp'] / s['gl'], 2) if s['gl'] > 0 else (99.0 if s['gp'] > 0 else 0.0)


async def revalidate(conn, out):
    print('\n== 1) Revalidación de paper ==', flush=True)
    rows = await conn.fetch("SELECT id, display_name, symbol, interval, params, backtest_id FROM paper_strategy_configs "
                            "WHERE active ORDER BY id")
    for r in rows:
        p = j(r['params'])
        b = await conn.fetchrow("SELECT config_params, metrics FROM backtests WHERE id = $1", r['backtest_id'])
        if b is None:
            print(f"#{r['id']} {r['display_name']}: sin backtest de origen")
            continue
        cp, m = j(b['config_params']), j(b['metrics'])
        diff = {k: (p.get(k), cp.get(k)) for k in sorted(set(p) | set(cp))
                if k in FIELDS and k not in ('symbol', 'interval', 'start_date', 'end_date', 'walk_forward', 'n_windows',
                                             'monthly_breakdown') and p.get(k) != cp.get(k)}
        req = {k: v for k, v in cp.items() if k in FIELDS}
        req.update(symbol=r['symbol'], interval=r['interval'])
        t = time.time()
        try:
            res = (await run_backtest(BacktestRequest(**req)))['result']
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con la siguiente
            print(f"#{r['id']} {r['display_name']}: ERROR {getattr(e, 'detail', e)}")
            continue
        mm = res['metrics']
        fund = round(sum(float(x.get('funding') or 0) for x in res['trades']), 2)
        ind = m.get('individual_results')
        old = None
        if isinstance(ind, dict):
            old = ind.get(r['symbol'])
        elif isinstance(ind, list):
            old = next((x for x in ind if isinstance(x, dict) and x.get('symbol') == r['symbol']), None)
        print(f"#{r['id']} {r['display_name']} ({time.time() - t:.1f}s)")
        print(f"   ahora : trades={mm['total_trades']} wr={mm['win_rate']:.1f}% ret={mm['total_return_pct']:.2f}% "
              f"pf={mm['profit_factor']:.2f} dd={mm['max_drawdown_pct']:.2f}% funding pagado={fund}")
        print(f"   antes : {json.dumps(old, ensure_ascii=False)[:400] if old else 'sin desglose por moneda'}")
        print(f"   paper vs backtest (parámetros distintos): {diff or 'ninguno'}")
        out['revalidation'].append(dict(id=r['id'], name=r['display_name'], now=dict(
            trades=mm['total_trades'], wr=mm['win_rate'], ret=mm['total_return_pct'], pf=mm['profit_factor'],
            dd=mm['max_drawdown_pct'], funding=fund), before=old, param_diff={k: list(v) for k, v in diff.items()}))
    from db import close_pools
    await close_pools()


async def strategies(conn, outdir):
    rows = await conn.fetch("SELECT id, name, code, config FROM strategies WHERE active ORDER BY id")
    with open(outdir / 'strategies_code.txt', 'w') as f:
        for r in rows:
            f.write(f"\n{'=' * 100}\n#{r['id']} {r['name']}  config={json.dumps(j(r['config']), ensure_ascii=False)}\n"
                    f"{'=' * 100}\n{r['code']}\n")
    return [(r['id'], r['name'], r['code'], j(r['config'])) for r in rows]


def audit(strats, symbols, intervals, months, out):
    start, end = ps.ui_period(months)
    end_n = ps.naive_utc(end)
    split = ps.naive_utc(start) + (end_n - ps.naive_utc(start)) * 2 / 3
    print(f'\n== 2) Filtros: {len(strats)} estrategias × {symbols} × {intervals} · {start:%Y-%m-%d}..{end:%Y-%m-%d} '
          f'(fuera de muestra desde {split:%Y-%m-%d}) ==', flush=True)
    for sym in symbols:
        t = time.time()
        asyncio.run(ps.load_data([sym], intervals, start, end))
        for iv in intervals:
            data = ps.DATA.get((sym, iv))
            if data is None:
                continue
            for sid, name, code, scfg in strats:
                base = run_one(name, code, scfg, sym, iv, BASE, data, start, split, end_n)
                rec = dict(strategy=name, symbol=sym, interval=iv, base=dict(full=base['full'], oos=base['oos'],
                           dd=base['dd'], funding=base['funding']), variants={})
                for vname, over in VARIANTS.items():
                    v = run_one(name, code, scfg, sym, iv, {**BASE, **over}, data, start, split, end_n)
                    rec['variants'][vname] = dict(changed=len(base['keys'] ^ v['keys']), full=v['full'], oos=v['oos'],
                                                  dd=v['dd'])
                out['audit'].append(rec)
        ps.drop_data([sym])
        print(f"  {sym}: listo en {time.time() - t:.0f}s", flush=True)


def summary(out):
    print('\n== Resumen por estrategia y filtro (Δ = filtro encendido − sin filtros) ==')
    print('   combos: moneda×temporalidad · sin efecto: no cambió ninguna operación · OOS mejor: gana más en el último 1/3')
    by = {}
    for rec in out['audit']:
        for vname, v in rec['variants'].items():
            by.setdefault((rec['strategy'], vname), []).append((rec['base'], v))
    cur = None
    for (sname, vname), items in by.items():
        if sname != cur:
            cur = sname
            b_n = sum(b['full']['n'] for b, _ in items)
            b_ret = sum(b['full']['pnl'] for b, _ in items) / (ps.INITIAL * len(items)) * 100
            print(f"\n  {sname}  (base: {b_n} operaciones, retorno medio {b_ret:+.1f}% por combo)")
        k = len(items)
        noeff = sum(v['changed'] == 0 for _, v in items)
        d_n = sum(v['full']['n'] - b['full']['n'] for b, v in items)
        d_ret = sum(v['full']['pnl'] - b['full']['pnl'] for b, v in items) / (ps.INITIAL * k) * 100
        d_oos = sum(v['oos']['pnl'] - b['oos']['pnl'] for b, v in items) / (ps.INITIAL * k) * 100
        better = sum(v['oos']['pnl'] > b['oos']['pnl'] for b, v in items if v['changed'])
        pf_b = pf(dict(gp=sum(b['full']['gp'] for b, _ in items), gl=sum(b['full']['gl'] for b, _ in items)))
        pf_v = pf(dict(gp=sum(v['full']['gp'] for _, v in items), gl=sum(v['full']['gl'] for _, v in items)))
        print(f"    {vname:<30} sin efecto {noeff:>2}/{k} · operaciones {d_n:+5d} · Δret {d_ret:+6.2f}% · "
              f"ΔOOS {d_oos:+6.2f}% · OOS mejor {better}/{k - noeff} · PF {pf_b:.2f}→{pf_v:.2f}")


def main():
    a = argparse.ArgumentParser()
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
            await revalidate(conn, out)
            return await strategies(conn, outdir)
        finally:
            await conn.close()

    t = time.time()
    strats = asyncio.run(db_part())
    audit(strats, a.symbols.split(','), a.intervals.split(','), a.months, out)
    summary(out)
    (outdir / 'filter_audit.json').write_text(json.dumps(out, ensure_ascii=False, default=str))
    print(f"\nFIN en {(time.time() - t) / 60:.1f} min · detalle: {outdir}/filter_audit.json · código: "
          f"{outdir}/strategies_code.txt")


if __name__ == '__main__':
    main()

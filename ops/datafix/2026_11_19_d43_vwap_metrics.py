#!/usr/bin/env python3
"""
D-43 (p82), decisión del dueño 19-nov («Corregirlos»): los números guardados de VWAP Tendencia salieron del código que
miraba el futuro (R-21). Este script repite cada backtest guardado de la estrategia con su código viejo y con el mismo
código corregido por p80, sobre los mismos datos y parámetros, y:
  1. Exige que la repetición con el código viejo dé EXACTO lo guardado (si un solo backtest no se reproduce, no se
     aplica nada: no se puede decir que la diferencia sea solo R-21).
  2. Con --apply, en una transacción: guarda en cada backtest las métricas corregidas (con las anteriores en
     `metrics.r21_previous`) y el código corregido en `config_params` y `strategy_snapshot` (implementar un backtest
     viejo ya no devuelve el código viejo a Paper); y en sus configs de Paper las columnas de métricas y estrellas con
     la misma cuenta que `StrategyConfigSync::metricAttributes` / `tradesPerMonth`. No toca params ni el estado
     (activa/apagada) de ninguna config. No escribe en `strategy_config_changes` (es el historial de PARÁMETROS).
Uso (desde python-engine/):
  venv/bin/python -I ../ops/datafix/2026_11_19_d43_vwap_metrics.py [--apply] [--backup archivo.json]
Salida: 0 = OK (o ya aplicado) · 1 = un backtest no se reproduce con el código viejo (no se aplica nada)
· 2 = la estrategia no tiene el código corregido de p80 · 3 = error (o algo cambió durante el cálculo: no se aplica).
"""
import argparse
import asyncio
import importlib
import json
import os
import sys
from datetime import date

STRATEGY_NAME = 'VWAP Tendencia'
SOURCE = 'p82 D-43'
# claves de backtests.metrics que se recalculan (las mismas que guarda BacktestingController::run)
METRIC_KEYS = ('total_trades', 'win_rate', 'sharpe_ratio', 'profit_factor', 'avg_monthly_pnl', 'consist_pct',
               'total_return_pct', 'max_drawdown_pct', 'max_drawdown_floating_pct', 'trades_by_symbol', 'closed_at_end')
# claves con las que se exige reproducir lo guardado (tolerancia: lo guardado puede venir sin redondear)
REPRO_KEYS = ('total_trades', 'win_rate', 'total_return_pct', 'sharpe_ratio', 'profit_factor', 'avg_monthly_pnl',
              'consist_pct')
REPRO_TOL = 0.006
CONFIG_COLS = ('avg_win_rate', 'sharpe_ratio', 'profit_factor', 'total_return_pct', 'avg_monthly_pnl',
               'consistency_pct', 'star_rating', 'avg_monthly_trades')


def as_dict(v):
    return json.loads(v) if isinstance(v, str) else dict(v or {})


def as_list(v):
    return json.loads(v) if isinstance(v, str) else list(v or [])


# ───────────────────────────── funciones puras (tests/Forensic/vwap_metrics_fix_test.py) ─────────────────────────────

def rating(wr: float, sharpe: float, pf: float, ret_mes: float, consist: float) -> float:
    """App\\Helpers\\RatingHelper::calculate."""
    s_wr = 5 if wr >= 65 else 4 if wr >= 55 else 3 if wr >= 45 else 2 if wr >= 35 else 1
    s_sh = 5 if sharpe >= 4 else 4 if sharpe >= 3 else 3 if sharpe >= 2 else 2 if sharpe >= 1 else 1
    s_pf = 5 if pf >= 2.5 else 4 if pf >= 2.0 else 3 if pf >= 1.5 else 2 if pf >= 1.0 else 1
    s_rt = 5 if ret_mes >= 20 else 4 if ret_mes >= 10 else 3 if ret_mes >= 5 else 2 if ret_mes >= 2 else 1
    s_cs = 5 if consist >= 80 else 4 if consist >= 60 else 3 if consist >= 40 else 2 if consist >= 20 else 1
    return round((s_wr + s_sh + s_pf + s_rt + s_cs) / 5 + 1e-9, 1)


def consolidate(per_symbol: list[dict]) -> dict:
    """La fila CONSOLIDADO de BacktestingController::run, en el formato de backtests.metrics. per_symbol: symbol,
    metrics (aggregate_metrics del motor), monthly (monthly_breakdown), closed_at_end."""
    trades = sum(int(r['metrics'].get('total_trades') or 0) for r in per_symbol)
    wins = sum(int(r['metrics'].get('winning_trades') or 0) for r in per_symbol)
    gp = sum(float(r['metrics'].get('gross_profit') or 0) for r in per_symbol)
    gl = sum(float(r['metrics'].get('gross_loss') or 0) for r in per_symbol)
    monthly: dict[str, float] = {}
    for r in per_symbol:
        for m in r.get('monthly') or []:
            monthly[m['month']] = monthly.get(m['month'], 0.0) + float(m.get('total_pnl_pct') or 0)
    n = len(per_symbol)

    def worst(key):
        vals = [float(r['metrics'][key]) for r in per_symbol if r['metrics'].get(key) is not None]
        return max(vals) if vals else None

    return dict(
        total_trades=trades,
        win_rate=round(wins / trades * 100, 2) if trades else 0,
        sharpe_ratio=round(sum(float(r['metrics'].get('sharpe_ratio') or 0) for r in per_symbol) / n, 2) if n else 0,
        profit_factor=round(gp / gl, 2) if gl > 0 else (999.99 if gp > 0 else 0),
        avg_monthly_pnl=round(sum(monthly.values()) / len(monthly), 2) if monthly else 0,
        consist_pct=round(sum(1 for v in monthly.values() if v > 0) / len(monthly) * 100, 1) if monthly else 0,
        total_return_pct=round(sum(monthly.values()), 2),
        max_drawdown_pct=worst('max_drawdown_pct'),
        max_drawdown_floating_pct=worst('max_drawdown_floating_pct'),
        trades_by_symbol={r['symbol']: max(0, int(r['metrics'].get('total_trades') or 0) - int(r.get('closed_at_end') or 0))
                          for r in per_symbol},
        closed_at_end=sum(int(r.get('closed_at_end') or 0) for r in per_symbol),
    )


def mismatches(saved: dict, repeated: dict) -> list[str]:
    """Claves en las que la repetición con el código viejo no da lo guardado."""
    out = []
    for k in REPRO_KEYS:
        if k not in saved:
            continue
        a, b = saved.get(k), repeated.get(k)
        try:
            if abs(float(a) - float(b)) > REPRO_TOL:
                out.append(f"{k} {a} vs {b}")
        except (TypeError, ValueError):
            out.append(f"{k} {a} vs {b}")
    return out


def corrected_metrics(saved: dict, new: dict, today: str) -> dict:
    """Métricas guardadas con las recalculadas; las anteriores quedan en r21_previous (trazabilidad en la base)."""
    out = dict(saved)
    out.update({k: new[k] for k in METRIC_KEYS})
    out['r21_previous'] = {k: saved[k] for k in METRIC_KEYS if k in saved}
    out['r21_corrected'] = f"{today} {SOURCE}"
    return out


def trades_per_month(metrics: dict, run_params: dict, months: int, symbol: str, n_symbols: int):
    """StrategyConfigSync::tradesPerMonth."""
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) or (isinstance(v, str) and _isnum(v))
    by = metrics.get('trades_by_symbol')
    if isinstance(by, dict) and symbol in by and num(by[symbol]):
        trades = float(by[symbol])
    elif n_symbols == 1 and num(metrics.get('total_trades')):
        trades = max(0.0, float(metrics['total_trades']) - float(metrics.get('closed_at_end') or 0))
    else:
        return None
    try:
        days = (date.fromisoformat(str(run_params.get('end_date'))[:10]) -
                date.fromisoformat(str(run_params.get('start_date'))[:10])).days
        span = days / 30.4375 if days > 0 else None
    except (TypeError, ValueError):
        span = None
    if span is None:
        span = float(months) if months > 0 else None
    if span is None or span < 0.5 or trades < 0:
        return None
    return round(min(trades / span, 9999.99), 2)


def _isnum(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def config_columns(metrics: dict, run_params: dict, months: int, symbol: str, n_symbols: int) -> dict:
    """StrategyConfigSync::metricAttributes (columnas de métricas) + avg_monthly_trades, sin params ni estado."""
    def num(k):
        v = metrics.get(k)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else (
            float(v) if isinstance(v, str) and _isnum(v) else None)

    def clamp(v, mx):
        return None if v is None else max(-mx, min(mx, v))
    wr, sh, pf, avg, cons = num('win_rate'), num('sharpe_ratio'), num('profit_factor'), num('avg_monthly_pnl'), num('consist_pct')
    return dict(avg_win_rate=clamp(wr, 999.99), sharpe_ratio=clamp(sh, 9999.99), profit_factor=clamp(pf, 999.99),
                total_return_pct=clamp(num('total_return_pct'), 9999.9999), avg_monthly_pnl=clamp(avg, 999.9999),
                consistency_pct=clamp(cons, 9999.9),
                star_rating=rating(wr or 0.0, sh or 0.0, pf or 0.0, avg or 0.0, cons or 0.0),
                avg_monthly_trades=trades_per_month(metrics, run_params, months, symbol, n_symbols))


# ───────────────────────────── E/S ─────────────────────────────

async def rerun(pool, cp: dict, symbols: list[str], codes: dict) -> dict:
    """Repite el backtest (cada moneda) con cada código de `codes`; devuelve {nombre: per_symbol}."""
    from api.v1.backtest import BacktestRequest, _simulate, load_backtest_data, parse_range
    out = {k: [] for k in codes}
    for sym in symbols:
        payload = dict(cp, symbol=sym, walk_forward=False, monthly_breakdown=True)
        reqs = {k: BacktestRequest(**dict(payload, strategy_code=c)) for k, c in codes.items()}
        r0 = next(iter(reqs.values()))
        start, end = parse_range(r0.start_date, r0.end_date)
        data = await load_backtest_data(pool, sym, r0.interval, start, end, macro=r0.macro_trend_filter,
                                        data_broker=r0.data_broker, btc_macro=r0.btc_trend_filter)
        for k, req in reqs.items():
            res = await asyncio.to_thread(_simulate, req, data, start, end, [])
            out[k].append(dict(symbol=sym, metrics=res['metrics'], monthly=res.get('monthly_breakdown'),
                               closed_at_end=res.get('closed_at_end') or 0))
    return out


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='D-43: métricas de VWAP Tendencia con el código corregido')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--backup', help='archivo JSON con los valores anteriores (al aplicar)')
    a = ap.parse_args(argv)
    sys.path.insert(0, os.getcwd())
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), '.env'))
    import asyncpg
    from db import DB_DSN
    import collectors.funding_collector as fc
    fc._to_download = lambda *x, **k: []   # mismo funding guardado con el que se hicieron (no se descarga nada)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    r21 = importlib.import_module('2026_11_19_r21_vwap_std')
    today = date.today().isoformat()

    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=2)
    try:
        st = await pool.fetchrow("SELECT id, code FROM strategies WHERE name = $1", STRATEGY_NAME)
        if st is None or not r21.is_patched(st['code']):
            print(f"«{STRATEGY_NAME}» no tiene el código corregido de p80: no se toca nada")
            return 2
        bts = await pool.fetch("""SELECT id, symbols, months, config_params::text AS cp, strategy_snapshot::text AS snap,
                                  metrics::text AS metrics FROM backtests WHERE strategy_id = $1 ORDER BY id""", st['id'])
        cfgs = await pool.fetch(f"""SELECT id, display_name, symbol, active, backtest_id, {', '.join(CONFIG_COLS)}
                                    FROM paper_strategy_configs WHERE backtest_id = ANY($1::bigint[]) ORDER BY id""",
                                [b['id'] for b in bts])
        print(f"«{STRATEGY_NAME}» #{st['id']} · backtests guardados: {len(bts)} · configs de Paper que vienen de ellos: {len(cfgs)}")
        plan, bad, done = [], [], 0
        for b in bts:
            cp, saved = as_dict(b['cp']), as_dict(b['metrics'])
            code = cp.get('strategy_code') or ''
            symbols = as_list(b['symbols'])
            if r21.is_patched(code) and 'r21_previous' in saved:
                done += 1
                plan.append(dict(b=b, cp=cp, metrics=saved, symbols=symbols, apply=False))
                continue
            if r21.OLD_LINE not in code:
                print(f"  #{b['id']}: su código no tiene la línea vieja de vwap_std_dev: no se toca")
                continue
            new_code = r21.patch_code(code)
            runs = await rerun(pool, cp, symbols, {'old': code, 'new': new_code})
            old_m, new_m = consolidate(runs['old']), consolidate(runs['new'])
            miss = mismatches(saved, old_m)
            if miss:
                bad.append(b['id'])
                print(f"  #{b['id']}: NO se reproduce con el código viejo: {'; '.join(miss)}")
                continue
            plan.append(dict(b=b, cp=cp, symbols=symbols, apply=True, old_code=code, new_code=new_code,
                             metrics=corrected_metrics(saved, new_m, today)))
            print(f"  #{b['id']} {symbols}: reproduce lo guardado · trades {old_m['total_trades']} → {new_m['total_trades']} "
                  f"· retorno {saved.get('total_return_pct')} → {new_m['total_return_pct']} % · estrellas "
                  f"{rating(*(float(old_m[k]) for k in ('win_rate', 'sharpe_ratio', 'profit_factor', 'avg_monthly_pnl', 'consist_pct')))}"
                  f" → {rating(*(float(new_m[k]) for k in ('win_rate', 'sharpe_ratio', 'profit_factor', 'avg_monthly_pnl', 'consist_pct')))}")
        if bad:
            print(f"VERIFICACIÓN FALLIDA: {len(bad)} backtest(s) no se reproducen con el código viejo {bad}: no se aplica nada")
            return 1

        # columnas de cada config, desde las métricas (corregidas o ya guardadas)
        by_bt = {p['b']['id']: p for p in plan}
        cfg_updates = []
        for c in cfgs:
            p = by_bt.get(c['backtest_id'])
            if p is None:
                continue
            cols = config_columns(p['metrics'], p['cp'], int(p['b']['months'] or 0), c['symbol'], len(p['symbols']))
            old = {k: (float(c[k]) if c[k] is not None else None) for k in CONFIG_COLS}
            changed = any((old[k] is None) != (cols[k] is None) or (cols[k] is not None and abs(old[k] - cols[k]) > 0.0051)
                          for k in CONFIG_COLS)
            if changed:
                cfg_updates.append((c, old, cols))
            print(f"  config #{c['id']} {c['display_name']} ({'ACTIVA' if c['active'] else 'apagada'}): estrellas "
                  f"{old['star_rating']} → {cols['star_rating']} · retorno {old['total_return_pct']} → {cols['total_return_pct']} % "
                  f"· trades/mes {old['avg_monthly_trades']} → {cols['avg_monthly_trades']}{'' if changed else ' (sin cambio)'}")
        todo = [p for p in plan if p['apply']]
        if not todo and not cfg_updates:
            print(f"YA APLICADO: {done} backtest(s) ya corregidos; configs al día")
            return 0
        print(f"a corregir: {len(todo)} backtest(s) y {len(cfg_updates)} config(s)")
        if not a.apply:
            print("(solo lectura: sin --apply no se cambia nada)")
            return 0

        if a.backup:
            with open(a.backup, 'w', encoding='utf-8') as f:
                json.dump(dict(backtests=[dict(id=p['b']['id'], config_params=p['b']['cp'], strategy_snapshot=p['b']['snap'],
                                               metrics=p['b']['metrics']) for p in todo],
                               configs=[dict(id=c['id'], **old) for c, old, _ in cfg_updates]), f, ensure_ascii=False)
        async with pool.acquire() as conn:
            async with conn.transaction():
                for p in todo:
                    b = p['b']
                    snap = as_dict(b['snap'])
                    if r21.OLD_LINE in (snap.get('code') or ''):
                        snap['code'] = r21.patch_code(snap['code'])
                    n = await conn.execute("""UPDATE backtests SET metrics = $1::json, config_params = $2::json,
                        strategy_snapshot = $3::json, updated_at = timezone('UTC', now())
                        WHERE id = $4 AND metrics::text = $5 AND config_params::text = $6""",
                                           json.dumps(p['metrics']), json.dumps(dict(p['cp'], strategy_code=p['new_code'])),
                                           json.dumps(snap), b['id'], b['metrics'], b['cp'])
                    if n != 'UPDATE 1':
                        raise RuntimeError(f"el backtest #{b['id']} cambió durante el cálculo: no se aplica nada")
                for c, old, cols in cfg_updates:
                    n = await conn.execute(f"""UPDATE paper_strategy_configs SET {', '.join(f'{k} = ${i + 1}' for i, k in enumerate(CONFIG_COLS))},
                        updated_at = timezone('UTC', now()) WHERE id = ${len(CONFIG_COLS) + 1} AND backtest_id = ${len(CONFIG_COLS) + 2}""",
                                           *[cols[k] for k in CONFIG_COLS], c['id'], c['backtest_id'])
                    if n != 'UPDATE 1':
                        raise RuntimeError(f"la config #{c['id']} cambió durante el cálculo: no se aplica nada")
        print(f"APLICADO: {len(todo)} backtest(s) con métricas y código corregidos (anteriores en metrics.r21_previous) y "
              f"{len(cfg_updates)} config(s) de Paper con métricas y estrellas corregidas (params y estado sin cambio)")
        return 0
    finally:
        await pool.close()


if __name__ == '__main__':
    try:
        sys.exit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception as e:   # noqa: BLE001
        print(f"ERROR: {type(e).__name__}: {' '.join(str(e).split())[:300]}")
        sys.exit(3)

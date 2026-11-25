#!/usr/bin/env python3
"""
C6-07 (D-45): comparación CONTROLADA de SL/TP fijo vs automático sobre las configs de Paper/Real.

Cada config se prueba dos veces en backtest con TODO igual (misma moneda, temporalidad, periodo, capital, comisiones,
slippage, reglas de entrada y filtros, y las mismas velas cargadas una sola vez); solo cambia el SL/TP:
  fijo        los parámetros de la config tal cual (hoy todas usan SL/TP fijo)
  automático  los mismos + SL = k × ATR(14) acotado [mín, máx] y TP = m × el SL (break-even en «veces el SL») — D-45
Periodo: el de la pantalla de backtest (D-58: 24 meses completos, termina el último día del mes anterior).
Solo lee la base y no cambia ninguna config: nada de lo que opera cambia. Corre en un proceso aparte, con prioridad
mínima de CPU y disco, una config a la vez (no compite con los ticks de Paper/Real).

Uso (desde python-engine/):
  venv/bin/python tools/analysis/compare_levels.py [--configs 3,7] [--months 24] [--sl-atr-mult 2 --tp-r-mult 2 ...]
                                                   [--json-out /root/c6_07.json]
Código de salida: 0 = comparación hecha · 2 = no se pudo comparar.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from backtesting import auto_levels  # noqa: E402
from backtesting.metrics import counted_trades  # noqa: E402
from collectors.broker_resolver import interval_delta  # noqa: E402

SKIP_KEYS = {'symbol', 'interval', 'start_date', 'end_date', 'walk_forward', 'monthly_breakdown', 'strategy',
             'n_windows', 'data_broker_note'}
LEVEL_KEYS = ('sl_level_mode', 'tp_level_mode', 'sl_tp_mode', 'sl_atr_mult', 'tp_r_mult', 'tp_atr_mult',
              'be_r_mult', 'sl_min_pct', 'sl_max_pct')
VARIANTS = ('fijo', 'auto')
EXIT_ORDER = ('take_profit_1', 'stop_loss', 'break_even', 'trailing_stop', 'time_exit', 'time_exit_profit',
              'opposite_signal', 'volatility_protection')


# ───────────────────────────── funciones puras (tests/Forensic/compare_levels_test.py) ─────────────────────────────

def as_dict(v) -> dict:
    return json.loads(v) if isinstance(v, str) else dict(v or {})


def params_key(params: dict) -> str:
    """Huella de los parámetros (reproducibilidad: misma huella = misma config)."""
    return hashlib.md5(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:8]


def auto_overrides(a) -> dict:
    """Los multiplicadores del modo automático: los de D-45 por defecto; el dueño puede pedir otros."""
    d = auto_levels.DEFAULTS
    return dict(sl_level_mode='atr', tp_level_mode='r',
                sl_atr_mult=a.sl_atr_mult if a.sl_atr_mult is not None else d['sl_atr_mult'],
                tp_r_mult=a.tp_r_mult if a.tp_r_mult is not None else d['tp_r_mult'],
                be_r_mult=a.be_r_mult if a.be_r_mult is not None else d['be_r_mult'],
                sl_min_pct=a.sl_min_pct if a.sl_min_pct is not None else d['sl_min_pct'],
                sl_max_pct=a.sl_max_pct if a.sl_max_pct is not None else d['sl_max_pct'])


def variant_payloads(cfg: dict, start: str, end: str, overrides: dict) -> dict[str, dict]:
    """
    Las dos pruebas de una config: idénticas salvo el SL/TP. «fijo» = la config tal cual, pero con el modo fijo
    explícito (si ya fuera automática, se compara igual contra el fijo); «auto» = lo mismo + `overrides`.
    """
    p = {k: v for k, v in as_dict(cfg['params']).items() if k not in SKIP_KEYS}
    base = dict(p, strategy=cfg.get('display_name') or f"config #{cfg['id']}", symbol=cfg['symbol'],
                interval=str(cfg['interval']), start_date=start, end_date=end, walk_forward=False,
                monthly_breakdown=True)
    fixed = {k: v for k, v in base.items() if k not in LEVEL_KEYS}
    fixed.update(sl_level_mode='fixed', tp_level_mode='fixed')
    auto = {k: v for k, v in base.items() if k not in LEVEL_KEYS}
    auto.update(overrides)
    return {'fijo': fixed, 'auto': auto}


def _round(x, nd=2):
    return None if x is None else round(float(x), nd)


def summarize(result: dict, interval: str) -> dict:
    """Las métricas que pide el informe (§C6-07) de UN backtest."""
    m = result.get('metrics') or {}
    trades = counted_trades(result.get('trades') or [])
    months = result.get('monthly_breakdown') or []
    step_h = interval_delta(str(interval)).total_seconds() / 3600
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.get('exit_reason') or '?'] = reasons.get(t.get('exit_reason') or '?', 0) + 1
    month_pct = [float(r.get('total_pnl_pct') or 0) for r in months]
    n = len(trades)
    return dict(
        retorno_pct=_round(m.get('total_return_pct')),
        profit_factor=_round(m.get('profit_factor')),
        drawdown_pct=_round(m.get('max_drawdown_pct')),
        trades=int(m.get('total_trades') or 0),
        win_rate=_round(m.get('win_rate')),
        expectancy=_round(m.get('expectancy')),
        expectancy_pct=_round(sum(float(t.get('pnl_pct') or 0) for t in trades) / n, 3) if n else None,
        meses=len(month_pct),
        meses_positivos=sum(1 for v in month_pct if v > 0),
        peor_mes_pct=_round(min(month_pct)) if month_pct else None,
        mejor_mes_pct=_round(max(month_pct)) if month_pct else None,
        duracion_media_h=_round(sum(float(t.get('bars_open') or 0) for t in trades) / n * step_h, 1) if n else None,
        salidas=dict(sorted(reasons.items(), key=lambda kv: (EXIT_ORDER.index(kv[0]) if kv[0] in EXIT_ORDER else 99,
                                                             kv[0]))),
        mensual={r['month']: _round(r.get('total_pnl_pct')) for r in months},
    )


def better(metric: str, fijo, auto) -> str | None:
    """Quién gana en una métrica: 'auto', 'fijo', '=' o None (sin dato). Drawdown y duración: menor es mejor."""
    if fijo is None or auto is None:
        return None
    if abs(float(auto) - float(fijo)) < 1e-9:
        return '='
    lower_better = metric in ('drawdown_pct',)
    return 'auto' if (float(auto) < float(fijo)) == lower_better else 'fijo'


ROWS = (('retorno_pct', 'Retorno neto %'), ('profit_factor', 'Profit factor'), ('drawdown_pct', 'Caída máxima %'),
        ('trades', 'Operaciones'), ('win_rate', '% ganadas'), ('expectancy', 'Ganancia media por trade (USDT)'),
        ('expectancy_pct', 'Ganancia media por trade %'), ('meses_positivos', 'Meses positivos'),
        ('peor_mes_pct', 'Peor mes %'), ('mejor_mes_pct', 'Mejor mes %'), ('duracion_media_h', 'Duración media (h)'))
SCORED = ('retorno_pct', 'profit_factor', 'drawdown_pct')


def fmt(v) -> str:
    return '—' if v is None else (f'{v:g}' if isinstance(v, (int, float)) else str(v))


def config_report(cfg: dict, s: dict[str, dict], warnings: list[str]) -> str:
    f, a = s['fijo'], s['auto']
    lines = [f"\n=== Config #{cfg['id']} · {cfg.get('display_name') or ''} · {cfg['symbol']} {cfg['interval']}"
             f"{'' if cfg.get('active', True) else ' · (inactiva)'} · parámetros {params_key(as_dict(cfg['params']))}",
             f"{'':34}{'Fijo':>12}{'Automático':>12}  Mejor"]
    for k, label in ROWS:
        w = better(k, f[k], a[k]) if k in SCORED else ''
        lines.append(f"{label:34}{fmt(f[k]):>12}{fmt(a[k]):>12}  {w or ''}")
    lines.append(f"{'Meses del periodo':34}{fmt(f['meses']):>12}{fmt(a['meses']):>12}")
    lines.append('Motivos de salida  fijo: ' + (', '.join(f'{k} {v}' for k, v in f['salidas'].items()) or '—'))
    lines.append('                   auto: ' + (', '.join(f'{k} {v}' for k, v in a['salidas'].items()) or '—'))
    for w in dict.fromkeys(warnings):
        lines.append(f'  {w}')
    return '\n'.join(lines)


def overall(rows: list[dict]) -> dict:
    """Conteo de configs donde gana cada modo, por métrica, y totales por moneda (suma de retornos)."""
    out = {k: dict(auto=0, fijo=0, empate=0, sin_dato=0) for k in SCORED}
    by_symbol: dict[str, dict] = {}
    for r in rows:
        for k in SCORED:
            w = better(k, r['fijo'][k], r['auto'][k])
            out[k][{'auto': 'auto', 'fijo': 'fijo', '=': 'empate', None: 'sin_dato'}[w]] += 1
        b = by_symbol.setdefault(r['symbol'], dict(configs=0, fijo_retorno=0.0, auto_retorno=0.0))
        b['configs'] += 1
        b['fijo_retorno'] = round(b['fijo_retorno'] + float(r['fijo']['retorno_pct'] or 0), 2)
        b['auto_retorno'] = round(b['auto_retorno'] + float(r['auto']['retorno_pct'] or 0), 2)
    return dict(por_metrica=out, por_moneda=by_symbol)


def overall_report(ov: dict, n: int, start: str, end: str, overrides: dict) -> str:
    lines = [f"\n=== Resumen: {n} config(s) · {start} → {end} · automático: SL {overrides['sl_atr_mult']:g}×ATR "
             f"[{overrides['sl_min_pct']:g}%–{overrides['sl_max_pct']:g}%], TP {overrides['tp_r_mult']:g}× el SL, "
             f"break-even a {overrides['be_r_mult']:g}× el SL"]
    for k, label in ROWS:
        if k in SCORED:
            c = ov['por_metrica'][k]
            lines.append(f"{label:20} gana automático en {c['auto']}, fijo en {c['fijo']}, empate {c['empate']}"
                         + (f", sin dato {c['sin_dato']}" if c['sin_dato'] else ''))
    lines.append('Por moneda (suma de retornos de sus configs, %):')
    for sym, b in sorted(ov['por_moneda'].items()):
        lines.append(f"  {sym:12} {b['configs']} config(s) · fijo {b['fijo_retorno']:g} · automático {b['auto_retorno']:g}")
    lines.append('Nota: es un backtest del pasado; ningún modo se activa por esto (lo decide el dueño, D-45).')
    return '\n'.join(lines)


# ───────────────────────────── base y backtest (servidor) ─────────────────────────────

async def load_configs(ids: list[int] | None) -> list[dict]:
    import asyncpg
    dsn = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
           f"{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute('SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY')
        q = 'SELECT id, display_name, symbol, interval, params, active FROM paper_strategy_configs'
        rows = await conn.fetch(q + (' WHERE id = ANY($1::bigint[]) ORDER BY id' if ids else ' ORDER BY id'),
                                *([ids] if ids else []))
    finally:
        await conn.close()
    return [dict(r) for r in rows]


def simulate_pair(payloads: dict[str, dict], data, start, end) -> tuple[dict[str, dict], list[str]]:
    """Las dos variantes sobre LAS MISMAS velas (cada una con su copia: una no ve las columnas de la otra)."""
    from dataclasses import replace

    from api.v1.backtest import BacktestRequest, _simulate
    out, warnings = {}, list(data.warnings)
    for k in VARIANTS:
        w: list[str] = []
        out[k] = _simulate(BacktestRequest(**payloads[k]), replace(data, df=data.df.copy()), start, end, w)
        warnings += w
    return out, warnings


async def run_pair(cfg: dict, payloads: dict[str, dict]) -> tuple[dict[str, dict], list[str]]:
    """Carga las velas UNA vez (el mismo camino que /backtest/run) y corre las dos variantes sobre ellas."""
    from api.v1.backtest import BacktestRequest, load_backtest_data, parse_range
    from db import close_pools, get_pool
    r0 = BacktestRequest(**payloads['fijo'])
    start, end = parse_range(r0.start_date, r0.end_date)
    pool = await get_pool('backtest')
    try:
        data = await load_backtest_data(pool, r0.symbol, r0.interval, start, end, macro=r0.macro_trend_filter,
                                        data_broker=r0.data_broker, btc_macro=r0.btc_trend_filter)
    finally:
        await close_pools()
    return simulate_pair(payloads, data, start, end)


def main(argv=None, loader=load_configs, runner=run_pair, today: date | None = None) -> int:
    ap = argparse.ArgumentParser(description='C6-07: SL/TP fijo vs automático, misma config y mismos datos')
    ap.add_argument('--configs', help='ids de paper_strategy_configs separados por coma (por defecto: todas)')
    ap.add_argument('--months', type=int, default=24, help='meses completos (D-58: 24)')
    for k in ('sl_atr_mult', 'tp_r_mult', 'be_r_mult', 'sl_min_pct', 'sl_max_pct'):
        ap.add_argument('--' + k.replace('_', '-'), type=float, dest=k)
    ap.add_argument('--json-out')
    a = ap.parse_args(argv)
    if not auto_levels.enabled():
        print('SLTP_AUTO_ENABLED=false en python-engine/.env: el modo automático está apagado y las dos pruebas '
              'saldrían iguales. No se compara.')
        return 2
    ids = [int(x) for x in a.configs.split(',')] if a.configs else None
    from cli.param_search import low_priority, ui_period
    low_priority()
    s_dt, e_dt = ui_period(a.months, today or datetime.now(timezone.utc).date())
    start, end = s_dt.date().isoformat(), (e_dt - timedelta(days=1)).date().isoformat()   # ui_period: fin exclusivo
    overrides = auto_overrides(a)
    cfgs = asyncio.run(loader(ids))
    if not cfgs:
        print('No hay configs para comparar')
        return 2
    print(f'Comparando {len(cfgs)} config(s), una a la vez y en baja prioridad · {start} → {end}')
    rows, failed = [], []
    for cfg in cfgs:
        try:
            res, warns = asyncio.run(runner(cfg, variant_payloads(cfg, start, end, overrides)))
        except Exception as e:   # una config que no corre no frena las demás
            failed.append(cfg['id'])
            print(f"\n=== Config #{cfg['id']}: no se pudo probar ({str(e)[:200]})")
            continue
        s = {k: summarize(res[k], str(cfg['interval'])) for k in VARIANTS}
        print(config_report(cfg, s, warns), flush=True)
        rows.append(dict(id=cfg['id'], name=cfg.get('display_name'), symbol=cfg['symbol'],
                         interval=str(cfg['interval']), active=cfg.get('active', True),
                         params_key=params_key(as_dict(cfg['params'])), **s))
    if not rows:
        return 2
    ov = overall(rows)
    print(overall_report(ov, len(rows), start, end, overrides))
    if failed:
        print(f"No se pudieron probar: {', '.join('#' + str(i) for i in failed)}")
    if a.json_out:
        with open(a.json_out, 'w', encoding='utf-8') as fh:
            json.dump(dict(start=start, end=end, months=a.months, auto=overrides, rows=rows, overall=ov,
                           failed=failed), fh, ensure_ascii=False, default=str, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())

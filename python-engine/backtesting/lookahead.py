"""
¿La estrategia mira el futuro? (R-21, p84). En el backtest la estrategia recibe TODO el historial de una vez; en Paper y
Real solo existen las velas hasta el minuto actual. Si el resultado de una vela cambia según haya o no velas POSTERIORES,
la estrategia usa el futuro y el backtest muestra operaciones que en vivo no existen (VWAP Tendencia, 19-nov: ~40 % de
sus operaciones).

Prueba (misma vela inicial en los dos lados, para separar el futuro de la diferencia conocida por el inicio de la
ventana, §5.1): señales e indicadores una vez con todas las velas y, para cada una de las últimas `last_n` velas t,
otra vez con las velas solo hasta t; en cada t se comparan la señal y cada columna numérica de la estrategia. Los
filtros de H4 (macro y BTC) se apagan: son de la plataforma y usan solo velas H4 ya cerradas.

Se usa al guardar una estrategia (smoke test: no se guarda si mira el futuro), en la revisión diaria
(`/v1/strategies/lookahead-audit`) y a mano (`tools/analysis/lookahead_probe.py`).
"""
from __future__ import annotations

import asyncio
import json
import math

import pandas as pd

SKIP_COLS = {'time', 'open', 'high', 'low', 'close', 'volume', 'turnover'}
OFF_FILTERS = {'macro_trend_filter': False, 'btc_trend_filter': False}
WARMUP = 300          # velas previas para los indicadores
LAST_AUDIT = 150      # velas revisadas por config en la revisión diaria
LAST_GUARD = 100      # velas revisadas por combinación al guardar (el smoke test tiene 120 s)
GUARD_COMBOS = 2      # combinaciones del smoke test revisadas al guardar (H1 y H4 de BTC)


def as_dict(v):
    return json.loads(v) if isinstance(v, str) else dict(v or {})


def run_strategy(code: str, params: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Señales e indicadores con el mismo constructor que backtest, Paper y Real (filtros H4 apagados)."""
    from backtesting.strategies.loader import build_strategy
    p = dict(params, strategy_code=code, **OFF_FILTERS)
    st = build_strategy(p)
    st.params = p
    return st.compute_signals(df.copy()).reset_index(drop=True)


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(fa) or math.isnan(fb):
        return math.isnan(fa) and math.isnan(fb)
    return fa == fb or abs(fa - fb) <= 1e-9 * max(1.0, abs(fa), abs(fb))


def _signal(row) -> int:
    v = row.get('signal', 0)
    try:
        return 0 if v is None or (isinstance(v, float) and math.isnan(v)) else int(v)
    except (TypeError, ValueError):
        return 0


def lookahead_check(code: str, params: dict, df: pd.DataFrame, last_n: int) -> dict:
    """En cada una de las últimas `last_n` velas: resultado con todas las velas contra resultado con las velas hasta
    ella. Devuelve velas revisadas, señales distintas (vela, con todo, solo hasta ella) y columnas distintas."""
    df = df.reset_index(drop=True)
    full = run_strategy(code, params, df)
    cols = [c for c in full.columns if c not in SKIP_COLS and c != 'signal'
            and (pd.api.types.is_numeric_dtype(full[c]) or pd.api.types.is_bool_dtype(full[c]))]
    n = len(df)
    first = max(1, n - last_n)
    sig_diff, col_diff = [], {}
    for t in range(first, n):
        part = run_strategy(code, params, df.iloc[:t + 1])
        a, b = full.iloc[t], part.iloc[-1]
        if _signal(a) != _signal(b):
            sig_diff.append((str(df['time'].iloc[t]), _signal(a), _signal(b)))
        for c in cols:
            if c in part.columns and not _same(a[c], b[c]):
                col_diff[c] = col_diff.get(c, 0) + 1
    return dict(checked=n - first, signal_diff=sig_diff, column_diff=col_diff,
                full_signals=int((full['signal'].iloc[first:].fillna(0) != 0).sum()) if 'signal' in full else 0)


def looks_ahead(r: dict) -> bool:
    return bool(r['signal_diff'] or r['column_diff'])


def _cols(r: dict, k: int = 6) -> str:
    return ', '.join(f"{c} ({v})" for c, v in sorted(r['column_diff'].items(), key=lambda x: -x[1])[:k])


def verdict(r: dict) -> str:
    if looks_ahead(r):
        cols = _cols(r)
        return (f"MIRA EL FUTURO: {len(r['signal_diff'])} señal(es) distinta(s) en {r['checked']} velas"
                f"{' · columnas: ' + cols if cols else ''}")
    return f"OK: no mira el futuro ({r['checked']} velas, {r['full_signals']} señales)"


def guard_message(symbol: str, interval: str, r: dict) -> str:
    """Motivo de rechazo al guardar (lo muestra la pantalla de estrategias en «Falló el Smoke Test: …»)."""
    cols = _cols(r)
    return (f"la estrategia mira el futuro: en {symbol} {interval}, de las últimas {r['checked']} velas, "
            f"{len(r['signal_diff'])} señal(es) cambian según existan velas posteriores"
            f"{' y estas columnas también: ' + cols if cols else ''}. En vivo esas velas no existen y el backtest "
            f"mostraría operaciones falsas. Cada vela debe calcularse solo con velas anteriores (por ejemplo, "
            f"expanding()/rolling() en vez de transform() sobre todo el día).")


# ───────────────────────────── E/S (solo lectura) ─────────────────────────────

async def load_bars(db, symbol: str, interval: str, n: int) -> pd.DataFrame:
    """Últimas `n` velas cerradas (hasta ayer) de Bybit. `db`: pool o conexión de asyncpg."""
    from collectors.bars import bars_frame
    rows = await db.fetch("""SELECT time, open, high, low, close, volume FROM ohlcv_data WHERE broker = 'bybit'
        AND symbol = $1 AND interval = $2 AND time < date_trunc('day', now()) ORDER BY time DESC LIMIT $3""",
                          symbol, str(interval), n)
    return bars_frame(rows, f'lookahead {symbol}').sort_values('time').reset_index(drop=True)


async def _check(slot, code, params, df, last_n) -> dict:
    # CPU en un hilo y de a uno con los backtests (R-06): el event loop sigue con los ticks
    async with slot:
        return await asyncio.to_thread(lookahead_check, code, params, df, last_n)


async def guard_code(db, slot, code: str, config: dict | None, combos: list[str],
                     warmup: int = WARMUP, last_n: int = LAST_GUARD) -> str | None:
    """Al guardar: None si no mira el futuro (o no hay datos para probarlo); si mira, el motivo del rechazo.
    Un error de la estrategia no se informa aquí: lo informa el smoke test que sigue."""
    for combo in combos[:GUARD_COMBOS]:
        symbol, _, interval = combo.partition(':')
        df = await load_bars(db, symbol, interval, warmup + last_n)
        if len(df) < warmup // 2 + 10:
            continue
        try:
            r = await _check(slot, code, dict(strategy_config=config or {}, symbol=symbol, interval=interval), df, last_n)
        except Exception:   # noqa: BLE001
            return None
        if looks_ahead(r):
            return guard_message(symbol, interval, r)
    return None


async def load_units(db) -> list[dict]:
    """Cada config activa de Paper (con su código congelado) y cada estrategia sin config activa con su mismo código."""
    units, in_use = [], set()
    for c in await db.fetch("""SELECT id, display_name, symbol, interval, params::text AS params
                               FROM paper_strategy_configs WHERE active ORDER BY id"""):
        p = as_dict(c['params'])
        code = p.get('strategy_code') or ''
        in_use.add(code)
        units.append(dict(label=f"config #{c['id']} {c['display_name']}", symbol=c['symbol'], interval=str(c['interval']),
                          params=p, code=code))
    for s in await db.fetch("SELECT id, name, code, config::text AS config FROM strategies ORDER BY id"):
        if s['code'] in in_use:
            continue
        units.append(dict(label=f"estrategia #{s['id']} {s['name']} (BTCUSDT H1)", symbol='BTCUSDT', interval='60',
                          params=dict(strategy_config=as_dict(s['config'])), code=s['code']))
    return units


async def audit(db, slot, warmup: int = WARMUP, last_n: int = LAST_AUDIT) -> dict:
    """Revisión de todas las configs activas y estrategias: lista de resultados y las que miran el futuro."""
    results = []
    for u in await load_units(db):
        df = await load_bars(db, u['symbol'], u['interval'], warmup + last_n)
        if len(df) < warmup // 2 + 10:
            results.append(dict(label=u['label'], ok=None, verdict=f"sin datos suficientes ({len(df)} velas)"))
            continue
        try:
            r = await _check(slot, u['code'], u['params'], df, last_n)
        except Exception as e:   # noqa: BLE001
            results.append(dict(label=u['label'], ok=None, verdict=f"error al evaluar: {type(e).__name__}: {str(e)[:160]}"))
            continue
        results.append(dict(label=u['label'], ok=not looks_ahead(r), verdict=verdict(r)))
    return dict(checked=len(results), bad=[x for x in results if x['ok'] is False],
                errors=[x for x in results if x['ok'] is None], results=results)

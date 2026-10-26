"""
Diagnóstico (solo lectura) de por qué una estrategia genera 0 operaciones.
Recorre el embudo exacto del backtest: velas -> señales crudas -> régimen -> short permitido -> trades.

Uso (desde python-engine/):
  venv/bin/python ../tests/Forensic/strategy_signal_diag.py "Reversión a la Media" [SIMBOLO:INTERVALO ...] [--days 90]
  Por defecto usa la matriz del smoke test: BTCUSDT:60 BTCUSDT:240 ETHUSDT:60
"""
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import BacktestRequest, WARMUP_BARS, load_ohlcv, load_strategy  # noqa: E402
from backtesting.engine import BacktestEngine, compute_regimes  # noqa: E402
from collectors.broker_resolver import interval_delta, resolve_backtest_source  # noqa: E402

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")


def _j(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


async def diagnose(pool, row, symbol: str, interval: str, days: int) -> None:
    end_d = datetime.now(timezone.utc).date() - timedelta(days=1)
    start_d = end_d - timedelta(days=days - 1)
    start = datetime(start_d.year, start_d.month, start_d.day, tzinfo=timezone.utc)
    end = datetime(end_d.year, end_d.month, end_d.day, tzinfo=timezone.utc) + timedelta(days=1)
    print(f"\n━━━ {symbol} {interval}  {start_d} → {end_d} ━━━")

    # Mismos parámetros por defecto que el smoke test (BacktestRequest sin overrides)
    req = BacktestRequest(strategy='diag', strategy_code=row['code'], strategy_config=dict(_j(row['config'])),
                          symbol=symbol, interval=interval, start_date=start_d.isoformat(),
                          end_date=end_d.isoformat(), walk_forward=False, monthly_breakdown=False)

    src = await resolve_backtest_source(pool, symbol, interval, start, end)
    if src is None:
        print("  ✗ sin velas en el rango")
        return
    df = await load_ohlcv(pool, symbol, interval, src.broker, start - interval_delta(interval) * WARMUP_BARS, end)
    print(f"  velas: {len(df)} (fuente {src.broker}, completitud {src.completeness * 100:.1f}%)")

    s = load_strategy(req)
    print(f"  clase: {type(s).__name__} | regime_filter={s.regime_filter} allowed={s.allowed_regimes} "
          f"allow_short={getattr(s, 'allow_short', True)} volume_filter={s.volume_filter} macro={s.macro_trend_filter}")

    prepared = s.prepare(df.copy())
    out = s.generate_signals(prepared)
    if 'signal' not in out.columns:
        print("  ✗ generate_signals NO devuelve la columna 'signal'")
        return
    times = pd.to_datetime(out['time'], utc=True)
    in_range = (times >= start).to_numpy()
    raw = out['signal']
    print(f"  valores de 'signal' (rango): {dict(Counter(raw[in_range].tolist()))}")

    new_cols = [c for c in out.columns if c not in df.columns and c != 'signal']
    if new_cols:
        nan_last = {c: int(out[c][in_range].isna().sum()) for c in new_cols}
        print(f"  indicadores (NaN dentro del rango): {nan_last}")

    sig = raw.fillna(0).astype(int).to_numpy()
    regimes = compute_regimes(out, s.regime_adx_trending, s.regime_adx_ranging, s.regime_ambiguous_as)
    print(f"  régimen (rango): {dict(Counter(regimes[in_range].tolist()))}")

    idx = np.where((sig != 0) & in_range)[0]
    idx = idx[idx < len(out) - 1]  # la entrada es en la vela siguiente
    print(f"  embudo: señales crudas={len(idx)}", end='')
    if len(idx) == 0:
        print("\n  ⇒ CAUSA: la estrategia no genera señales (lógica/umbral de generate_signals o indicadores en NaN)")
        return
    by_regime = Counter(str(regimes[i]) for i in idx)
    ok_regime = [i for i in idx if s.should_operate(str(regimes[i]))]
    ok_side = [i for i in ok_regime if sig[i] == 1 or getattr(s, 'allow_short', True)]
    print(f" | por régimen {dict(by_regime)} | pasan régimen={len(ok_regime)} | pasan short={len(ok_side)}")

    s.slippage_pct = float(req.slippage_pct)
    res = BacktestEngine(strategy=s, df=df, initial_balance=req.initial_balance,
                         risk_per_trade_pct=req.risk_per_trade_pct, trade_from=start).run()
    n = res['metrics']['total_trades']
    print(f"  trades del motor: {n}")
    if not ok_regime:
        print(f"  ⇒ CAUSA: TODAS las señales caen en regímenes no permitidos {s.allowed_regimes}")
    elif not ok_side:
        print("  ⇒ CAUSA: solo hay señales short y allow_short=False")
    elif n == 0:
        print("  ⇒ CAUSA: hay señales válidas pero el motor no abrió (tamaño 0: revisar sl_pct / riesgo / apalancamiento)")


async def main() -> None:
    args = [a for a in sys.argv[1:]]
    days = 90
    if '--days' in args:
        k = args.index('--days')
        days = int(args[k + 1])
        del args[k:k + 2]
    if not args:
        sys.exit("Uso: strategy_signal_diag.py \"Nombre estrategia\" [SIMBOLO:INTERVALO ...] [--days N]")
    name, combos = args[0], args[1:] or ["BTCUSDT:60", "BTCUSDT:240", "ETHUSDT:60"]

    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, code, config FROM strategies WHERE name ILIKE $1 ORDER BY id",
                                    f"%{name}%")
        if not rows:
            sys.exit(f"No hay estrategias que coincidan con '{name}'")
        for row in rows:
            print(f"══ Estrategia #{row['id']} '{row['name']}' ══")
            print(f"config: {json.dumps(_j(row['config']), ensure_ascii=False)}")
            print("código:\n" + "\n".join(f"  {i + 1:3} | {line}" for i, line in enumerate((row['code'] or '').splitlines())))
            for combo in combos:
                symbol, _, interval = combo.partition(':')
                try:
                    await diagnose(pool, row, symbol, interval, days)
                except Exception as e:
                    print(f"  ✗ error: {type(e).__name__}: {e}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

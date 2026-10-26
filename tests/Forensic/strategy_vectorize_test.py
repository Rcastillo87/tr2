"""
Vectorización de estrategias: la versión nueva debe dar EXACTAMENTE las mismas señales que la guardada
en la DB, sobre datos reales. Además mide el tiempo y si las señales dependen de dónde empieza la ventana
de datos (paper/real calculan sobre las últimas ~500 velas; el backtest sobre todo el rango).
Solo lectura: no modifica la estrategia en la DB.

Uso (desde python-engine/):
  venv/bin/python ../tests/Forensic/strategy_vectorize_test.py "Reversión a la Media" /root/patches/strategies/mean_reversion_v2.py
  venv/bin/python ../tests/Forensic/strategy_vectorize_test.py "VWAP Reversión" /root/patches/strategies/vwap_reversion_v2.py
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402
import numpy as np  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import load_ohlcv  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402
from collectors.broker_resolver import resolve_backtest_source  # noqa: E402

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
COMBOS = ["BTCUSDT:60", "ETHUSDT:60", "SOLUSDT:15", "LINKUSDT:240", "SUIUSDT:5"]
LIVE_WINDOW = 500  # velas que usan paper/real


def signals(code: str, cfg: dict, df, symbol: str, interval: str):
    s = build_strategy({'strategy_code': code, 'strategy_config': cfg, 'symbol': symbol, 'interval': interval})
    t0 = time.perf_counter()
    out = s.generate_signals(s.prepare(df))
    return out['signal'].fillna(0).astype(int).to_numpy(), time.perf_counter() - t0


async def main() -> int:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    name, new_path = sys.argv[1], Path(sys.argv[2])
    new_code = new_path.read_text(encoding='utf-8')
    fails = 0
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=2)
    try:
        row = await pool.fetchrow("SELECT id, name, code, config FROM strategies WHERE name = $1", name)
        if not row:
            sys.exit(f"No existe la estrategia '{name}'")
        cfg = json.loads(row['config']) if isinstance(row['config'], str) else (row['config'] or {})
        print(f"Estrategia #{row['id']} '{row['name']}'  config={cfg}")
        end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=730)
        for combo in COMBOS:
            symbol, _, interval = combo.partition(':')
            src = await resolve_backtest_source(pool, symbol, interval, start, end)
            if src is None:
                print(f"  {combo:13} sin datos")
                continue
            df = await load_ohlcv(pool, symbol, interval, src.broker, start, end)
            old, t_old = signals(row['code'], cfg, df, symbol, interval)
            new, t_new = signals(new_code, cfg, df, symbol, interval)
            diff = np.flatnonzero(old != new)
            ok = len(diff) == 0
            fails += not ok
            print(f"  {'PASS' if ok else 'FAIL'} {combo:13} velas={len(df):>7} señales={int((old != 0).sum()):>6} "
                  f"diferencias={len(diff)}  v1={t_old:6.2f}s  v2={t_new:6.3f}s  (x{t_old / max(t_new, 1e-6):.0f})")
            for i in diff[:3]:
                print(f"         {df['time'].iloc[i]}: v1={old[i]} v2={new[i]}")

            # ¿La señal de una vela depende de dónde empieza la ventana? (paper/real usan las últimas 500)
            tail = df.iloc[-(LIVE_WINDOW + 50):].reset_index(drop=True)
            moved = 0
            for k in range(50):  # 50 ventanas consecutivas de 500 velas, como 50 ticks seguidos en vivo
                win = tail.iloc[k:k + LIVE_WINDOW].reset_index(drop=True)
                live, _ = signals(new_code, cfg, win, symbol, interval)
                moved += int(live[-1] != new[len(df) - (LIVE_WINDOW + 50) + k + LIVE_WINDOW - 1])
            print(f"         vivo vs backtest (última vela de 50 ventanas de {LIVE_WINDOW}): {moved} señales distintas")
    finally:
        await pool.close()
    print('\nRESULTADO:', 'TODO OK (señales idénticas)' if fails == 0 else f'{fails} FALLO(S)')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

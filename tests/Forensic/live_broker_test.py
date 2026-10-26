"""
Prueba forense del paso 8a (solo lectura): qué fuente usa cada config activa en vivo.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/live_broker_test.py
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path.cwd() / '.env')  # el .env de python-engine, no el de la carpeta del script

from collectors.broker_resolver import resolve_live_broker  # noqa: E402

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")


async def main() -> int:
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3)
    fails = 0
    try:
        configs = await pool.fetch(
            "SELECT DISTINCT symbol, interval FROM paper_strategy_configs WHERE active ORDER BY 1, 2")
        now = datetime.now(timezone.utc)
        for c in configs:
            symbol, interval = c['symbol'], c['interval']
            broker = await resolve_live_broker(pool, symbol, interval)
            minute = await resolve_live_broker(pool, symbol, '1', require_fresh=False)
            last = await pool.fetchval(
                "SELECT max(time) FROM ohlcv_data WHERE broker = $1 AND symbol = $2 AND interval = $3",
                broker, symbol, interval) if broker else None
            ok = broker is not None
            fails += 0 if ok else 1
            lag = f"{(now - last).total_seconds() / 60:.0f} min" if last else "-"
            print(f"{'PASS' if ok else 'FAIL'}  {symbol:9} {interval:>4}  fuente={broker or 'NINGUNA':15} "
                  f"ultima_vela={last:%Y-%m-%d %H:%M} retraso={lag:>8}  1m={minute}" if last else
                  f"FAIL  {symbol:9} {interval:>4}  sin fuente fresca  1m={minute}")
    finally:
        await pool.close()
    print("\nRESULTADO: TODO OK" if fails == 0 else f"\nRESULTADO: {fails} FALLO(S)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

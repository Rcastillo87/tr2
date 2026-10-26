"""
Prueba forense del paso 9c. Escribe en ohlcv_data SOLO velas oficiales de Bybit
(las mismas que guardaría el collector), por lo que no hay nada que revertir.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_upsert_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path.cwd() / '.env')

from collectors.ohlcv_collector import BYBIT_LIMIT, OhlcvCollector  # noqa: E402

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
SYMBOL, INTERVAL = 'BTCUSDT', '60'


async def main() -> int:
    fails = 0

    def check(name: str, ok: bool, detail: str = '') -> None:
        nonlocal fails
        fails += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + detail if detail else ''}")

    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3)
    try:
        col = OhlcvCollector(pool)
        check('BYBIT_LIMIT = 1000', BYBIT_LIMIT == 1000, str(BYBIT_LIMIT))

        # 1. Velas cerradas de las últimas 6 h desde la API oficial
        now = datetime.now(timezone.utc)
        bars = await col.fetch_from_bybit(SYMBOL, INTERVAL, int((now - timedelta(hours=6)).timestamp()), int(now.timestamp()))
        closed_cutoff = now.replace(minute=0, second=0, microsecond=0)
        closed = [b for b in bars if b['time'] < closed_cutoff]
        check('API devolvió velas cerradas', len(closed) >= 5, f"{len(closed)} velas")

        times = [b['time'] for b in closed]
        before = {r['time']: r for r in await pool.fetch(
            "SELECT time, open, high, low, close FROM ohlcv_data WHERE broker='bybit' AND symbol=$1 AND interval=$2 AND time = ANY($3)",
            SYMBOL, INTERVAL, times)}
        stale = sum(1 for b in closed if b['time'] in before and float(before[b['time']]['high']) != b['high'])
        print(f"      velas guardadas que difieren de la API antes del fix: {stale}/{len(closed)}")

        # 2. UPSERT repara; segunda pasada no escribe nada
        w1 = await col.save_bars(closed, broker='bybit')
        w2 = await col.save_bars(closed, broker='bybit')
        check('1ª pasada escribe las velas distintas', w1 >= stale, f"escritas={w1}")
        check('2ª pasada idempotente (0 escrituras)', w2 == 0, f"escritas={w2}")

        after = {r['time']: r for r in await pool.fetch(
            "SELECT time, open, high, low, close FROM ohlcv_data WHERE broker='bybit' AND symbol=$1 AND interval=$2 AND time = ANY($3)",
            SYMBOL, INTERVAL, times)}
        mismatch = [b['time'] for b in closed
                    if b['time'] not in after or any(abs(float(after[b['time']][k]) - b[k]) > 1e-6
                                                     for k in ('open', 'high', 'low', 'close'))]
        check('DB idéntica a la API tras el UPSERT', not mismatch, f"distintas={len(mismatch)}")

        # 3. Última vela por broker (antes mezclaba fuentes)
        xb = await col.get_last_timestamp('XRPUSDT', '60', 'bybit')
        xv = await col.get_last_timestamp('XRPUSDT', '60', 'binance_vision')
        check('get_last_timestamp separa brokers', xb is not None and xv is not None and xb != xv,
              f"bybit={xb:%Y-%m-%d %H:%M} binance_vision={xv:%Y-%m-%d %H:%M}" if xb and xv else f"{xb} {xv}")
    finally:
        await pool.close()

    print("\nRESULTADO: TODO OK" if fails == 0 else f"\nRESULTADO: {fails} FALLO(S)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

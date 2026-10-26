"""
Diagnóstico forense del paso 8d (solo lectura): para cada backtest guardado,
qué fuente usaría ahora el motor, qué cobertura real tiene y si las velas de
1m se usarían o no. Uso: cd python-engine && venv/bin/python ../tests/Forensic/backtest_coverage_test.py
"""
import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import parse_range  # noqa: E402
from collectors.broker_resolver import coverage_by_broker, interval_delta, pick_best_source  # noqa: E402

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")


async def main() -> int:
    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3)
    errors = 0
    try:
        backtests = await pool.fetch("SELECT id, symbols, interval, months, config_params FROM backtests ORDER BY id")
        for bt in backtests:
            params = json.loads(bt['config_params']) if isinstance(bt['config_params'], str) else bt['config_params']
            symbols = json.loads(bt['symbols']) if isinstance(bt['symbols'], str) else bt['symbols']
            start, end = parse_range(params.get('start_date'), params.get('end_date'))
            print(f"\n=== Backtest #{bt['id']}  intervalo={bt['interval']}  {bt['months']} meses  "
                  f"rango={start:%Y-%m-%d} → {end:%Y-%m-%d} (fin exclusivo)")
            for symbol in symbols:
                try:
                    candidates = await coverage_by_broker(pool, symbol, bt['interval'], start, end)
                    main = pick_best_source(candidates)
                    if main is None:
                        print(f"  {symbol:9} SIN DATOS")
                        continue
                    others = ", ".join(f"{c.broker}={c.bars}" for c in candidates if c is not main) or "-"
                    print(f"  {symbol:9} fuente={main.broker:15} velas={main.bars:>7} "
                          f"({main.first_bar:%Y-%m-%d} → {main.last_bar:%Y-%m-%d})  otras: {others}")
                    for p in main.problems():
                        print(f"            {p}")
                    if interval_delta(bt['interval']) >= timedelta(hours=1):
                        data_end = main.last_bar + interval_delta(bt['interval'])
                        minute = pick_best_source(await coverage_by_broker(pool, symbol, '1', main.first_bar, data_end))
                        if minute and minute.covers(main.first_bar, data_end):
                            print(f"            1m: SE USA ({minute.broker}, {minute.completeness * 100:.1f}% completo)")
                        else:
                            have = (f"{minute.first_bar:%Y-%m-%d} → {minute.last_bar:%Y-%m-%d}" if minute else "ninguna")
                            print(f"            1m: NO se usa (disponible: {have}) -> vela grande SL primero")
                except Exception as e:  # diagnóstico: reportar y seguir
                    errors += 1
                    print(f"  {symbol:9} ERROR {type(e).__name__}: {e}")
    finally:
        await pool.close()
    print("\nRESULTADO: TODO OK" if errors == 0 else f"\nRESULTADO: {errors} ERROR(ES)")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

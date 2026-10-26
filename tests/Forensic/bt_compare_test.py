"""
Diagnóstico del paso 14a (solo lectura): re-ejecuta un backtest guardado con el motor V3
sobre datos reales y lo compara con las métricas guardadas (motor anterior, ~30% del período).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/bt_compare_test.py [backtest_id]
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import BacktestRequest, run_backtest  # noqa: E402

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
BT_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 75


def _j(value):
    return json.loads(value) if isinstance(value, str) else value


async def main() -> None:
    conn = await asyncpg.connect(DSN)
    row = await conn.fetchrow("SELECT symbols, config_params, metrics, months FROM backtests WHERE id=$1", BT_ID)
    await conn.close()
    cfg, symbols, old = _j(row['config_params']), _j(row['symbols']), _j(row['metrics']) or {}
    print(f"Backtest #{BT_ID} ({row['months']} meses), motor anterior: trades={old.get('total_trades')} "
          f"WR={old.get('win_rate')} PF={old.get('profit_factor')} prom.mensual={old.get('avg_monthly_pnl')} "
          f"consistencia={old.get('consist_pct')}")
    total = 0
    for sym in symbols:
        req = BacktestRequest(**{**cfg, 'symbol': sym, 'monthly_breakdown': True})
        t0 = time.monotonic()
        out = await run_backtest(req)
        elapsed = time.monotonic() - t0
        r = out['result']
        m = r['aggregate_metrics']
        months = r.get('monthly_breakdown', [])
        empty = sum(1 for x in months if x['total_trades'] == 0)
        used_1m = not any('1 minuto' in w for w in out['warnings'])
        total += m['total_trades']
        print(f"  {sym:9} V3: trades={m['total_trades']:<4} WR={m['win_rate']:<6} PF={m['profit_factor']:<6} "
              f"ret%={m['total_return_pct']:<8} DD%={m['max_drawdown_pct']:<6} meses={len(months)} "
              f"(sin trades: {empty}) 1m={'sí' if used_1m else 'no'} {elapsed:.1f}s")
        for w in r.get('window_results', []):
            print(f"            tramo {w['window']}: trades={w['total_trades']:<3} PF={w['profit_factor']} ret%={w['total_return_pct']}")
    print(f"\nTotal V3: {total} operaciones en el período COMPLETO "
          f"(motor anterior: {old.get('total_trades')} en ~30% del período)")


if __name__ == "__main__":
    asyncio.run(main())

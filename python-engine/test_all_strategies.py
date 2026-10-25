import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from api.v1.backtest import run_backtest, BacktestRequest

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test_all():
    pool = await asyncpg.create_pool(DB_DSN)
    async with pool.acquire() as conn:
        strategies = await conn.fetch("SELECT name, code FROM strategies WHERE active = true")
    await pool.close()

    print("🚀 PROBANDO TODAS LAS ESTRATEGIAS (BTCUSDT, H4, 6 meses)...\n")

    for strat in strategies:
        name = strat['name']
        code = strat['code']
        
        req = BacktestRequest(
            strategy=name,
            strategy_code=code,
            strategy_config={},
            symbol="BTCUSDT",
            interval="240",
            start_date="2026-04-01",
            end_date="2026-10-24",
            sl_pct=1.0, tp_pct=1.5, be_pct=2.0, max_duration=24,
            regime_filter=False,
            initial_balance=10000, risk_per_trade_pct=1.0,
            commission_pct=0.055,
            walk_forward=False, n_windows=1
        )
        
        try:
            res = await run_backtest(req)
            metrics = res.get('result', {}).get('aggregate_metrics', {})
            trades = metrics.get('total_trades', 0)
            print(f"✅ OK    | {name.ljust(25)} -> {trades:3} trades")
        except Exception as e:
            print(f"❌ FALLO | {name.ljust(25)} -> {str(e)}")

asyncio.run(test_all())

import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from api.v1.backtest import run_backtest, BacktestRequest

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test():
    pool = await asyncpg.create_pool(DB_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT code FROM strategies WHERE name = 'VWAP Reversión'")
        code = row['code']
    await pool.close()

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "HYPEUSDT", "SUIUSDT"]
    print("🚀 Ejecutando run_backtest directamente (H4, Walk-Forward = True)...\n")

    for sym in symbols:
        req = BacktestRequest(
            strategy="VWAP Reversión",
            strategy_code=code,
            strategy_config={"mode": "reversion", "vwap_std_entry": 1.0, "zone_bars": 4, "regime_filter": False},
            symbol=sym,
            interval="240",
            start_date="2026-04-01",
            end_date="2026-10-24",
            sl_pct=1.0,
            tp_pct=1.5,
            be_pct=2.0,
            max_duration=24,
            regime_filter=False,
            initial_balance=10000,
            risk_per_trade_pct=1.0,
            commission_pct=0.055,
            walk_forward=True,
            n_windows=5
        )
        
        try:
            res = await run_backtest(req)
            metrics = res.get('result', {}).get('aggregate_metrics', {})
            trades = metrics.get('total_trades', 0)
            status = "✅ OK" if trades > 0 else "❌ 0 TRADES"
            print(f"{status} | {sym.ljust(8)} -> {trades:3} trades")
        except Exception as e:
            print(f"❌ ERROR | {sym.ljust(8)} -> {str(e)}")

asyncio.run(test())

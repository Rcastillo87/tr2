import asyncio
import httpx
import asyncpg
import os
import subprocess
from dotenv import load_dotenv

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test_api():
    api_key = subprocess.check_output("cd /home/tr2/htdocs/tr2.srv685835.hstgr.cloud && php artisan tinker --execute=\"echo config('trading.python_internal_api_key');\"", shell=True).decode().strip()

    pool = await asyncpg.create_pool(DB_DSN)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT code FROM strategies WHERE name = 'VWAP Reversión'")
        code = row['code']
    await pool.close()

    payload = {
        "strategy": "VWAP Reversión",
        "strategy_code": code,
        "strategy_config": {
            "mode": "reversion",
            "vwap_std_entry": 1.0,
            "zone_bars": 4,
            "regime_filter": False
        },
        "interval": "240",
        "start_date": "2026-04-01",
        "end_date": "2026-10-24",
        "sl_pct": 1.0,
        "tp_pct": 1.5,
        "be_pct": 2.0,
        "max_duration": 24,
        "regime_filter": False,
        "initial_balance": 10000,
        "risk_per_trade_pct": 1.0,
        "commission_pct": 0.055,
        "walk_forward": False,  # 🔥 LA CLAVE: Desactivamos el Walk Forward
        "n_windows": 1
    }

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "HYPEUSDT", "SUIUSDT"]
    print("🚀 Simulando petición de Laravel (walk_forward=False)...\n")

    async with httpx.AsyncClient(timeout=60) as client:
        for sym in symbols:
            payload["symbol"] = sym
            try:
                response = await client.post(
                    "http://127.0.0.1:8002/v1/backtest/run",
                    json=payload,
                    headers={"X-Internal-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    res = response.json()
                    metrics = res.get('result', {}).get('aggregate_metrics', {})
                    trades = metrics.get('total_trades', 0)
                    wr = metrics.get('win_rate', 0)
                    ret = metrics.get('total_return_pct', 0)
                    
                    status = "✅ OK" if trades > 0 else "❌ 0 TRADES"
                    print(f"{status} | {sym.ljust(8)} -> {trades:3} trades | WR: {wr:.2f}% | Ret: {ret:.2f}%")
                else:
                    print(f"❌ ERROR | {sym.ljust(8)} -> {response.status_code} - {response.text[:80]}")
            except Exception as e:
                print(f"❌ EXCEPCIÓN | {sym.ljust(8)} -> {str(e)}")

asyncio.run(test_api())

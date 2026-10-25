import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from collectors.broker_resolver import resolve_broker

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test():
    pool = await asyncpg.create_pool(DB_DSN)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'HYPEUSDT', 'SUIUSDT']
    
    for sym in symbols:
        # ¿Qué broker elige el sistema?
        try:
            broker = await resolve_broker(pool, sym)
        except Exception as e:
            broker = f"ERROR: {e}"
            
        print(f"\n📈 {sym}")
        print(f"   -> Broker que elige el motor: {broker}")
        
        # ¿En qué brokers HAY datos reales?
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT broker, COUNT(*) as count FROM ohlcv_data WHERE symbol = $1 AND interval = '240' GROUP BY broker", 
                sym
            )
            if rows:
                for r in rows:
                    print(f"   -> Datos disponibles en: {r['broker']} ({r['count']} velas)")
            else:
                print("   -> ❌ NO HAY DATOS en ningún broker")

    await pool.close()

asyncio.run(test())

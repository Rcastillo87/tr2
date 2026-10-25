import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from api.v1.backtest import load_ohlcv
from collectors.broker_resolver import resolve_broker

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test():
    pool = await asyncpg.create_pool(DB_DSN)
    
    print("=== 1. PROBANDO RESOLVER BROKER PARA BTC ===")
    broker = await resolve_broker(pool, 'BTCUSDT')
    print(f"Broker elegido por el sistema: {broker}")
    
    print("\n=== 2. CARGANDO DATOS CON LA MISMA FUNCIÓN DE LA API ===")
    try:
        # Simulamos exactamente los parámetros que envía la UI (Abril a Octubre)
        df = await load_ohlcv(pool, 'BTCUSDT', '240', '2026-04-01', '2026-10-24', broker=None)
        print(f"Velas cargadas: {len(df)}")
        if len(df) > 0:
            print(f"Primera vela: {df['time'].iloc[0]}")
            print(f"Última vela:  {df['time'].iloc[-1]}")
            print(f"Columnas: {df.columns.tolist()}")
            print("\n¿Tiene volumen el DataFrame?")
            print(df[['time', 'close', 'volume']].head(3))
        else:
            print("❌ El DataFrame está VACÍO. La función load_ohlcv no está encontrando datos.")
    except Exception as e:
        print(f"❌ ERROR en load_ohlcv: {e}")

    print("\n=== 3. VERIFICANDO SI LOS DATOS EXISTEN EN LA DB ===")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as count FROM ohlcv_data WHERE symbol = 'BTCUSDT' AND interval = '240' AND broker = 'binance_vision' AND time >= '2026-04-01' AND time <= '2026-10-24'"
        )
        print(f"Velas de BTC en binance_vision en ese rango de fechas: {row['count']}")

    await pool.close()

asyncio.run(test())

import asyncio
import pandas as pd
import asyncpg
import os
from dotenv import load_dotenv
from trading.paper_trader import PaperTrader
from collectors.regime_detector import detect_regime

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test_regime():
    pool = await asyncpg.create_pool(DB_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT time, open, high, low, close, volume FROM ohlcv_data WHERE symbol = 'BTCUSDT' AND interval = '240' ORDER BY time DESC LIMIT 500")
        df = pd.DataFrame([dict(r) for r in rows])
        df = df.sort_values('time')

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    # Calcular régimen para la última vela
    last_rows = df.tail(100).copy()
    
    # Simulamos la función interna de regime
    from indicators.regime_indicators import calculate_adx
    try:
        adx = calculate_adx(last_rows['high'], last_rows['low'], last_rows['close'], period=14)
        last_adx = adx.iloc[-1]
        print(f'ADX actual de BTCUSDT: {last_adx:.2f}')
        
        if last_adx > 25:
            print("Régimen: TRENDING (Tendencia fuerte)")
        elif last_adx < 20:
            print("Régimen: RANGING (Lateral)")
        else:
            print("Régimen: AMBIGUO (Zona gris)")
    except Exception as e:
        print(f"Error calculando ADX: {e}")

asyncio.run(test_regime())

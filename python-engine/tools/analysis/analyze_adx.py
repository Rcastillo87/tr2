"""
Script de analisis: calcula el ADX historico (H1) para cada simbolo
y muestra estadisticas de distribucion, para decidir si el umbral
ADX > 25 para TRENDING es razonable dado el comportamiento real del mercado.

Uso: python3 analyze_adx.py
(ejecutar desde python-engine/, con el venv activado)
"""

import asyncio
import asyncpg
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

SYMBOLS = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')
INTERVAL = '60'


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high  = df['high']
    low   = df['low']
    close = df['close']

    prev_high  = high.shift(1)
    prev_low   = low.shift(1)
    prev_close = close.shift(1)

    plus_dm  = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    plus_dm  = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    plus_di  = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return adx


async def analyze_symbol(pool, symbol: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND interval = $2
            ORDER BY time ASC
            """,
            symbol, INTERVAL
        )

    if not rows:
        print(f"{symbol}: sin datos")
        return

    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    adx = calculate_adx(df).dropna()

    if len(adx) == 0:
        print(f"{symbol}: no hay suficientes velas para calcular ADX")
        return

    total = len(adx)
    above_25 = (adx > 25).sum()
    above_20 = (adx > 20).sum()
    above_22 = (adx > 22).sum()

    print(f"\n=== {symbol} (H1, {total} velas con ADX calculado) ===")
    print(f"  Rango de fechas: {df['time'].iloc[0]} a {df['time'].iloc[-1]}")
    print(f"  ADX actual:      {adx.iloc[-1]:.2f}")
    print(f"  ADX promedio:    {adx.mean():.2f}")
    print(f"  ADX mediana:     {adx.median():.2f}")
    print(f"  ADX max:         {adx.max():.2f}")
    print(f"  ADX min:         {adx.min():.2f}")
    print(f"  % velas con ADX > 25: {above_25 / total * 100:.1f}% ({above_25} velas)")
    print(f"  % velas con ADX > 22: {above_22 / total * 100:.1f}% ({above_22} velas)")
    print(f"  % velas con ADX > 20: {above_20 / total * 100:.1f}% ({above_20} velas)")


async def main():
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)

    for symbol in SYMBOLS:
        await analyze_symbol(pool, symbol)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

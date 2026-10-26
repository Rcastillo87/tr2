"""
Analiza el ADX y la volatilidad (ATR) de BTCUSDT H1 en meses especificos,
para entender por que la estrategia VWAP Tendencia (4TP) perdio en
abril 2025, julio 2025 y diciembre 2025.
"""

import asyncio
import asyncpg
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

SYMBOL = "BTCUSDT"
INTERVAL = "60"

# Meses a analizar: (year, month, label)
TARGET_MONTHS = [
    (2025, 4, "Abril 2025 (peor mes, -13.13%)"),
    (2025, 7, "Julio 2025 (-6.05%)"),
    (2025, 12, "Diciembre 2025 (-8.88%)"),
    (2025, 11, "Noviembre 2025 (mejor mes, +19.11% — control)"),
]


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df['high'], df['low'], df['close']
    prev_high, prev_low, prev_close = high.shift(1), low.shift(1), close.shift(1)

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


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


async def main():
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND interval = $2
            ORDER BY time ASC
            """,
            SYMBOL, INTERVAL
        )

    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df['time'] = pd.to_datetime(df['time'])

    df['adx'] = calculate_adx(df)
    df['atr'] = calculate_atr(df)
    df['atr_avg'] = df['atr'].rolling(50).mean()

    for year, month, label in TARGET_MONTHS:
        mask = (df['time'].dt.year == year) & (df['time'].dt.month == month)
        month_df = df[mask]

        if month_df.empty:
            print(f"\n=== {label} === SIN DATOS")
            continue

        adx_mean = month_df['adx'].mean()
        adx_above_25_pct = (month_df['adx'] > 25).sum() / len(month_df) * 100

        atr_ratio = (month_df['atr'] / month_df['atr_avg']).mean()

        price_start = month_df['close'].iloc[0]
        price_end = month_df['close'].iloc[-1]
        price_change_pct = (price_end - price_start) / price_start * 100

        # Volatilidad intra-mes: cuantas veces el precio cruzo su propia media movil de 20 (proxy de "whipsaw")
        month_df = month_df.copy()
        month_df['sma20'] = month_df['close'].rolling(20).mean()
        month_df['above_sma'] = month_df['close'] > month_df['sma20']
        crosses = (month_df['above_sma'] != month_df['above_sma'].shift(1)).sum()

        print(f"\n=== {label} ===")
        print(f"  Velas: {len(month_df)}")
        print(f"  ADX promedio: {adx_mean:.2f}")
        print(f"  % tiempo con ADX > 25 (TRENDING): {adx_above_25_pct:.1f}%")
        print(f"  ATR actual / ATR promedio: {atr_ratio:.2f}x")
        print(f"  Cambio de precio en el mes: {price_change_pct:+.2f}%")
        print(f"  Cruces de SMA20 (whipsaw): {crosses}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
Corre el backtest (sin walk-forward, motor simple) de VWAP Tendencia BTC
con la configuracion ganadora, y muestra el detalle de cada trade en
abril y julio 2025 para entender por que perdio en meses de tendencia alcista.
"""

import asyncio
import asyncpg
import pandas as pd
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, '.')

from backtesting.strategies.vwap_strategy import VwapStrategy
from backtesting.engine import BacktestEngine

load_dotenv()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

SYMBOL = "BTCUSDT"
INTERVAL = "60"

TARGET_MONTHS = ["2025-04", "2025-07"]


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

    params = {
        'symbol': SYMBOL, 'interval': INTERVAL, 'mode': 'trend_follow',
        'sl_pct': 1.0, 'tp_pct': 1.0, 'tp2_pct': 2.0, 'tp3_pct': 3.0, 'tp4_pct': 4.0,
        'be_pct': 1.8, 'max_duration': 24, 'regime_filter': True,
        'allowed_regimes': ['TRENDING'],
    }

    strategy = VwapStrategy(params)
    engine = BacktestEngine(strategy=strategy, df=df, initial_balance=10000.0, risk_per_trade_pct=1.0)
    result = engine.run()

    trades_df = pd.DataFrame(result['trades'])
    trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
    trades_df['month'] = trades_df['entry_time'].dt.strftime('%Y-%m')

    for month in TARGET_MONTHS:
        month_trades = trades_df[trades_df['month'] == month]

        print(f"\n=== {month} - {len(month_trades)} trades ===")
        longs = (month_trades['side'] == 'long').sum()
        shorts = (month_trades['side'] == 'short').sum()
        long_pnl = month_trades[month_trades['side'] == 'long']['pnl_pct'].sum()
        short_pnl = month_trades[month_trades['side'] == 'short']['pnl_pct'].sum()

        print(f"  LONG: {longs} trades, pnl acumulado: {long_pnl:.2f}%")
        print(f"  SHORT: {shorts} trades, pnl acumulado: {short_pnl:.2f}%")

        reason_counts = month_trades['exit_reason'].value_counts()
        print(f"  Razones de cierre: {dict(reason_counts)}")

        print(f"\n  Detalle de trades:")
        for _, t in month_trades.iterrows():
            print(f"    {t['entry_time']} | {t['side'].upper():5} | entry={t['entry_price']:.2f} | "
                  f"exit={t['exit_price']:.2f} | pnl={t['pnl_pct']:+.3f}% | reason={t['exit_reason']}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

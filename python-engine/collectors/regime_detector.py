"""
Market Regime Detector V2
Calcula ADX, ATR, BB Width sobre velas H1 y clasifica el régimen de mercado.
Guarda el resultado en Redis para que los Signal Jobs lo consulten.
"""

import asyncpg
import pandas as pd
import logging
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from indicators.regime_indicators import (
    calculate_atr,
    calculate_adx,
    calculate_bb_width,
    classify_regime,
)

load_dotenv()

logger = logging.getLogger(__name__)

SYMBOLS = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')

REGIME_INTERVAL = '60'   # H1
LOOKBACK_BARS   = 100    # velas necesarias para indicadores estables
ATR_AVG_WINDOW  = 50      # ventana para promedio histórico de ATR
BB_AVG_WINDOW   = 50


class RegimeDetector:

    def __init__(self, pool: asyncpg.Pool, redis_client):
        self.pool  = pool
        self.redis = redis_client

    async def get_bars(self, symbol: str) -> pd.DataFrame:
        """Obtiene las últimas N velas H1 de la DB."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                ORDER BY time DESC
                LIMIT $3
                """,
                symbol, REGIME_INTERVAL, LOOKBACK_BARS
            )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df = df.iloc[::-1].reset_index(drop=True)  # orden ascendente

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    async def detect(self, symbol: str) -> dict | None:
        """Calcula el régimen actual para un símbolo."""
        df = await self.get_bars(symbol)

        if len(df) < ATR_AVG_WINDOW + 14:
            logger.warning(f"[{symbol}] Datos insuficientes para calcular régimen ({len(df)} velas)")
            return None

        df['atr']      = calculate_atr(df)
        df['adx']      = calculate_adx(df)
        df['bb_width'] = calculate_bb_width(df)

        last = df.iloc[-1]

        atr_avg      = df['atr'].tail(ATR_AVG_WINDOW).mean()
        bb_width_avg = df['bb_width'].tail(BB_AVG_WINDOW).mean()

        regime = classify_regime(
            adx=last['adx'],
            atr=last['atr'],
            atr_avg=atr_avg,
            bb_width=last['bb_width'],
            bb_width_avg=bb_width_avg,
        )

        result = {
            "symbol":       symbol,
            "regime":       regime,
            "adx":          round(float(last['adx']), 2),
            "atr":          round(float(last['atr']), 4),
            "atr_avg":      round(float(atr_avg), 4),
            "bb_width":     round(float(last['bb_width']), 4),
            "bb_width_avg": round(float(bb_width_avg), 4),
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "candle_time":  last['time'].isoformat(),
        }

        return result

    async def detect_all(self) -> dict:
        """Calcula y guarda el régimen para todos los símbolos configurados."""
        results = {}

        for symbol in SYMBOLS:
            try:
                result = await self.detect(symbol)
                if result:
                    key = f"regime:{symbol}"
                    await self.redis.set(key, json.dumps(result))
                    results[symbol] = result
                else:
                    results[symbol] = {"error": "datos insuficientes"}
            except Exception as e:
                logger.error(f"[{symbol}] Error calculando régimen: {e}")
                results[symbol] = {"error": str(e)}

        return results

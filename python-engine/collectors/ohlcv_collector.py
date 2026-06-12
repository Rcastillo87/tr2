"""
OHLCV Collector — Data Collector V2
Recolecta y almacena velas históricas y en tiempo real desde Bybit.
"""

import asyncio
import asyncpg
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
SYMBOLS   = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')
INTERVALS = os.getenv('INTERVALS', '1,5,15,60').split(',')

# Máximo de velas por llamada a Bybit
BYBIT_LIMIT = 200

# Cuántos días de historia descargar en carga inicial
HISTORY_DAYS = 730  # 2 años


class OhlcvCollector:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ─────────────────────────────────────────────
    # Fetch desde Bybit
    # ─────────────────────────────────────────────

    async def fetch_from_bybit(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
    ) -> list[dict]:
        """Obtiene velas OHLCV de Bybit entre start_ts y end_ts (unix segundos)."""
        all_bars = []
        end_ms   = end_ts * 1000
        start_ms = start_ts * 1000

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                r = await client.get(
                    f'{BYBIT_BASE_URL}/v5/market/kline',
                    params={
                        'category': 'linear',
                        'symbol':   symbol,
                        'interval': interval,
                        'limit':    BYBIT_LIMIT,
                        'end':      end_ms,
                    }
                )
                r.raise_for_status()
                bars = r.json().get('result', {}).get('list', [])

                if not bars:
                    break

                stop = False
                for b in bars:
                    ts = int(b[0])
                    if ts < start_ms:
                        stop = True
                        break
                    all_bars.append({
                        'time':   datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                        'symbol': symbol,
                        'interval': interval,
                        'open':   float(b[1]),
                        'high':   float(b[2]),
                        'low':    float(b[3]),
                        'close':  float(b[4]),
                        'volume': float(b[5]),
                    })

                if stop:
                    break

                new_end = int(bars[-1][0]) - 1
                if new_end >= end_ms:
                    break
                end_ms = new_end

                await asyncio.sleep(0.1)  # respetar rate limit

        all_bars.reverse()
        return all_bars

    # ─────────────────────────────────────────────
    # Guardar en DB
    # ─────────────────────────────────────────────

    async def save_bars(self, bars: list[dict]) -> int:
        """Inserta velas en ohlcv_data. Ignora duplicados."""
        if not bars:
            return 0

        async with self.pool.acquire() as conn:
            result = await conn.executemany(
                """
                INSERT INTO ohlcv_data
                    (time, symbol, interval, open, high, low, close, volume)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, interval, time)
                DO NOTHING
                """,
                [
                    (
                        b['time'], b['symbol'], b['interval'],
                        b['open'], b['high'], b['low'],
                        b['close'], b['volume'],
                    )
                    for b in bars
                ]
            )
        return len(bars)

    # ─────────────────────────────────────────────
    # Último timestamp guardado
    # ─────────────────────────────────────────────

    async def get_last_timestamp(self, symbol: str, interval: str) -> Optional[datetime]:
        """Retorna el timestamp de la vela más reciente guardada."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(time) as last_time
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                """,
                symbol, interval
            )
            return row['last_time'] if row else None

    # ─────────────────────────────────────────────
    # Carga histórica inicial
    # ─────────────────────────────────────────────

    async def initial_load(self, symbol: str, interval: str) -> int:
        """Descarga 2 años de historia si no hay datos previos."""
        last = await self.get_last_timestamp(symbol, interval)

        if last:
            logger.info(f"[{symbol}/{interval}] Ya tiene datos hasta {last} — saltando carga inicial")
            return 0

        logger.info(f"[{symbol}/{interval}] Iniciando carga histórica de {HISTORY_DAYS} días...")

        now      = int(datetime.now(timezone.utc).timestamp())
        start_ts = now - (HISTORY_DAYS * 24 * 60 * 60)

        bars  = await self.fetch_from_bybit(symbol, interval, start_ts, now)
        saved = await self.save_bars(bars)

        logger.info(f"[{symbol}/{interval}] Carga inicial: {saved} velas guardadas")
        return saved

    # ─────────────────────────────────────────────
    # Actualización continua
    # ─────────────────────────────────────────────

    async def update(self, symbol: str, interval: str) -> int:
        """Descarga solo las velas nuevas desde el último registro."""
        last = await self.get_last_timestamp(symbol, interval)

        if not last:
            return await self.initial_load(symbol, interval)

        start_ts = int(last.timestamp())
        end_ts   = int(datetime.now(timezone.utc).timestamp())

        if end_ts - start_ts < 60:
            return 0  # nada nuevo todavía

        bars  = await self.fetch_from_bybit(symbol, interval, start_ts, end_ts)
        saved = await self.save_bars(bars)

        if saved > 0:
            logger.info(f"[{symbol}/{interval}] Actualización: {saved} velas nuevas")

        return saved

    # ─────────────────────────────────────────────
    # Correr todos los símbolos e intervalos
    # ─────────────────────────────────────────────

    async def run_all(self) -> dict:
        """Actualiza todos los símbolos e intervalos configurados."""
        results = {}
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                try:
                    saved = await self.update(symbol, interval)
                    results[f"{symbol}/{interval}"] = saved
                except Exception as e:
                    logger.error(f"[{symbol}/{interval}] Error: {e}")
                    results[f"{symbol}/{interval}"] = -1
        return results

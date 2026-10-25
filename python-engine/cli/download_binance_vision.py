#!/usr/bin/env python3
"""
Importador de Binance Vision → ohlcv_data (broker='binance_vision').

Descarga ZIPs mensuales de https://data.binance.vision y los inserta en
PostgreSQL con broker='binance_vision'. Idempotente (ON CONFLICT DO NOTHING).

Uso:
    python -m cli.download_binance_vision
    python -m cli.download_binance_vision --dry-run        # solo cuenta, no inserta
    python -m cli.download_binance_vision --only BTCUSDT   # un solo símbolo

Constantes editables abajo.
"""
import asyncio
import asyncpg
import argparse
import io
import logging
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import httpx
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# EDITAR AQUÍ
# ═══════════════════════════════════════════════════════════════════════════

# Símbolos a importar (en formato Binance: BTCUSDT, sin slash)
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"]

# Timeframes (formato Binance: '1m', '5m', '15m', '1h', '2h', '4h', '1d')
# Nota: tus otros componentes usan intervalos '1','5','15','60','120','240','D'
# Este script los mapea automáticamente.
INTERVALS = ["1m", "5m", "15m", "1h", "2h", "4h", "1d"]

# Rango mensual (inclusive)
START_YEAR_MONTH = (2024, 6)   # 2024-06
END_YEAR_MONTH   = (2026, 9)   # 2026-09 (el mes en curso no está completo en monthly)

# ═══════════════════════════════════════════════════════════════════════════

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
BROKER = "binance_vision"
BATCH_SIZE = 5000

# Mapeo Binance interval → tu DB interval
INTERVAL_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360",
    "8h": "480", "12h": "720", "1d": "D", "3d": "3D", "1w": "W",
}


def db_dsn() -> str:
    return f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"


async def download_month(client: httpx.AsyncClient, symbol: str, interval: str,
                          year: int, month: int) -> pd.DataFrame | None:
    """Descarga y parsea un mes. None si no existe (par no listado ese mes)."""
    url = f"{BASE_URL}/{symbol}/{interval}/{symbol}-{interval}-{year:04d}-{month:02d}.zip"
    try:
        r = await client.get(url, timeout=60)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        buf = io.BytesIO(r.content)
        with zipfile.ZipFile(buf) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(
                    f, header=None,
                    names=["open_time","open","high","low","close","volume",
                           "close_time","quote_volume","trades",
                           "taker_buy_base","taker_buy_quote","ignore"],
                    dtype={"open_time": "int64","close_time": "int64"},
                )
        return df
    except httpx.HTTPStatusError as e:
        logger.warning(f"[{symbol} {interval} {year}-{month:02d}] HTTP {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"[{symbol} {interval} {year}-{month:02d}] error descarga: {e}")
        return None


def normalize(df: pd.DataFrame, symbol: str, interval_db: str) -> list[tuple]:
    """Convierte el DataFrame a lista de tuplas para insertar.
    Binance open_time viene en milisegundos (o microsegundos en versiones nuevas).
    """
    if df is None or df.empty:
        return []

    # Detectar ms vs µs: si open_time > 10^15, está en µs (después de ~2001 en µs)
    sample = int(df['open_time'].iloc[0])
    divisor = 1_000_000 if sample > 10**14 else 1_000

    rows = []
    for _, r in df.iterrows():
        try:
            ts = datetime.fromtimestamp(int(r['open_time']) / divisor, tz=timezone.utc)
            rows.append((
                ts, BROKER, symbol, interval_db,
                float(r['open']), float(r['high']), float(r['low']),
                float(r['close']), float(r['volume']),
            ))
        except Exception:
            continue
    return rows


async def insert_rows(pool: asyncpg.Pool, rows: list[tuple]) -> int:
    """INSERT con ON CONFLICT DO NOTHING. Devuelve cantidad realmente insertada."""
    if not rows:
        return 0
    async with pool.acquire() as conn:
        total = 0
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            result = await conn.executemany(
                """
                INSERT INTO ohlcv_data
                    (time, broker, symbol, interval, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (broker, symbol, interval, time) DO NOTHING
                """,
                batch,
            )
            # executemany no devuelve count directo; aproximamos por len del batch
            total += len(batch)
        return total


def iterate_months(start: tuple[int,int], end: tuple[int,int]):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="No inserta en DB, solo cuenta")
    parser.add_argument("--only", type=str, default=None, help="Un solo símbolo (ej. BTCUSDT)")
    args = parser.parse_args()

    symbols = [args.only] if args.only else SYMBOLS

    pool = await asyncpg.create_pool(db_dsn(), min_size=2, max_size=4)
    logger.info(f"Iniciando importación: {len(symbols)} símbolos × {len(INTERVALS)} intervals")
    logger.info(f"Rango: {START_YEAR_MONTH} → {END_YEAR_MONTH}")
    logger.info(f"Modo: {'DRY-RUN' if args.dry_run else 'INSERT'}")

    total_descargados = 0
    total_insertados = 0
    missing = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for symbol in symbols:
            for interval in INTERVALS:
                interval_db = INTERVAL_MAP[interval]
                sym_total = 0
                for (y, m) in iterate_months(START_YEAR_MONTH, END_YEAR_MONTH):
                    df = await download_month(client, symbol, interval, y, m)
                    if df is None:
                        missing.append((symbol, interval, y, m))
                        continue
                    rows = normalize(df, symbol, interval_db)
                    if not rows:
                        continue
                    sym_total += len(rows)
                    total_descargados += len(rows)
                    if not args.dry_run:
                        ins = await insert_rows(pool, rows)
                        total_insertados += ins
                    logger.info(f"[{symbol} {interval} {y}-{m:02d}] {len(rows):>6} velas"
                                + ("" if args.dry_run else f" ({ins} nuevas)"))
                logger.info(f"── {symbol} {interval}: {sym_total} velas totales ──")

    await pool.close()

    logger.info("")
    logger.info("═" * 60)
    logger.info(f"✅ Importación completa")
    logger.info(f"   Descargadas: {total_descargados:,} velas")
    if not args.dry_run:
        logger.info(f"   Insertadas:  {total_insertados:,} velas nuevas")
    logger.info(f"   Meses no disponibles (par no listado aún): {len(missing)}")
    if missing[:10]:
        logger.info(f"   Primeros 10: {missing[:10]}")
    logger.info("═" * 60)


if __name__ == "__main__":
    asyncio.run(main())

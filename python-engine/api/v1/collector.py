"""
Endpoint Data Collector V2
"""

import asyncpg
import logging
import os
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from collectors.ohlcv_collector import OhlcvCollector, SYMBOLS, INTERVALS

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


@router.post("/collector/run")
async def run_collector():
    """Ejecuta una actualización de todos los símbolos e intervalos."""
    try:
        pool = await get_pool()
        collector = OhlcvCollector(pool)
        results = await collector.run_all()
        await pool.close()

        return {
            "status": "ok",
            "results": results,
            "total_saved": sum(v for v in results.values() if v >= 0),
        }
    except Exception as e:
        logger.error(f"Collector error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collector/initial-load")
async def initial_load():
    """Ejecuta la carga histórica inicial para todos los símbolos."""
    try:
        pool = await get_pool()
        collector = OhlcvCollector(pool)
        results = {}

        for symbol in SYMBOLS:
            for interval in INTERVALS:
                try:
                    saved = await collector.initial_load(symbol, interval)
                    results[f"{symbol}/{interval}"] = saved
                except Exception as e:
                    logger.error(f"[{symbol}/{interval}] Error en carga inicial: {e}")
                    results[f"{symbol}/{interval}"] = -1

        await pool.close()

        return {
            "status": "ok",
            "results": results,
            "total_saved": sum(v for v in results.values() if v >= 0),
        }
    except Exception as e:
        logger.error(f"Initial load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collector/status")
async def collector_status():
    """Retorna el estado actual de la recolección de datos."""
    try:
        pool = await get_pool()
        collector = OhlcvCollector(pool)
        status = {}

        for symbol in SYMBOLS:
            for interval in INTERVALS:
                last = await collector.get_last_timestamp(symbol, interval)
                status[f"{symbol}/{interval}"] = {
                    "last_candle": last.isoformat() if last else None,
                    "has_data": last is not None,
                }

        await pool.close()

        return {"status": "ok", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

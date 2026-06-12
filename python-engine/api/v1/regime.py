"""
Endpoint Market Regime Detector V2
"""

import asyncpg
import redis.asyncio as redis
import logging
import json
import os
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from collectors.regime_detector import RegimeDetector, SYMBOLS

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379')


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


async def get_redis():
    return redis.from_url(REDIS_URL, decode_responses=True)


@router.post("/regime/run")
async def run_regime_detector():
    """Calcula y guarda el régimen de mercado para todos los símbolos."""
    try:
        pool  = await get_pool()
        rds   = await get_redis()

        detector = RegimeDetector(pool, rds)
        results  = await detector.detect_all()

        await pool.close()
        await rds.close()

        return {"status": "ok", "results": results}
    except Exception as e:
        logger.error(f"Regime detector error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime/status")
async def regime_status():
    """Retorna el régimen actual cacheado en Redis para cada símbolo."""
    try:
        rds = await get_redis()
        results = {}

        for symbol in SYMBOLS:
            cached = await rds.get(f"regime:{symbol}")
            results[symbol] = json.loads(cached) if cached else None

        await rds.close()

        return {"status": "ok", "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime/{symbol}")
async def regime_by_symbol(symbol: str):
    """Retorna el régimen actual de un símbolo específico."""
    try:
        rds = await get_redis()
        cached = await rds.get(f"regime:{symbol.upper()}")
        await rds.close()

        if not cached:
            raise HTTPException(status_code=404, detail=f"No hay datos de régimen para {symbol}")

        return {"status": "ok", "data": json.loads(cached)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

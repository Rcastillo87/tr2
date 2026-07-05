"""
Trading Platform V2 — Python Engine
FastAPI server — solo accesible en 127.0.0.1:8001
"""

import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

logger = logging.getLogger(__name__)

from api.v1.collector import router as collector_router
from api.v1.regime import router as regime_router
from api.v1.backtest import router as backtest_router
from api.v1.paper_trading import router as paper_router
from api.v1.broker import router as broker_router
from api.v1.real_trading import router as real_trading_router
from api.v1.prices import router as prices_router

app = FastAPI(
    title="Trading Platform V2 — Python Engine",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
)

# Middleware de autenticación interna
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY')

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    key = request.headers.get("X-Internal-API-Key")
    if key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await call_next(request)

# Rutas
app.include_router(collector_router, prefix="/v1")
app.include_router(regime_router, prefix="/v1")
app.include_router(backtest_router, prefix="/v1")
app.include_router(paper_router, prefix="/v1")
app.include_router(broker_router, prefix="/v1")
app.include_router(real_trading_router, prefix="/v1")
app.include_router(prices_router, prefix="/v1")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}

"""
Trading Platform V2 — Python Engine
FastAPI server — solo accesible en 127.0.0.1:8002
"""

import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

logging.getLogger('httpx').setLevel(logging.WARNING)  # una línea por request a Bybit saturaba el log

logger = logging.getLogger(__name__)

from api.v1.collector import router as collector_router
from api.v1.regime import router as regime_router
from api.v1.backtest import router as backtest_router
from api.v1.paper_trading import router as paper_router
from api.v1.broker import router as broker_router
from api.v1.real_trading import router as real_trading_router
from api.v1.prices import router as prices_router
from api.v1.period_pnl import router as period_pnl_router

app = FastAPI(
    title="Trading Platform V2 — Python Engine",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
)

# Middleware de autenticación interna: falla cerrada (N-12)
from fastapi.responses import JSONResponse  # noqa: E402
from api.internal_auth import HEADER, configured_key, key_ok  # noqa: E402

INTERNAL_API_KEY = configured_key()
if not INTERNAL_API_KEY:
    logger.critical("INTERNAL_API_KEY no está definida: el motor rechaza todo pedido salvo /health (503)")


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    if not INTERNAL_API_KEY:
        return JSONResponse({"detail": "Motor sin INTERNAL_API_KEY configurada"}, status_code=503)
    if not key_ok(request.headers.get(HEADER), INTERNAL_API_KEY):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)



# R-07 (p65): el 422 por defecto de FastAPI repite en 'input' lo recibido; en los pedidos Real eso incluye las claves
# del broker, y Laravel registra la respuesta. Se responde lo mismo (loc, msg, type, ctx) sin 'input'.
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402


@app.exception_handler(RequestValidationError)
async def validation_error_without_input(request: Request, exc: RequestValidationError):
    errors = [{k: v for k, v in e.items() if k != 'input'} for e in exc.errors()]
    return JSONResponse(status_code=422, content={'detail': jsonable_encoder(errors)})

# Rutas
app.include_router(collector_router, prefix="/v1")
app.include_router(regime_router, prefix="/v1")
app.include_router(backtest_router, prefix="/v1")
app.include_router(paper_router, prefix="/v1")
app.include_router(broker_router, prefix="/v1")
app.include_router(real_trading_router, prefix="/v1")
app.include_router(prices_router, prefix="/v1")
app.include_router(period_pnl_router, prefix="/v1")

from db import close_pools  # noqa: E402

app.add_event_handler('shutdown', close_pools)


# Capacidades que Laravel consulta antes de usarlas. sub_entries (p62): /real/tick respeta entries_allowed por
# suscripción; sin ella Laravel no envía suscripciones pausadas (un motor anterior las trataría con entradas).
FEATURES = ["sub_entries"]


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "features": FEATURES}

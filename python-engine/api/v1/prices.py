"""
Endpoint de precios en vivo — usado por widgets que necesitan el precio
actual de varios simbolos sin pasar por el motor de trading completo
(ej. el panel de precios del dashboard). Tambien es el endpoint que
Laravel (TradingController::getLivePrices) ya esperaba encontrar aqui
para el PnL flotante de posiciones abiertas, pero que nunca existio.
"""
import logging
from fastapi import APIRouter, Query
from trading.bybit_client import get_current_prices

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/prices")
async def get_prices(symbols: str = Query(..., description="Simbolos separados por coma, ej. BTCUSDT,ETHUSDT")):
    """Retorna el precio actual (last price) de los simbolos pedidos."""
    symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
    if not symbol_list:
        return {"status": "ok", "prices": {}}

    prices = await get_current_prices(symbol_list)
    return {"status": "ok", "prices": prices}

"""
Cliente Bybit — Precios en tiempo real (público, sin auth)
"""

import httpx
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')


async def get_current_price(symbol: str) -> float | None:
    """Obtiene el precio actual (last price) de un símbolo en Bybit."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f'{BYBIT_BASE_URL}/v5/market/tickers',
                params={'category': 'linear', 'symbol': symbol}
            )
            r.raise_for_status()
            data = r.json()
            tickers = data.get('result', {}).get('list', [])

            if not tickers:
                return None

            return float(tickers[0]['lastPrice'])

    except Exception as e:
        logger.error(f"Error obteniendo precio de {symbol}: {e}")
        return None


async def get_current_prices(symbols: list[str]) -> dict[str, float]:
    """Obtiene precios actuales para varios símbolos."""
    prices = {}
    for symbol in symbols:
        price = await get_current_price(symbol)
        if price is not None:
            prices[symbol] = price
    return prices

"""Resuelve el broker activo para un símbolo, leyendo collector_configs.
Fallback: 'bybit' si no hay config o la DB falla.
"""
import logging
logger = logging.getLogger(__name__)
_RESOLVER_CACHE: dict[str, str] = {}
_CACHE_MAX_SIZE = 256

async def resolve_broker(pool, symbol: str) -> str:
    if symbol in _RESOLVER_CACHE:
        return _RESOLVER_CACHE[symbol]
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT broker FROM collector_configs
                WHERE symbol = $1 AND active = true
                ORDER BY (broker = 'bybit') DESC
                LIMIT 1
                """,
                symbol,
            )
        broker = row['broker'] if row and row['broker'] else 'bybit'
    except Exception as e:
        logger.warning(f"[broker_resolver] DB falló para {symbol}: {e} — usando 'bybit'")
        broker = 'bybit'
    if len(_RESOLVER_CACHE) >= _CACHE_MAX_SIZE:
        _RESOLVER_CACHE.clear()
    _RESOLVER_CACHE[symbol] = broker
    return broker

def clear_cache():
    _RESOLVER_CACHE.clear()

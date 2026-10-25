import logging
import asyncpg

logger = logging.getLogger(__name__)

async def resolve_broker(pool: asyncpg.Pool, symbol: str) -> str:
    """
    Resuelve el mejor broker para un símbolo basándose en la fecha de la
    última vela disponible. Prioriza el broker con los datos más recientes.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT broker, MAX(time) as last_time
            FROM ohlcv_data
            WHERE symbol = $1 AND interval = '240'
            GROUP BY broker
            ORDER BY last_time DESC
            LIMIT 1
            """,
            symbol
        )
        
        if row and row['broker']:
            return row['broker']
            
    # Fallback por defecto
    return 'bybit'

"""
Selección de la fuente de velas (broker) dentro de ohlcv_data.

Dos necesidades distintas que NO deben compartir criterio:

- En vivo (paper, real, régimen): la fuente con la vela MÁS RECIENTE del
  intervalo que se opera. Si esa vela está desactualizada se devuelve None y el
  llamador no opera: es preferible perder una entrada a operar sobre datos viejos.
- Backtest: la fuente con MAYOR COBERTURA del rango pedido (ver
  resolve_backtest_source, paso 8b). Mientras tanto se conserva resolve_broker
  solo para el backtest.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import asyncpg

logger = logging.getLogger(__name__)

INTERVAL_MINUTES = {'1': 1, '5': 5, '15': 15, '60': 60, '120': 120, '240': 240, 'D': 1440}

# Antigüedad máxima tolerada de la última vela, medida en intervalos.
# H1 -> 3 h, 15m -> 45 min, H2 -> 6 h. La vela en formación cuenta como reciente.
LIVE_MAX_LAG_BARS = 3

_BROKER_CACHE_TTL_S = 600
_broker_cache: tuple[float, list[str]] = (0.0, [])


def interval_delta(interval: str) -> timedelta:
    try:
        return timedelta(minutes=INTERVAL_MINUTES[str(interval)])
    except KeyError:
        raise ValueError(f"Intervalo desconocido: {interval!r}") from None


async def list_brokers(pool: asyncpg.Pool) -> list[str]:
    """Brokers presentes en ohlcv_data (loose index scan, cacheado 10 min)."""
    global _broker_cache
    cached_at, brokers = _broker_cache
    if brokers and time.monotonic() - cached_at < _BROKER_CACHE_TTL_S:
        return brokers

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH RECURSIVE b(broker) AS (
                SELECT min(broker) FROM ohlcv_data
                UNION ALL
                SELECT (SELECT min(o.broker) FROM ohlcv_data o WHERE o.broker > b.broker)
                FROM b WHERE b.broker IS NOT NULL
            )
            SELECT broker FROM b WHERE broker IS NOT NULL
            """
        )
    brokers = [r['broker'] for r in rows]
    _broker_cache = (time.monotonic(), brokers)
    return brokers


async def resolve_live_broker(pool: asyncpg.Pool, symbol: str, interval: str,
                              *, require_fresh: bool = True) -> str | None:
    """
    Fuente con la vela más reciente de (symbol, interval).

    Devuelve None (y registra ERROR) si no hay datos o si, con require_fresh,
    la última vela supera LIVE_MAX_LAG_BARS intervalos de antigüedad.
    """
    step = interval_delta(interval)
    brokers = await list_brokers(pool)
    if not brokers:
        logger.error("[DATA] ohlcv_data no contiene ningún broker")
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.broker,
                   (SELECT o.time FROM ohlcv_data o
                     WHERE o.broker = b.broker AND o.symbol = $2 AND o.interval = $3
                     ORDER BY o.time DESC LIMIT 1) AS last_bar
            FROM unnest($1::text[]) AS b(broker)
            """,
            brokers, symbol, str(interval),
        )

    candidates = [(r['broker'], r['last_bar']) for r in rows if r['last_bar'] is not None]
    if not candidates:
        logger.error(f"[DATA] {symbol} {interval}: sin velas en ninguna fuente")
        return None

    broker, last_bar = max(candidates, key=lambda c: c[1])
    if last_bar.tzinfo is None:
        last_bar = last_bar.replace(tzinfo=timezone.utc)

    if require_fresh:
        lag = datetime.now(timezone.utc) - last_bar
        if lag > step * LIVE_MAX_LAG_BARS:
            logger.error(
                f"[DATA] {symbol} {interval}: última vela {last_bar:%Y-%m-%d %H:%M} UTC "
                f"(fuente {broker}, retraso {lag}). Sin nuevas entradas hasta que el "
                f"collector se ponga al día."
            )
            return None

    return broker


async def resolve_broker(pool: asyncpg.Pool, symbol: str) -> str:
    """
    OBSOLETO - solo lo usa el backtest hasta el paso 8b. NO usar en vivo:
    elige por la vela H4 más reciente sin mirar el intervalo pedido.
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
    return 'bybit'

"""
Pools de conexiones a PostgreSQL compartidos por proceso.

get_pool(kind)  -> sin codecs (jsonb llega como str). kind: 'backtest' | 'live' (pools aislados: un lote de
                   backtests pesados no puede dejar sin conexiones al tick de paper/collector).
get_json_pool() -> jsonb/json <-> dict (lo usa real_trading: config_snapshot, audit_log).
SharedPool.close() no cierra nada: los endpoints pueden seguir llamando `await pool.close()`.
Los pools se cierran en el shutdown de la app (close_pools).
"""
import asyncio
import json
import os

import asyncpg

DB_DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
          f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
POOL_MIN, POOL_MAX = 1, 10

_pools: dict[str, asyncpg.Pool] = {}
_lock = asyncio.Lock()


class SharedPool:
    """Envoltorio del pool compartido: todo se delega salvo close()."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    def __getattr__(self, name):
        return getattr(self._pool, name)

    async def close(self) -> None:  # compartido: lo cierra close_pools() al apagar la app
        return None


async def _jsonb_codec(conn) -> None:
    await conn.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')
    await conn.set_type_codec('json', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')


async def _get(kind: str) -> SharedPool:
    pool = _pools.get(kind)
    if pool is None or pool.is_closing():
        async with _lock:
            pool = _pools.get(kind)
            if pool is None or pool.is_closing():
                pool = await asyncpg.create_pool(DB_DSN, min_size=POOL_MIN, max_size=POOL_MAX,
                                                 init=_jsonb_codec if kind == 'json' else None)
                _pools[kind] = pool
    return SharedPool(pool)


async def get_pool(kind: str = 'live') -> SharedPool:
    if kind not in ('backtest', 'live'):
        raise ValueError(f"pool desconocido: {kind}")
    return await _get(kind)


async def get_json_pool() -> SharedPool:
    return await _get('json')


async def close_pools() -> None:
    for kind in list(_pools):
        await _pools.pop(kind).close()

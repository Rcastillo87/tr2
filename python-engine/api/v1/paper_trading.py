"""
Endpoint Paper Trading V2 — Refactorizado
Lee las configuraciones de estrategias desde la tabla paper_strategy_configs,
eliminando cualquier config hardcodeada. El admin gestiona todo desde Laravel.
"""

import asyncio
import asyncpg
from db import get_pool as shared_get_pool
import logging
import os
import json
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from trading.paper_trader import PaperTrader
from backtesting.strategies.loader import build_strategy

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

DEFAULT_PARAMS = {
    "sl_pct":             1.5,
    "tp_pct":             3.0,
    "be_pct":             2.0,
    "max_duration":       24,
    "regime_filter":      True,
    "risk_per_trade_pct": 1.0,
}


async def get_pool():
    return await shared_get_pool('live')  # pool compartido por proceso (db.py)


async def load_active_configs(pool: asyncpg.Pool) -> list[dict]:
    """
    Carga todas las configuraciones activas desde paper_strategy_configs.
    Devuelve lista de dicts con: id, display_name, strategy_class, symbol, interval, params.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, display_name, strategy_class, symbol, interval, params
            FROM paper_strategy_configs
            WHERE active = true
            ORDER BY id ASC
            """
        )
    return [dict(r) for r in rows]


def build_config_map(configs: list[dict]) -> dict[int, dict]:
    """{config_id: config} solo con las configs cuya estrategia se puede construir."""
    config_map = {}
    for cfg in configs:
        try:
            params = cfg['params'] if isinstance(cfg['params'], dict) else json.loads(cfg['params'])
            build_strategy({**params, 'symbol': cfg['symbol'], 'interval': cfg['interval']})
            config_map[cfg['id']] = cfg
        except Exception as e:
            logger.error(f"Config #{cfg['id']} '{cfg['display_name']}' no se puede construir: {e}")
    return config_map


_tick_lock = asyncio.Lock()


@router.post("/paper/tick")
async def paper_tick():
    """Un solo tick a la vez por proceso: si llega otro con uno en curso, se omite (corre cada minuto)."""
    if _tick_lock.locked():
        return {"status": "busy", "message": "Tick anterior aún en curso: omitido", "monitor": {}, "signals": {}}
    async with _tick_lock:
        return await _paper_tick()


async def _paper_tick():
    """
    Ejecuta un ciclo completo de paper trading:
      0. Carga configs activas desde DB
      1. Evalua controles de riesgo
      2. Monitorea posiciones abiertas (SL/TP/BE/tiempo, Max G/Max P flotante)
      3. Busca nuevas senales y abre posiciones si corresponde
    """
    try:
        pool    = await get_pool()
        configs = await load_active_configs(pool)

        config_map = build_config_map(configs)

        trader = PaperTrader(pool, DEFAULT_PARAMS, config_map)

        # Siempre: las posiciones abiertas usan su config_snapshot, no la config viva.
        monitor_results = await trader.monitor_open_trades()
        # sin configs activas: solo se gestionan las posiciones abiertas (no hay señales que buscar)
        signal_results  = await trader.check_new_signals() if config_map else {}

        await pool.close()

        return {
            "status":  "ok",
            "configs": len(configs),
            "monitor": monitor_results,
            "signals": signal_results,
        }
    except Exception as e:
        logger.error(f"Paper tick error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/open")
async def paper_open_trades():
    """Lista posiciones abiertas con precio actual y PnL flotante."""
    try:
        pool    = await get_pool()
        configs = await load_active_configs(pool)

        trader = PaperTrader(pool, DEFAULT_PARAMS, build_config_map(configs))
        trades = await trader.get_open_trades_with_live_price()

        await pool.close()
        return {"status": "ok", "data": trades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/summary")
async def paper_summary():
    """Resumen de resultados por display_name (config)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    strategy,
                    COUNT(*) FILTER (WHERE status = 'closed') as total_trades,
                    COUNT(*) FILTER (WHERE status = 'closed' AND pnl > 0) as wins,
                    COUNT(*) FILTER (WHERE status = 'open') as open_trades,
                    COALESCE(SUM(pnl_pct) FILTER (WHERE status = 'closed'), 0) as total_pnl_pct
                FROM paper_trades
                GROUP BY strategy
                """
            )
        await pool.close()

        summary = []
        for r in rows:
            total    = r['total_trades']
            wins     = r['wins']
            win_rate = round(wins / total * 100, 2) if total > 0 else 0.0

            summary.append({
                "strategy":      r['strategy'],
                "total_trades":  total,
                "wins":          wins,
                "losses":        total - wins,
                "win_rate":      win_rate,
                "open_trades":   r['open_trades'],
                "total_pnl_pct": float(r['total_pnl_pct']),
            })

        return {"status": "ok", "data": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/trades/{strategy}")
async def paper_trades_by_strategy(strategy: str):
    """Lista de trades de una configuracion de estrategia especifica."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, strategy, symbol, side, entry_price, exit_price, sl, tp,
                       be_activated, size, pnl, pnl_pct, max_profit_pct, max_loss_pct,
                       exit_reason, regime, entry_time, exit_time, status
                FROM paper_trades
                WHERE strategy = $1
                ORDER BY entry_time DESC
                LIMIT 200
                """,
                strategy
            )
        await pool.close()
        return {"status": "ok", "data": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

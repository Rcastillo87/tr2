"""
Endpoint Paper Trading V2 — Refactorizado
Lee las configuraciones de estrategias desde la tabla paper_strategy_configs,
eliminando cualquier config hardcodeada. El admin gestiona todo desde Laravel.
"""

import asyncpg
import logging
import os
import importlib
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from trading.paper_trader import PaperTrader
from trading.risk_manager import RiskManager

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

# Mapa de clase Python por nombre (extensible sin tocar logica del motor)
STRATEGY_CLASS_MAP = {
    'VwapStrategy':          ('backtesting.strategies.vwap_strategy',  'VwapStrategy'),
    'MeanReversionStrategy': ('backtesting.strategies.mean_reversion',  'MeanReversionStrategy'),
    'EmaDonchianStrategy':   ('backtesting.strategies.ema_donchian',    'EmaDonchianStrategy'),
}


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


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


def instantiate_strategy(config: dict) -> object:
    """
    Instancia la clase de estrategia correspondiente con los params de la config.
    Lanza ValueError si la clase no esta registrada.
    """
    class_name = config['strategy_class']

    if class_name not in STRATEGY_CLASS_MAP:
        raise ValueError(f"Clase de estrategia no registrada: {class_name}")

    module_path, cls_name = STRATEGY_CLASS_MAP[class_name]
    module   = importlib.import_module(module_path)
    cls      = getattr(module, cls_name)

    import json
    params = config['params'] if isinstance(config['params'], dict) else json.loads(config['params'])
    params['symbol']   = config['symbol']
    params['interval'] = config['interval']

    return cls(params)


@router.post("/paper/tick")
async def paper_tick():
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

        if not configs:
            await pool.close()
            return {"status": "ok", "message": "Sin configuraciones activas", "monitor": {}, "signals": {}}

        # Construir el mapa de estrategias para el PaperTrader:
        # {display_name: clase} y params por config
        strategies = {}
        config_map = {}  # display_name -> config completa

        for cfg in configs:
            try:
                strategy_instance = instantiate_strategy(cfg)
                strategies[cfg['display_name']] = type(strategy_instance)
                config_map[cfg['display_name']] = cfg
            except Exception as e:
                logger.error(f"Error instanciando {cfg['display_name']}: {e}")

        # Parametros base comunes (pueden ser sobreescritos por los params de cada config)
        default_params = {
            "sl_pct":             1.5,
            "tp_pct":             3.0,
            "be_pct":             2.0,
            "max_duration":       24,
            "regime_filter":      True,
            "risk_per_trade_pct": 1.0,
        }

        risk_manager = RiskManager(pool)
        symbols = list(set(cfg['symbol'] for cfg in configs))
        strategy_names = list(strategies.keys())

        risk_results = await risk_manager.evaluate(
            strategies=strategy_names,
            symbols=symbols,
        )

        trader = PaperTrader(pool, strategies, default_params, config_map)

        monitor_results = await trader.monitor_open_trades()
        signal_results  = await trader.check_new_signals()

        await pool.close()

        return {
            "status":  "ok",
            "configs": len(configs),
            "risk":    risk_results,
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

        strategies = {}
        config_map = {}
        default_params = {"sl_pct": 1.5, "tp_pct": 3.0, "be_pct": 2.0,
                          "max_duration": 24, "regime_filter": True, "risk_per_trade_pct": 1.0}

        for cfg in configs:
            try:
                strategy_instance = instantiate_strategy(cfg)
                strategies[cfg['display_name']] = type(strategy_instance)
                config_map[cfg['display_name']] = cfg
            except Exception as e:
                logger.error(f"Error instanciando {cfg['display_name']}: {e}")

        trader = PaperTrader(pool, strategies, default_params, config_map)
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

"""
Endpoint Paper Trading V2
"""

import asyncpg
import logging
import os
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

from trading.paper_trader import PaperTrader
from trading.risk_manager import RiskManager
from backtesting.strategies.ema_donchian import EmaDonchianStrategy
from backtesting.strategies.mean_reversion import MeanReversionStrategy
from backtesting.strategies.vwap_intraday import VwapIntradayStrategy

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

STRATEGIES = {
    "Tendencia EMA/Donchian": EmaDonchianStrategy,
    "Reversión a la Media":   MeanReversionStrategy,
    "VWAP Intradía":          VwapIntradayStrategy,
}

DEFAULT_PARAMS = {
    "interval":           "60",
    "sl_pct":             1.5,
    "tp_pct":             3.0,
    "be_pct":             2.0,
    "max_duration":       24,
    "regime_filter":      True,
    "risk_per_trade_pct": 1.0,
}


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


@router.post("/paper/tick")
async def paper_tick():
    """
    Ejecuta un ciclo completo de paper trading:
      0. Evalúa controles de riesgo (drawdown, volatilidad, kill switch)
      1. Monitorea posiciones abiertas (SL/TP/BE/tiempo, y actualiza Max G/Max P flotante)
      2. Busca nuevas señales y abre posiciones si corresponde
    """
    try:
        pool = await get_pool()

        risk_manager = RiskManager(pool)
        risk_results = await risk_manager.evaluate(
            strategies=list(STRATEGIES.keys()),
            symbols=os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(','),
        )

        trader = PaperTrader(pool, STRATEGIES, DEFAULT_PARAMS)

        monitor_results = await trader.monitor_open_trades()
        signal_results  = await trader.check_new_signals()

        await pool.close()

        return {
            "status": "ok",
            "risk": risk_results,
            "monitor": monitor_results,
            "signals": signal_results,
        }
    except Exception as e:
        logger.error(f"Paper tick error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/open")
async def paper_open_trades():
    """
    Lista todas las posiciones abiertas, enriquecidas con el precio actual
    de mercado y el PnL flotante (en % y en USDT virtual).
    """
    try:
        pool = await get_pool()
        trader = PaperTrader(pool, STRATEGIES, DEFAULT_PARAMS)

        trades = await trader.get_open_trades_with_live_price()

        await pool.close()

        return {"status": "ok", "data": trades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/summary")
async def paper_summary():
    """Resumen de resultados por estrategia."""
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
                    COALESCE(SUM(pnl) FILTER (WHERE status = 'closed'), 0) as total_pnl
                FROM paper_trades
                GROUP BY strategy
                """
            )
        await pool.close()

        summary = []
        for r in rows:
            total = r['total_trades']
            wins  = r['wins']
            win_rate = round(wins / total * 100, 2) if total > 0 else 0.0

            summary.append({
                "strategy":     r['strategy'],
                "total_trades": total,
                "wins":         wins,
                "losses":       total - wins,
                "win_rate":     win_rate,
                "open_trades":  r['open_trades'],
                "total_pnl":    float(r['total_pnl']),
            })

        return {"status": "ok", "data": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/trades/{strategy}")
async def paper_trades_by_strategy(strategy: str):
    """Lista de trades (abiertos y cerrados) de una estrategia específica."""
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
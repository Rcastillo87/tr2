"""
Endpoint Backtesting V2 — Actualizado
Estrategias alineadas con paper_strategy_configs y VwapStrategy unificada.
"""

import asyncpg
import pandas as pd
import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from backtesting.walk_forward import WalkForwardValidator
from backtesting.engine import BacktestEngine

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"


class BacktestRequest(BaseModel):
    strategy:            str
    symbol:              str            = "BTCUSDT"
    interval:            str            = "60"
    initial_balance:     float          = 10000.0
    risk_per_trade_pct:  float          = 1.0
    sl_pct:              float          = 1.5
    tp_pct:              float          = 3.0
    be_pct:              float          = 2.0
    max_duration:        int            = 24
    regime_filter:       bool           = True
    walk_forward:        bool           = True
    n_windows:           int            = 5
    train_pct:           float          = 0.7
    mode:                Optional[str]  = None  # para VwapStrategy: "trend_follow" | "reversion"


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


async def load_ohlcv(pool: asyncpg.Pool, symbol: str, interval: str) -> pd.DataFrame:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND interval = $2
            ORDER BY time ASC
            """,
            symbol, interval
        )

    if not rows:
        raise ValueError(f"No hay datos para {symbol}/{interval}")

    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df


def load_strategy(request: BacktestRequest):
    """
    Carga la estrategia solicitada por nombre.
    Nombres reconocidos (alineados con BacktestingController de Laravel):
      - "VWAP Tendencia"          → VwapStrategy(mode=trend_follow)
      - "VWAP Reversión"          → VwapStrategy(mode=reversion)
      - "Reversión a la Media"    → MeanReversionStrategy
      - "Tendencia EMA/Donchian"  → EmaDonchianStrategy
    """
    params = {
        "symbol":        request.symbol,
        "interval":      request.interval,
        "sl_pct":        request.sl_pct,
        "tp_pct":        request.tp_pct,
        "be_pct":        request.be_pct,
        "max_duration":  request.max_duration,
        "regime_filter": request.regime_filter,
    }

    # VwapStrategy unificada — modo desde el request o inferido por nombre
    try:
        from backtesting.strategies.vwap_strategy import VwapStrategy

        if request.strategy == "VWAP Tendencia":
            mode = request.mode or "trend_follow"
            params["mode"] = mode
            params["allowed_regimes"] = ["TRENDING"]
            return VwapStrategy(params)

        if request.strategy == "VWAP Reversión":
            mode = request.mode or "reversion"
            params["mode"] = mode
            params["allowed_regimes"] = ["TRENDING"]
            return VwapStrategy(params)

    except ImportError as e:
        logger.warning(f"VwapStrategy no disponible: {e}")

    # Estrategias individuales
    try:
        from backtesting.strategies.mean_reversion import MeanReversionStrategy
        if request.strategy == "Reversión a la Media":
            params["allowed_regimes"] = ["RANGING"]
            return MeanReversionStrategy(params)
    except ImportError:
        pass

    try:
        from backtesting.strategies.ema_donchian import EmaDonchianStrategy
        if request.strategy == "Tendencia EMA/Donchian":
            params["allowed_regimes"] = ["TRENDING"]
            return EmaDonchianStrategy(params)
    except ImportError:
        pass

    # Estrategias legacy (para backtests historicos, no en produccion)
    try:
        from backtesting.strategies.vwap_intraday import VwapIntradayStrategy
        if request.strategy == "VWAP Intradía":
            return VwapIntradayStrategy(params)
    except ImportError:
        pass

    available = ["VWAP Tendencia", "VWAP Reversión", "Reversión a la Media", "Tendencia EMA/Donchian"]
    raise ValueError(f"Estrategia '{request.strategy}' no encontrada. Disponibles: {available}")


@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest):
    """Ejecuta un backtest completo con walk-forward validation."""
    try:
        pool     = await get_pool()
        df       = await load_ohlcv(pool, request.symbol, request.interval)
        strategy = load_strategy(request)
        await pool.close()

        if request.walk_forward:
            validator = WalkForwardValidator(
                strategy=strategy,
                df=df,
                initial_balance=request.initial_balance,
                risk_per_trade_pct=request.risk_per_trade_pct,
                n_windows=request.n_windows,
                train_pct=request.train_pct,
            )
            result = validator.run()
        else:
            engine = BacktestEngine(
                strategy=strategy,
                df=df,
                initial_balance=request.initial_balance,
                risk_per_trade_pct=request.risk_per_trade_pct,
            )
            result = engine.run()

        return {"status": "ok", "result": result}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/strategies")
async def list_strategies():
    """Lista las estrategias disponibles para backtesting."""
    available = [
        {"name": "VWAP Tendencia",         "description": "VWAP trend follow — mejor en ETH H2"},
        {"name": "VWAP Reversión",          "description": "VWAP reversión extremos ±2σ (E-13) — mejor en BTC/SOL H1"},
        {"name": "Reversión a la Media",    "description": "Bollinger + RSI en régimen RANGING"},
        {"name": "Tendencia EMA/Donchian",  "description": "EMA cruce + Donchian breakout en régimen TRENDING"},
    ]
    return {"status": "ok", "strategies": available}

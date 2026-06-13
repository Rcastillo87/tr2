"""
Endpoint Backtesting V2
"""

import asyncpg
import pandas as pd
import logging
import os
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
    symbol:              str   = "BTCUSDT"
    interval:            str   = "60"
    initial_balance:     float = 10000.0
    risk_per_trade_pct:  float = 1.0
    sl_pct:              float = 1.5
    tp_pct:              float = 3.0
    be_pct:              float = 0.8
    max_duration:        int   = 24
    regime_filter:       bool  = True
    walk_forward:        bool  = True
    n_windows:           int   = 5
    train_pct:           float = 0.7


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


async def load_ohlcv(pool: asyncpg.Pool, symbol: str, interval: str) -> pd.DataFrame:
    """Carga datos OHLCV desde la DB propia."""
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
    """Carga la estrategia solicitada por nombre."""
    params = {
        "symbol":        request.symbol,
        "interval":      request.interval,
        "sl_pct":        request.sl_pct,
        "tp_pct":        request.tp_pct,
        "be_pct":        request.be_pct,
        "max_duration":  request.max_duration,
        "regime_filter": request.regime_filter,
    }

    strategy_map = {}

    # Importar estrategias disponibles
    try:
        from backtesting.strategies.ema_donchian import EmaDonchianStrategy
        strategy_map["Tendencia EMA/Donchian"] = EmaDonchianStrategy
    except ImportError:
        pass

    try:
        from backtesting.strategies.mean_reversion import MeanReversionStrategy
        strategy_map["Reversión a la Media"] = MeanReversionStrategy
    except ImportError:
        pass

    try:
        from backtesting.strategies.vwap_intraday import VwapIntradayStrategy
        strategy_map["VWAP Intradía"] = VwapIntradayStrategy
    except ImportError:
        pass

    if request.strategy not in strategy_map:
        available = list(strategy_map.keys())
        raise ValueError(f"Estrategia '{request.strategy}' no encontrada. Disponibles: {available}")

    return strategy_map[request.strategy](params)


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
    """Lista las estrategias disponibles."""
    available = []

    strategy_checks = [
        ("Tendencia EMA/Donchian",  "backtesting.strategies.ema_donchian",  "EmaDonchianStrategy"),
        ("Reversión a la Media",    "backtesting.strategies.mean_reversion", "MeanReversionStrategy"),
        ("VWAP Intradía",           "backtesting.strategies.vwap_intraday",  "VwapIntradayStrategy"),
    ]

    for name, module, cls in strategy_checks:
        try:
            __import__(module)
            available.append({"name": name, "status": "disponible"})
        except ImportError:
            available.append({"name": name, "status": "no implementada aún"})

    return {"status": "ok", "strategies": available}

"""
Endpoint Backtesting V2 — Extendido
Soporta: rango de fechas, hasta 4 niveles de TP, Trailing Stop,
Proteccion por volatilidad, y desglose de resultados mes a mes.
"""

import asyncpg
import pandas as pd
import logging
import os
from typing import Optional
from datetime import datetime
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
    symbol:              str             = "BTCUSDT"
    interval:            str             = "60"
    initial_balance:     float           = 10000.0
    risk_per_trade_pct:  float           = 1.0
    sl_pct:              float           = 1.5
    tp_pct:              float           = 3.0
    tp2_pct:             Optional[float] = None
    tp3_pct:             Optional[float] = None
    tp4_pct:             Optional[float] = None
    be_pct:              float           = 2.0
    max_duration:        int             = 24
    regime_filter:       bool            = True
    walk_forward:        bool            = True
    n_windows:           int             = 5
    train_pct:           float           = 0.7
    mode:                Optional[str]   = None
    macro_trend_filter:  Optional[bool]  = None  # None = usar default de la estrategia segun mode

    # Filtro de persistencia de tendencia (solo VWAP Tendencia)
    trend_persistence_filter: bool          = False
    trend_persistence_bars:   int            = 4
    trend_adx_threshold:      float          = 25

    # SL dinamico en zona ADX debil (solo VWAP Tendencia)
    dynamic_sl_filter:    bool  = False
    adx_strong_threshold: float = 30
    sl_pct_weak_zone:     float = 0.7

    # Rango de fechas opcional — si no se especifica, usa todo el historico disponible
    start_date: Optional[str] = None  # formato YYYY-MM-DD
    end_date:   Optional[str] = None  # formato YYYY-MM-DD

    # Trailing stop
    trailing_mode:          Optional[str]        = None  # None | "fixed" | "stepped"
    trailing_distance_pct:  float                = 1.0
    trailing_steps:         Optional[list]       = None  # [[gain_pct, new_sl_pct], ...]

    # Proteccion por volatilidad
    volatility_protection_mode: Optional[str] = None  # None | "close" | "widen"
    volatility_atr_multiplier:  float         = 2.5
    volatility_widen_pct:       float         = 1.0
    # Filtro de volumen
    volume_filter:              bool          = False
    volume_filter_period:       int           = 20
    volume_filter_mult:         float         = 1.2
    # Filtro horario
    hour_filter:                bool          = False
    hour_filter_start:          int           = 7
    hour_filter_end:            int           = 21
    # Filtro fin de semana
    weekend_filter:             bool          = False
    # Horas bloqueadas (lista de horas UTC 0-23)
    blocked_hours:              list          = []
    # Dias bloqueados (0=Lun,1=Mar,2=Mie,3=Jue,4=Vie,5=Sab,6=Dom)
    blocked_days:               list          = []

    # Si True, ademas de las metricas agregadas devuelve un desglose mes a mes
    monthly_breakdown: bool = False


async def get_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)


async def load_ohlcv(pool: asyncpg.Pool, symbol: str, interval: str,
                      start_date: str | None, end_date: str | None) -> pd.DataFrame:
    """Carga datos OHLCV desde la DB, opcionalmente acotados a un rango de fechas."""
    query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 AND interval = $2
    """
    args = [symbol, interval]

    if start_date:
        query += f" AND time >= ${len(args) + 1}"
        args.append(datetime.fromisoformat(start_date))
    if end_date:
        query += f" AND time <= ${len(args) + 1}"
        args.append(datetime.fromisoformat(end_date))

    query += " ORDER BY time ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)

    if not rows:
        raise ValueError(f"No hay datos para {symbol}/{interval} en el rango especificado")

    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df


def load_strategy(request: BacktestRequest):
    """Carga la estrategia solicitada con todos los parametros extendidos."""
    params = {
        "symbol":        request.symbol,
        "interval":      request.interval,
        "sl_pct":        request.sl_pct,
        "tp_pct":        request.tp_pct,
        "tp2_pct":       request.tp2_pct,
        "tp3_pct":       request.tp3_pct,
        "tp4_pct":       request.tp4_pct,
        "be_pct":        request.be_pct,
        "max_duration":  request.max_duration,
        "regime_filter": request.regime_filter,

        "trailing_mode":          request.trailing_mode,
        "trailing_distance_pct":  request.trailing_distance_pct,
        "trailing_steps":         request.trailing_steps or [],

        "volatility_protection_mode": request.volatility_protection_mode,
        "volatility_atr_multiplier":  request.volatility_atr_multiplier,
        "volatility_widen_pct":       request.volatility_widen_pct,
        "volume_filter":              request.volume_filter,
        "volume_filter_period":       request.volume_filter_period,
        "volume_filter_mult":         request.volume_filter_mult,
        "hour_filter":                request.hour_filter,
        "hour_filter_start":          request.hour_filter_start,
        "hour_filter_end":            request.hour_filter_end,
        "weekend_filter":             request.weekend_filter,
        "blocked_hours":              request.blocked_hours,
        "blocked_days":               request.blocked_days,

        "trend_persistence_filter": request.trend_persistence_filter,
        "trend_persistence_bars":   request.trend_persistence_bars,
        "trend_adx_threshold":      request.trend_adx_threshold,

        "dynamic_sl_filter":    request.dynamic_sl_filter,
        "adx_strong_threshold": request.adx_strong_threshold,
        "sl_pct_weak_zone":     request.sl_pct_weak_zone,
    }

    try:
        from backtesting.strategies.vwap_strategy import VwapStrategy

        if request.macro_trend_filter is not None:
            params["macro_trend_filter"] = request.macro_trend_filter

        if request.strategy == "VWAP Tendencia":
            params["mode"] = request.mode or "trend_follow"
            params["allowed_regimes"] = ["TRENDING"]
            return VwapStrategy(params)

        if request.strategy == "VWAP Reversión":
            params["mode"] = request.mode or "reversion"
            params["allowed_regimes"] = ["TRENDING"]
            return VwapStrategy(params)

    except ImportError as e:
        logger.warning(f"VwapStrategy no disponible: {e}")

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

    available = ["VWAP Tendencia", "VWAP Reversión", "Reversión a la Media", "Tendencia EMA/Donchian"]
    raise ValueError(f"Estrategia '{request.strategy}' no encontrada. Disponibles: {available}")


def build_monthly_breakdown(trades: list[dict], initial_balance: float) -> list[dict]:
    """
    Agrupa los trades cerrados por mes calendario (segun entry_time) y calcula
    metricas resumidas por mes: trades, win_rate, pnl_pct, pnl total.
    """
    if not trades:
        return []

    df = pd.DataFrame(trades)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['month'] = df['entry_time'].dt.strftime('%Y-%m')

    breakdown = []
    for month, group in df.groupby('month'):
        total = len(group)
        wins  = (group['pnl'] > 0).sum()
        breakdown.append({
            "month":       month,
            "total_trades": int(total),
            "wins":        int(wins),
            "losses":      int(total - wins),
            "win_rate":    round(float(wins) / total * 100, 2) if total > 0 else 0.0,
            "total_pnl":   round(float(group['pnl'].sum()), 4),
            "total_pnl_pct": round(float(group['pnl_pct'].sum()), 4),
        })

    breakdown.sort(key=lambda x: x['month'])
    return breakdown


@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest):
    """Ejecuta un backtest completo con walk-forward validation."""
    try:
        pool     = await get_pool()
        df       = await load_ohlcv(pool, request.symbol, request.interval,
                                     request.start_date, request.end_date)
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
            all_trades = []
            # WalkForwardValidator no expone trades crudos directamente en result,
            # se reconstruyen corriendo el engine simple sobre todo el rango para el desglose mensual
            if request.monthly_breakdown:
                _regime_data = WalkForwardValidator(
                    strategy=strategy, df=df,
                    initial_balance=request.initial_balance,
                    risk_per_trade_pct=request.risk_per_trade_pct,
                )._build_regime_data(df)
                engine_full = BacktestEngine(
                    strategy=strategy, df=df,
                    initial_balance=request.initial_balance,
                    risk_per_trade_pct=request.risk_per_trade_pct,
                    regime_data=_regime_data,
                )
                full_result = engine_full.run()
                result['monthly_breakdown'] = build_monthly_breakdown(
                    full_result['trades'], request.initial_balance
                )
                # Se guarda el backtest completo (in-sample, sobre el 100% del histórico)
                # como referencia informativa para el desglose mensual — pero SIN
                # sobreescribir aggregate_metrics/passed/pass_reasons, que deben seguir
                # siendo las del walk-forward (fuera de muestra). Sobreescribirlas
                # anulaba por completo el propósito de la validación walk-forward:
                # el badge "Aprobada" y el rating de estrellas terminaban reflejando
                # desempeño in-sample, mucho más propenso a sobreajuste.
                result['in_sample_metrics'] = full_result.get('metrics', {})
        else:
            engine = BacktestEngine(
                strategy=strategy, df=df,
                initial_balance=request.initial_balance,
                risk_per_trade_pct=request.risk_per_trade_pct,
            )
            result = engine.run()
            if request.monthly_breakdown:
                result['monthly_breakdown'] = build_monthly_breakdown(
                    result['trades'], request.initial_balance
                )

        return {"status": "ok", "result": result}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/strategies")
async def list_strategies():
    available = [
        {"name": "VWAP Tendencia",         "description": "VWAP trend follow"},
        {"name": "VWAP Reversión",          "description": "VWAP reversión extremos ±2σ con filtro macro H4"},
        {"name": "Reversión a la Media",    "description": "Bollinger + RSI en régimen RANGING"},
        {"name": "Tendencia EMA/Donchian",  "description": "EMA cruce + Donchian breakout en régimen TRENDING"},
    ]
    return {"status": "ok", "strategies": available}


@router.get("/backtest/data-range/{symbol}/{interval}")
async def get_data_range(symbol: str, interval: str):
    """Devuelve el rango de fechas disponible en ohlcv_data para un simbolo/intervalo."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MIN(time) as first, MAX(time) as last, COUNT(*) as total
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                """,
                symbol, interval
            )
        await pool.close()

        if not row or row['total'] == 0:
            return {"status": "ok", "data": None}

        return {
            "status": "ok",
            "data": {
                "first_date": row['first'].isoformat() if row['first'] else None,
                "last_date":  row['last'].isoformat() if row['last'] else None,
                "total_bars": row['total'],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

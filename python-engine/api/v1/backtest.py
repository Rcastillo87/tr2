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
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from backtesting.walk_forward import WalkForwardValidator
from backtesting.engine import BacktestEngine
from collectors.broker_resolver import (
    coverage_by_broker, interval_delta, pick_best_source, resolve_backtest_source,
)

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"


class BacktestRequest(BaseModel):
    strategy:            str
    strategy_code:       Optional[str]   = None
    strategy_config:     Optional[dict]  = None
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
    regime_adx_trending: float           = 25
    regime_adx_ranging:  float           = 20
    regime_ambiguous_as: str             = "RANGING"
    walk_forward:        bool            = True
    n_windows:           int             = 5
    macro_trend_filter:  bool            = False
    volume_filter:       bool            = False
    volume_filter_period: int            = 20
    volume_filter_mult:  float           = 1.2
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
    trailing_mode:          Optional[str]        = None  # None | "fixed" | "stepped" | "atr"
    trailing_distance_pct:  float                = 1.0
    trailing_activation_buffer_pct: float         = 0.0
    trailing_atr_mult:      float                = 2.0
    close_on_opposite:      bool                 = False
    exit_on_opposite:       bool                 = False
    allow_short:            bool                 = True
    max_duration_profit:    bool                 = False
    commission_pct:         float                = 0.055
    # data_broker: fuente de datos para el backtest. Si None, se resuelve
    # via collector_configs (mismo comportamiento que paper/real).
    # Valores válidos: None | "bybit" | "binance_vision" | "ig".
    # Permite comparar la MISMA estrategia contra distintos exchanges.
    data_broker:            Optional[str]        = None
    max_leverage:           float                = 1.0
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


def parse_range(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
    """Rango semiabierto [start, end) en UTC. Un end_date 'YYYY-MM-DD' incluye ese día completo."""
    def to_utc(value: str) -> datetime:
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

    start = to_utc(start_date) if start_date else None
    end = None
    if end_date:
        end = to_utc(end_date)
        if len(end_date) == 10:  # solo fecha: día completo
            end += timedelta(days=1)
    return start, end


async def load_ohlcv(pool: asyncpg.Pool, symbol: str, interval: str, broker: str,
                     start: datetime | None, end: datetime | None) -> pd.DataFrame:
    """Velas de UNA fuente en [start, end). Sin datos -> ValueError."""
    query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE broker = $1 AND symbol = $2 AND interval = $3
    """
    args: list = [broker, symbol, interval]
    if start is not None:
        args.append(start)
        query += f" AND time >= ${len(args)}"
    if end is not None:
        args.append(end)
        query += f" AND time < ${len(args)}"
    query += " ORDER BY time ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)

    if not rows:
        raise ValueError(f"No hay datos para {symbol}/{interval} ({broker}) en el rango especificado")

    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df


def load_strategy(request: BacktestRequest):
    """Carga la estrategia solicitada. Si viene código dinámico, lo compila y ejecuta."""
    
    if request.strategy_code and request.strategy_code.strip():
        from backtesting.strategies.base_strategy import BaseStrategy
        import pandas as pd
        import numpy as np
        
        # Namespace seguro para la ejecución
        namespace = {"BaseStrategy": BaseStrategy, "pd": pd, "np": np}
        try:
            exec(request.strategy_code, namespace)
        except Exception as e:
            raise ValueError(f"Error compilando el código Python: {str(e)}")
        
            # Buscar la clase que herede de BaseStrategy
        strategy_cls = None
        for k, v in namespace.items():
            if isinstance(v, type) and k != 'BaseStrategy' and issubclass(v, BaseStrategy):
                strategy_cls = v
                break
        
        if not strategy_cls:
            raise ValueError("El código no contiene una clase que herede de BaseStrategy.")
        
        # Mezclar la configuración propia de la estrategia con los parámetros de operación
        params = request.strategy_config or {}
        params.update({
            'symbol': request.symbol,
            'interval': request.interval,
            'sl_pct': request.sl_pct,
            'tp_pct': request.tp_pct,
            'close_on_opposite': request.close_on_opposite,
            'exit_on_opposite': request.exit_on_opposite,
            'allow_short': request.allow_short,
            'max_duration_profit': request.max_duration_profit,
            'trailing_atr_mult': request.trailing_atr_mult,
            'tp2_pct': request.tp2_pct,
            'tp3_pct': request.tp3_pct,
            'tp4_pct': request.tp4_pct,
            'be_pct': request.be_pct,
            'max_duration': request.max_duration,
            'regime_filter': request.regime_filter,
            'risk_per_trade_pct': request.risk_per_trade_pct,
            'commission_pct': request.commission_pct,
            'trailing_mode': request.trailing_mode,
            'trailing_distance_pct': request.trailing_distance_pct,
            'trailing_activation_buffer_pct': request.trailing_activation_buffer_pct,
            'trailing_distance_pct': request.trailing_distance_pct,
            'trailing_activation_buffer_pct': request.trailing_activation_buffer_pct,
            'trailing_steps': request.trailing_steps,
            'regime_adx_trending': request.regime_adx_trending,
            'regime_adx_ranging': request.regime_adx_ranging,
            'regime_ambiguous_as': request.regime_ambiguous_as,
            'macro_trend_filter': request.macro_trend_filter,
            'volume_filter': request.volume_filter,
            'volume_filter_period': request.volume_filter_period,
            'volume_filter_mult': request.volume_filter_mult,
        })
        # FIX FORENSE: Sobrescribir explícitamente con los valores de la request (UI)
        params['sl_pct'] = request.sl_pct
        params['tp_pct'] = request.tp_pct
        params['be_pct'] = request.be_pct
        params['trailing_mode'] = request.trailing_mode
        params['trailing_distance_pct'] = request.trailing_distance_pct
        params['trailing_activation_buffer_pct'] = request.trailing_activation_buffer_pct
        
        # FIX: Agregamos los 3 parámetros de volatilidad que faltaban
        params['volatility_protection_mode'] = request.volatility_protection_mode
        params['volatility_atr_multiplier'] = request.volatility_atr_multiplier
        params['volatility_widen_pct'] = request.volatility_widen_pct

        return strategy_cls(params)

    # Si no hay código dinámico, usar la lógica legacy (mapeo de nombres)
    params = {
        "symbol":        request.symbol,
        "interval":      request.interval,
        "sl_pct":        request.sl_pct,
        "tp_pct":        request.tp_pct,
        "close_on_opposite": request.close_on_opposite,
        "max_duration_profit": request.max_duration_profit,
        "trailing_atr_mult": request.trailing_atr_mult,
        "tp2_pct":       request.tp2_pct,
        "tp3_pct":       request.tp3_pct,
        "tp4_pct":       request.tp4_pct,
        "be_pct":        request.be_pct,
        "max_duration":  request.max_duration,
        "regime_filter": request.regime_filter,
        "regime_adx_trending": request.regime_adx_trending,
        "regime_adx_ranging":  request.regime_adx_ranging,
        "regime_ambiguous_as": request.regime_ambiguous_as,

        "trailing_mode":          request.trailing_mode,
        "trailing_distance_pct":  request.trailing_distance_pct,
        "trailing_activation_buffer_pct": request.trailing_activation_buffer_pct,
        "commission_pct":         request.commission_pct,
        "max_leverage":           request.max_leverage,
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
    warnings = []
    coverage = {}
    try:
        start, end = parse_range(request.start_date, request.end_date)
        pool = await get_pool()
        try:
            # 1. Velas principales: fuente con la mayor cobertura REAL del rango pedido.
            if request.data_broker:
                forced = [c for c in await coverage_by_broker(pool, request.symbol, request.interval, start, end)
                          if c.broker == request.data_broker]
                main_src = forced[0] if forced else None
            else:
                main_src = await resolve_backtest_source(pool, request.symbol, request.interval, start, end)
            if main_src is None:
                raise ValueError(f"No hay velas de {request.symbol} {request.interval} en el rango solicitado.")
            warnings.extend(main_src.problems())
            coverage['main'] = main_src.as_dict()
            df = await load_ohlcv(pool, request.symbol, request.interval, main_src.broker, start, end)

            strategy = load_strategy(request)

            # 2. Velas de 1m para simular la salida dentro de cada vela (interval >= H1).
            #    Regla de oro 4: solo si cubren TODO el rango del dataset principal.
            #    Si no, vela grande con SL primero (pesimista) en TODO el rango: mezclar
            #    ambos métodos daría un backtest con dos criterios distintos según el mes.
            minute_df = None
            if interval_delta(request.interval) >= timedelta(hours=1):
                data_start = df['time'].iloc[0].to_pydatetime()
                data_end = df['time'].iloc[-1].to_pydatetime() + interval_delta(request.interval)
                minute_src = await resolve_backtest_source(pool, request.symbol, '1', data_start, data_end)
                coverage['minute'] = minute_src.as_dict() if minute_src else None
                if minute_src is not None and minute_src.covers(data_start, data_end):
                    minute_df = await load_ohlcv(pool, request.symbol, '1', minute_src.broker, data_start, data_end)
                else:
                    available = (
                        f"{minute_src.first_bar:%Y-%m-%d} → {minute_src.last_bar:%Y-%m-%d}, "
                        f"{minute_src.completeness * 100:.0f}% completo" if minute_src else "ninguna"
                    )
                    warnings.append(
                        f"Aviso: velas de 1 minuto de {request.symbol} insuficientes para "
                        f"{data_start:%Y-%m-%d} → {data_end:%Y-%m-%d} (disponibles: {available}). "
                        f"Salidas simuladas con vela grande y SL primero (pesimista) en todo el rango."
                    )
        finally:
            await pool.close()

        if request.walk_forward:
            validator = WalkForwardValidator(
                strategy=strategy,
                df=df,
                initial_balance=request.initial_balance,
                risk_per_trade_pct=request.risk_per_trade_pct,
                n_windows=request.n_windows,
                train_pct=request.train_pct,
                minute_df=minute_df,
            )
            result = validator.run()
            
            # Usar los trades del Walk-Forward para el desglose mensual
            if request.monthly_breakdown:
                result['monthly_breakdown'] = build_monthly_breakdown(
                    result.get('trades', []), request.initial_balance
                )
        else:
            engine = BacktestEngine(
                strategy=strategy, df=df,
                initial_balance=request.initial_balance,
                risk_per_trade_pct=request.risk_per_trade_pct,
                minute_df=minute_df,
            )
            result = engine.run()
            if request.monthly_breakdown:
                result['monthly_breakdown'] = build_monthly_breakdown(
                    result['trades'], request.initial_balance
                )

        return {"status": "ok", "result": result, "warnings": warnings, "data_coverage": coverage}

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
    """Rango disponible de la MEJOR fuente única (la unión de fuentes sobrestima la historia real)."""
    try:
        pool = await get_pool()
        try:
            src = pick_best_source(await coverage_by_broker(pool, symbol, interval))
        finally:
            await pool.close()

        if src is None:
            return {"status": "ok", "data": None}

        return {
            "status": "ok",
            "data": {
                "first_date": src.first_bar.isoformat(),
                "last_date":  src.last_bar.isoformat(),
                "total_bars": src.bars,
                "broker":     src.broker,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ValidateStrategyRequest(BaseModel):
    run_backtest: bool = False
    code: str
    type: str = "python"
    config: Optional[dict] = None   # config propia de la estrategia (strategy_config)
    matrix: list[str] = ["BTCUSDT:60", "BTCUSDT:240", "ETHUSDT:60"]  # "símbolo:intervalo"
    days: int = 90

@router.post("/strategies/validate")
async def validate_strategy_code(req: ValidateStrategyRequest):
    """Smoke test: valida sintaxis y ejecuta un backtest REAL de los últimos `days` días."""
    if req.type == "json":
        try:
            import json
            json.loads(req.code)
            return {"status": "ok", "message": "JSON válido"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"JSON inválido: {str(e)}")

    import ast
    try:
        ast.parse(req.code)
    except SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Error de sintaxis Python: {e.msg} (línea {e.lineno})")

    if "|" in req.code:
        parts = req.code.split("|")
        valid_classes = ["VwapStrategy", "MeanReversionStrategy", "EmaDonchianStrategy", "DynamicStrategy"]
        if parts[0] not in valid_classes:
            raise HTTPException(status_code=400, detail=f"Clase '{parts[0]}' no registrada en el motor.")

    if req.run_backtest:
        end = datetime.now(timezone.utc).date() - timedelta(days=1)   # último día completo
        start = end - timedelta(days=req.days - 1)
        tried, errors = [], []
        for combo in req.matrix:
            symbol, _, interval = combo.partition(':')
            smoke = BacktestRequest(
                strategy='smoke-test', strategy_code=req.code, strategy_config=req.config or {},
                symbol=symbol, interval=interval,
                start_date=start.isoformat(), end_date=end.isoformat(),
                walk_forward=False, monthly_breakdown=False,
            )
            try:
                out = await run_backtest(smoke)
            except HTTPException as e:
                errors.append(f"{symbol} {interval}: {e.detail}")
                continue
            trades = int(out['result']['metrics']['total_trades'])
            tried.append(f"{symbol} {interval}={trades}")
            if trades > 0:  # basta una combinación con operaciones
                return {
                    "status": "ok",
                    "message": f"Smoke Test: {trades} operaciones en {symbol} {interval} ({start} → {end})",
                    "trades": trades,
                    "warnings": out.get('warnings', []),
                }
        if not tried:
            raise HTTPException(status_code=400, detail="Error en Smoke Test: " + " | ".join(errors))
        return {
            "status": "ok",
            "message": f"Sin operaciones en ninguna combinación ({', '.join(tried)}; {start} → {end})",
            "trades": 0,
            "warnings": errors,
        }

    return {"status": "ok", "message": "Sintaxis Python válida"}


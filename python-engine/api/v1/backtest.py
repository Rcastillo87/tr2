"""
Endpoint Backtesting V2 — Extendido
Soporta: rango de fechas, hasta 4 niveles de TP, Trailing Stop,
Proteccion por volatilidad, y desglose de resultados mes a mes.
"""

import asyncpg
from db import get_pool as shared_get_pool
import pandas as pd
import logging
from dataclasses import dataclass
import os
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from backtesting.metrics import calculate_metrics
from backtesting.engine import BacktestEngine
from collectors.funding_collector import FundingData, load_funding
from backtesting.strategies.loader import build_strategy
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
    walk_forward:        bool            = True   # True = reportar estabilidad por ventanas (sin descartar datos)
    slippage_pct:        float           = 0.0    # % por lado en cada ejecución a mercado
    n_windows:           int             = 5
    macro_trend_filter:  bool            = False

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
    # Valores válidos: None | "bybit" | "binance_vision".
    # Permite comparar la MISMA estrategia contra distintos exchanges.
    data_broker:            Optional[str]        = None
    max_leverage:           float                = 1.0
    trailing_steps:         list                 = []    # [[gain_pct, new_sl_pct], ...] (mismo default que BaseStrategy)

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


async def get_pool():
    return await shared_get_pool('backtest')  # pool compartido por proceso (db.py)


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


# Campos del request que son del backtest (datos/reporte), no de la estrategia
_RUN_ONLY_FIELDS = {'strategy', 'start_date', 'end_date', 'walk_forward', 'n_windows',
                    'monthly_breakdown', 'data_broker', 'initial_balance'}


def strategy_params(request: BacktestRequest) -> dict:
    """
    Parámetros de la estrategia: los mismos que Laravel guarda en config_params (snapshot de paper/real).
    Solo los campos ENVIADOS: un valor por defecto del request no debe pisar una opción escrita en el JSON de la
    estrategia (allow_short, hour_filter, tp2_pct...), igual que en paper/real (loader.build_strategy).
    """
    params = request.model_dump(exclude=_RUN_ONLY_FIELDS, exclude_unset=True)
    params['strategy_config'] = dict(request.strategy_config or {})
    return params


def load_strategy(request: BacktestRequest):
    """Construye la estrategia con el MISMO constructor que paper y real (loader.build_strategy)."""
    if not (request.strategy_code or '').strip():
        raise ValueError("La estrategia no trae código (strategy_code): no hay nada que ejecutar.")
    try:
        return build_strategy(strategy_params(request))
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Error compilando la estrategia: {e}") from e


WARMUP_BARS = 500  # velas previas al inicio para calentar indicadores (paper usa 500)


def build_monthly_breakdown(trades: list[dict], initial_balance: float,
                            start: datetime | None = None, end: datetime | None = None) -> list[dict]:
    """
    Métricas por mes calendario (según entry_time). Incluye TODOS los meses del rango
    pedido: un mes sin operaciones aparece con 0 (antes se omitía e inflaba el promedio
    mensual y la consistencia).
    """
    rows: dict[str, dict] = {}
    if start is not None and end is not None:
        for p in pd.period_range(start.replace(tzinfo=None), (end - timedelta(seconds=1)).replace(tzinfo=None), freq='M'):
            rows[str(p)] = {"month": str(p), "total_trades": 0, "wins": 0, "losses": 0,
                            "win_rate": 0.0, "total_pnl": 0.0, "total_pnl_pct": 0.0}
    if trades:
        df = pd.DataFrame(trades)
        df['month'] = pd.to_datetime(df['entry_time'], utc=True).dt.strftime('%Y-%m')
        for month, group in df.groupby('month'):
            total = len(group)
            wins = int((group['pnl'] > 0).sum())
            rows[month] = {
                "month":         month,
                "total_trades":  int(total),
                "wins":          wins,
                "losses":        int(total - wins),
                "win_rate":      round(wins / total * 100, 2) if total else 0.0,
                "total_pnl":     round(float(group['pnl'].sum()), 4),
                "total_pnl_pct": round(float(group['pnl_pct'].sum()), 4),
            }
    return [rows[k] for k in sorted(rows)]


def window_stats(trades: list[dict], start: datetime | None, end: datetime | None,
                 n_windows: int, initial_balance: float) -> list[dict]:
    """Estabilidad: métricas de los trades de cada tramo temporal (todos los datos simulados)."""
    if start is None or end is None or n_windows < 2:
        return []
    edges = pd.date_range(start, end, periods=n_windows + 1)
    entry_times = pd.to_datetime([t['entry_time'] for t in trades], utc=True) if trades else []
    out = []
    for k in range(n_windows):
        chunk = [t for t, ts in zip(trades, entry_times) if edges[k] <= ts < edges[k + 1]]
        m = calculate_metrics(chunk, initial_balance)
        out.append({
            "window": k + 1, "from": edges[k].isoformat(), "to": edges[k + 1].isoformat(),
            "total_trades": m['total_trades'], "win_rate": m['win_rate'],
            "profit_factor": m['profit_factor'], "sharpe_ratio": m['sharpe_ratio'],
            "max_drawdown_pct": m['max_drawdown_pct'], "total_return_pct": m['total_return_pct'],
            "total_pnl": m['total_pnl'],
        })
    return out


def evaluate_for_paper(aggregate: dict) -> dict:
    """Criterios mínimos orientativos (los mismos que usaba el walk-forward)."""
    reasons = []
    if aggregate['total_trades'] < 10:
        reasons.append(f"Trades insuficientes: {aggregate['total_trades']} (mínimo 10)")
    if aggregate['sharpe_ratio'] < 0.5:
        reasons.append(f"Sharpe Ratio bajo: {aggregate['sharpe_ratio']} (mínimo 0.5)")
    if aggregate['win_rate'] < 45:
        reasons.append(f"Win Rate bajo: {aggregate['win_rate']}% (mínimo 45%)")
    if aggregate['max_drawdown_pct'] > 15:
        reasons.append(f"Drawdown alto: {aggregate['max_drawdown_pct']}% (máximo 15%)")
    if aggregate['profit_factor'] is not None and aggregate['profit_factor'] < 1.2:
        reasons.append(f"Profit Factor bajo: {aggregate['profit_factor']} (mínimo 1.2)")
    passed = not reasons
    return {"passed": passed, "reasons": reasons or ["Estrategia aprobada para paper trading"]}


@dataclass
class BacktestData:
    df: pd.DataFrame                       # velas principales (con calentamiento)
    macro_df: Optional[pd.DataFrame]       # H4 para 'Tendencia macro H4' (None si no se pidió o no hay)
    minute_df: Optional[pd.DataFrame]      # 1m para simular salidas (None = vela grande, SL primero)
    warnings: list
    coverage: dict
    funding: Optional[FundingData] = None  # funding de Bybit del rango operado (None = no disponible)


async def load_backtest_data(pool: asyncpg.Pool, symbol: str, interval: str, start: datetime | None,
                             end: datetime | None, macro: bool, data_broker: str | None = None) -> BacktestData:
    """
    Velas de un backtest. ÚNICO camino de datos para /backtest/run y cli/param_search (la búsqueda de
    configuraciones debe dar exactamente lo mismo que un backtest de la pantalla). Sin velas -> ValueError.
    """
    warnings: list = []
    coverage: dict = {}
    # 1. Velas principales: fuente con la mayor cobertura REAL del rango pedido.
    if data_broker:
        forced = [c for c in await coverage_by_broker(pool, symbol, interval, start, end) if c.broker == data_broker]
        main_src = forced[0] if forced else None
    else:
        main_src = await resolve_backtest_source(pool, symbol, interval, start, end)
    if main_src is None:
        raise ValueError(f"No hay velas de {symbol} {interval} en el rango solicitado.")
    warnings.extend(main_src.problems())
    coverage['main'] = main_src.as_dict()
    # Calentamiento: velas previas al inicio solo para indicadores (como paper, 500 velas)
    warm_start = start - interval_delta(interval) * WARMUP_BARS if start else None
    df = await load_ohlcv(pool, symbol, interval, main_src.broker, warm_start, end)

    # Tendencia macro H4: velas H4 reales con calentamiento para la EMA (igual que paper/real)
    macro_df = None
    if macro:
        from backtesting.strategies.base_strategy import MACRO_INTERVAL, MACRO_WARMUP_BARS
        m_from = (start or df['time'].iloc[0].to_pydatetime()) - interval_delta(MACRO_INTERVAL) * MACRO_WARMUP_BARS
        m_src = await resolve_backtest_source(pool, symbol, MACRO_INTERVAL, m_from, end)
        if m_src is None:
            warnings.append(f"Aviso: sin velas H4 de {symbol}: con 'Tendencia macro H4' activa no se opera.")
        else:
            warnings.extend(m_src.problems())
            macro_df = await load_ohlcv(pool, symbol, MACRO_INTERVAL, m_src.broker, m_from, end)
            coverage['macro'] = m_src.as_dict()

    # 2. Velas de 1m para simular la salida dentro de cada vela (interval >= H1).
    #    Regla de oro 4: solo si cubren TODO el rango del dataset principal.
    #    Si no, vela grande con SL primero (pesimista) en TODO el rango: mezclar
    #    ambos métodos daría un backtest con dos criterios distintos según el mes.
    minute_df = None
    if interval_delta(interval) >= timedelta(hours=1):
        data_start = max(df['time'].iloc[0].to_pydatetime(), start) if start else df['time'].iloc[0].to_pydatetime()
        data_end = df['time'].iloc[-1].to_pydatetime() + interval_delta(interval)
        minute_src = await resolve_backtest_source(pool, symbol, '1', data_start, data_end)
        coverage['minute'] = minute_src.as_dict() if minute_src else None
        if minute_src is not None and minute_src.covers(data_start, data_end):
            minute_df = await load_ohlcv(pool, symbol, '1', minute_src.broker, data_start, data_end)
        else:
            available = (
                f"{minute_src.first_bar:%Y-%m-%d} → {minute_src.last_bar:%Y-%m-%d}, "
                f"{minute_src.completeness * 100:.0f}% completo" if minute_src else "ninguna"
            )
            warnings.append(
                f"Aviso: velas de 1 minuto de {symbol} insuficientes para "
                f"{data_start:%Y-%m-%d} → {data_end:%Y-%m-%d} (disponibles: {available}). "
                f"Salidas simuladas con vela grande y SL primero (pesimista) en todo el rango."
            )
    # 3. Funding de Bybit del rango operado (se opera en Bybit aunque las velas sean de otra fuente)
    funding = None
    f_start = start or df['time'].iloc[0].to_pydatetime()
    f_end = df['time'].iloc[-1].to_pydatetime() + interval_delta(interval)
    try:
        funding, f_warnings = await load_funding(pool, symbol, f_start, f_end)
        warnings.extend(f_warnings)
        coverage['funding'] = funding.as_dict()
    except Exception as e:  # sin funding el backtest corre igual, avisando que es optimista
        logger.error(f"[FUNDING] {symbol}: {e}")
        warnings.append(f"Aviso: funding de {symbol} no disponible ({e}): los trades no descuentan funding (optimista).")
    return BacktestData(df=df, macro_df=macro_df, minute_df=minute_df, warnings=warnings, coverage=coverage,
                        funding=funding)


@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest):
    """Backtest continuo de todo el rango, con calentamiento, régimen, slippage y comisiones."""
    warnings = []
    coverage = {}
    try:
        start, end = parse_range(request.start_date, request.end_date)
        pool = await get_pool()
        try:
            data = await load_backtest_data(pool, request.symbol, request.interval, start, end,
                                            macro=request.macro_trend_filter, data_broker=request.data_broker)
        finally:
            await pool.close()
        warnings.extend(data.warnings)
        coverage.update(data.coverage)
        df, minute_df = data.df, data.minute_df

        strategy = load_strategy(request)
        if request.macro_trend_filter:
            strategy.macro_df = data.macro_df   # None si no hay H4: con el filtro activo no se opera

        strategy.slippage_pct = float(request.slippage_pct)
        if request.slippage_pct <= 0:
            warnings.append("Aviso: slippage en 0%: entradas y salidas al precio exacto (optimista frente a órdenes reales).")

        # Simulación CONTINUA de todo el rango (sin descartar datos)
        engine = BacktestEngine(
            strategy=strategy, df=df,
            initial_balance=request.initial_balance,
            risk_per_trade_pct=request.risk_per_trade_pct,
            minute_df=minute_df,
            trade_from=start,
            funding=data.funding,
        )
        result = engine.run()
        result['aggregate_metrics'] = result['metrics']
        result['n_windows'] = request.n_windows if request.walk_forward else 1
        result['window_results'] = (window_stats(result['trades'], start, end, request.n_windows, request.initial_balance)
                                    if request.walk_forward else [])
        verdict = evaluate_for_paper(result['metrics'])
        result.update(passed=verdict['passed'], pass_reasons=verdict['reasons'], ready_for_paper=verdict['passed'])
        if request.monthly_breakdown:
            result['monthly_breakdown'] = build_monthly_breakdown(result['trades'], request.initial_balance, start, end)

        return {"status": "ok", "result": result, "warnings": warnings, "data_coverage": coverage}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


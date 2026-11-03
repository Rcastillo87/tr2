"""
Endpoint Data Collector V2
"""
import asyncio
import asyncpg
import time
from datetime import datetime, timezone

import httpx
from db import get_pool as shared_get_pool
import logging
import os
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from collectors.ohlcv_collector import OhlcvCollector

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"


async def get_pool():
    return await shared_get_pool('live')  # pool compartido por proceso (db.py)


_run_lock = asyncio.Lock()


@router.post("/collector/run")
async def run_collector():
    """
    Actualiza todas las series activas. Nunca dos corridas a la vez: si la anterior sigue viva responde
    status=busy sin hacer nada (antes se solapaban cuando una corrida pasaba de 60 s).
    """
    if _run_lock.locked():
        return {"status": "busy", "results": {}, "total_saved": 0, "errors": {}, "duration_s": 0}
    async with _run_lock:
        t0 = time.monotonic()
        pool = None
        try:
            pool      = await get_pool()
            collector = OhlcvCollector(pool)
            errors: dict = {}
            results   = await collector.run_all(errors)
            return {
                "status":      "ok",
                "results":     results,
                "total_saved": sum(v for v in results.values() if v >= 0),
                "series":      len(results),
                "failed":      sum(1 for v in results.values() if v < 0),
                "errors":      errors,
                "aborted":     collector.last_abort_reason,   # C-02: corrida cortada por límite de tasa de Bybit
                "catching_up": getattr(collector, 'catching_up', {}),   # C-05: series poniéndose al día por ventanas
                "duration_s":  round(time.monotonic() - t0, 2),
            }
        except Exception as e:
            logger.error(f"Collector error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if pool is not None:   # también si falla (antes el pool quedaba abierto)
                await pool.close()


@router.post("/collector/initial-load")
async def initial_load():
    """Ejecuta la carga histórica inicial para todos los símbolos e intervalos activos."""
    try:
        pool      = await get_pool()
        collector = OhlcvCollector(pool)

        # Leer configs activas desde DB
        active_configs = await collector.get_active_configs()

        results = {}
        for symbol, interval, broker in active_configs:
            try:
                saved = await collector.initial_load(symbol, interval, broker)
                results[f"{symbol}/{interval}"] = saved
            except Exception as e:
                logger.error(f"[{symbol}/{interval}] Error en carga inicial: {e}")
                results[f"{symbol}/{interval}"] = -1

        await pool.close()
        return {
            "status":      "ok",
            "results":     results,
            "total_saved": sum(v for v in results.values() if v >= 0),
        }
    except Exception as e:
        logger.error(f"Initial load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collector/status")
async def collector_status():
    """Retorna el estado actual de la recolección — solo simbolos/intervalos activos."""
    try:
        pool      = await get_pool()
        collector = OhlcvCollector(pool)

        active_configs = await collector.get_active_configs()

        status = {}
        for symbol, interval, broker in active_configs:
            last = await collector.get_last_timestamp(symbol, interval, broker)
            status[f"{symbol}/{interval}"] = {
                "last_candle": last.isoformat() if last else None,
                "has_data":    last is not None,
            }

        await pool.close()
        return {"status": "ok", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints de gestión de históricos (2026-10-21)
# ═══════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class BackfillRequest(BaseModel):
    symbol: str
    interval: str
    broker: str
    start_date: str          # 'YYYY-MM-DD'
    end_date: Optional[str] = None  # None = hasta ahora


class InvalidateRequest(BaseModel):
    symbol: str
    interval: str
    broker: str
    start_date: Optional[str] = None  # None = desde el principio
    end_date: Optional[str] = None
    confirm: bool = False  # requiere confirm=True para ejecutar


class AddSymbolRequest(BaseModel):
    symbol: str
    broker: str
    intervals: list[str]
    active: bool = True


@router.get("/collector/coverage")
async def collector_coverage(
    broker: Optional[str] = None,
    symbol: Optional[str] = None,
    interval: Optional[str] = None,
):
    """Devuelve tabla completa de cobertura: broker × symbol × interval con rango y filas."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            where_clauses = []
            args = []
            i = 1
            if broker:
                where_clauses.append(f"broker = ${i}"); args.append(broker); i += 1
            if symbol:
                where_clauses.append(f"symbol = ${i}"); args.append(symbol); i += 1
            if interval:
                where_clauses.append(f"interval = ${i}"); args.append(interval); i += 1
            where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            rows = await conn.fetch(
                f"""
                SELECT broker, symbol, interval,
                       COUNT(*) AS total,
                       MIN(time) AS desde,
                       MAX(time) AS hasta,
                       (MAX(time) > now() - interval '1 hour') AS actualizado
                FROM ohlcv_data
                {where_sql}
                GROUP BY broker, symbol, interval
                ORDER BY broker, symbol, interval::text
                """,
                *args,
            )
        await pool.close()
        return {
            "status": "ok",
            "data": [
                {
                    "broker": r["broker"],
                    "symbol": r["symbol"],
                    "interval": r["interval"],
                    "total": r["total"],
                    "desde": r["desde"].isoformat() if r["desde"] else None,
                    "hasta": r["hasta"].isoformat() if r["hasta"] else None,
                    "actualizado": bool(r["actualizado"]),
                }
                for r in rows
            ],
        }
    except Exception as e:
        logger.error(f"[COVERAGE] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collector/symbols")
async def collector_symbols():
    """Símbolos configurados en collector_configs + estado."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol, interval, broker, active
                FROM collector_configs
                ORDER BY broker, symbol, interval::text
                """,
            )
        await pool.close()
        return {
            "status": "ok",
            "data": [dict(r) for r in rows],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collector/backfill")
async def collector_backfill(req: BackfillRequest):
    """Descarga un rango específico y lo inserta. Útil para llenar gaps."""
    try:
        from collectors.ohlcv_collector import OhlcvCollector
        pool = await get_pool()
        collector = OhlcvCollector(pool)

        start_ts = int(datetime.fromisoformat(req.start_date).timestamp())
        end_ts = int(datetime.fromisoformat(req.end_date).timestamp()) if req.end_date else int(datetime.now().timestamp())

        if req.broker == "bybit":
            bars = await collector.fetch_from_bybit(req.symbol, req.interval, start_ts, end_ts)
        else:
            raise ValueError(f"Broker no soportado: {req.broker}")

        saved = await collector.save_bars(bars, broker=req.broker)
        await pool.close()
        return {
            "status": "ok",
            "velas_insertadas": saved,
            "rango": {"desde": req.start_date, "hasta": req.end_date or "now"},
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[BACKFILL] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collector/invalidate")
async def collector_invalidate(req: InvalidateRequest):
    """Borra un rango de ohlcv_data. Requiere confirm=True (protección)."""
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Debes pasar confirm=True para ejecutar esta operación destructiva",
        )
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            where = "broker=$1 AND symbol=$2 AND interval=$3"
            args = [req.broker, req.symbol, req.interval]
            if req.start_date:
                where += " AND time >= $4"
                args.append(datetime.fromisoformat(req.start_date))
            if req.end_date:
                where += f" AND time <= ${len(args)+1}"
                args.append(datetime.fromisoformat(req.end_date))

            result = await conn.execute(f"DELETE FROM ohlcv_data WHERE {where}", *args)
            deleted = int(result.split()[-1]) if result else 0
        await pool.close()
        return {
            "status": "ok",
            "velas_borradas": deleted,
        }
    except Exception as e:
        logger.error(f"[INVALIDATE] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────── Recarga = re-verificación completa sin borrar (C-10) ───────────────
# Antes: DELETE de toda la serie y descarga desde cero dentro de la petición (un corte la dejaba vacía o a medias,
# Paper/Real/backtests leían un hueco y Laravel cortaba a los 600 s). Ahora compara toda la serie contra Bybit en
# segundo plano, corrige con UPSERT y elimina solo sobrantes confirmados al final. Una a la vez.
_reload_state: dict = {'running': False, 'task': None, 'progress': None, 'result': None, 'error': None,
                       'started_at': None, 'finished_at': None}


def _reload_public() -> dict:
    return {k: v for k, v in _reload_state.items() if k != 'task'}


async def _reload_job(symbol: str, interval: str) -> None:
    from cli.collector_audit import reverify_series
    from collectors.ohlcv_collector import HISTORY_DAYS
    st = _reload_state
    try:
        pool = await get_pool()
        collector = OhlcvCollector(pool)
        async with httpx.AsyncClient(timeout=30) as client:
            st['result'] = await reverify_series(
                pool, collector, client, symbol, interval, HISTORY_DAYS,
                progress=lambda p: st.__setitem__('progress', p))
        r = st['result']
        logger.info(f"[RELOAD] {symbol}/{interval}: {r['compared']} comparadas, {r['repaired']} corregidas, "
                    f"{r['extra_deleted']} sobrantes eliminadas, completa={r['complete']} {r['stopped'] or ''}")
    except asyncio.CancelledError:
        st['error'] = 'interrumpida (el motor se detuvo); no se eliminó nada'
        raise
    except Exception as e:   # noqa: BLE001 - se informa en el estado; nada se borró
        logger.error(f"[RELOAD] {symbol}/{interval} error: {e}")
        st['error'] = f'{e}'[:300] + ' (no se eliminó nada)'
    finally:
        st['running'], st['task'] = False, None
        st['finished_at'] = datetime.now(timezone.utc).isoformat()


@router.post("/collector/reload/{symbol}/{interval}/{broker}")
async def collector_reload(symbol: str, interval: str, broker: str, confirm: bool = False):
    """Re-verifica TODA la serie contra Bybit en segundo plano (no la vacía). Requiere confirm=True. 409 si hay otra."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Debes pasar ?confirm=true para ejecutar esta operación")
    if broker != 'bybit':
        raise HTTPException(status_code=400, detail=f"Broker no soportado: {broker}")
    from collectors.broker_resolver import interval_delta
    try:
        interval_delta(interval)
    except Exception:   # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Intervalo no soportado: {interval}")
    if _reload_state['running']:
        p = _reload_state['progress'] or {}
        raise HTTPException(status_code=409, detail=(
            f"Ya hay una recarga en curso ({_reload_state.get('symbol')}/{_reload_state.get('interval')}); "
            f"espera a que termine" + (f" (ventana {p.get('windows')} de {p.get('total_windows')})" if p else '')))
    now = datetime.now(timezone.utc).isoformat()
    _reload_state.update(running=True, symbol=symbol, interval=interval, progress=None, result=None, error=None,
                         started_at=now, finished_at=None)
    _reload_state['task'] = asyncio.create_task(_reload_job(symbol, interval))
    return {"status": "started", **_reload_public()}


@router.get("/collector/reload-status")
async def collector_reload_status():
    return {"status": "ok", **_reload_public()}


@router.post("/collector/add-symbol")
async def collector_add_symbol(req: AddSymbolRequest):
    """Añade un símbolo a collector_configs (activo o no)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            inserted = 0
            for interval in req.intervals:
                result = await conn.execute(
                    """
                    INSERT INTO collector_configs (symbol, interval, broker, active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, now(), now())
                    ON CONFLICT (symbol, interval, broker) DO NOTHING
                    """,
                    req.symbol, interval, req.broker, req.active,
                )
                if result.startswith("INSERT"):
                    inserted += 1
        await pool.close()
        return {
            "status": "ok",
            "inserted": inserted,
            "configs": [{"symbol": req.symbol, "interval": i, "broker": req.broker} for i in req.intervals],
        }
    except Exception as e:
        logger.error(f"[ADD_SYMBOL] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints módulo unificado (2026-10-21)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/collector/unified")
async def collector_unified(
    broker: Optional[str] = None,
    symbol: Optional[str] = None,
):
    """
    Data Collector: collector_configs + primera y última vela REAL de cada serie (historial completo, por índice:
    sin contar millones de filas) + atraso y estado con la regla POR INTERVALO (la última vela guardada es la que
    está en curso, así que en 4h/1D su hora de inicio puede ser de hace horas y estar al día):
      ok       = atraso ≤ 1 vela + 2 min
      atrasado = atraso ≤ 3 velas + 2 min
      detenido = más atrasado
      vacio    = sin velas
    """
    from datetime import timezone as _tz
    from collectors.broker_resolver import interval_delta
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            where = []
            args = []
            i = 1
            if broker:
                where.append(f"cc.broker = ${i}"); args.append(broker); i += 1
            if symbol:
                where.append(f"cc.symbol = ${i}"); args.append(symbol); i += 1
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""

            rows = await conn.fetch(
                f"""
                SELECT cc.broker, cc.symbol, cc.interval, cc.active,
                       (SELECT o.time FROM ohlcv_data o
                         WHERE o.broker = cc.broker AND o.symbol = cc.symbol AND o.interval = cc.interval
                         ORDER BY o.time ASC LIMIT 1) AS desde,
                       (SELECT o.time FROM ohlcv_data o
                         WHERE o.broker = cc.broker AND o.symbol = cc.symbol AND o.interval = cc.interval
                         ORDER BY o.time DESC LIMIT 1) AS hasta
                FROM collector_configs cc
                {where_sql}
                ORDER BY cc.broker, cc.symbol, cc.interval::text
                """,
                *args,
            )
        await pool.close()
        now = datetime.now(_tz.utc)
        grace = 120
        data = []
        for r in rows:
            try:
                step_s = int(interval_delta(r["interval"]).total_seconds())
            except ValueError:
                step_s = None
            lag_s = int((now - r["hasta"]).total_seconds()) if r["hasta"] else None
            if lag_s is None:
                estado = "vacio"
            elif step_s is None or lag_s <= step_s + grace:
                estado = "ok"
            elif lag_s <= 3 * step_s + grace:
                estado = "atrasado"
            else:
                estado = "detenido"
            data.append({
                "broker": r["broker"], "symbol": r["symbol"], "interval": r["interval"],
                "active": bool(r["active"]),
                "desde": r["desde"].isoformat() if r["desde"] else None,
                "hasta": r["hasta"].isoformat() if r["hasta"] else None,
                "lag_s": lag_s, "step_s": step_s, "estado": estado,
                "actualizado": estado == "ok",
            })
        return {"status": "ok", "data": data}
    except Exception as e:
        logger.error(f"[UNIFIED] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collector/toggle-all/{broker}/{symbol}")
async def collector_toggle_all(broker: str, symbol: str, active: bool):
    """Activa o desactiva TODOS los intervals de un símbolo."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE collector_configs SET active = $1, updated_at = now() WHERE broker = $2 AND symbol = $3",
                active, broker, symbol,
            )
            count = int(result.split()[-1]) if result else 0
        await pool.close()
        return {"status": "ok", "updated": count, "active": active}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collector/toggle-one")
async def collector_toggle_one(body: dict):
    """Activa o desactiva UN interval específico de un símbolo."""
    try:
        broker = body.get("broker")
        symbol = body.get("symbol")
        interval = body.get("interval")
        active = bool(body.get("active"))
        if not all([broker, symbol, interval]):
            raise HTTPException(status_code=400, detail="Faltan parámetros: broker, symbol, interval")
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE collector_configs SET active = $1, updated_at = now() WHERE broker = $2 AND symbol = $3 AND interval = $4",
                active, broker, symbol, interval,
            )
            count = int(result.split()[-1]) if result else 0
        await pool.close()
        return {"status": "ok", "updated": count, "active": active}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

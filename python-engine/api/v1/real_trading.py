"""
Endpoint Real Trading V2
Recibe las credenciales desencriptadas desde Laravel (que las lee del DB
y las desencripta usando la APP_KEY de Laravel). Python nunca lee
credenciales directamente de la DB para evitar el problema de encriptacion.
"""

import asyncio
import asyncpg
from db import get_json_pool
import logging
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from trading.real_trader import (RealTrader, BybitClient, CIRCUIT_BREAKER_THRESHOLD, BybitAPIError,
                                 ORDER_DEAD_STATUSES, epoch_ms)
from trading.risk_manager import RiskManager
from trading.broker_events import emit_event
from trading.bybit_client import api_permission_problems

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', '')

class SubscriptionPayload(BaseModel):
    subscription_id:          int
    user_id:                  int
    broker_account_id:        int
    paper_strategy_config_id: Optional[int] = None
    strategy:                 str
    symbol:                   str
    interval:                 str
    strategy_class:           Optional[str] = None
    config_params:            Optional[dict] = None
    risk_override_pct:        Optional[float] = None   # sin declararlo Pydantic lo descartaba


class AccountPayload(BaseModel):
    id:           int
    broker:       str
    account_type: str
    api_key:      str
    api_secret:   str
    subscriptions: list[SubscriptionPayload]
    # False: cuenta pausada con posiciones abiertas -> se gestionan (BE, trailing, tiempo) pero no se abre nada
    entries_allowed: bool = True


def _build_broker_client(account) -> BybitClient:
    """Cliente del broker de la cuenta. Hoy solo Bybit."""
    if account.broker != 'bybit':
        raise ValueError(f"Broker no soportado en Real: {account.broker}")
    return BybitClient(
        api_key      = account.api_key,
        api_secret   = account.api_secret,
        account_type = account.account_type,
    )


class RealTickRequest(BaseModel):
    accounts: list[AccountPayload]


def instantiate_strategy(sub: SubscriptionPayload):
    """Misma construcción que paper y backtest (strategy_code compilado + params de la config)."""
    from backtesting.strategies.loader import build_strategy
    params = dict(sub.config_params or {})
    if not params:
        raise ValueError(f"Suscripción #{sub.subscription_id} sin config_params")
    params['symbol']   = sub.symbol
    params['interval'] = sub.interval
    instance = build_strategy(params)
    instance.params = params
    return instance


# Estado de las claves por cuenta (en memoria del motor): solo se emite evento en los cambios.
_auth_state: dict[int, bool] = {}


async def _track_auth(pool, account_id: int, ok: bool | None, reason: str) -> None:
    """Emite api_auth_failed / api_auth_ok solo al cambiar el estado (y el primer OK tras arrancar el motor,
    que cierra un aviso que hubiera quedado abierto). ok=None (no se pudo saber) no cambia nada."""
    if ok is None:
        return
    prev = _auth_state.get(account_id)
    _auth_state[account_id] = ok
    if ok is False and prev is not False:
        await emit_event(pool, account_id, 'api_auth_failed', reason=reason)
    elif ok is True and prev is not True:
        await emit_event(pool, account_id, 'api_auth_ok')


# Permisos de la clave por cuenta (REAL-09, opción A del dueño: solo avisa, la cuenta sigue operando).
# Se revisan una vez al día por cuenta; si Bybit no responde, se reintenta en una hora.
PERMISSIONS_CHECK_EVERY = timedelta(hours=24)
PERMISSIONS_RETRY_AFTER = timedelta(hours=1)
_perm_state: dict[int, bool] = {}
_perm_next_check: dict[int, datetime] = {}


async def _track_permissions(pool, account_id: int, client, now: datetime | None = None) -> None:
    """Emite api_permissions_bad / api_permissions_ok solo al cambiar (y el primero tras arrancar el motor:
    Laravel no repite un incidente abierto ni avisa un cierre si no había incidente). Nunca bloquea el tick."""
    now = now or datetime.now(timezone.utc)
    if now < _perm_next_check.get(account_id, now - timedelta(seconds=1)):
        return
    try:
        info = await client.get_api_key_info()
    except Exception as e:  # noqa: BLE001 - un fallo aquí no puede frenar la gestión de posiciones
        logger.error(f"[REAL] permisos de la clave (cuenta {account_id}): {e}")
        info = None
    if info is None:
        _perm_next_check[account_id] = now + PERMISSIONS_RETRY_AFTER
        return
    _perm_next_check[account_id] = now + PERMISSIONS_CHECK_EVERY
    problems = api_permission_problems(info)
    prev = _perm_state.get(account_id)
    _perm_state[account_id] = not problems
    if problems and prev is not False:
        await emit_event(pool, account_id, 'api_permissions_bad', problems=problems)
    elif not problems and prev is not True:
        await emit_event(pool, account_id, 'api_permissions_ok')


async def _process_account(trader, account):
    account_key     = f"account_{account.id}_{account.broker}"
    account_results = {}
    try:
        client = _build_broker_client(account)
        auth_ok, auth_reason = await client.check_auth()
        await _track_auth(trader.pool, account.id, auth_ok, auth_reason)
        if auth_ok is False:
            return account_key, {"error": f"Bybit rechaza las claves API: {auth_reason}"}
        await trader.ensure_month_baseline(account.id, client)
        await _track_permissions(trader.pool, account.id, client)

        entries_allowed = account.entries_allowed
        error_count = await trader.get_circuit_breaker_errors(account.id) if entries_allowed else 0
        if error_count >= CIRCUIT_BREAKER_THRESHOLD:
            last_errors = await trader.get_last_error_messages(account.id)
            non_critical_patterns = [
                'firma', 'timestamp', '10001', 'stopLoss', 'takeProfit',
                'rechazada por bybit', 'qty', 'invalid', 'no confirmada'
            ]
            critical = any(
                msg and not any(p in msg.lower() for p in non_critical_patterns)
                for msg in last_errors
                if msg
            )
            if critical:
                await trader.pause_account(
                    account.id,
                    f"{error_count} errores criticos en las ultimas 2h"
                )
                logger.error(f"[CIRCUIT] Cuenta {account.id} pausada por {error_count} errores criticos")
                entries_allowed = False  # las posiciones abiertas se siguen gestionando en este mismo tick
            else:
                await trader.clear_non_critical_errors(account.id)
                logger.warning(f"[CIRCUIT] {error_count} errores no criticos ignorados para cuenta {account.id}")

        monitor_result = await trader.monitor_open_trades(account.id, client)
        account_results["monitor"] = monitor_result

        # Cuenta pausada o kill switch: sin entradas ni reversas, pero las posiciones abiertas con salida por señal
        # opuesta se siguen gestionando (igual que Paper). check_new_signals sale enseguida si no hay posición.
        kill = await RiskManager(trader.pool).is_kill_switch_active()
        entries_ok = entries_allowed and not kill
        if not entries_allowed:
            account_results["entries"] = "Cuenta pausada — solo se gestionan las posiciones abiertas"
        elif kill:
            account_results["entries"] = "KILL SWITCH activo — sin nuevas entradas"

        signal_results = {}
        for sub in account.subscriptions:
            sub_dict = sub.dict()
            try:
                strategy = instantiate_strategy(sub)
                sub_dict["broker"] = account.broker
                result   = await trader.check_new_signals(sub_dict, strategy, client, entries_allowed=entries_ok)
                signal_results[sub.strategy] = result
            except Exception as e:
                logger.error(f"[REAL] Error procesando {sub.strategy}: {e}")
                signal_results[sub.strategy] = f"ERROR: {str(e)}"

        account_results["signals"] = signal_results
        return account_key, account_results

    except Exception as e:
        logger.error(f"[REAL] Error procesando cuenta {account.id}: {e}")
        return account_key, {"error": f"Error inesperado procesando la cuenta: {str(e)}"}


_account_locks: dict[int, asyncio.Lock] = {}

# Espera máxima del circuit breaker y de la reconciliación por el turno de una cuenta (s). Menor que los timeouts
# HTTP de sus jobs (25 s y 90 s): si se agota, la cuenta se omite y queda para el próximo ciclo.
CIRCUIT_BREAKER_LOCK_WAIT = 15.0
RECONCILE_LOCK_WAIT = 20.0
# El tick también espera (R-14): circuit breaker y tick salen del mismo schedule:run cada minuto y llegan casi juntos;
# con espera 0 el tick se omitía minuto tras minuto y las posiciones quedaban sin BE, trailing ni cierre por tiempo.
# Menor que el timeout HTTP de RealTradingAccountTickJob (60 s).
TICK_LOCK_WAIT = 15.0


async def _exclusive(account_id: int, wait: float, work):
    """
    Turno exclusivo de la cuenta para todo lo que abre, cierra o reescribe sus trades: tick, circuit breaker y
    reconciliación nunca corren a la vez sobre la misma cuenta (N-07). Un solo proceso del motor (uvicorn sin
    --workers): el candado es de memoria. wait=0 (tick, cada minuto): si la cuenta está ocupada se omite; wait>0:
    espera hasta ese plazo. Devuelve (True, resultado de work()) o (False, None) si no obtuvo el turno.
    """
    lock = _account_locks.setdefault(account_id, asyncio.Lock())
    if wait <= 0:
        if lock.locked():
            return False, None
        await lock.acquire()   # libre: no suspende
    else:
        try:
            await asyncio.wait_for(lock.acquire(), timeout=wait)
        except asyncio.TimeoutError:
            return False, None
    try:
        return True, await work()
    finally:
        lock.release()


async def _process_account_locked(trader, account):
    """Un tick a la vez por cuenta. Espera su turno hasta TICK_LOCK_WAIT (el circuit breaker o la reconciliación pueden
    tenerla unos segundos); si se agota, se omite con 'skipped' (estructura que Laravel distingue de 'signals')."""
    got, result = await _exclusive(account.id, TICK_LOCK_WAIT, lambda: _process_account(trader, account))
    if not got:
        logger.warning(f"[REAL] Tick de la cuenta {account.id} omitido: ocupada más de {TICK_LOCK_WAIT:g} s")
        return f"account_{account.id}_{account.broker}", {
            "skipped": f"la cuenta tiene otro proceso en curso más de {TICK_LOCK_WAIT:g} s: tick omitido"}
    return result


@router.post('/real/tick')
async def real_tick(
    request: RealTickRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    # max_size=5: cada pedido ahora maneja tipicamente UNA cuenta (desde
    # RealTradingAccountTickJob), coincide con el limite de 5 trades
    # simultaneos por cuenta (semaphore en monitor_open_trades). Antes
    # necesitaba mas margen porque un solo pedido procesaba TODAS las
    # cuentas juntas.
    pool    = await get_json_pool()  # compartido (db.py), con codec jsonb
    trader  = RealTrader(pool)
    results = {}

    try:
        if not request.accounts:
            return {'status': 'ok', 'message': 'Sin cuentas activas', 'results': {}}

        account_results_list = await asyncio.gather(
            *[_process_account_locked(trader, account) for account in request.accounts],
            return_exceptions=True
        )
        for item in account_results_list:
            if isinstance(item, Exception):
                logger.error(f"[REAL] Excepcion no capturada procesando una cuenta: {item}")
                continue
            account_key, account_results = item
            results[account_key] = account_results

    finally:
        await pool.close()

    return {'status': 'ok', 'results': results}


@router.post('/real/circuit-breaker-max-loss')
async def circuit_breaker_max_loss(
    request: RealTickRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    pool    = await get_json_pool()  # compartido (db.py), con codec jsonb
    trader  = RealTrader(pool)
    results = {}

    try:
        if not request.accounts:
            return {'status': 'ok', 'message': 'Sin cuentas activas', 'results': {}}

        async def _check_account(account):
            client = _build_broker_client(account)
            try:
                got, result = await _exclusive(account.id, CIRCUIT_BREAKER_LOCK_WAIT,
                                               lambda: trader.check_max_loss_circuit_breaker(account.id, client))
                if not got:
                    logger.warning(f"[CIRCUIT-MAXLOSS] Cuenta {account.id} ocupada más de {CIRCUIT_BREAKER_LOCK_WAIT:g} s: "
                                   f"se revisa en el próximo ciclo")
                    return account.id, {"skipped": "cuenta ocupada por otro proceso"}
                return account.id, result
            except Exception as e:
                logger.error(f"[CIRCUIT-MAXLOSS] Error inesperado en cuenta {account.id}: {e}")
                return account.id, {"error": str(e)}

        account_results_list = await asyncio.gather(
            *[_check_account(account) for account in request.accounts],
            return_exceptions=True
        )
        for item in account_results_list:
            if isinstance(item, Exception):
                logger.error(f"[CIRCUIT-MAXLOSS] Excepcion no capturada: {item}")
                continue
            account_id, account_result = item
            results[f"account_{account_id}"] = account_result

    finally:
        await pool.close()

    return {'status': 'ok', 'results': results}


# Aperturas interrumpidas: open_trade tarda < 1 min; una fila en 'pending_open' más vieja que esto quedó
# a medias (reinicio o caída del motor entre el registro y la confirmación).
PENDING_OPEN_STALE = '3 minutes'


async def _recover_pending_opens(trader, client, account, pool, results) -> None:
    """Resuelve cada 'pending_open' viejo preguntándole a Bybit por SU orden (order_link_id):
    ejecutada y viva -> se adopta; ejecutada y ya cerrada -> se liquida con Bybit; nunca ejecutada -> failed.
    Si Bybit no responde, no se toca (próximo ciclo)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT rt.*, COALESCE(rt.config_snapshot, psc.params) AS snapshot
                FROM real_trades rt
                LEFT JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id
                LEFT JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id
                WHERE rt.broker_account_id = $1 AND rt.status = 'pending_open'
                  AND rt.created_at < now() - interval '{PENDING_OPEN_STALE}'
                ORDER BY rt.id""",
            account.id
        )
    for row in rows:
        trade = {**dict(row), 'config_snapshot': row['snapshot']}
        tid, symbol, link = trade['id'], trade['symbol'], trade.get('order_link_id')
        order = None
        try:
            if link:
                order = await client.get_order_by_link_id(symbol, link)   # None = no existe; lanza si no se sabe
            executed = (order is not None and order.get('orderStatus') not in ORDER_DEAD_STATUSES) if link else None
            position = await client.get_open_position(symbol) if executed is not False else None
        except BybitAPIError as e:
            logger.error(f"[RECONCILE] pending_open #{tid} {symbol}: Bybit no responde ({e}) — próximo ciclo")
            results['ok'].append({'trade_id': tid, 'symbol': symbol, 'note': 'pending_open_api_error'})
            continue

        live = bool(position) and float(position.get('size', 0) or 0) > 0
        if live:
            async with pool.acquire() as conn:
                other = await conn.fetchval(
                    "SELECT id FROM real_trades WHERE broker_account_id=$1 AND symbol=$2"
                    " AND status IN ('open','pending_close') AND id<>$3 LIMIT 1",
                    account.id, symbol, tid
                )
            if other and not link:
                # fila antigua sin orderLinkId y la posición ya la gestiona otro trade: esta no se ejecutó
                live = False
        if live:
            avg = float(position.get('avgPrice', 0) or trade['entry_price'])
            adopted = await _adopt_position(trader, client, trade, avg, trade['side'], symbol)
            if order and order.get('orderId'):
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE real_trades SET order_id=$1 WHERE id=$2", order['orderId'], tid)
            await emit_event(pool, account.id, 'reconcile_adopted', tid, symbol=symbol, side=trade['side'],
                             kind='pending', protected=adopted)
            results['reconciled'].append({'trade_id': tid, 'symbol': symbol, 'reason': 'pending_open_adopted'})
            continue

        if executed:
            # La orden se ejecutó pero la posición ya no existe (p. ej. tocó el SL): se liquida con Bybit
            avg = float(order.get('avgPrice') or 0) or float(trade['entry_price'])
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE real_trades SET status='open', entry_price=$1, order_id=$2, updated_at=now()"
                    " WHERE id=$3 AND status='pending_open'", avg, order.get('orderId'), tid)
            trade.update(status='open', entry_price=avg)
            ref = trade['entry_time'] if trade['entry_time'].tzinfo else trade['entry_time'].replace(tzinfo=timezone.utc)
            settled = await trader.settle_exchange_close(trade, client, account.id, int(ref.timestamp() * 1000))
            if settled is None:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE real_trades SET status='orphaned', error_message="
                        "'Posicion cerrada en Bybit, no se pudo obtener pnl real (apertura interrumpida)',"
                        " updated_at=now() WHERE id=$1", tid)
            else:
                await emit_event(pool, account.id, 'reconcile_closed', tid, symbol=symbol)
                results['reconciled'].append({'trade_id': tid, 'symbol': symbol, 'reason': 'pending_open_closed'})
            continue

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE real_trades SET status='failed', error_message=$1, updated_at=now()"
                " WHERE id=$2 AND status='pending_open'",
                'Apertura interrumpida: la orden no llegó a ejecutarse en Bybit', tid)
        logger.warning(f"[RECONCILE] pending_open #{tid} {symbol} → failed (la orden no se ejecutó)")
        await emit_event(pool, account.id, 'reconcile_discarded', tid, symbol=symbol)


@router.post('/real/reconcile')
async def reconcile(
    request: RealTickRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    pool    = await get_json_pool()  # compartido (db.py), con codec jsonb
    trader  = RealTrader(pool)
    results = {'reconciled': [], 'orphaned': [], 'ok': []}

    try:
        async def _reconcile_account(account):
            client = _build_broker_client(account)

            # 0. Aperturas interrumpidas ('pending_open' viejos)
            await _recover_pending_opens(trader, client, account, pool, results)

            # 1. Trades abiertos en DB cuya posición ya no existe en Bybit
            for trade in await trader.get_open_trades(account.id):
                symbol = trade['symbol']
                if datetime.now(timezone.utc) - trade['entry_time'].replace(tzinfo=timezone.utc) < timedelta(minutes=10):
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol})
                    continue
                try:
                    position = await client.get_open_position(symbol)
                except BybitAPIError as e:
                    logger.error(f"[RECONCILE] {symbol} #{trade['id']}: error consultando Bybit ({e}) — se omite, NO se marca cerrado")
                    results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'error': str(e)})
                    continue
                if position:
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol})
                    continue
                settled = await trader.settle_exchange_close(trade, client, account.id, epoch_ms(trade['entry_time']))
                if settled is None:
                    logger.warning(f"[RECONCILE] Trade #{trade['id']} {symbol}: cerrada en Bybit sin closed-pnl — 'orphaned'")
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE real_trades SET status = 'orphaned',
                                   error_message = 'Posicion cerrada en Bybit, no se pudo obtener pnl real (get_closed_pnl sin match)',
                                   updated_at = now()
                               WHERE id = $1 AND status IN ('open', 'pending_close')""",
                            trade['id']
                        )
                    results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'no_exit_price_found'})
                else:
                    results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'closed_on_exchange'})
                    if settled:
                        await emit_event(pool, account.id, 'reconcile_closed', trade['id'], symbol=symbol)

            # 2. Trades 'orphaned'
            async with pool.acquire() as conn:
                orphaned_trades = await conn.fetch(
                    """SELECT rt.*, COALESCE(rt.config_snapshot, psc.params) AS snapshot
                       FROM real_trades rt
                       LEFT JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id
                       LEFT JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id
                       WHERE rt.broker_account_id = $1 AND rt.status = 'orphaned'
                       ORDER BY rt.created_at DESC""",
                    account.id
                )
            for row in orphaned_trades:
                trade  = {**dict(row), 'config_snapshot': row['snapshot']}
                symbol = trade['symbol']

                # 2a. Orphaned de CIERRE: la posición cerró pero faltaba el pnl → reintentar
                if trade['error_message'] and 'no se pudo obtener pnl real' in trade['error_message']:
                    trade['status'] = 'open'  # close_trade solo actualiza filas 'open'
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE real_trades SET status='open' WHERE id=$1 AND status='orphaned'", trade['id'])
                    settled = await trader.settle_exchange_close(trade, client, account.id, epoch_ms(trade['entry_time']),
                                                                 exit_reason='reconciled_sl_tp_bybit')
                    if settled is None:
                        async with pool.acquire() as conn:
                            await conn.execute("UPDATE real_trades SET status='orphaned' WHERE id=$1 AND status='open'", trade['id'])
                        results['ok'].append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_pending_pnl'})
                    else:
                        results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'orphaned_pnl_recovered'})
                        if settled:
                            await emit_event(pool, account.id, 'reconcile_closed', trade['id'], symbol=symbol)
                    continue

                # 2b. Orphaned de APERTURA (confirmación perdida): ¿hay posición real?
                try:
                    position = await client.get_open_position(symbol)
                except BybitAPIError as e:
                    logger.error(f"[RECONCILE] Orphaned #{trade['id']} {symbol}: error consultando Bybit ({e}) — próximo ciclo")
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_api_error'})
                    continue
                if position and float(position.get('size', 0) or 0) > 0:
                    avg_price = float(position.get('avgPrice', 0) or trade['entry_price'])
                    adopted = await _adopt_position(trader, client, trade, avg_price, trade['side'], trade['symbol'])
                    await emit_event(pool, account.id, 'reconcile_adopted', trade['id'], symbol=symbol,
                                     side=trade['side'], kind='orphaned', protected=adopted)
                    if adopted:
                        results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'orphaned_adopted'})
                    else:
                        results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_sin_config'})
                else:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE real_trades SET status='failed',
                               error_message='Orphaned sin posicion en Bybit', updated_at=now()
                               WHERE id=$1 AND status='orphaned'""",
                            trade['id']
                        )
                    logger.warning(f"[RECONCILE] Orphaned #{trade['id']} {symbol} → failed (sin posicion en Bybit)")
                    await emit_event(pool, account.id, 'reconcile_discarded', trade['id'], symbol=symbol)

            # 3. Posiciones en Bybit sin registro en DB
            symbols_checked = set()
            for sub in account.subscriptions:
                if sub.symbol in symbols_checked:
                    continue
                symbols_checked.add(sub.symbol)
                try:
                    position = await client.get_open_position(sub.symbol)
                except BybitAPIError as e:
                    logger.error(f"[RECONCILE] {sub.symbol} error consultando Bybit: {e}")
                    results.setdefault('errors', []).append({'account_id': account.id, 'symbol': sub.symbol, 'error': str(e)})
                    continue
                if not position or float(position.get('size', 0) or 0) <= 0:
                    continue
                if await trader.has_open_trade(sub.subscription_id, sub.symbol):
                    continue
                async with pool.acquire() as conn:
                    existing = await conn.fetchrow(
                        "SELECT id FROM real_trades WHERE broker_account_id=$1 AND symbol=$2 AND status IN ('open','pending_open','pending_close','orphaned')",
                        account.id, sub.symbol
                    )
                if existing:
                    continue
                pos_size  = float(position.get('size', 0))
                pos_side  = position.get('side', '')
                db_side   = 'long' if pos_side == 'Buy' else 'short'
                avg_price = float(position.get('avgPrice', 0) or position.get('entryPrice', 0))
                snapshot  = {**(sub.config_params or {}), 'symbol': sub.symbol, 'interval': sub.interval}
                try:
                    async with pool.acquire() as conn:
                        trade_id = await conn.fetchval(
                            """
                            INSERT INTO real_trades
                                (user_id, subscription_id, broker_account_id, paper_strategy_config_id,
                                 strategy, symbol, broker, interval, side,
                                 entry_price, entry_price_signal, sl, tp,
                                 be_level, be_activated, size, original_size, leverage,
                                 balance_before, regime, entry_time, config_snapshot,
                                 status, created_at, updated_at)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10,0,0,0,false,$11,$11,1,0,'UNKNOWN',now(),$12,
                                    'orphaned',now(),now())
                            RETURNING id
                            """,
                            sub.user_id, sub.subscription_id, account.id, sub.paper_strategy_config_id,
                            sub.strategy, sub.symbol, account.broker, sub.interval, db_side,
                            avg_price, pos_size, snapshot
                        )
                    trade = {'id': trade_id, 'symbol': sub.symbol, 'interval': sub.interval, 'config_snapshot': snapshot}
                    adopted = await _adopt_position(trader, client, trade, avg_price, db_side, sub.symbol)
                    await emit_event(pool, account.id, 'reconcile_adopted', trade_id, symbol=sub.symbol,
                                     side=db_side, kind='untracked', protected=adopted)
                    results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side,
                                                'reason': 'registrada en DB' if adopted else 'registrada sin config'})
                except Exception as e:
                    logger.error(f"[RECONCILE] No se pudo registrar posicion huerfana {sub.symbol}: {e}")
                    results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side, 'reason': f'ERROR: {e}'})

        for account in request.accounts:
            got, _ = await _exclusive(account.id, RECONCILE_LOCK_WAIT, lambda: _reconcile_account(account))
            if not got:
                logger.warning(f"[RECONCILE] Cuenta {account.id} ocupada más de {RECONCILE_LOCK_WAIT:g} s: "
                               f"se reconcilia en el próximo ciclo")
                results.setdefault('errors', []).append({'account_id': account.id, 'note': 'cuenta ocupada: omitida'})

    finally:
        await pool.close()

    return {'status': 'ok', 'results': results}


async def _adopt_position(trader: RealTrader, client, trade: dict, avg_price: float, side: str, symbol: str) -> bool:
    """Deja un trade 'open' con SL/TP/BE de SU config (mismas fórmulas que una apertura normal)."""
    strategy = trader._trade_strategy(trade)
    if strategy is None:
        return False
    params = trader._snapshot(trade)
    sl, tp, _, _, _, be = trader._levels(strategy, avg_price, side, trader._effective_sl_pct(strategy, params))
    ts_ok = await client.set_trading_stop(symbol, sl, tp)
    async with trader.pool.acquire() as conn:
        await conn.execute(
            """UPDATE real_trades SET status='open', entry_price=$1, sl=$2, original_sl=$2, tp=$3, be_level=$4,
                   error_message='Adoptado por reconciliador', updated_at=now()
               WHERE id=$5""",
            avg_price, sl, tp, be, trade['id']
        )
    logger.warning(f"[RECONCILE] #{trade['id']} {symbol} adoptado @ {avg_price} sl={sl} tp={tp} be={be} ts={'OK' if ts_ok else 'FALLO'}")
    return True

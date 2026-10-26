"""
Endpoint Real Trading V2
Recibe las credenciales desencriptadas desde Laravel (que las lee del DB
y las desencripta usando la APP_KEY de Laravel). Python nunca lee
credenciales directamente de la DB para evitar el problema de encriptacion.
"""

import asyncio
import asyncpg
import logging
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from trading.real_trader import RealTrader, BybitClient, CIRCUIT_BREAKER_THRESHOLD, BybitAPIError
from trading.risk_manager import RiskManager

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


async def _setup_jsonb_codec(conn):
    import json
    await conn.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')
    await conn.set_type_codec('json', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')

async def _process_account(trader, account):
    account_key     = f"account_{account.id}_{account.broker}"
    account_results = {}
    try:
        error_count = await trader.get_circuit_breaker_errors(account.id)
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
                return account_key, {
                    "error": f"Circuit breaker activado ({error_count} errores criticos) - cuenta pausada"
                }
            else:
                await trader.clear_non_critical_errors(account.id)
                logger.warning(f"[CIRCUIT] {error_count} errores no criticos ignorados para cuenta {account.id}")

        client = _build_broker_client(account)

        monitor_result = await trader.monitor_open_trades(account.id, client)
        account_results["monitor"] = monitor_result

        # Kill switch manual: sin entradas nuevas (las abiertas ya se gestionaron arriba)
        if await RiskManager(trader.pool).is_kill_switch_active():
            account_results["signals"] = "KILL SWITCH activo — sin nuevas entradas"
            return account_key, account_results

        signal_results = {}
        for sub in account.subscriptions:
            sub_dict = sub.dict()
            try:
                strategy = instantiate_strategy(sub)
                sub_dict["broker"] = account.broker
                result   = await trader.check_new_signals(sub_dict, strategy, client)
                signal_results[sub.strategy] = result
            except Exception as e:
                logger.error(f"[REAL] Error procesando {sub.strategy}: {e}")
                signal_results[sub.strategy] = f"ERROR: {str(e)}"

        account_results["signals"] = signal_results
        return account_key, account_results

    except Exception as e:
        logger.error(f"[REAL] Error procesando cuenta {account.id}: {e}")
        return account_key, {"error": f"Error inesperado procesando la cuenta: {str(e)}"}


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
    pool    = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=5, init=_setup_jsonb_codec)
    trader  = RealTrader(pool)
    results = {}

    try:
        if not request.accounts:
            return {'status': 'ok', 'message': 'Sin cuentas activas', 'results': {}}

        account_results_list = await asyncio.gather(
            *[_process_account(trader, account) for account in request.accounts],
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

    pool    = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=5, init=_setup_jsonb_codec)
    trader  = RealTrader(pool)
    results = {}

    try:
        if not request.accounts:
            return {'status': 'ok', 'message': 'Sin cuentas activas', 'results': {}}

        async def _check_account(account):
            client = _build_broker_client(account)
            try:
                return account.id, await trader.check_max_loss_circuit_breaker(account.id, client)
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


@router.post('/real/reconcile')
async def reconcile(
    request: RealTickRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    pool    = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=5, init=_setup_jsonb_codec)
    trader  = RealTrader(pool)
    results = {'reconciled': [], 'orphaned': [], 'ok': []}

    def _since_ms(ref_time) -> int:
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        return int(ref_time.timestamp() * 1000)

    try:
        for account in request.accounts:
            client = _build_broker_client(account)

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
                settled = await trader.settle_exchange_close(trade, client, account.id, _since_ms(trade['entry_time']))
                if settled is None:
                    logger.warning(f"[RECONCILE] Trade #{trade['id']} {symbol}: cerrada en Bybit sin closed-pnl — 'orphaned'")
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE real_trades SET status = 'orphaned',
                                   error_message = 'Posicion cerrada en Bybit, no se pudo obtener pnl real (get_closed_pnl sin match)',
                                   updated_at = now()
                               WHERE id = $1""",
                            trade['id']
                        )
                    results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'no_exit_price_found'})
                else:
                    results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'closed_on_exchange'})

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
                    settled = await trader.settle_exchange_close(trade, client, account.id, _since_ms(trade['entry_time']),
                                                                 exit_reason='reconciled_sl_tp_bybit')
                    if settled is None:
                        async with pool.acquire() as conn:
                            await conn.execute("UPDATE real_trades SET status='orphaned' WHERE id=$1 AND status='open'", trade['id'])
                        results['ok'].append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_pending_pnl'})
                    else:
                        results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'orphaned_pnl_recovered'})
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
                    if adopted:
                        results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'orphaned_adopted'})
                    else:
                        results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_sin_config'})
                else:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE real_trades SET status='failed',
                               error_message='Orphaned sin posicion en Bybit', updated_at=now()
                               WHERE id=$1""",
                            trade['id']
                        )
                    logger.warning(f"[RECONCILE] Orphaned #{trade['id']} {symbol} → failed (sin posicion en Bybit)")

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
                    results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side,
                                                'reason': 'registrada en DB' if adopted else 'registrada sin config'})
                except Exception as e:
                    logger.error(f"[RECONCILE] No se pudo registrar posicion huerfana {sub.symbol}: {e}")
                    results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side, 'reason': f'ERROR: {e}'})

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

"""
Endpoint Real Trading V2
Recibe las credenciales desencriptadas desde Laravel (que las lee del DB
y las desencripta usando la APP_KEY de Laravel). Python nunca lee
credenciales directamente de la DB para evitar el problema de encriptacion.
"""

import asyncio
import asyncpg
import json as _json
import importlib
import json
import logging
import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from trading.ig_client import IGClient
from typing import Optional
from dotenv import load_dotenv

from trading.real_trader import RealTrader, BybitClient, CIRCUIT_BREAKER_THRESHOLD, BybitAPIError

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', '')

STRATEGY_CLASS_MAP = {
    'VwapStrategy':          ('backtesting.strategies.vwap_strategy', 'VwapStrategy'),
    'MeanReversionStrategy': ('backtesting.strategies.mean_reversion', 'MeanReversionStrategy'),
    'EmaDonchianStrategy':   ('backtesting.strategies.ema_donchian',   'EmaDonchianStrategy'),
}


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


class AccountPayload(BaseModel):
    id:           int
    broker:       str
    account_type: str
    api_key:      str
    api_secret:   str
    credentials_extra: Optional[str] = None
    subscriptions: list[SubscriptionPayload]


def _build_broker_client(account):
    """
    Instancia el cliente correcto segun account.broker.
    IG requiere usuario+contraseña ademas de la api_key, viajan en
    credentials_extra como JSON string: {"username": "...", "password": "..."}
    """
    if account.broker == 'ig':
        import json as _json
        extra = _json.loads(account.credentials_extra) if account.credentials_extra else {}
        return IGClient(
            api_key      = account.api_key,
            username     = extra.get('username', ''),
            password     = extra.get('password', ''),
            account_type = account.account_type,
        )
    return BybitClient(
        api_key      = account.api_key,
        api_secret   = account.api_secret,
        account_type = account.account_type,
    )


class RealTickRequest(BaseModel):
    accounts: list[AccountPayload]


def instantiate_strategy(sub: SubscriptionPayload):
    class_name = sub.strategy_class
    if not class_name or class_name not in STRATEGY_CLASS_MAP:
        raise ValueError(f"Clase no registrada: {class_name}")

    module_path, cls_name = STRATEGY_CLASS_MAP[class_name]
    module = importlib.import_module(module_path)
    cls    = getattr(module, cls_name)

    params = sub.config_params or {}
    params['symbol']   = sub.symbol
    params['interval'] = sub.interval
    instance = cls(params)
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

    try:
        for account in request.accounts:
            client = _build_broker_client(account)
            open_trades = await trader.get_open_trades(account.id)
            for trade in open_trades:
                symbol   = trade['symbol']
                # No reconciliar trades con menos de 10 minutos
                from datetime import datetime, timezone as tz, timedelta
                trade_time = trade['entry_time']
                if trade_time.tzinfo is None:
                    trade_time = trade_time.replace(tzinfo=tz.utc)
                trade_age = datetime.now(tz.utc) - trade_time
                if trade_age.total_seconds() < 600:
                    logger.info(f"[RECONCILE] Trade #{trade['id']} {symbol} < 10min — omitiendo")
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol})
                    continue
                try:
                    position = await client.get_open_position(symbol)
                except BybitAPIError as e:
                    logger.error(f"[RECONCILE] {symbol} #{trade['id']}: error consultando Bybit ({e}) — se omite, NO se marca cerrado")
                    results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'error': str(e)})
                    continue

                if not position:
                    # Obtener precio de cierre real del historial de Bybit
                    exit_price  = None
                    exit_reason = 'reconciled_sl_tp_bybit'
                    try:
                        # Buscar en historial de cierres filtrando por entry_price para identificar el trade correcto
                        closed_pnl = await client.get_closed_pnl(symbol)
                        if closed_pnl:
                            # Verificar que el avgEntryPrice coincide con el entry del trade
                            closed_entry = float(closed_pnl.get('avgEntryPrice', 0) or 0)
                            trade_entry  = float(trade['entry_price'])
                            if abs(closed_entry - trade_entry) / trade_entry < 0.001:  # 0.1% tolerancia
                                exit_price = float(closed_pnl.get('avgExitPrice') or closed_pnl.get('exitPrice') or 0) or None
                                if closed_pnl.get('orderType') == 'StopLoss':
                                    # Mismo criterio que real_trader.py: distinguir si el
                                    # SL que disparo el cierre era el original o uno movido
                                    # por el trailing nativo, en vez de 'stop_loss' generico.
                                    exit_reason = 'trailing_stop' if trade.get('trailing_applied') else 'stop_loss'
                                elif closed_pnl.get('orderType') in ('TakeProfit', 'PartialTakeProfit'):
                                    exit_reason = 'take_profit_1'
                            else:
                                logger.warning(f"[RECONCILE] closed_pnl entry={closed_entry} no coincide con trade entry={trade_entry} — usando precio estimado")
                    except Exception as e:
                        logger.error(f"[RECONCILE] Error obteniendo closed PnL: {e}")

                    if exit_price:
                        # Reusar close_trade() en vez de duplicar la logica de cierre:
                        # calcula commission, balance_after y pnl_pct correctamente,
                        # que la version anterior (UPDATE manual aqui mismo) nunca hacia.
                        await trader.close_trade(
                            trade, exit_reason, client, account.id,
                            exit_price_override=exit_price
                        )
                        results['reconciled'].append({
                            'trade_id': trade['id'],
                            'symbol':   symbol,
                            'reason':   exit_reason,
                        })
                    else:
                        # No se pudo determinar el pnl real (get_closed_pnl sin match).
                        # NO cerrar con datos incompletos — marcar 'orphaned' para que
                        # el reconciliador de orphaned lo reintente con get_closed_pnl_history
                        # (mas robusto, con reintento y ventana mas amplia).
                        logger.warning(f"[RECONCILE] Trade #{trade['id']} {symbol}: posicion cerrada pero no se encontro closed_pnl — marcando orphaned")
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE real_trades
                                SET status = 'orphaned',
                                    error_message = 'Posicion cerrada en Bybit, no se pudo obtener pnl real (get_closed_pnl sin match)',
                                    updated_at = now()
                                WHERE id = $1
                                """,
                                trade['id']
                            )
                        results.setdefault('errors', []).append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'no_exit_price_found'})
                    logger.warning(f"[RECONCILE] Trade #{trade['id']} {symbol} reconciliado exit={exit_price} pnl={pnl} reason={exit_reason}")
                else:
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol})
            # Adoptar trades 'orphaned' — abiertos en DB pero no confirmados
            async with pool.acquire() as conn:
                orphaned_trades = await conn.fetch(
                    """SELECT * FROM real_trades
                       WHERE broker_account_id = $1 AND status = 'orphaned'
                       ORDER BY created_at DESC""",
                    account.id
                )
            for trade in orphaned_trades:
                symbol = trade['symbol']

                # Distinguir el origen del 'orphaned': si viene de un CIERRE ya
                # confirmado (Bug B: pos_size<=0 detectado, pero closed-pnl vacio),
                # NO tiene sentido volver a chequear si hay posicion abierta —
                # ya sabemos que no la hay. Hay que reintentar el pnl del cierre,
                # no tratarlo como si nunca se hubiera confirmado la apertura.
                if trade['error_message'] and 'no se pudo obtener pnl real' in trade['error_message']:
                    from datetime import timezone as _tz
                    ref_time = trade['entry_time']
                    if ref_time.tzinfo is None:
                        ref_time = ref_time.replace(tzinfo=_tz.utc)
                    since_ms = int(ref_time.timestamp() * 1000)
                    history = await client.get_closed_pnl_history(
                        symbol, float(trade['entry_price']), since_ms, limit=50
                    )
                    if history:
                        total_pnl  = sum(float(h.get('closedPnl', 0)) for h in history)
                        total_size = sum(float(h.get('closedSize', 0)) for h in history)
                        last_entry = max(history, key=lambda h: int(h.get('updatedTime', 0)))
                        exit_price = float(last_entry.get('avgExitPrice', trade['entry_price']))
                        size = float(trade['size'])
                        if size > 0 and total_size > 0:
                            entry_f = float(trade['entry_price'])
                            if trade['side'] == 'long':
                                exit_price = entry_f + (total_pnl / size)
                            else:
                                exit_price = entry_f - (total_pnl / size)
                        success = await trader.close_trade(
                            trade, 'reconciled_sl_tp_bybit', client, account.id,
                            exit_price_override=exit_price
                        )
                        logger.warning(f"[RECONCILE] Orphaned #{trade['id']} {symbol} pnl recuperado en reintento: exit={exit_price} pnl_total={round(total_pnl,4)}")
                        results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'orphaned_pnl_recovered'})
                else:
                    # Sigue sin aparecer — se deja 'orphaned' para el proximo
                    # ciclo de reconciliacion, en vez de descartarlo como failed.
                    logger.warning(f"[RECONCILE] Orphaned #{trade['id']} {symbol}: closed-pnl aun vacio, se reintentara en el proximo ciclo")
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_pending_pnl'})
                continue

                try:
                    position = await client.get_open_position(symbol)
                except BybitAPIError as e:
                    logger.error(f"[RECONCILE] Orphaned #{trade['id']} {symbol}: error consultando Bybit ({e}) — se reintenta en el proximo ciclo")
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol, 'note': 'orphaned_api_error'})
                    continue
                if position and float(position.get('size', 0) or 0) > 0:
                    avg_price = float(position.get('avgPrice', 0) or trade['entry_price'])
                    # Calcular SL/TP reales con avgPrice real
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT psc.params FROM real_trades rt"
                            " JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id"
                            " JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id"
                            " WHERE rt.id = $1", trade['id']
                        )
                    params = row['params'] if row else {}
                    sl_pct = float(params.get('sl_pct', 0.8)) / 100
                    tp_pct = float(params.get('tp_pct', 1.6)) / 100
                    t_side = trade['side']
                    if t_side == 'short':
                        sl_real = round(avg_price * (1 + sl_pct), 8)
                        tp_real = round(avg_price * (1 - tp_pct), 8)
                    else:
                        sl_real = round(avg_price * (1 - sl_pct), 8)
                        tp_real = round(avg_price * (1 + tp_pct), 8)
                    # Aplicar SL/TP reales via trading-stop
                    ts_ok = await client.set_trading_stop(symbol, sl_real, tp_real)
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE real_trades SET status='open', entry_price=$1,
                               sl=$2, tp=$3, updated_at=now(),
                               error_message='Adoptado por reconciliador'
                               WHERE id=$4""",
                            avg_price, sl_real, tp_real, trade['id']
                        )
                    logger.warning(f"[RECONCILE] Orphaned #{trade['id']} {symbol} adoptado @ {avg_price} sl={sl_real} tp={tp_real} ts={'OK' if ts_ok else 'FALLO'}")
                    results['reconciled'].append({'trade_id': trade['id'], 'symbol': symbol, 'reason': 'orphaned_adopted'})
                else:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """UPDATE real_trades SET status='failed',
                               error_message='Orphaned sin posicion en Bybit', updated_at=now()
                               WHERE id=$1""",
                            trade['id']
                        )
                    logger.warning(f"[RECONCILE] Orphaned #{trade['id']} {symbol} → failed (sin posicion en Bybit)")

            symbols_checked = set()
            for sub in account.subscriptions:
                if sub.symbol in symbols_checked:
                    continue
                symbols_checked.add(sub.symbol)
                position = await client.get_open_position(sub.symbol)
                if not position:
                    continue
                # Verificar por simbolo completo — evita duplicados entre suscripciones del mismo simbolo
                has_trade = await trader.has_open_trade(sub.subscription_id, sub.symbol)
                # Doble verificacion directa por simbolo en DB
                if not has_trade:
                    async with pool.acquire() as conn:
                        existing = await conn.fetchrow(
                            "SELECT id FROM real_trades WHERE broker_account_id=$1 AND symbol=$2 AND status IN ('open','pending_open','pending_close','orphaned')",
                            account.id, sub.symbol
                        )
                    if existing:
                        has_trade = True
                if not has_trade:
                    pos_size = float(position.get('size', 0))
                    pos_side = position.get('side', '')
                    if pos_size <= 0:
                        continue
                    try:
                        entry_price = float(position.get('avgPrice', 0) or position.get('entryPrice', 0))
                        db_side = 'long' if pos_side == 'Buy' else 'short'
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                INSERT INTO real_trades
                                    (user_id, subscription_id, broker_account_id, paper_strategy_config_id,
                                     strategy, symbol, broker, interval, side,
                                     entry_price, entry_price_signal, sl, tp,
                                     be_level, be_activated, size, leverage,
                                     balance_before, regime, entry_time,
                                     status, created_at, updated_at)
                                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10,0,0,0,false,$11,1,0,'UNKNOWN',now(),'open',now(),now())
                                """,
                                sub.user_id, sub.subscription_id, account.id,
                                sub.paper_strategy_config_id,
                                sub.strategy, sub.symbol, account.broker,
                                sub.interval, db_side,
                                entry_price, pos_size
                            )
                        # Aplicar SL/TP reales via trading-stop
                        params = sub.config_params if isinstance(sub.config_params, dict) else {}
                        sl_pct = float(params.get('sl_pct', 0.8)) / 100
                        tp_pct = float(params.get('tp_pct', 1.6)) / 100
                        if db_side == 'short':
                            sl_real = round(entry_price * (1 + sl_pct), 8)
                            tp_real = round(entry_price * (1 - tp_pct), 8)
                        else:
                            sl_real = round(entry_price * (1 - sl_pct), 8)
                            tp_real = round(entry_price * (1 + tp_pct), 8)
                        ts_ok = await client.set_trading_stop(sub.symbol, sl_real, tp_real)
                        if ts_ok:
                            async with pool.acquire() as conn:
                                await conn.execute(
                                    "UPDATE real_trades SET sl=$1, tp=$2 WHERE broker_account_id=$3 AND symbol=$4 AND status='open' AND sl=0",
                                    sl_real, tp_real, account.id, sub.symbol
                                )
                        results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side, 'reason': 'registrada en DB'})
                        logger.warning(f"[RECONCILE] Posicion huerfana registrada en DB: {sub.symbol} {pos_side} size={pos_size} @ {entry_price} sl={sl_real} tp={tp_real} ts={'OK' if ts_ok else 'FALLO'}")
                    except Exception as e:
                        logger.error(f"[RECONCILE] No se pudo registrar posicion huerfana {sub.symbol}: {e}")
                        results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side, 'reason': f'ERROR: {str(e)}'})

    finally:
        await pool.close()

    return {'status': 'ok', 'results': results}

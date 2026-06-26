"""
Endpoint Real Trading V2
Recibe las credenciales desencriptadas desde Laravel (que las lee del DB
y las desencripta usando la APP_KEY de Laravel). Python nunca lee
credenciales directamente de la DB para evitar el problema de encriptacion.
"""

import asyncpg
import importlib
import json
import logging
import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from trading.real_trader import RealTrader, BybitClient, CIRCUIT_BREAKER_THRESHOLD

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
    subscriptions: list[SubscriptionPayload]


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


@router.post('/real/tick')
async def real_tick(
    request: RealTickRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    pool    = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)
    trader  = RealTrader(pool)
    results = {}

    try:
        if not request.accounts:
            return {'status': 'ok', 'message': 'Sin cuentas activas', 'results': {}}

        for account in request.accounts:
            account_key     = f"account_{account.id}_{account.broker}"
            account_results = {}

            # Circuit breaker — solo pausa si los errores son criticos
            # Errores de parametros (10001) o precios desactualizados no pausan la cuenta
            error_count = await trader.get_circuit_breaker_errors(account.id)
            if error_count >= CIRCUIT_BREAKER_THRESHOLD:
                last_errors = await trader.get_last_error_messages(account.id)
                # No critico: errores de parametros, SL/TP invalido, orden rechazada por params
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
                        f'{error_count} errores criticos en las ultimas 2h'
                    )
                    results[account_key] = {
                        'error': f'Circuit breaker activado ({error_count} errores criticos) — cuenta pausada'
                    }
                    logger.error(f"[CIRCUIT] Cuenta {account.id} pausada por {error_count} errores criticos")
                    continue
                else:
                    # Errores no criticos — limpiar y continuar
                    await trader.clear_non_critical_errors(account.id)
                    logger.warning(f"[CIRCUIT] {error_count} errores no criticos ignorados para cuenta {account.id}")

            # Cliente Bybit con credenciales desencriptadas por Laravel
            client = BybitClient(
                api_key      = account.api_key,
                api_secret   = account.api_secret,
                account_type = account.account_type,
            )

            # 1. Monitorear posiciones abiertas
            monitor_result = await trader.monitor_open_trades(account.id, client)
            account_results['monitor'] = monitor_result

            # 2. Buscar nuevas señales
            signal_results = {}
            for sub in account.subscriptions:
                sub_dict = sub.dict()
                try:
                    strategy = instantiate_strategy(sub)
                    sub_dict['broker'] = account.broker  # agregar broker desde account
                    result   = await trader.check_new_signals(sub_dict, strategy, client)
                    signal_results[sub.strategy] = result
                except Exception as e:
                    logger.error(f"[REAL] Error procesando {sub.strategy}: {e}")
                    signal_results[sub.strategy] = f"ERROR: {str(e)}"

            account_results['signals'] = signal_results
            results[account_key] = account_results

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

    pool    = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=5)
    trader  = RealTrader(pool)
    results = {'reconciled': [], 'orphaned': [], 'ok': []}

    try:
        for account in request.accounts:
            client = BybitClient(
                api_key      = account.api_key,
                api_secret   = account.api_secret,
                account_type = account.account_type,
            )

            open_trades = await trader.get_open_trades(account.id)

            for trade in open_trades:
                symbol   = trade['symbol']
                position = await client.get_open_position(symbol)

                if not position:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE real_trades
                            SET status = 'closed',
                                exit_reason = 'reconciled_sl_tp_bybit',
                                exit_time = now(), updated_at = now()
                            WHERE id = $1
                            """,
                            trade['id']
                        )
                    results['reconciled'].append({
                        'trade_id': trade['id'],
                        'symbol':   symbol,
                        'reason':   'cerrada en Bybit mientras servidor caido',
                    })
                    logger.warning(f"[RECONCILE] Trade #{trade['id']} {symbol} reconciliado")
                else:
                    results['ok'].append({'trade_id': trade['id'], 'symbol': symbol})
            symbols_checked = set()
            for sub in account.subscriptions:
                if sub.symbol in symbols_checked:
                    continue
                symbols_checked.add(sub.symbol)
                position = await client.get_open_position(sub.symbol)
                if not position:
                    continue
                has_trade = await trader.has_open_trade(sub.subscription_id, sub.symbol)
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
                        results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side, 'reason': 'registrada en DB'})
                        logger.warning(f"[RECONCILE] Posicion huerfana registrada en DB: {sub.symbol} {pos_side} size={pos_size} @ {entry_price}")
                    except Exception as e:
                        logger.error(f"[RECONCILE] No se pudo registrar posicion huerfana {sub.symbol}: {e}")
                        results['orphaned'].append({'symbol': sub.symbol, 'size': pos_size, 'side': pos_side, 'reason': f'ERROR: {str(e)}'})

    finally:
        await pool.close()

    return {'status': 'ok', 'results': results}

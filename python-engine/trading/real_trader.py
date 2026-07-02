"""
Real Trader V1
Ejecuta ordenes reales en Bybit usando las mismas estrategias y parametros
que paper trading. La logica de señales es identica — solo cambia la capa
de ejecucion (ordenes reales en lugar de filas en DB simuladas).

Flujo por suscripcion activa:
  1. Verificar que no hay posicion abierta (DB + Bybit)
  2. Generar señal con la misma estrategia/params de paper_strategy_configs
  3. Consultar balance real en Bybit
  4. Calcular tamaño de posicion con balance real
  5. Colocar orden MARKET en Bybit
  6. Confirmar ejecucion (status = Filled)
  7. Guardar en real_trades con order_id, balance_before, etc.

Cierre de posiciones:
  1. Monitorear precios vs SL/TP/BE/tiempo
  2. Colocar orden MARKET de cierre en Bybit
  3. Confirmar ejecucion
  4. Actualizar real_trades con balance_after, comision, net_pnl
"""

import asyncpg
import asyncio
import hashlib
import hmac
import httpx
import json
import logging
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

from trading.bybit_client import get_current_price, bybit_sign
from indicators.regime_indicators import calculate_atr, calculate_adx, calculate_bb_width, classify_regime
from backtesting.strategies.base_strategy import calculate_trailing_sl_standalone

load_dotenv()
logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

BYBIT_MAINNET = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
BYBIT_TESTNET = os.getenv('BYBIT_TESTNET_URL', 'https://api-testnet.bybit.com')


def compute_native_trailing_params(entry_price, side, trailing_distance_pct):
    """
    Calcula trailingStop (distancia en precio absoluto, no %) y activePrice
    (nivel donde arma el trailing nativo de Bybit) a partir del
    trailing_distance_pct configurado en la estrategia.

    activePrice queda apenas mas favorable que el precio de ENTRADA (buffer
    de 0.05%), para que arme apenas la posicion entra en ganancia - mismo
    criterio que el trailing del bot (gain_pct > 0). Confirmado contra
    Bybit testnet: activePrice se valida contra el precio de entrada de la
    posicion, no contra el precio de mercado actual.
    """
    trailing_stop_price = entry_price * (trailing_distance_pct / 100)
    buffer_pct = 0.0005
    if side == 'long':
        active_price = entry_price * (1 + buffer_pct)
    else:
        active_price = entry_price * (1 - buffer_pct)
    return round(trailing_stop_price, 8), round(active_price, 8)

# Circuit breaker: pausar cuenta tras N errores consecutivos de API
CIRCUIT_BREAKER_THRESHOLD = 3

# Comision estimada Bybit (taker) — se actualiza con el valor real al cerrar
BYBIT_TAKER_FEE = 0.00055  # 0.055%


# ─────────────────────────────────────────────────────────────────
# Cliente Bybit autenticado
# ─────────────────────────────────────────────────────────────────

class BybitClient:

    def __init__(self, api_key: str, api_secret: str, account_type: str = 'real'):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.base_url   = BYBIT_TESTNET if account_type == 'demo' else BYBIT_MAINNET

    async def get_closed_pnl_history(self, symbol, entry_price_hint, since_time_ms, limit=20):
        """
        Trae el historial de cierres de Bybit para este simbolo, filtrado a
        los que pertenecen a ESTA posicion especifica (mismo precio de
        entrada, cerrados despues de since_time_ms). Usado para capturar
        TODOS los tramos cuando Bybit divide el cierre en varias ordenes
        por iliquidez, en vez de quedarnos solo con el ultimo tramo.
        """
        params = {"category": "linear", "limit": str(limit), "symbol": symbol}
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        headers = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{self.base_url}/v5/position/closed-pnl?{query_string}",
                    headers=headers,
                )
            data = r.json()
            if data.get("retCode") != 0:
                retmsg_hist = data.get("retMsg")
                logger.error(f"[BYBIT] get_closed_pnl_history error: {retmsg_hist}")
                return []

            matching = []
            for item in data.get("result", {}).get("list", []):
                try:
                    item_entry = float(item.get("avgEntryPrice", 0))
                    item_time  = int(item.get("createdTime", 0))
                except (TypeError, ValueError):
                    continue
                if item_time < since_time_ms:
                    continue
                if entry_price_hint > 0 and abs(item_entry - entry_price_hint) / entry_price_hint > 0.0005:
                    continue
                matching.append(item)
            return matching
        except Exception as e:
            logger.error(f"[BYBIT] get_closed_pnl_history exception: {e}")
            return []

    async def get_closed_pnl(self, symbol: str) -> dict | None:
        """Obtiene el ultimo trade cerrado de Bybit para obtener precio de salida y razon."""
        params = {'category': 'linear', 'limit': '1', 'symbol': symbol}
        # Construir query string ordenado para que coincida con la firma
        query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        headers = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/position/closed-pnl?{query_string}',
                    headers=headers,
                )
            data = r.json()
            if data.get('retCode') == 0:
                items = data.get('result', {}).get('list', [])
                if items:
                    return items[0]
            else:
                logger.error(f"[BYBIT] get_closed_pnl error: {data.get('retMsg')}")
        except Exception as e:
            logger.error(f"[BYBIT] get_closed_pnl exception: {e}")
        return None

    async def get_market_price(self, symbol: str) -> float | None:
        """Obtiene precio actual usando la URL correcta (testnet o mainnet)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/market/tickers',
                    params={'category': 'linear', 'symbol': symbol}
                )
                data = r.json()
                tickers = data.get('result', {}).get('list', [])
                if tickers:
                    return float(tickers[0]['lastPrice'])
        except Exception as e:
            logger.error(f"[BYBIT] Error obteniendo precio {symbol}: {e}")
        return None

    def _sign(self, params: dict) -> dict:
        """Firma para requests GET. Delega la firma HMAC a bybit_sign (bybit_client.py) -
        antes esta formula estaba duplicada aca y en broker.py por separado."""
        query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        headers = bybit_sign(self.api_key, self.api_secret, query_string, recv_window='10000')
        headers['Content-Type'] = 'application/json'
        return headers

    def _sign_body(self, body: dict) -> dict:
        """Firma para requests con body JSON (POST). Delega la firma HMAC a bybit_sign."""
        body_str = json.dumps(body, separators=(',', ':'), ensure_ascii=True)
        headers = bybit_sign(self.api_key, self.api_secret, body_str, recv_window='10000')
        headers['Content-Type'] = 'application/json'
        return headers

    async def get_balance(self) -> float | None:
        """Obtiene el balance disponible (USDT) de la cuenta UNIFIED."""
        params = {'accountType': 'UNIFIED', 'coin': 'USDT'}
        headers = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/account/wallet-balance',
                    params=params,
                    headers=headers,
                )
            if not r.text or r.status_code in (401, 403):
                logger.error(f"[BYBIT] get_balance auth error: HTTP {r.status_code}")
                return None
            data = r.json()
            if data.get('retCode') != 0:
                logger.error(f"[BYBIT] get_balance error: {data.get('retMsg')}")
                return None

            accounts = data['result']['list']
            if not accounts:
                return None

            coins = accounts[0].get('coin', [])
            for coin in coins:
                if coin.get('coin') == 'USDT':
                    logger.info(f"[BYBIT] USDT coin data: {dict(coin)}")
                    for field in ['availableToWithdraw', 'walletBalance', 'equity', 'totalOrderIM']:
                        val = coin.get(field, '')
                        if val and val != '' and val != '0':
                            logger.info(f"[BYBIT] Using field {field}={val}")
                            return float(val)
                    return 0.0

            # Si no hay USDT en coins, usar totalEquity
            logger.info(f"[BYBIT] Account data: totalEquity={accounts[0].get('totalEquity')} totalAvailableBalance={accounts[0].get('totalAvailableBalance')}")
            for field in ['totalAvailableBalance', 'totalEquity']:
                val = accounts[0].get(field, '')
                if val and val != '':
                    return float(val)
            return 0.0

        except Exception as e:
            logger.error(f"[BYBIT] get_balance exception: {e}")
            return None

    async def get_min_qty(self, symbol: str) -> tuple[float, float]:
        """Obtiene el lot size minimo y qty step para un simbolo."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/market/instruments-info',
                    params={'category': 'linear', 'symbol': symbol},
                )
            data = r.json()
            if data.get('retCode') != 0:
                return 0.001, 0.001

            items = data['result']['list']
            if not items:
                return 0.001, 0.001

            lot_filter = items[0].get('lotSizeFilter', {})
            min_qty  = float(lot_filter.get('minOrderQty', 0.001))
            qty_step = float(lot_filter.get('qtyStep', min_qty))
            logger.info(f"[BYBIT] {symbol} minQty={min_qty} qtyStep={qty_step}")
            return min_qty, qty_step

        except Exception:
            return 0.001, 0.001

    async def place_market_order(self, symbol: str, side: str, qty: float,
                                  sl: float = None, tp: float = None) -> dict | None:
        """
        Coloca una orden MARKET con SL/TP provisionales para garantizar aceptacion.
        SL provisional = mark_price × 1.03 (SHORT) | × 0.97 (LONG)
        TP provisional = mark_price × 0.95 (SHORT) | × 1.05 (LONG)
        Los provisionales se reemplazan con valores reales via trading-stop despues de confirmar.
        """
        body = {
            'category':  'linear',
            'symbol':    symbol,
            'side':      side,
            'orderType': 'Market',
            'qty':       str(qty),
        }
        # Calcular SL/TP provisionales basados en mark_price actual
        mark_price = await self.get_market_price(symbol)
        if mark_price:
            # SL provisional: 5% para demo (testnet volatil), 3% para mainnet
            is_demo = 'testnet' in self.base_url
            # Demo: SL=5%, TP=10% | Mainnet: SL=2%, TP=4%
            sl_margin = 1.05 if is_demo else 1.02
            tp_margin = 0.90 if is_demo else 0.96
            if side == 'Sell':  # SHORT
                sl_prov = round(mark_price * sl_margin, 8)         # SL arriba
                tp_prov = round(mark_price * tp_margin, 8)         # TP abajo
            else:  # LONG
                sl_prov = round(mark_price * (2 - sl_margin), 8)  # SL abajo
                tp_prov = round(mark_price * (2 - tp_margin), 8)  # TP arriba
            body['stopLoss']    = str(sl_prov)
            body['slTriggerBy'] = 'LastPrice'
            body['takeProfit']  = str(tp_prov)
            body['tpTriggerBy'] = 'LastPrice'
            logger.info(f"[BYBIT] SL provisional={sl_prov} TP provisional={tp_prov} mark={mark_price} side={side} symbol={symbol} demo={is_demo}")
        else:
            # Sin mark price — incluir SL/TP originales si existen
            if sl and sl > 0:
                body['stopLoss']    = str(round(sl, 8))
                body['slTriggerBy'] = 'LastPrice'
            if tp and tp > 0:
                body['takeProfit']  = str(round(tp, 8))
                body['tpTriggerBy'] = 'LastPrice'
        logger.info(f"[BYBIT] body orden: {body}")

        headers = self._sign_body(body)

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(
                        f'{self.base_url}/v5/order/create',
                        content=json.dumps(body, separators=(',', ':'), ensure_ascii=True).encode(),
                        headers=headers,
                    )
                data = r.json()
                if data.get('retCode') == 0:
                    return data['result']
                else:
                    logger.error(f"[BYBIT] place_order error (attempt {attempt+1}): {data.get('retMsg')} code={data.get('retCode')}")
                    if attempt < 2:
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"[BYBIT] place_order exception (attempt {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)

        return None

    async def place_reduce_only_order(self, symbol: str, side: str, qty: float) -> dict | None:
        """
        Coloca una orden MARKET reduceOnly para cerrar parcialmente una
        posicion (usada para TP2/TP3/TP4 manuales). No adjunta SL/TP -
        Bybit rechaza la orden si reduceOnly=true viene junto con
        stopLoss/takeProfit en el mismo request.
        """
        body = {
            "category":   "linear",
            "symbol":     symbol,
            "side":       side,
            "orderType":  "Market",
            "qty":        str(qty),
            "reduceOnly": True,
        }
        headers = self._sign_body(body)

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(
                        f"{self.base_url}/v5/order/create",
                        content=json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode(),
                        headers=headers,
                    )
                data = r.json()
                if data.get("retCode") == 0:
                    return data["result"]
                else:
                    retmsg = data.get("retMsg")
                    retcode = data.get("retCode")
                    logger.error(f"[BYBIT] place_reduce_only_order error (attempt {attempt+1}): {retmsg} code={retcode}")
                    if attempt < 2:
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"[BYBIT] place_reduce_only_order exception (attempt {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2)

        return None

    async def get_native_trailing_level(self, symbol):
        """
        Consulta el nivel actual del trailing NATIVO de Bybit (orden
        condicional tipo TrailingProfit, aun no disparada). Bybit no
        expone este nivel en position/list, solo en order/realtime.
        Devuelve None si no hay trailing armado.
        """
        params = {'category': 'linear', 'orderFilter': 'StopOrder', 'symbol': symbol}
        query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        headers = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/order/realtime?{query_string}',
                    headers=headers,
                )
            data = r.json()
            if data.get('retCode') != 0:
                return None
            for order in data.get('result', {}).get('list', []):
                if order.get('stopOrderType') == 'TrailingProfit' and order.get('orderStatus') == 'Untriggered':
                    return float(order.get('triggerPrice'))
        except Exception as e:
            logger.error(f"[BYBIT] get_native_trailing_level exception: {e}")
        return None

    async def set_trading_stop(self, symbol: str, sl: float, tp: float, side: str = None,
                                trailing_stop: float = None, active_price: float = None) -> bool:
        """
        Configura SL y TP en Bybit para una posicion abierta.
        Se llama despues de confirmar la apertura de la orden.
        side: 'long' o 'short' (se convierte a Buy/Sell internamente)

        trailing_stop / active_price: si se pasan, arma ADEMAS el trailing
        NATIVO de Bybit. No reemplaza el stopLoss fijo - coexisten
        (confirmado empiricamente contra Bybit testnet). activePrice debe
        ser mas favorable que el precio de ENTRADA de la posicion, no que
        el precio de mercado actual, o Bybit rechaza el pedido.
        """
        position_idx = 0  # one-way mode
        body = {
            'category':    'linear',
            'symbol':      symbol,
            'positionIdx': position_idx,
            'tpslMode':    'Full',
            'stopLoss':    str(round(sl, 8)),
            'takeProfit':  str(round(tp, 8)),
            'slTriggerBy': 'LastPrice',
            'tpTriggerBy': 'LastPrice',
        }
        if trailing_stop is not None:
            body['trailingStop'] = str(round(trailing_stop, 8))
        if active_price is not None:
            body['activePrice'] = str(round(active_price, 8))
        headers = self._sign_body(body)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f'{self.base_url}/v5/position/trading-stop',
                    content=json.dumps(body, separators=(',', ':'), ensure_ascii=True).encode(),
                    headers=headers,
                )
            data = r.json()
            logger.info(f"[BYBIT] trading-stop response: retCode={data.get('retCode')} msg={data.get('retMsg')} symbol={symbol}")
            if data.get('retCode') == 0:
                logger.info(f"[BYBIT] SL/TP configurado en Bybit: {symbol} SL={sl} TP={tp}")
                return True
            else:
                logger.error(f"[BYBIT] set_trading_stop error: {data.get('retMsg')} code={data.get('retCode')} body={body}")
                return False
        except Exception as e:
            logger.error(f"[BYBIT] set_trading_stop exception: {e}")
            return False

    async def get_order(self, symbol: str, order_id: str) -> dict | None:
        """Verifica el estado de una orden por su ID."""
        params = {'category': 'linear', 'symbol': symbol, 'orderId': order_id}
        headers = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/order/realtime',
                    params=params,
                    headers=headers,
                )
            data = r.json()
            if data.get('retCode') == 0:
                items = data['result']['list']
                return items[0] if items else None
        except Exception as e:
            logger.error(f"[BYBIT] get_order exception: {e}")
        return None

    async def get_open_position(self, symbol: str) -> dict | None:
        """Verifica si hay posicion abierta en Bybit para ese simbolo."""
        params = {'category': 'linear', 'symbol': symbol}
        headers = self._sign(params)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f'{self.base_url}/v5/position/list',
                    params=params,
                    headers=headers,
                )
            if not r.text or r.status_code in (401, 403):
                logger.error(f"[BYBIT] get_position auth error: HTTP {r.status_code}")
                return None
            data = r.json()
            if data.get('retCode') == 0:
                positions = data['result']['list']
                for pos in positions:
                    if float(pos.get('size', 0)) > 0:
                        return pos
        except Exception as e:
            logger.error(f"[BYBIT] get_position exception: {e}")
        return None


# ─────────────────────────────────────────────────────────────────
# Real Trader
# ─────────────────────────────────────────────────────────────────

class RealTrader:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ─────────────────────────────────────────────
    # Helpers de DB
    # ─────────────────────────────────────────────

    async def get_active_subscriptions(self) -> list[dict]:
        """Carga suscripciones activas con la config de paper_strategy_configs."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    rss.id              AS subscription_id,
                    rss.user_id,
                    rss.broker_account_id,
                    rss.paper_strategy_config_id,
                    rss.strategy,
                    rss.symbol,
                    rss.interval,
                    ba.broker,
                    ba.account_type,
                    ba.api_key,
                    ba.api_secret,
                    ba.status           AS account_status,
                    psc.strategy_class,
                    psc.params          AS config_params,
                    psc.active          AS config_active
                FROM real_strategy_subscriptions rss
                JOIN broker_accounts ba ON ba.id = rss.broker_account_id
                JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id
                WHERE rss.status = 'active'
                  AND ba.status  = 'active'
                  AND psc.active = true
                ORDER BY rss.id ASC
                """
            )
        return [dict(r) for r in rows]

    async def get_open_trades(self, account_id: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, subscription_id, strategy, symbol, interval, side,
                       entry_price, sl, tp, tp2, tp3, tp4, be_level, be_activated,
                       size, original_size, tp2_hit, tp3_hit, tp4_hit, realized_pnl_partial,
                       entry_time, updated_at, order_id, balance_before, status
                FROM real_trades
                WHERE broker_account_id = $1
                  AND status IN ('open', 'pending_close')
                """,
                account_id
            )
        return [dict(r) for r in rows]

    async def has_open_trade(self, subscription_id: int, symbol: str) -> bool:
        # Verifica por simbolo Y por broker_account_id — evita duplicados entre suscripciones del mismo simbolo
        async with self.pool.acquire() as conn:
            # Obtener broker_account_id de la suscripcion
            sub_row = await conn.fetchrow(
                "SELECT broker_account_id FROM real_strategy_subscriptions WHERE id = $1",
                subscription_id
            )
            if not sub_row:
                return False
            row = await conn.fetchrow(
                """
                SELECT id FROM real_trades
                WHERE broker_account_id = $1 AND symbol = $2
                  AND status IN ('pending_open', 'open', 'pending_close', 'orphaned')
                """,
                sub_row['broker_account_id'], symbol
            )
        return row is not None

    async def get_circuit_breaker_errors(self, account_id: int) -> int:
        """Cuenta errores consecutivos de API en las ultimas 2 horas."""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM real_trades
                WHERE broker_account_id = $1 AND status = 'error'
                  AND updated_at >= NOW() - INTERVAL '2 hours'
                """,
                account_id
            )
        return int(count or 0)

    async def get_last_error_messages(self, account_id: int) -> list:
        """Obtiene los mensajes de error recientes para clasificar el circuit breaker."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT error_message FROM real_trades
                WHERE broker_account_id = $1 AND status = 'error'
                AND updated_at >= NOW() - INTERVAL '2 hours'
                ORDER BY updated_at DESC LIMIT 5
                """,
                account_id
            )
        return [r['error_message'] for r in rows]

    async def clear_non_critical_errors(self, account_id: int):
        """Marca errores no criticos como 'ignored' para no contar en el circuit breaker."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE real_trades SET status = 'ignored', updated_at = now()
                WHERE broker_account_id = $1 AND status = 'error'
                AND updated_at >= NOW() - INTERVAL '2 hours'
                """,
                account_id
            )
        logger.info(f"[CIRCUIT] Errores no criticos limpiados para cuenta {account_id}")

    async def get_last_error_messages(self, account_id: int) -> list:
        """Obtiene los mensajes de error recientes para clasificar el circuit breaker."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT error_message FROM real_trades
                WHERE broker_account_id = $1 AND status = 'error'
                AND updated_at >= NOW() - INTERVAL '2 hours'
                ORDER BY updated_at DESC LIMIT 5
                """,
                account_id
            )
        return [r['error_message'] for r in rows]

    async def clear_non_critical_errors(self, account_id: int):
        """Marca errores no criticos como 'ignored' para no contar en el circuit breaker."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE real_trades SET status = 'ignored', updated_at = now()
                WHERE broker_account_id = $1 AND status = 'error'
                AND updated_at >= NOW() - INTERVAL '2 hours'
                """,
                account_id
            )
        logger.info(f"[CIRCUIT] Errores no criticos limpiados para cuenta {account_id}")

    async def pause_account(self, account_id: int, reason: str):
        """Pausa la cuenta automaticamente (circuit breaker)."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE broker_accounts SET status = 'paused', updated_at = now() WHERE id = $1",
                account_id
            )
        logger.warning(f"[REAL] Circuit breaker activado — cuenta {account_id} pausada: {reason}")

    async def log_audit(self, trade_id: int, action: str, data: dict):
        """Agrega entrada al audit_log del trade."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT audit_log FROM real_trades WHERE id = $1", trade_id)
                raw = row['audit_log'] if row and row['audit_log'] else []
                # Normalizar a lista — puede venir como str, str-dentro-str, lista o None
                if isinstance(raw, list):
                    existing = raw
                elif isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                        # Doble encode: "[{...}]" -> parsea a string -> parsear de nuevo
                        if isinstance(parsed, str):
                            parsed = json.loads(parsed)
                        existing = parsed if isinstance(parsed, list) else []
                    except Exception:
                        existing = []
                else:
                    existing = []
                existing.append({'action': action, 'timestamp': datetime.now(timezone.utc).isoformat(), 'data': data})
                await conn.execute(
                    "UPDATE real_trades SET audit_log = $1::jsonb, updated_at = now() WHERE id = $2",
                    json.dumps(existing), trade_id
                )
        except Exception as e:
            logger.error(f"[REAL] log_audit error trade #{trade_id}: {e}")

    # ─────────────────────────────────────────────
    # Datos de mercado
    # ─────────────────────────────────────────────

    async def get_bars(self, symbol: str, interval: str) -> list:
        import pandas as pd
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                ORDER BY time DESC LIMIT 200
                """,
                symbol, interval
            )
        if not rows:
            return []

        import pandas as pd
        df = pd.DataFrame(rows, columns=['time','open','high','low','close','volume'])
        df = df.iloc[::-1].reset_index(drop=True)
        for col in ['open','high','low','close','volume']:
            df[col] = df[col].astype(float)
        return df

    async def get_current_regime(self, df) -> str:
        if len(df) < 64:
            return "RANGING"
        atr      = calculate_atr(df)
        adx      = calculate_adx(df)
        bb_width = calculate_bb_width(df)
        atr_avg      = atr.rolling(50).mean()
        bb_width_avg = bb_width.rolling(50).mean()
        last = len(df) - 1
        return classify_regime(
            adx=float(adx.iloc[last]),
            atr=float(atr.iloc[last]),
            atr_avg=float(atr_avg.iloc[last]),
            bb_width=float(bb_width.iloc[last]),
            bb_width_avg=float(bb_width_avg.iloc[last]),
        )

    # ─────────────────────────────────────────────
    # Abrir posicion real
    # ─────────────────────────────────────────────

    async def open_trade(self, sub: dict, strategy_instance, side: str,
                          entry_signal_price: float, regime: str, client: BybitClient) -> bool:
        symbol   = sub['symbol']
        interval = sub['interval']

        # 1. Balance real antes de abrir
        balance = await client.get_balance()
        if balance is None or balance <= 0:
            logger.error(f"[REAL] No se pudo obtener balance para {sub['broker_account_id']}")
            return False

        # 2. Obtener precio actual del mercado para calcular SL/TP
        # Usar el precio del mismo entorno (testnet/mainnet) donde se ejecutara la orden
        current_price = await client.get_market_price(symbol)
        entry_price_for_calc = current_price if current_price else entry_signal_price
        if current_price and abs(current_price - entry_signal_price) / entry_signal_price > 0.02:
            logger.warning(f"[REAL] Precio actual ({current_price}) difiere >2% del precio de señal ({entry_signal_price}) para {symbol}")

        sl, tp1 = strategy_instance.calculate_sl_tp(entry_price_for_calc, side)
        be      = strategy_instance.calculate_breakeven(entry_price_for_calc, side)

        tp2 = strategy_instance.calculate_tp2(entry_price_for_calc, side) \
              if hasattr(strategy_instance, 'calculate_tp2') else None
        tp3 = getattr(strategy_instance, 'tp3_pct', None)
        tp4 = getattr(strategy_instance, 'tp4_pct', None)

        if tp3:
            tp3 = entry_price_for_calc * (1 + tp3/100) if side == 'long' else entry_price_for_calc * (1 - tp3/100)
        if tp4:
            tp4 = entry_price_for_calc * (1 + tp4/100) if side == 'long' else entry_price_for_calc * (1 - tp4/100)

        # 3. Calcular tamaño con balance real y riesgo configurado
        # risk_override_pct de la suscripcion tiene prioridad sobre config
        risk_override = sub.get('risk_override_pct')
        if risk_override is not None and str(risk_override).strip() not in ('', 'None', 'null'):
            risk_pct = float(risk_override)
        else:
            config_params = sub.get('config_params') or {}
            if isinstance(config_params, str):
                import json as _j
                config_params = _j.loads(config_params)
            risk_pct = float(config_params.get('risk_per_trade_pct', 1.0))
        logger.debug(f"[REAL] Risk calculado: {risk_pct}% (override={risk_override}) para {sub.get('symbol')}")
        risk_amount = balance * (risk_pct / 100)
        sl_distance = abs(entry_signal_price - sl)
        size        = round(risk_amount / sl_distance, 6) if sl_distance > 0 else 0

        if size <= 0:
            logger.warning(f"[REAL] Tamaño calculado <= 0 para {symbol}")
            return False

        # 4. Verificar lot size minimo y redondear al step size
        min_qty, qty_step = await client.get_min_qty(symbol)
        if size < min_qty:
            logger.warning(f"[REAL] Tamaño {size} < minimo {min_qty} para {symbol}")
            return False
        # Redondear al step size (ej. SOLUSDT = 0.1, BTCUSDT = 0.001)
        if qty_step > 0:
            import math
            decimals = max(0, -int(math.floor(math.log10(qty_step))))
            size = round(math.floor(size / qty_step) * qty_step, decimals)
        if size <= 0:
            logger.warning(f"[REAL] Tamaño tras redondeo <= 0 para {symbol}")
            return False

        # 4b. Obtener balance actualizado justo antes de insertar
        balance = await client.get_balance() or balance
        # 5. Crear registro en pending_open ANTES de enviar a Bybit
        async with self.pool.acquire() as conn:
            trade_id = await conn.fetchval(
                """
                INSERT INTO real_trades
                    (user_id, subscription_id, broker_account_id, paper_strategy_config_id,
                     strategy, symbol, broker, interval, side,
                     entry_price, entry_price_signal, sl, tp, tp2, tp3, tp4,
                     be_level, be_activated, size, original_size, leverage,
                     balance_before, regime, entry_time,
                     status, created_at, updated_at)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                     $10, $11, $12, $13, $14, $15, $16,
                     $17, false, $18, $18, 1,
                     $19, $20, $21,
                     'pending_open', now(), now())
                RETURNING id
                """,
                sub['user_id'], sub['subscription_id'], sub['broker_account_id'],
                sub['paper_strategy_config_id'],
                sub['strategy'], symbol, sub['broker'], interval, side,
                entry_signal_price, entry_signal_price, sl, tp1, tp2, tp3, tp4,
                be, size, balance, regime,
                datetime.now(timezone.utc).replace(tzinfo=None)
            )

        # 6. Recalcular SL/TP con precio actual justo antes de enviar
        bybit_side = 'Buy' if side == 'long' else 'Sell'
        current_price = await client.get_market_price(symbol)
        if current_price and abs(current_price - entry_signal_price) / entry_signal_price > 0.005:
            # Precio movio mas de 0.5% — recalcular SL/TP con precio actual
            logger.warning(f"[REAL] Precio movio de {entry_signal_price} a {current_price} — recalculando SL/TP")
            sl_pct = strategy_instance.sl_pct / 100
            tp_pct = strategy_instance.tp_pct / 100
            if side == 'long':
                sl  = round(current_price * (1 - sl_pct), 8)
                tp1 = round(current_price * (1 + tp_pct), 8)
            else:
                sl  = round(current_price * (1 + sl_pct), 8)
                tp1 = round(current_price * (1 - tp_pct), 8)
            entry_signal_price = current_price
        # Actualizar SL/TP en DB si fueron recalculados
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE real_trades SET sl=$1, tp=$2, entry_price_signal=$3, updated_at=now() WHERE id=$4",
                sl, tp1, entry_signal_price, trade_id
            )
        logger.info(f"[REAL] Abriendo {side} {symbol} entry={entry_signal_price} sl={sl} tp1={tp1} size={size}")
        result = await client.place_market_order(symbol, bybit_side, size, sl=sl, tp=tp1)

        if result is None:
            # Marcar como error
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE real_trades
                    SET status = 'error', error_message = 'Orden rechazada por Bybit tras 3 intentos',
                        updated_at = now()
                    WHERE id = $1
                    """,
                    trade_id
                )
            await self.log_audit(trade_id, 'open_failed', {'reason': 'bybit_rejected'})
            return False

        order_id = result.get('orderId')

        # 7. Esperar confirmacion — 1s inicial
        filled_price = entry_signal_price
        filled = False
        await asyncio.sleep(1)
        position = await client.get_open_position(symbol)
        if position and float(position.get('size', 0) or 0) > 0:
            filled_price = float(position.get('avgPrice', entry_signal_price) or entry_signal_price)
            filled = True
            logger.info(f"[REAL] Confirmado via posicion (3s): {symbol} @ {filled_price}")

        # Si no confirmo — 5s luego verificar de nuevo
        if not filled:
            await asyncio.sleep(5)
            position = await client.get_open_position(symbol)
            if position and float(position.get('size', 0) or 0) > 0:
                filled_price = float(position.get('avgPrice', entry_signal_price) or entry_signal_price)
                filled = True
                logger.warning(f"[REAL] Confirmado via posicion (8s): {symbol} @ {filled_price}")

        # Si sigue sin confirmar — reintentar hasta 3 veces (10s entre intentos)
        if not filled:
            for retry in range(3):
                await asyncio.sleep(10)
                logger.warning(f"[REAL] Reintento {retry+1}/3 abriendo {symbol}")
                # Verificar si la senal sigue activa
                df_retry = await self.get_bars(symbol, interval)
                if len(df_retry) >= 64:
                    df_retry = strategy_instance.prepare(df_retry)
                    df_retry = strategy_instance.generate_signals(df_retry)
                    current_signal = int(df_retry.iloc[-2]['signal'])
                    expected_signal = 1 if side == 'long' else -1
                    if current_signal != expected_signal:
                        logger.warning(f"[REAL] Senal no activa en reintento {retry+1} para {symbol} — abortando")
                        async with self.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE real_trades SET status='failed', error_message='Senal no activa en reintento', updated_at=now() WHERE id=$1",
                                trade_id
                            )
                        return False
                # Reintenta orden con provisionales actualizados
                retry_result = await client.place_market_order(symbol, bybit_side, size)
                if retry_result:
                    await asyncio.sleep(3)
                    position = await client.get_open_position(symbol)
                    if position and float(position.get('size', 0) or 0) > 0:
                        filled_price = float(position.get('avgPrice', entry_signal_price) or entry_signal_price)
                        filled = True
                        order_id = retry_result.get('orderId', order_id)
                        logger.info(f"[REAL] Reintento {retry+1} exitoso: {symbol} @ {filled_price}")
                        break

        # Si despues de 3 reintentos sigue sin confirmar → orphaned
        if not filled:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE real_trades SET status='orphaned', error_message='No confirmada tras 3 reintentos (38s)', updated_at=now() WHERE id=$1",
                    trade_id
                )
            logger.error(f"[REAL] Trade #{trade_id} {symbol} marcado como orphaned tras 3 reintentos")
            return False

        # 7b. Calcular SL/TP reales con avgPrice real de ejecucion
        avg_price = filled_price
        sl_pct_val = strategy_instance.sl_pct / 100
        tp_pct_val = strategy_instance.tp_pct / 100
        if side == 'long':
            sl  = round(avg_price * (1 - sl_pct_val), 8)
            tp1 = round(avg_price * (1 + tp_pct_val), 8)
            if tp2: tp2 = round(avg_price * (1 + (strategy_instance.tp2_pct or 0)/100), 8)
            if tp3: tp3 = round(avg_price * (1 + (strategy_instance.tp3_pct or 0)/100), 8)
            if tp4: tp4 = round(avg_price * (1 + (strategy_instance.tp4_pct or 0)/100), 8)
            be  = round(avg_price * (1 + strategy_instance.be_pct/100), 8)
        else:
            sl  = round(avg_price * (1 + sl_pct_val), 8)
            tp1 = round(avg_price * (1 - tp_pct_val), 8)
            if tp2: tp2 = round(avg_price * (1 - (strategy_instance.tp2_pct or 0)/100), 8)
            if tp3: tp3 = round(avg_price * (1 - (strategy_instance.tp3_pct or 0)/100), 8)
            if tp4: tp4 = round(avg_price * (1 - (strategy_instance.tp4_pct or 0)/100), 8)
            be  = round(avg_price * (1 - strategy_instance.be_pct/100), 8)
        logger.info(f"[REAL] SL/TP reales calculados: sl={sl} tp={tp1} be={be} avg={avg_price}")

        # 7c. Actualizar SL/TP reales en Bybit via trading-stop.
        # Si trailing_mode='fixed', se arma ADEMAS el trailing NATIVO de
        # Bybit (Bybit lo gestiona solo desde este momento). Modo 'stepped'
        # no tiene equivalente nativo, lo sigue manejando el bot.
        trailing_stop_price = None
        active_price = None
        if getattr(strategy_instance, 'trailing_mode', None) == 'fixed':
            trailing_stop_price, active_price = compute_native_trailing_params(
                avg_price, side, strategy_instance.trailing_distance_pct
            )
            logger.info(f"[REAL] Trailing NATIVO armado: {symbol} trailingStop={trailing_stop_price} activePrice={active_price}")

        ts_ok = await client.set_trading_stop(
            symbol, sl, tp1, trailing_stop=trailing_stop_price, active_price=active_price
        )
        if not ts_ok:
            logger.error(f"[REAL] trading-stop fallo para {symbol} — posicion con SL provisional")

        slippage_pct = abs(filled_price - entry_signal_price) / entry_signal_price * 100

        # 8. Actualizar a 'open' con precio real y SL/TP exactos
        update_ok = False
        for attempt in range(4):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE real_trades
                        SET status = 'open', order_id = $1,
                            entry_price = $2, slippage_pct = $3,
                            sl = $4, tp = $5, tp2 = $6, tp3 = $7, tp4 = $8,
                            be_level = $9, updated_at = now()
                        WHERE id = $10
                        """,
                        order_id, filled_price, round(slippage_pct, 6),
                        sl, tp1, tp2, tp3, tp4, be, trade_id
                    )
                update_ok = True
                break
            except Exception as e:
                wait = [2, 5, 30][attempt] if attempt < 3 else 0
                logger.error(f"[REAL] UPDATE a open fallo (intento {attempt+1}): {e}")
                if wait:
                    await asyncio.sleep(wait)
        if not update_ok:
            logger.critical(
                f"[REAL] CRITICO: trade #{trade_id} {symbol} abierto en Bybit "
                f"order_id={order_id} pero no se pudo actualizar en DB tras 4 intentos."
            )

        await self.log_audit(trade_id, 'opened', {
            'order_id': order_id,
            'filled_price': filled_price,
            'signal_price': entry_signal_price,
            'slippage_pct': slippage_pct,
            'balance_before': balance,
        })

        logger.info(
            f"[REAL] OPEN #{trade_id} {sub['strategy']} {symbol} {side.upper()} "
            f"@ {filled_price} (señal={entry_signal_price}) "
            f"SL={sl} TP={tp1} size={size} balance_before={balance}"
        )
        return True

    # ─────────────────────────────────────────────
    # Cerrar posicion real
    # ─────────────────────────────────────────────

    async def close_trade(self, trade: dict, exit_reason: str, client: BybitClient,
                           account_id: int, exit_price_override: float = None) -> bool:
        side   = trade['side']
        symbol = trade['symbol']
        # Si viene exit_price_override — posicion ya cerrada en Bybit por SL/TP
        if exit_price_override:
            entry_price = float(trade["entry_price"])
            size        = float(trade["size"])
            bal_before  = float(trade["balance_before"]) if trade.get("balance_before") else 0
            if side == "short":
                pnl = (entry_price - exit_price_override) * size
            else:
                pnl = (exit_price_override - entry_price) * size
            commission    = abs(exit_price_override * size * BYBIT_TAKER_FEE)
            net_pnl       = pnl - commission
            pnl_pct       = pnl / bal_before * 100 if bal_before > 0 else 0
            balance_after = await client.get_balance() or 0
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE real_trades SET status='closed', exit_price=$1, exit_reason=$2,"
                    " exit_time=now(), pnl=$3, pnl_pct=$4, net_pnl=$5, commission=$6,"
                    " balance_after=$7, updated_at=now() WHERE id=$8",
                    exit_price_override, exit_reason,
                    round(pnl,4), round(pnl_pct,4), round(net_pnl,4), round(commission,4),
                    balance_after, trade["id"]
                )
            logger.info(f"[REAL] CLOSE #{trade['id']} {symbol} override exit={exit_price_override} pnl={round(pnl,4)}")
            return True

        # Verificar que hay posicion abierta en Bybit
        position = await client.get_open_position(symbol)
        if not position:
            # Posicion ya cerrada en Bybit — reconciliar DB
            logger.warning(f"[REAL] Trade #{trade['id']} no tiene posicion en Bybit — reconciliando")
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE real_trades SET status = 'closed',
                        exit_reason = 'reconciled', exit_time = now(), updated_at = now()
                    WHERE id = $1
                    """,
                    trade['id']
                )
            return True

        # Marcar pending_close
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE real_trades SET status = 'pending_close', updated_at = now() WHERE id = $1",
                trade['id']
            )

        # Orden de cierre (lado contrario) - usa el tamano REAL de la posicion
        # en Bybit (no el guardado en DB), por si ya hubo un cierre parcial
        # de TP2/TP3/TP4 en este mismo ciclo que dejo el size de la DB desactualizado.
        close_side  = 'Sell' if side == 'long' else 'Buy'
        live_size   = float(position.get('size', 0) or 0)
        size        = live_size if live_size > 0 else float(trade['size'])
        result      = await client.place_market_order(symbol, close_side, size)

        if result is None:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE real_trades SET status = 'error',
                        error_message = 'Orden de cierre rechazada por Bybit',
                        updated_at = now()
                    WHERE id = $1
                    """,
                    trade['id']
                )
            await self.log_audit(trade['id'], 'close_failed', {'reason': 'bybit_rejected'})
            return False

        close_order_id = result.get('orderId')

        # Esperar confirmacion
        exit_price = await client.get_market_price(symbol) or float(trade['entry_price'])
        for _ in range(6):
            await asyncio.sleep(5)
            order = await client.get_order(symbol, close_order_id)
            if order and order.get('orderStatus') == 'Filled':
                exit_price = float(order.get('avgPrice', exit_price))
                break

        # Balance real despues del cierre
        balance_after = await client.get_balance()

        # Calcular PnL - suma esta pierna final mas lo ya realizado en
        # cierres parciales previos (TP2/TP3/TP4), si hubo.
        entry_price = float(trade['entry_price'])
        if side == 'long':
            pnl_leg = (exit_price - entry_price) * size
        else:
            pnl_leg = (entry_price - exit_price) * size

        partial_pnl = float(trade.get('realized_pnl_partial') or 0)
        pnl = pnl_leg + partial_pnl

        commission = abs(exit_price * size * BYBIT_TAKER_FEE)
        net_pnl    = pnl - commission
        pnl_pct    = pnl / float(trade['balance_before']) * 100 if trade.get('balance_before') else 0

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE real_trades
                SET status = 'closed', close_order_id = $1,
                    exit_price = $2, exit_reason = $3, exit_time = $4,
                    pnl = $5, pnl_pct = $6, net_pnl = $7, commission = $8,
                    balance_after = $9, updated_at = now()
                WHERE id = $10
                """,
                close_order_id, exit_price, exit_reason,
                datetime.now(timezone.utc).replace(tzinfo=None),
                round(pnl, 4), round(pnl_pct, 4), round(net_pnl, 4),
                round(commission, 6), balance_after, trade['id']
            )

        await self.log_audit(trade['id'], 'closed', {
            'close_order_id': close_order_id,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': round(pnl, 4),
            'net_pnl': round(net_pnl, 4),
            'commission': round(commission, 6),
            'balance_after': balance_after,
        })

        logger.info(
            f"[REAL] CLOSE #{trade['id']} {trade['strategy']} {symbol} "
            f"{side.upper()} @ {exit_price} reason={exit_reason} "
            f"pnl={round(pnl, 2)} net_pnl={round(net_pnl, 2)} commission={round(commission, 4)}"
        )
        return True

    async def update_breakeven(self, trade_id: int, new_sl: float,
                               client: 'BybitClient' = None, symbol: str = None, side: str = None, tp: float = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE real_trades SET sl = $1, be_activated = true, updated_at = now() WHERE id = $2",
                new_sl, trade_id
            )
        # Actualizar SL en Bybit para que este protegido aunque caiga el servidor
        if client and symbol and side:
            await client.set_trading_stop(symbol, new_sl, tp or 0)
            logger.info(f"[REAL] BE activado — SL actualizado en Bybit: {symbol} nuevo_sl={new_sl}")

    async def close_partial(self, trade, level, client, current_price, original_size):
        symbol   = trade["symbol"]
        side     = trade["side"]
        trade_id = trade["id"]

        close_side = "Sell" if side == "long" else "Buy"
        min_qty, qty_step = await client.get_min_qty(symbol)
        qty_to_close = original_size * 0.25
        if qty_step > 0:
            qty_to_close = round(qty_to_close / qty_step) * qty_step
        qty_to_close = round(qty_to_close, 8)

        if qty_to_close < min_qty:
            logger.warning(f"[REAL] {level} trade #{trade_id}: qty parcial {qty_to_close} menor a min_qty {min_qty}, se omite")
            return False

        result = await client.place_reduce_only_order(symbol, close_side, qty_to_close)
        if result is None:
            logger.error(f"[REAL] {level} trade #{trade_id}: orden reduceOnly rechazada por Bybit")
            return False

        entry_price = float(trade["entry_price"])
        if side == "long":
            pnl = (current_price - entry_price) * qty_to_close
        else:
            pnl = (entry_price - current_price) * qty_to_close

        hit_columns = {"take_profit_2": "tp2_hit", "take_profit_3": "tp3_hit", "take_profit_4": "tp4_hit"}
        hit_column = hit_columns[level]

        async with self.pool.acquire() as conn:
            query = "UPDATE real_trades SET size = size - $1, " + hit_column + " = true, realized_pnl_partial = realized_pnl_partial + $2, updated_at = now() WHERE id = $3"
            await conn.execute(query, qty_to_close, round(pnl, 8), trade_id)

        logger.info(f"[REAL] Cierre parcial {level}: {symbol} qty={qty_to_close} price={current_price} pnl={round(pnl, 4)}")
        return True

    # ─────────────────────────────────────────────
    # Monitor: revisar posiciones abiertas
    # ─────────────────────────────────────────────

    async def monitor_open_trades(self, account_id: int, client: BybitClient) -> dict:
        open_trades = await self.get_open_trades(account_id)
        results     = {"checked": 0, "closed": 0, "be_activated": 0, "errors": 0}
        price_cache: dict[str, float] = {}

        for trade in open_trades:
            results["checked"] += 1
            symbol   = trade["symbol"]
            side     = trade["side"]
            entry    = float(trade["entry_price"])
            sl       = float(trade["sl"])
            tp       = float(trade["tp"])
            tp2      = float(trade["tp2"]) if trade.get("tp2") is not None else None
            tp3      = float(trade["tp3"]) if trade.get("tp3") is not None else None
            tp4      = float(trade["tp4"]) if trade.get("tp4") is not None else None
            original_size = float(trade["original_size"]) if trade.get("original_size") else float(trade["size"])
            be_level = float(trade["be_level"]) if trade.get("be_level") else 0
            trade_id = trade["id"]

            try:
                # 1. Verificar si posicion existe en Bybit
                position = await client.get_open_position(symbol)
                pos_size = float(position.get("size", 0) or 0) if position else 0

                if pos_size <= 0:
                    since_time_ms = 0
                    ref_time = trade.get("updated_at") or trade.get("entry_time")
                    if ref_time:
                        if ref_time.tzinfo is None:
                            ref_time = ref_time.replace(tzinfo=timezone.utc)
                        since_time_ms = int(ref_time.timestamp() * 1000)

                    history = await client.get_closed_pnl_history(symbol, entry, since_time_ms)

                    if history:
                        total_pnl  = sum(float(h.get("closedPnl", 0)) for h in history)
                        total_size = sum(float(h.get("closedSize", 0)) for h in history)
                        last_entry = max(history, key=lambda h: int(h.get("updatedTime", 0)))
                        exit_price = float(last_entry.get("avgExitPrice", entry))

                        if len(history) > 1:
                            logger.info(
                                f"[REAL] {symbol}: cierre dividido en {len(history)} tramos por Bybit "
                                f"(iliquidez) - pnl total sumado={round(total_pnl, 4)}"
                            )

                        sl_val = float(trade["sl"])
                        tp_val = float(trade["tp"])
                        if side == "short":
                            if exit_price >= sl_val:
                                exit_reason = "stop_loss"
                            elif exit_price <= tp_val:
                                exit_reason = "take_profit_1"
                            else:
                                exit_reason = "closed_other"
                        else:
                            if exit_price <= sl_val:
                                exit_reason = "stop_loss"
                            elif exit_price >= tp_val:
                                exit_reason = "take_profit_1"
                            else:
                                exit_reason = "closed_other"

                        remaining_size = float(trade["size"])
                        if remaining_size > 0 and total_size > 0:
                            if side == "long":
                                exit_price = entry + (total_pnl / remaining_size)
                            else:
                                exit_price = entry - (total_pnl / remaining_size)
                    else:
                        exit_price  = entry
                        exit_reason = "reconciled_sl_tp_bybit"
                    success = await self.close_trade(trade, exit_reason, client, account_id, exit_price_override=exit_price)
                    if success:
                        results["closed"] += 1
                    else:
                        results["errors"] += 1
                    continue
                # 2. Verificar si SL es provisional (>2.5%) — reintentar trading-stop
                sl_pct_actual = abs(sl - entry) / entry * 100 if entry > 0 else 0
                if sl_pct_actual > 2.5:
                    strategy_sl_pct = 0.8
                    q = "SELECT psc.params->>'sl_pct' as sl_pct FROM real_trades rt"
                    q += " JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id"
                    q += " JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id"
                    q += " WHERE rt.id = $1"
                    async with self.pool.acquire() as conn:
                        row = await conn.fetchrow(q, trade_id)
                        if row and row["sl_pct"]:
                            strategy_sl_pct = float(row["sl_pct"])
                    if side == "short":
                        sl_real = round(entry * (1 + strategy_sl_pct/100), 8)
                    else:
                        sl_real = round(entry * (1 - strategy_sl_pct/100), 8)
                    ts_ok = await client.set_trading_stop(symbol, sl_real, tp)
                    if ts_ok:
                        async with self.pool.acquire() as conn:
                            await conn.execute("UPDATE real_trades SET sl=$1, updated_at=now() WHERE id=$2", sl_real, trade_id)
                        logger.info(f"[MONITOR] SL provisional actualizado a real: {symbol} sl={sl_real}")

                # 3. Precio actual
                if symbol not in price_cache:
                    price = await client.get_market_price(symbol)
                    if price is None:
                        continue
                    price_cache[symbol] = price
                current_price = price_cache[symbol]

                # 4. Break-even via trading-stop
                if be_level > 0 and not trade["be_activated"]:
                    be_reached = (side == "long" and current_price >= be_level) or \
                                 (side == "short" and current_price <= be_level)
                    if be_reached:
                        ts_ok = await client.set_trading_stop(symbol, entry, tp)
                        if ts_ok:
                            async with self.pool.acquire() as conn:
                                await conn.execute(
                                    "UPDATE real_trades SET be_activated=true, sl=$1, updated_at=now() WHERE id=$2",
                                    entry, trade_id
                                )
                            results["be_activated"] += 1
                            logger.info(f"[MONITOR] BE activado: {symbol} sl movido a entry={entry}")

                # 5. Trailing Stop: modo 'fixed' usa el trailing NATIVO de Bybit,
                # armado una sola vez al abrir el trade (ver open_trade) - Bybit
                # lo gestiona en su propio motor, sin depender de que el bot este
                # corriendo. Modo 'stepped' no tiene equivalente nativo en Bybit,
                # sigue gestionado por el bot aca.
                q3 = "SELECT psc.params->>'trailing_mode' as trailing_mode, "
                q3 += "psc.params->>'trailing_distance_pct' as trailing_distance_pct, "
                q3 += "psc.params->>'trailing_steps' as trailing_steps FROM real_trades rt"
                q3 += " JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id"
                q3 += " JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id"
                q3 += " WHERE rt.id = $1"
                async with self.pool.acquire() as conn:
                    row3 = await conn.fetchrow(q3, trade_id)

                trailing_mode = row3["trailing_mode"] if row3 else None
                if trailing_mode == "stepped":
                    trailing_distance_pct = float(row3["trailing_distance_pct"]) if row3["trailing_distance_pct"] else 1.0
                    trailing_steps = json.loads(row3["trailing_steps"]) if row3["trailing_steps"] else []

                    new_sl = calculate_trailing_sl_standalone(
                        trailing_mode, trailing_distance_pct, trailing_steps,
                        entry, side, current_price, sl
                    )
                    if new_sl != sl:
                        ts_ok = await client.set_trading_stop(symbol, new_sl, tp)
                        if ts_ok:
                            async with self.pool.acquire() as conn:
                                await conn.execute(
                                    "UPDATE real_trades SET sl=$1, trailing_applied=true, updated_at=now() WHERE id=$2",
                                    new_sl, trade_id
                                )
                            sl = new_sl
                            logger.info(f"[MONITOR] Trailing aplicado (bot, modo stepped): {symbol} sl movido a {new_sl}")
                elif trailing_mode == "fixed":
                    native_sl = await client.get_native_trailing_level(symbol)
                    if native_sl is not None and round(native_sl, 8) != round(sl, 8):
                        async with self.pool.acquire() as conn:
                            await conn.execute(
                                "UPDATE real_trades SET sl=$1, trailing_applied=true, updated_at=now() WHERE id=$2",
                                native_sl, trade_id
                            )
                        sl = native_sl
                        logger.info(f"[MONITOR] Trailing nativo sincronizado: {symbol} sl={native_sl}")

                # 6. Proteccion por volatilidad - usa ATR de las ultimas velas reales.
                # mode="close": cierra la posicion completa (como time_exit).
                # mode="widen": ensancha el SL fijo via set_trading_stop.
                q4 = "SELECT psc.params->>'volatility_protection_mode' as volatility_protection_mode, "
                q4 += "psc.params->>'volatility_atr_multiplier' as volatility_atr_multiplier, "
                q4 += "psc.params->>'volatility_widen_pct' as volatility_widen_pct FROM real_trades rt"
                q4 += " JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id"
                q4 += " JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id"
                q4 += " WHERE rt.id = $1"
                async with self.pool.acquire() as conn:
                    row4 = await conn.fetchrow(q4, trade_id)

                vol_mode = row4["volatility_protection_mode"] if row4 else None
                if vol_mode in ("close", "widen"):
                    bars = await self.get_bars(symbol, trade["interval"])
                    if len(bars) >= 51:
                        atr_multiplier = float(row4["volatility_atr_multiplier"]) if row4["volatility_atr_multiplier"] else 2.5
                        widen_pct = float(row4["volatility_widen_pct"]) if row4["volatility_widen_pct"] else 1.0
                        atr_series = calculate_atr(bars)
                        current_atr = float(atr_series.iloc[-1])
                        avg_atr = float(atr_series.rolling(50).mean().iloc[-1])

                        if avg_atr > 0 and current_atr > avg_atr * atr_multiplier:
                            if vol_mode == "close":
                                success = await self.close_trade(trade, "volatility_protection", client, account_id)
                                if success:
                                    results["closed"] += 1
                                else:
                                    results["errors"] += 1
                                continue
                            elif vol_mode == "widen":
                                if side == "long":
                                    new_sl_v = round(sl * (1 - widen_pct / 100), 8)
                                else:
                                    new_sl_v = round(sl * (1 + widen_pct / 100), 8)
                                ts_ok = await client.set_trading_stop(symbol, new_sl_v, tp)
                                if ts_ok:
                                    async with self.pool.acquire() as conn:
                                        await conn.execute(
                                            "UPDATE real_trades SET sl=$1, updated_at=now() WHERE id=$2",
                                            new_sl_v, trade_id
                                        )
                                    sl = new_sl_v
                                    logger.info(f"[MONITOR] SL ensanchado por volatilidad: {symbol} nuevo_sl={new_sl_v}")

                # 7. Take Profit parcial - TP4 > TP3 > TP2 (prioridad), 25% cada uno.
                # No cierra si ya se disparo ese nivel antes.
                for level, tp_level, hit_flag in [
                    ("take_profit_4", tp4, trade.get("tp4_hit")),
                    ("take_profit_3", tp3, trade.get("tp3_hit")),
                    ("take_profit_2", tp2, trade.get("tp2_hit")),
                ]:
                    if tp_level is None or hit_flag:
                        continue
                    reached = (side == "long" and current_price >= tp_level) or (side == "short" and current_price <= tp_level)
                    if reached:
                        await self.close_partial(trade, level, client, current_price, original_size)
                        break

                # 8. Cierre por duracion maxima
                q2 = "SELECT psc.params->>'max_duration' as max_duration FROM real_trades rt"
                q2 += " JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id"
                q2 += " JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id"
                q2 += " WHERE rt.id = $1"
                max_duration = 24
                async with self.pool.acquire() as conn:
                    row2 = await conn.fetchrow(q2, trade_id)
                    if row2 and row2["max_duration"]:
                        max_duration = int(row2["max_duration"])

                entry_time = trade["entry_time"]
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                hours_open = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                if hours_open >= max_duration:
                    success = await self.close_trade(trade, "time_exit", client, account_id)
                    if success:
                        results["closed"] += 1
                    else:
                        results["errors"] += 1

            except Exception as e:
                logger.error(f"[MONITOR] Error trade #{trade_id} {symbol}: {e}", exc_info=True)
                results["errors"] += 1

        return results

    # Buscar nuevas señales
    # ─────────────────────────────────────────────

    async def check_new_signals(self, sub: dict, strategy_instance,
                                 client: BybitClient) -> str:
        symbol   = sub['symbol']
        interval = sub['interval']

        # Verificar duplicado en DB
        if await self.has_open_trade(sub['subscription_id'], symbol):
            return f"{symbol}: ya tiene posicion abierta"

        # Verificar duplicado en Bybit (doble verificacion)
        bybit_position = await client.get_open_position(symbol)
        if bybit_position:
            return f"{symbol}: posicion abierta en Bybit (no registrada en DB)"

        # Obtener barras y generar señal
        df = await self.get_bars(symbol, interval)
        if len(df) < 64:
            return f"{symbol}: datos insuficientes"

        regime = await self.get_current_regime(df)
        if not strategy_instance.should_operate(regime):
            return f"{symbol}: regimen no permitido ({regime})"

        df = strategy_instance.prepare(df)
        df = strategy_instance.generate_signals(df)

        last_closed = df.iloc[-2]
        signal = int(last_closed['signal'])

        if signal == 0:
            return f"{symbol}: sin señal"

        side        = 'long' if signal == 1 else 'short'
        entry_price = await client.get_market_price(symbol)

        if entry_price is None:
            return f"{symbol}: error obteniendo precio"
        try:
            success = await self.open_trade(sub, strategy_instance, side,
                                                 entry_price, regime, client)
            return f"{symbol}: {'ABIERTA' if success else 'ERROR'} {side} @ {entry_price}"
        except Exception as e:
            logger.error(f"[REAL] open_trade exception {symbol}: {e}", exc_info=True)
            return f"{symbol}: EXCEPTION {side} @ {entry_price}: {str(e)}"

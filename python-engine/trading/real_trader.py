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

from trading.bybit_client import get_current_price
from indicators.regime_indicators import calculate_atr, calculate_adx, calculate_bb_width, classify_regime

load_dotenv()
logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

BYBIT_MAINNET = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
BYBIT_TESTNET = os.getenv('BYBIT_TESTNET_URL', 'https://api-testnet.bybit.com')

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
        timestamp   = str(int(time.time() * 1000))
        recv_window = '5000'

        # Bybit V5 GET: param_str = timestamp + api_key + recv_window + query_string
        query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        param_str = timestamp + self.api_key + recv_window + query_string

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            'X-BAPI-API-KEY':     self.api_key,
            'X-BAPI-TIMESTAMP':   timestamp,
            'X-BAPI-SIGN':        signature,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type':       'application/json',
        }

    def _sign_body(self, body: dict) -> dict:
        """Firma para requests con body JSON (POST). Bybit V5: timestamp+key+recv+body."""
        timestamp   = str(int(time.time() * 1000))
        recv_window = '5000'
        body_str    = json.dumps(body, separators=(',', ':'), ensure_ascii=True)

        param_str = timestamp + self.api_key + recv_window + body_str

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            'X-BAPI-API-KEY':     self.api_key,
            'X-BAPI-TIMESTAMP':   timestamp,
            'X-BAPI-SIGN':        signature,
            'X-BAPI-RECV-WINDOW': recv_window,
            'Content-Type':       'application/json',
        }

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
        Coloca una orden MARKET con SL y TP incluidos.
        side: 'Buy' o 'Sell'
        sl/tp: precios absolutos de stop loss y take profit
        Retorna el resultado de Bybit o None si fallo.
        """
        body = {
            'category':  'linear',
            'symbol':    symbol,
            'side':      side,
            'orderType': 'Market',
            'qty':       str(qty),
        }
        # Incluir SL y TP directamente en la orden — mas seguro que configurarlos despues
        if sl and sl > 0:
            logger.info(f"[BYBIT] SL recibido: {sl} side={side} symbol={symbol}")
            body['stopLoss']    = str(round(sl, 8))
            body['slTriggerBy'] = 'LastPrice'
        if tp and tp > 0:
            logger.info(f"[BYBIT] TP recibido: {tp} side={side} symbol={symbol}")
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

    async def set_trading_stop(self, symbol: str, side: str, sl: float, tp: float) -> bool:
        """
        Configura SL y TP en Bybit para una posicion abierta.
        Se llama despues de confirmar la apertura de la orden.
        side: 'long' o 'short' (se convierte a Buy/Sell internamente)
        """
        position_idx = 0  # one-way mode
        body = {
            'category':    'linear',
            'symbol':      symbol,
            'positionIdx': position_idx,
            'stopLoss':    str(round(sl, 8)),
            'takeProfit':  str(round(tp, 8)),
            'slTriggerBy': 'LastPrice',
            'tpTriggerBy': 'LastPrice',
        }
        headers = self._sign_body(body)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f'{self.base_url}/v5/position/trading-stop',
                    content=json.dumps(body, separators=(',', ':'), ensure_ascii=True).encode(),
                    headers=headers,
                )
            data = r.json()
            if data.get('retCode') == 0:
                logger.info(f"[BYBIT] SL/TP configurado en Bybit: {symbol} SL={sl} TP={tp}")
                return True
            else:
                logger.error(f"[BYBIT] set_trading_stop error: {data.get('retMsg')} code={data.get('retCode')}")
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
                       size, entry_time, order_id, balance_before, status
                FROM real_trades
                WHERE broker_account_id = $1
                  AND status IN ('open', 'pending_close')
                """,
                account_id
            )
        return [dict(r) for r in rows]

    async def has_open_trade(self, subscription_id: int, symbol: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM real_trades
                WHERE subscription_id = $1 AND symbol = $2
                  AND status IN ('pending_open', 'open', 'pending_close')
                """,
                subscription_id, symbol
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
        risk_pct    = strategy_instance.params.get('risk_per_trade_pct', 1.0)
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

        # 5. Crear registro en pending_open ANTES de enviar a Bybit
        async with self.pool.acquire() as conn:
            trade_id = await conn.fetchval(
                """
                INSERT INTO real_trades
                    (user_id, subscription_id, broker_account_id, paper_strategy_config_id,
                     strategy, symbol, broker, interval, side,
                     entry_price, entry_price_signal, sl, tp, tp2, tp3, tp4,
                     be_level, be_activated, size, leverage,
                     balance_before, regime, entry_time,
                     status, created_at, updated_at)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                     $10, $11, $12, $13, $14, $15, $16,
                     $17, false, $18, 1,
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

        # 6. Enviar orden MARKET a Bybit con SL y TP incluidos
        bybit_side = 'Buy' if side == 'long' else 'Sell'
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

        # 7. Esperar confirmacion — 3s inicial
        filled_price = entry_signal_price
        filled = False
        await asyncio.sleep(3)
        order = await client.get_order(symbol, order_id)
        if order and order.get('orderStatus') == 'Filled':
            filled_price = float(order.get('avgPrice', entry_signal_price))
            filled = True

        # Si no confirmo via order — 5s luego verificar posicion en Bybit
        if not filled:
            await asyncio.sleep(5)
            position = await client.get_open_position(symbol)
            if position and float(position.get('size', 0) or 0) > 0:
                filled_price = float(position.get('avgPrice', entry_signal_price) or entry_signal_price)
                filled = True
                logger.warning(f"[REAL] Confirmado via posicion Bybit: {symbol} @ {filled_price}")

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
                # Reintenta con precio actualizado
                new_price = await client.get_market_price(symbol)
                if new_price:
                    new_sl, new_tp1 = strategy_instance.calculate_sl_tp(new_price, side)
                    retry_result = await client.place_market_order(symbol, bybit_side, size, sl=new_sl, tp=new_tp1)
                    if retry_result:
                        retry_order_id = retry_result.get('orderId', '')
                        await asyncio.sleep(3)
                        retry_order = await client.get_order(symbol, retry_order_id)
                        if retry_order and retry_order.get('orderStatus') == 'Filled':
                            filled_price = float(retry_order.get('avgPrice', new_price))
                            filled = True
                            order_id = retry_order_id
                            sl, tp1 = new_sl, new_tp1
                            async with self.pool.acquire() as conn:
                                await conn.execute(
                                    "UPDATE real_trades SET sl=$1, tp=$2, entry_price_signal=$3, updated_at=now() WHERE id=$4",
                                    new_sl, new_tp1, new_price, trade_id
                                )
                            logger.info(f"[REAL] Reintento {retry+1} exitoso: {symbol} @ {filled_price}")
                            break
                    # Verificar posicion tras reintento
                    position = await client.get_open_position(symbol)
                    if position and float(position.get('size', 0) or 0) > 0:
                        filled_price = float(position.get('avgPrice', new_price) or new_price)
                        filled = True
                        logger.warning(f"[REAL] Reintento {retry+1} confirmado via posicion: {symbol} @ {filled_price}")
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

        slippage_pct = abs(filled_price - entry_signal_price) / entry_signal_price * 100

        # 8. Actualizar a 'open' con precio real — hasta 4 reintentos
        update_ok = False
        for attempt in range(4):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE real_trades
                        SET status = 'open', order_id = $1,
                            entry_price = $2, slippage_pct = $3,
                            updated_at = now()
                        WHERE id = $4
                        """,
                        order_id, filled_price, round(slippage_pct, 6), trade_id
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
                f"order_id={order_id} pero no se pudo actualizar en DB tras 4 intentos. "
                f"El reconciliador (5min) lo detectara y creara el registro."
            )

        # Configurar SL y TP en Bybit inmediatamente tras confirmar apertura
        # Esto protege la posicion aunque el servidor caiga
        await client.set_trading_stop(symbol, side, sl, tp1)

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
                           account_id: int) -> bool:
        symbol = trade['symbol']
        side   = trade['side']

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

        # Orden de cierre (lado contrario)
        close_side = 'Sell' if side == 'long' else 'Buy'
        size       = float(trade['size'])
        result     = await client.place_market_order(symbol, close_side, size)

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

        # Calcular PnL
        entry_price = float(trade['entry_price'])
        if side == 'long':
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

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
            await client.set_trading_stop(symbol, side, new_sl, tp or 0)
            logger.info(f"[REAL] BE activado — SL actualizado en Bybit: {symbol} nuevo_sl={new_sl}")

    # ─────────────────────────────────────────────
    # Monitor: revisar posiciones abiertas
    # ─────────────────────────────────────────────

    async def monitor_open_trades(self, account_id: int, client: BybitClient) -> dict:
        open_trades = await self.get_open_trades(account_id)
        results     = {"checked": 0, "closed": 0, "be_activated": 0, "errors": 0}
        price_cache: dict[str, float] = {}

        for trade in open_trades:
            results["checked"] += 1
            symbol = trade['symbol']

            if symbol not in price_cache:
                price = await client.get_market_price(symbol)
                if price is None:
                    continue
                price_cache[symbol] = price

            current_price = price_cache[symbol]
            side     = trade['side']
            sl       = float(trade['sl'])
            tp       = float(trade['tp'])
            tp2      = float(trade['tp2']) if trade.get('tp2') else None
            tp3      = float(trade['tp3']) if trade.get('tp3') else None
            tp4      = float(trade['tp4']) if trade.get('tp4') else None
            be_level = float(trade['be_level'])
            entry    = float(trade['entry_price'])

            exit_price  = None
            exit_reason = None

            # Break-even
            if not trade['be_activated']:
                if (side == 'long' and current_price >= be_level) or \
                   (side == 'short' and current_price <= be_level):
                    await self.update_breakeven(trade['id'], entry, client=client, symbol=symbol, side=side, tp=tp)
                    results["be_activated"] += 1

            # Stop Loss
            if side == 'long' and current_price <= sl:
                exit_price, exit_reason = sl, 'stop_loss'
            elif side == 'short' and current_price >= sl:
                exit_price, exit_reason = sl, 'stop_loss'

            # Take Profit (prioridad TP4 > TP3 > TP2 > TP1)
            if exit_price is None:
                for tp_val, tp_name in [
                    (tp4, 'take_profit_4'),
                    (tp3, 'take_profit_3'),
                    (tp2, 'take_profit_2'),
                    (tp,  'take_profit_1'),
                ]:
                    if tp_val is None:
                        continue
                    if (side == 'long' and current_price >= tp_val) or \
                       (side == 'short' and current_price <= tp_val):
                        exit_price, exit_reason = tp_val, tp_name
                        break

            # Cierre por tiempo
            if exit_price is None:
                entry_time = trade['entry_time']
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                hours_open = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600

                # Usar max_duration de la config de la suscripcion (por defecto 24h)
                max_duration = 24
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT psc.params->>'max_duration' as max_duration
                        FROM real_trades rt
                        JOIN real_strategy_subscriptions rss ON rss.id = rt.subscription_id
                        JOIN paper_strategy_configs psc ON psc.id = rss.paper_strategy_config_id
                        WHERE rt.id = $1
                        """,
                        trade['id']
                    )
                    if row and row['max_duration']:
                        max_duration = int(row['max_duration'])
                if hours_open >= max_duration:
                    exit_price, exit_reason = current_price, 'time_exit'

            if exit_price is not None:
                success = await self.close_trade(trade, exit_reason, client, account_id)
                if success:
                    results["closed"] += 1
                else:
                    results["errors"] += 1

        return results

    # ─────────────────────────────────────────────
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

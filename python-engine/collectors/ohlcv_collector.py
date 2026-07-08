"""
OHLCV Collector — Data Collector V2
Recolecta y almacena velas históricas y en tiempo real desde Bybit.
Los símbolos e intervalos activos se leen desde la tabla collector_configs (DB),
no desde variables de entorno. El admin los gestiona desde la UI de Laravel.
"""

import asyncio
import asyncpg
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

from trading.ig_client import IGClient, IGAPIError

logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')

# Fallback si la DB no responde (no debería ocurrir en producción)
FALLBACK_SYMBOLS   = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')
FALLBACK_INTERVALS = os.getenv('INTERVALS', '1,5,15,60,120').split(',')

BYBIT_LIMIT  = 200
HISTORY_DAYS = 730  # 2 años (Bybit, sin limite de cuota)
IG_HISTORY_DAYS = 365  # 1 año (IG tiene cuota semanal de 10,000 puntos)

# Mapeo interval (mismo naming que collector_configs) -> resolution IG
IG_RESOLUTION_MAP = {
    '60':  'HOUR',
    '240': 'HOUR_4',
}
IG_BATCH_HOURS = {
    '60':  24 * 20,   # ~20 dias por llamada = ~480 velas H1
    '240': 24 * 80,   # ~80 dias por llamada = ~480 velas H4
}


class OhlcvCollector:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self._ig_client: Optional[IGClient] = None

    # ─────────────────────────────────────────────
    # Leer configuracion activa desde DB
    # ─────────────────────────────────────────────

    async def get_active_configs(self) -> list[tuple[str, str, str, Optional[str]]]:
        """
        Retorna lista de (symbol, interval, broker, epic) activos desde
        collector_configs. Si la tabla no existe o falla, usa el fallback
        del .env (siempre broker='bybit', epic=None).
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT symbol, interval, broker, epic
                    FROM collector_configs
                    WHERE active = true
                    ORDER BY symbol, interval
                    """
                )
            if rows:
                return [(r['symbol'], r['interval'], r['broker'], r['epic']) for r in rows]
        except Exception as e:
            logger.warning(f"[Collector] Error leyendo collector_configs, usando fallback: {e}")

        # Fallback: producto cartesiano de FALLBACK_SYMBOLS × FALLBACK_INTERVALS (bybit)
        return [
            (symbol, interval, 'bybit', None)
            for symbol in FALLBACK_SYMBOLS
            for interval in FALLBACK_INTERVALS
        ]

    # ─────────────────────────────────────────────
    # Fetch desde Bybit
    # ─────────────────────────────────────────────

    async def fetch_from_bybit(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
    ) -> list[dict]:
        """Obtiene velas OHLCV de Bybit entre start_ts y end_ts (unix segundos)."""
        all_bars = []
        end_ms   = end_ts * 1000
        start_ms = start_ts * 1000

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                r = await client.get(
                    f'{BYBIT_BASE_URL}/v5/market/kline',
                    params={
                        'category': 'linear',
                        'symbol':   symbol,
                        'interval': interval,
                        'limit':    BYBIT_LIMIT,
                        'end':      end_ms,
                    }
                )
                r.raise_for_status()
                bars = r.json().get('result', {}).get('list', [])

                if not bars:
                    break

                stop = False
                for b in bars:
                    ts = int(b[0])
                    if ts < start_ms:
                        stop = True
                        break
                    all_bars.append({
                        'time':     datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                        'symbol':   symbol,
                        'interval': interval,
                        'open':     float(b[1]),
                        'high':     float(b[2]),
                        'low':      float(b[3]),
                        'close':    float(b[4]),
                        'volume':   float(b[5]),
                    })

                if stop:
                    break

                new_end = int(bars[-1][0]) - 1
                if new_end >= end_ms:
                    break
                end_ms = new_end

                await asyncio.sleep(0.1)

        all_bars.reverse()
        return all_bars

    # ─────────────────────────────────────────────
    # Fetch desde IG (con manejo de cuota semanal)
    # ─────────────────────────────────────────────

    async def _get_ig_client(self) -> Optional[IGClient]:
        """
        Busca la cuenta IG activa en broker_accounts (prioriza 'real' sobre
        'demo' si ambas existen) y arma un IGClient. Cachea la instancia -
        IGClient ya cachea su propia sesion CST/X-SECURITY-TOKEN internamente.
        """
        if self._ig_client is not None:
            return self._ig_client

        import json as _json
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT api_key, credentials_extra, account_type
                FROM broker_accounts
                WHERE broker = 'ig' AND status = 'active'
                ORDER BY (account_type = 'real') DESC
                LIMIT 1
                """
            )

        if not row or not row['credentials_extra']:
            logger.error("[Collector] No hay cuenta IG activa con credenciales en broker_accounts")
            return None

        from trading.laravel_crypt import laravel_decrypt
        api_key_dec = laravel_decrypt(row['api_key'])
        extra_dec   = laravel_decrypt(row['credentials_extra'])
        extra = _json.loads(extra_dec)
        self._ig_client = IGClient(
            api_key      = api_key_dec,
            username     = extra.get('username', ''),
            password     = extra.get('password', ''),
            account_type = row['account_type'],
        )
        return self._ig_client

    async def _ig_quota_blocked_until(self) -> Optional[datetime]:
        """Lee de python_engine_state si la cuota de IG esta bloqueada, y hasta cuando."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM python_engine_state WHERE key = 'ig_quota_blocked_until'"
            )
        if not row:
            return None
        try:
            return datetime.fromisoformat(row['value'])
        except ValueError:
            return None

    async def _set_ig_quota_blocked_until(self, until: datetime):
        """Guarda hasta cuando saltarse las llamadas a IG por cuota agotada."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO python_engine_state (key, value, updated_at)
                VALUES ('ig_quota_blocked_until', $1, now())
                ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = now()
                """,
                until.isoformat(),
            )

    async def fetch_from_ig(
        self,
        epic: str,
        interval: str,
        start_ts: int,
        end_ts: int,
    ) -> list[dict]:
        """
        Obtiene velas OHLCV de IG entre start_ts y end_ts (unix segundos),
        paginando en bloques y respetando la cuota semanal (10,000 puntos).
        Si la cuota se agota a mitad de camino, corta ahi, guarda en
        python_engine_state hasta cuando reintentar, y devuelve lo
        conseguido - la proxima corrida retoma desde el ultimo timestamp
        guardado (mismo patron que fetch_from_bybit).
        """
        resolution = IG_RESOLUTION_MAP.get(interval)
        if not resolution:
            logger.error(f"[IG-Collector] interval {interval} sin mapeo a resolution IG")
            return []

        blocked_until = await self._ig_quota_blocked_until()
        if blocked_until and datetime.now(timezone.utc) < blocked_until:
            logger.debug(f"[IG-Collector] {epic}/{interval} cuota bloqueada hasta {blocked_until}, saltando")
            return []

        client = await self._get_ig_client()
        if not client:
            return []

        batch_hours = IG_BATCH_HOURS.get(interval, 24 * 20)
        batch_seconds = batch_hours * 3600

        all_bars = []
        cursor = start_ts

        while cursor < end_ts:
            batch_end = min(cursor + batch_seconds, end_ts)
            start_str = datetime.fromtimestamp(cursor, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            end_str   = datetime.fromtimestamp(batch_end, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            try:
                data = await client.get_historical_prices(epic, resolution, start_str, end_str)
            except IGAPIError as e:
                if 'exceeded-account-historical-data-allowance' in str(e):
                    until = datetime.now(timezone.utc) + timedelta(days=7)
                    await self._set_ig_quota_blocked_until(until)
                    logger.warning(f"[IG-Collector] {epic}/{interval} cuota semanal agotada, "
                                    f"pausando llamadas a IG hasta {until}")
                else:
                    logger.error(f"[IG-Collector] {epic}/{interval} error obteniendo precios: {e}")
                break

            prices = data.get('prices', [])
            for p in prices:
                try:
                    ts_str = p['snapshotTime']
                    ts = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    open_p  = (p['openPrice']['bid']  + p['openPrice']['ask'])  / 2
                    high_p  = (p['highPrice']['bid']  + p['highPrice']['ask'])  / 2
                    low_p   = (p['lowPrice']['bid']   + p['lowPrice']['ask'])   / 2
                    close_p = (p['closePrice']['bid'] + p['closePrice']['ask']) / 2
                    volume  = p.get('lastTradedVolume') or 0
                    all_bars.append({
                        'time':     ts,
                        'symbol':   None,  # se completa en el caller
                        'interval': interval,
                        'open':     open_p,
                        'high':     high_p,
                        'low':      low_p,
                        'close':    close_p,
                        'volume':   float(volume),
                    })
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(f"[IG-Collector] vela descartada, formato inesperado: {e}")
                    continue

            allowance = data.get('allowance', {})
            remaining = allowance.get('remainingAllowance', 0)
            logger.info(f"[IG-Collector] {epic}/{interval} batch {start_str}→{end_str}: "
                        f"{len(prices)} velas, cuota restante={remaining}")

            # Cortar si la cuota esta baja (dejamos margen de 50 puntos)
            if remaining < 50:
                logger.warning(f"[IG-Collector] {epic}/{interval} cuota casi agotada ({remaining}), "
                                f"cortando descarga - continuara la proxima corrida")
                break

            cursor = batch_end
            await asyncio.sleep(0.3)

        return all_bars

    # ─────────────────────────────────────────────
    # Guardar en DB
    # ─────────────────────────────────────────────

    async def save_bars(self, bars: list[dict]) -> int:
        if not bars:
            return 0

        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO ohlcv_data
                    (time, symbol, interval, open, high, low, close, volume)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, interval, time)
                DO NOTHING
                """,
                [
                    (
                        b['time'], b['symbol'], b['interval'],
                        b['open'], b['high'], b['low'],
                        b['close'], b['volume'],
                    )
                    for b in bars
                ]
            )
        return len(bars)

    # ─────────────────────────────────────────────
    # Último timestamp guardado
    # ─────────────────────────────────────────────

    async def get_last_timestamp(self, symbol: str, interval: str) -> Optional[datetime]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(time) as last_time
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                """,
                symbol, interval
            )
            return row['last_time'] if row else None

    # ─────────────────────────────────────────────
    # Carga histórica inicial
    # ─────────────────────────────────────────────

    async def initial_load(self, symbol: str, interval: str,
                            broker: str = 'bybit', epic: Optional[str] = None) -> int:
        last = await self.get_last_timestamp(symbol, interval)

        if last:
            logger.info(f"[{symbol}/{interval}] Ya tiene datos hasta {last} — saltando carga inicial")
            return 0

        now = int(datetime.now(timezone.utc).timestamp())

        if broker == 'ig':
            logger.info(f"[{symbol}/{interval}] Iniciando carga histórica IG de {IG_HISTORY_DAYS} días...")
            start_ts = now - (IG_HISTORY_DAYS * 24 * 60 * 60)
            bars = await self.fetch_from_ig(epic, interval, start_ts, now)
            for b in bars:
                b['symbol'] = symbol
        else:
            logger.info(f"[{symbol}/{interval}] Iniciando carga histórica de {HISTORY_DAYS} días...")
            start_ts = now - (HISTORY_DAYS * 24 * 60 * 60)
            bars = await self.fetch_from_bybit(symbol, interval, start_ts, now)

        saved = await self.save_bars(bars)
        logger.info(f"[{symbol}/{interval}] Carga inicial: {saved} velas guardadas")
        return saved

    # ─────────────────────────────────────────────
    # Actualización continua
    # ─────────────────────────────────────────────

    async def update(self, symbol: str, interval: str,
                      broker: str = 'bybit', epic: Optional[str] = None) -> int:
        last = await self.get_last_timestamp(symbol, interval)

        if not last:
            return await self.initial_load(symbol, interval, broker, epic)

        start_ts = int(last.timestamp())
        end_ts   = int(datetime.now(timezone.utc).timestamp())

        if end_ts - start_ts < 60:
            return 0

        if broker == 'ig':
            bars = await self.fetch_from_ig(epic, interval, start_ts, end_ts)
            for b in bars:
                b['symbol'] = symbol
        else:
            bars = await self.fetch_from_bybit(symbol, interval, start_ts, end_ts)

        saved = await self.save_bars(bars)

        if saved > 0:
            logger.info(f"[{symbol}/{interval}] Actualización: {saved} velas nuevas")

        return saved

    # ─────────────────────────────────────────────
    # Correr todos los simbolos e intervalos activos
    # ─────────────────────────────────────────────

    async def run_all(self) -> dict:
        """Actualiza todas las combinaciones activas en collector_configs."""
        active_configs = await self.get_active_configs()
        results = {}

        for symbol, interval, broker, epic in active_configs:
            try:
                saved = await self.update(symbol, interval, broker, epic)
                results[f"{symbol}/{interval}"] = saved
            except Exception as e:
                logger.error(f"[{symbol}/{interval}] Error: {e}")
                results[f"{symbol}/{interval}"] = -1

        return results

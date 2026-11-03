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
from datetime import datetime, timezone
from typing import Optional
import os
from dotenv import load_dotenv
from collectors.bybit_http import get_json, BybitRateLimited

load_dotenv()


logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')

BYBIT_LIMIT  = 1000  # máximo permitido por /v5/market/kline
RUN_HTTP_TIMEOUT_S = 10.0    # timeout por petición en la corrida automática (antes 30 s, sin reintentos)
RATE_LIMIT_ABORT_AFTER = 3  # series seguidas limitadas por Bybit que cortan el resto de la corrida (C-02)
COLLECT_CONCURRENCY = 4  # series en paralelo (pool "live" = 10 conexiones compartidas con los ticks; Bybit sobra)
HISTORY_DAYS = 730  # 2 años (Bybit, sin limite de cuota)


class OhlcvCollector:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ─────────────────────────────────────────────
    # Leer configuracion activa desde DB
    # ─────────────────────────────────────────────

    async def get_active_configs(self) -> list[tuple[str, str, str]]:
        """
        (symbol, interval, broker) activos en collector_configs: la ÚNICA fuente de verdad (C-01). Sin series activas
        devuelve [] (no se descarga nada); si la base falla, la excepción sube y ese ciclo no corre (el vigilante avisa
        si los datos se atrasan). Antes caía a una lista fija del .env (SYMBOLS/INTERVALS) que nadie supervisaba.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT symbol, interval, broker
                FROM collector_configs
                WHERE active = true
                ORDER BY symbol, interval
                """
            )
        if not rows:
            logger.warning("[Collector] collector_configs sin series activas: no se descarga nada")
        return [(r['symbol'], r['interval'], r['broker']) for r in rows]

    # ─────────────────────────────────────────────
    # Fetch desde Bybit
    # ─────────────────────────────────────────────

    async def fetch_from_bybit(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
        client: Optional[httpx.AsyncClient] = None,
    ) -> list[dict]:
        """Obtiene velas OHLCV de Bybit entre start_ts y end_ts (unix segundos). client: reutilizar conexiones."""
        all_bars = []
        end_ms   = end_ts * 1000
        start_ms = start_ts * 1000

        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=30)
        try:
            while True:
                # Reintentos acotados (C-02): red, 429, 5xx y límite de tasa; 403 y errores de parámetros no
                payload = await get_json(client, f'{BYBIT_BASE_URL}/v5/market/kline', params={
                    'category': 'linear',
                    'symbol':   symbol,
                    'interval': interval,
                    'limit':    BYBIT_LIMIT,
                    'end':      end_ms,
                })
                bars = payload.get('result', {}).get('list', [])

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
        finally:
            if owns_client:
                await client.aclose()

        all_bars.reverse()
        return all_bars

    # ─────────────────────────────────────────────
    # Guardar en DB
    # ─────────────────────────────────────────────

    async def save_bars(self, bars: list[dict], broker: str = 'bybit') -> int:
        """
        UPSERT de velas en ohlcv_data. Devuelve las filas REALMENTE escritas.

        DO UPDATE es obligatorio: el collector descarga la vela en formación y la
        vuelve a descargar cada minuto hasta que cierra. Con DO NOTHING quedaba
        congelada con los OHLC de su primera descarga (~25 s de vida).
        El WHERE evita reescribir filas idénticas (WAL y bloat innecesarios).
        broker debe ser el real de collector_configs (no asumir 'bybit').
        """
        if not bars:
            return 0

        series: dict[tuple[str, str], list[dict]] = {}
        for b in bars:
            series.setdefault((b['symbol'], b['interval']), []).append(b)

        written = 0
        async with self.pool.acquire() as conn:
            for (symbol, interval), rows in series.items():
                status = await conn.execute(
                    """
                    INSERT INTO ohlcv_data (time, broker, symbol, interval, open, high, low, close, volume)
                    SELECT u.t, $2, $3, $4, u.o, u.h, u.l, u.c, u.v
                    FROM unnest($1::timestamptz[], $5::float8[], $6::float8[], $7::float8[],
                                $8::float8[], $9::float8[]) AS u(t, o, h, l, c, v)
                    ON CONFLICT (broker, symbol, interval, time) DO UPDATE
                    SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, volume = EXCLUDED.volume
                    WHERE (ohlcv_data.open, ohlcv_data.high, ohlcv_data.low, ohlcv_data.close, ohlcv_data.volume)
                          IS DISTINCT FROM
                          (EXCLUDED.open, EXCLUDED.high, EXCLUDED.low, EXCLUDED.close, EXCLUDED.volume)
                    """,
                    [r['time'] for r in rows], broker, symbol, interval,
                    [float(r['open']) for r in rows], [float(r['high']) for r in rows],
                    [float(r['low']) for r in rows], [float(r['close']) for r in rows],
                    [float(r['volume']) for r in rows],
                )
                written += int(status.split()[-1])
        return written

    # ─────────────────────────────────────────────
    # Último timestamp guardado
    # ─────────────────────────────────────────────

    async def get_last_timestamp(self, symbol: str, interval: str, broker: str = 'bybit') -> Optional[datetime]:
        """Última vela de ESTE broker (otras fuentes no cuentan: crearían huecos)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT time AS last_time
                FROM ohlcv_data
                WHERE broker = $1 AND symbol = $2 AND interval = $3
                ORDER BY time DESC LIMIT 1
                """,
                broker, symbol, interval
            )
            return row['last_time'] if row else None

    # ─────────────────────────────────────────────
    # Carga histórica inicial
    # ─────────────────────────────────────────────

    async def initial_load(self, symbol: str, interval: str, broker: str = 'bybit') -> int:
        if broker != 'bybit':
            raise ValueError(f"Broker no soportado por el collector: {broker}")
        last = await self.get_last_timestamp(symbol, interval, broker)
        if last:
            logger.info(f"[{symbol}/{interval}] Ya tiene datos hasta {last} — saltando carga inicial")
            return 0

        now = int(datetime.now(timezone.utc).timestamp())
        logger.info(f"[{symbol}/{interval}] Iniciando carga histórica de {HISTORY_DAYS} días...")
        bars = await self.fetch_from_bybit(symbol, interval, now - HISTORY_DAYS * 24 * 60 * 60, now)
        saved = await self.save_bars(bars, broker=broker)
        logger.info(f"[{symbol}/{interval}] Carga inicial: {saved} velas guardadas")
        return saved

    # ─────────────────────────────────────────────
    # Actualización continua
    # ─────────────────────────────────────────────

    async def update(self, symbol: str, interval: str, broker: str = 'bybit',
                     client: Optional[httpx.AsyncClient] = None) -> int:
        if broker != 'bybit':
            raise ValueError(f"Broker no soportado por el collector: {broker}")
        last = await self.get_last_timestamp(symbol, interval, broker)
        if not last:
            return await self.initial_load(symbol, interval, broker)

        start_ts = int(last.timestamp())
        end_ts   = int(datetime.now(timezone.utc).timestamp())
        if end_ts - start_ts < 60:
            return 0

        bars = await self.fetch_from_bybit(symbol, interval, start_ts, end_ts, client=client)
        saved = await self.save_bars(bars, broker=broker)
        if saved > 0:
            logger.debug(f"[{symbol}/{interval}] {saved} velas escritas (nuevas o actualizadas)")
        return saved

    # ─────────────────────────────────────────────
    # Correr todos los simbolos e intervalos activos
    # ─────────────────────────────────────────────

    async def run_all(self, errors: Optional[dict] = None) -> dict:
        """
        Actualiza todas las combinaciones activas en collector_configs: un cliente HTTP compartido y
        COLLECT_CONCURRENCY series a la vez. Resultado por serie: velas escritas, o -1 si falló
        (el detalle va a `errors` si se pasa un dict).
        """
        active_configs = await self.get_active_configs()
        results: dict = {}
        sem = asyncio.Semaphore(COLLECT_CONCURRENCY)
        # Corte por límite de tasa (C-02): un 403 o RATE_LIMIT_ABORT_AFTER series seguidas limitadas cortan el resto
        # de la corrida (el minuto siguiente vuelve a intentar) en vez de seguir golpeando a Bybit.
        state = {'limited_streak': 0, 'abort': None}
        self.last_abort_reason = None

        # Timeout corto: con 3 intentos el peor caso por petición queda en ~33 s, dentro de la corrida de 75 s (C-02)
        async with httpx.AsyncClient(timeout=RUN_HTTP_TIMEOUT_S) as client:
            async def one(symbol: str, interval: str, broker: str) -> None:
                key = f"{symbol}/{interval}"
                async with sem:
                    if state['abort']:
                        results[key] = -1
                        if errors is not None:
                            errors[key] = f"omitida: {state['abort']} (se reintenta el próximo minuto)"
                        return
                    try:
                        results[key] = await self.update(symbol, interval, broker, client=client)
                        state['limited_streak'] = 0
                    except BybitRateLimited as e:
                        state['limited_streak'] += 1
                        if e.blocked or state['limited_streak'] >= RATE_LIMIT_ABORT_AFTER:
                            state['abort'] = state['abort'] or f'límite de tasa de Bybit ({e})'[:200]
                        logger.error(f"[{key}] Bybit limita: {e}")
                        results[key] = -1
                        if errors is not None:
                            errors[key] = str(e)[:300]
                    except Exception as e:
                        logger.error(f"[{key}] Error: {e}")
                        results[key] = -1
                        if errors is not None:
                            errors[key] = str(e)[:300]

            await asyncio.gather(*(one(s, i, b) for s, i, b in active_configs))

        self.last_abort_reason = state['abort']
        if state['abort']:
            logger.error(f"[Collector] corrida cortada: {state['abort']}")
        return dict(sorted(results.items()))

"""
OHLCV Collector — Data Collector V2
Recolecta y almacena velas históricas y en tiempo real desde Bybit.
Los símbolos e intervalos activos se leen desde la tabla collector_configs (DB),
no desde variables de entorno. El admin los gestiona desde la UI de Laravel.
"""

import asyncio
import time
import asyncpg
import httpx
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional
import os
from dotenv import load_dotenv
from collectors.bybit_http import get_json, BybitRateLimited
from collectors.broker_resolver import INTERVAL_MINUTES, interval_delta

load_dotenv()


logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')

BYBIT_LIMIT  = 1000  # máximo permitido por /v5/market/kline
RUN_HTTP_TIMEOUT_S = 10.0    # timeout por petición en la corrida automática (antes 30 s, sin reintentos)
RATE_LIMIT_ABORT_AFTER = 3  # series seguidas limitadas por Bybit que cortan el resto de la corrida (C-02)
COLLECT_CONCURRENCY = 4  # series en paralelo (pool "live" = 10 conexiones compartidas con los ticks; Bybit sobra)
HISTORY_DAYS = 730  # 2 años (Bybit, sin limite de cuota)
# Puesta al día por ventanas (C-05): una serie nueva o atrasada avanza HACIA ADELANTE en ventanas de BYBIT_LIMIT velas,
# guardando cada una al llegar, con un presupuesto de tiempo por corrida; la corrida siguiente sigue desde la última vela.
CATCHUP_SERIES_BUDGET_S = 20.0   # tiempo máximo por serie atrasada en una corrida
RUN_DEADLINE_S = 60.0            # la corrida termina antes de los 75 s que Laravel espera


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _floor(t: datetime, step: timedelta) -> datetime:
    """Inicio de la vela que contiene t (alineado a UTC)."""
    return _EPOCH + ((t - _EPOCH) // step) * step


def bar_problem(b: dict) -> str | None:
    """
    Motivo por el que una vela NO se puede guardar (None = válida). Barrera única de escritura (C-04): la usan
    save_bars (descarga automática, carga inicial, reparación, auditoría, importación) y el backfill.
    Nunca se corrige un precio: una vela inválida no se guarda y la validación diaria marca el hueco.
    """
    try:
        o, h, lo, c, v = (float(b[k]) for k in ('open', 'high', 'low', 'close', 'volume'))
    except (KeyError, TypeError, ValueError):
        return 'campos faltantes o no numéricos'
    if not all(math.isfinite(x) for x in (o, h, lo, c, v)):
        return 'NaN o infinito'
    if lo <= 0:
        return 'precio <= 0'
    if lo > min(o, c) or h < max(o, c) or h < lo:
        return 'OHLC incoherente (low/high fuera de rango)'
    if v < 0:
        return 'volumen negativo'
    t, minutes = b.get('time'), INTERVAL_MINUTES.get(str(b.get('interval')))
    if not isinstance(t, datetime) or t.tzinfo is None:
        return 'hora sin zona horaria'
    if minutes and (t - _EPOCH) % timedelta(minutes=minutes):   # intervalo desconocido: sin chequeo de horario
        return 'hora fuera del horario del intervalo'
    return None


def valid_bar(b: dict) -> bool:
    return bar_problem(b) is None


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
        self.last_rejected = 0
        if not bars:
            return 0
        bad = [(b, bar_problem(b)) for b in bars]
        bad = [(b, why) for b, why in bad if why]
        if bad:   # C-04: ninguna vela inválida llega a ohlcv_data
            self.last_rejected = len(bad)
            b0, why0 = bad[0]
            logger.error(f"[Collector] {len(bad)} vela(s) inválida(s) NO guardadas ({b0.get('symbol')} {b0.get('interval')} "
                         f"{b0.get('time')}: {why0})")
            rejected = {id(b) for b, _ in bad}
            bars = [b for b in bars if id(b) not in rejected]
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

    async def fetch_window(self, client, symbol: str, interval: str, start: datetime, end: datetime) -> list[dict]:
        """Velas con start <= time <= end (máx. BYBIT_LIMIT), en orden ascendente."""
        payload = await get_json(client, f'{BYBIT_BASE_URL}/v5/market/kline', params={
            'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': BYBIT_LIMIT,
            'start': int(start.timestamp() * 1000), 'end': int(end.timestamp() * 1000)})
        bars = [{
            'time': datetime.fromtimestamp(int(b[0]) / 1000, tz=timezone.utc), 'symbol': symbol, 'interval': interval,
            'open': float(b[1]), 'high': float(b[2]), 'low': float(b[3]), 'close': float(b[4]), 'volume': float(b[5]),
        } for b in payload.get('result', {}).get('list', [])]
        bars.sort(key=lambda b: b['time'])
        return [b for b in bars if start <= b['time'] <= end]

    async def _first_listed(self, client, symbol: str, since: datetime, until: datetime) -> datetime | None:
        """Primer día con velas en Bybit entre since y until (una consulta diaria): salta el tiempo antes del listado."""
        days = await self.fetch_window(client, symbol, 'D', _floor(since, timedelta(days=1)), until)
        return days[0]['time'] if days else None

    async def catch_up(self, symbol: str, interval: str, broker: str, since: datetime, client,
                       deadline: float | None = None, clock=None) -> dict:
        """
        Avanza la serie desde `since` hasta la vela en curso, ventana a ventana, guardando cada una (C-05).
        Se detiene al llegar a hoy o a `deadline` (reloj monotónico); la próxima llamada sigue desde la última vela
        guardada, así una interrupción nunca deja el histórico a medias por el principio.
        """
        clock = clock or time.monotonic   # se resuelve en cada llamada (no al definir la función)
        step = interval_delta(interval)
        now_bar = _floor(datetime.now(timezone.utc), step)
        cur, saved, windows, jumped = _floor(since, step), 0, 0, False
        while cur <= now_bar:
            if deadline is not None and clock() >= deadline:
                break
            end = min(cur + step * (BYBIT_LIMIT - 1), now_bar)
            bars = await self.fetch_window(client, symbol, interval, cur, end)
            windows += 1
            if not bars:
                if not jumped:   # antes del listado de la moneda: salta al primer día con datos (una sola vez)
                    jumped = True
                    first = await self._first_listed(client, symbol, cur, now_bar)
                    if first is None:
                        break
                    cur = max(_floor(first, step), end + step)
                    continue
                cur = end + step
                continue
            saved += await self.save_bars(bars, broker=broker)
            cur = bars[-1]['time'] + step
        done = cur > now_bar
        behind = None if done else max(0.0, (now_bar - cur).total_seconds() / 3600)
        return dict(saved=saved, windows=windows, done=done, behind_hours=round(behind, 1) if behind else behind)

    async def initial_load(self, symbol: str, interval: str, broker: str = 'bybit', client=None,
                           deadline: float | None = None) -> int:
        """Carga inicial de una serie sin datos: HISTORY_DAYS hacia atrás, avanzando hacia hoy por ventanas (C-05)."""
        if broker != 'bybit':
            raise ValueError(f"Broker no soportado por el collector: {broker}")
        last = await self.get_last_timestamp(symbol, interval, broker)
        if last:
            logger.info(f"[{symbol}/{interval}] Ya tiene datos hasta {last} — saltando carga inicial")
            return 0
        since = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
        logger.info(f"[{symbol}/{interval}] Carga inicial desde {since:%Y-%m-%d} por ventanas")
        owns = client is None
        client = client or httpx.AsyncClient(timeout=30)
        try:
            r = await self.catch_up(symbol, interval, broker, since, client, deadline)
        finally:
            if owns:
                await client.aclose()
        self._note_catch_up(symbol, interval, r)
        logger.info(f"[{symbol}/{interval}] Carga inicial: {r['saved']} velas en {r['windows']} ventanas"
                    + ('' if r['done'] else f" (sigue en la próxima corrida; faltan ~{r['behind_hours']} h)"))
        return r['saved']

    def _note_catch_up(self, symbol: str, interval: str, r: dict) -> None:
        if not hasattr(self, 'catching_up'):
            self.catching_up = {}
        key = f"{symbol}/{interval}"
        if r['done']:
            self.catching_up.pop(key, None)
        else:
            self.catching_up[key] = dict(behind_hours=r['behind_hours'], saved=r['saved'], windows=r['windows'])

    async def update(self, symbol: str, interval: str, broker: str = 'bybit',
                     client: Optional[httpx.AsyncClient] = None, deadline: float | None = None,
                     last: Optional[datetime] = None) -> int:
        if broker != 'bybit':
            raise ValueError(f"Broker no soportado por el collector: {broker}")
        last = last or await self.get_last_timestamp(symbol, interval, broker)
        if not last:
            return await self.initial_load(symbol, interval, broker, client=client, deadline=deadline)

        step = interval_delta(interval)
        now = datetime.now(timezone.utc)
        if (now - last).total_seconds() < 60:
            return 0
        if now - last > step * (BYBIT_LIMIT - 1):   # atrasada: ponerse al día por ventanas, con presupuesto (C-05)
            owns = client is None
            client = client or httpx.AsyncClient(timeout=30)
            try:
                r = await self.catch_up(symbol, interval, broker, last, client, deadline)
            finally:
                if owns:
                    await client.aclose()
            self._note_catch_up(symbol, interval, r)
            return r['saved']

        # Caso normal (1-2 velas): una sola consulta, como siempre
        bars = await self.fetch_from_bybit(symbol, interval, int(last.timestamp()), int(now.timestamp()), client=client)
        saved = await self.save_bars(bars, broker=broker)
        if saved > 0:
            logger.debug(f"[{symbol}/{interval}] {saved} velas escritas (nuevas o actualizadas)")
        return saved

    async def run_all(self, errors: Optional[dict] = None) -> dict:
        """
        Actualiza todas las combinaciones activas en collector_configs: un cliente HTTP compartido y
        COLLECT_CONCURRENCY series a la vez. Resultado por serie: velas escritas, o -1 si falló
        (el detalle va a `errors` si se pasa un dict).
        """
        t0 = time.monotonic()
        run_deadline = t0 + RUN_DEADLINE_S
        active_configs = await self.get_active_configs()
        results: dict = {}
        sem = asyncio.Semaphore(COLLECT_CONCURRENCY)
        self.catching_up = {}
        # Prioridad (C-05): primero las series al día (1 consulta cada una); después, con el tiempo que sobra, las
        # nuevas o atrasadas, que avanzan por ventanas hasta CATCHUP_SERIES_BUDGET_S y siguen en la próxima corrida.
        lasts: dict = {}
        for s_, i_, b_ in active_configs:
            try:
                lasts[(s_, i_, b_)] = await self.get_last_timestamp(s_, i_, b_)
            except Exception:   # noqa: BLE001 - sin el dato, la serie va con las normales
                lasts[(s_, i_, b_)] = 'unknown'
        now_ = datetime.now(timezone.utc)

        def lagging(cfg) -> bool:
            last = lasts.get(cfg)
            if last == 'unknown':
                return False
            return last is None or now_ - last > interval_delta(cfg[1]) * (BYBIT_LIMIT - 1)
        normal = [c for c in active_configs if not lagging(c)]
        behind = [c for c in active_configs if lagging(c)]
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
                        cfg = (symbol, interval, broker)
                        last = lasts.get(cfg)
                        kw = dict(client=client, last=last if isinstance(last, datetime) else None)
                        if cfg in behind_set:
                            if time.monotonic() >= run_deadline:
                                results[key] = 0
                                self.catching_up.setdefault(key, dict(behind_hours=None, saved=0, windows=0,
                                                                      note='sin tiempo en esta corrida'))
                                return
                            kw['deadline'] = min(time.monotonic() + CATCHUP_SERIES_BUDGET_S, run_deadline)
                        results[key] = await self.update(symbol, interval, broker, **kw)
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

            behind_set = set(behind)
            await asyncio.gather(*(one(s, i, b) for s, i, b in normal))
            await asyncio.gather(*(one(s, i, b) for s, i, b in behind))

        self.last_abort_reason = state['abort']
        if state['abort']:
            logger.error(f"[Collector] corrida cortada: {state['abort']}")
        return dict(sorted(results.items()))

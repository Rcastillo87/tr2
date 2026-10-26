#!/usr/bin/env python3
"""
Backfill + auditoría de velas de Bybit (perpetuos lineales) en ohlcv_data.

Re-descarga desde la API oficial /v5/market/kline TODAS las velas CERRADAS de las
series activas (collector_configs, broker='bybit') en la ventana pedida y las
guarda con UPSERT (OhlcvCollector.save_bars): completa huecos y repara velas
dañadas; las velas correctas no se reescriben. Idempotente: se puede repetir o
reanudar con --since sin efectos secundarios.

Uso (desde python-engine/):
    venv/bin/python -m cli.backfill_bybit --audit                 # solo reporte, sin API ni escrituras
    venv/bin/python -m cli.backfill_bybit --dry-run               # plan: llamadas y duración estimadas
    venv/bin/python -m cli.backfill_bybit                         # backfill 730 días, todas las series
    venv/bin/python -m cli.backfill_bybit --only BTCUSDT --intervals 60,1
    venv/bin/python -m cli.backfill_bybit --since 2026-06-01      # solo un tramo
    venv/bin/python -m cli.backfill_bybit --gaps --intervals 1    # solo los huecos reales de la DB
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

from collectors.broker_resolver import interval_delta  # noqa: E402
from collectors.ohlcv_collector import BYBIT_BASE_URL, BYBIT_LIMIT, OhlcvCollector  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('backfill_bybit')
logging.getLogger('httpx').setLevel(logging.WARNING)  # sin una línea por request en el journal

DSN = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
       f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
BROKER = 'bybit'
MAX_RETRIES = 6
RATE_LIMIT_RETCODES = {10006, 10018}  # "too many visits" / IP limit


@dataclass
class SeriesResult:
    symbol: str
    interval: str
    first_available: datetime | None = None
    windows: int = 0
    received: int = 0
    written: int = 0
    rejected: int = 0
    errors: list[str] = field(default_factory=list)


class RateLimiter:
    """Espaciado mínimo entre llamadas (proceso secuencial; sin ráfagas)."""

    def __init__(self, per_second: float):
        self.min_gap = 1.0 / per_second
        self._last = 0.0

    async def wait(self) -> None:
        delay = self._last + self.min_gap - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        self._last = time.monotonic()


def floor_to_interval(dt: datetime, interval: str) -> datetime:
    """Inicio de la vela que contiene dt (alineado a UTC)."""
    step = interval_delta(interval)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return epoch + ((dt - epoch) // step) * step


def valid_bar(b: dict) -> bool:
    return (b['low'] > 0 and b['low'] <= min(b['open'], b['close'])
            and b['high'] >= max(b['open'], b['close']) and b['volume'] >= 0)


async def fetch_window(client: httpx.AsyncClient, limiter: RateLimiter, symbol: str, interval: str,
                       start: datetime, end: datetime) -> list[dict]:
    """Velas con start <= time <= end (máx. BYBIT_LIMIT), en orden ascendente."""
    params = {'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': BYBIT_LIMIT,
              'start': int(start.timestamp() * 1000), 'end': int(end.timestamp() * 1000)}
    for attempt in range(1, MAX_RETRIES + 1):
        await limiter.wait()
        try:
            r = await client.get(f'{BYBIT_BASE_URL}/v5/market/kline', params=params)
            if r.status_code in (403, 429):
                raise RuntimeError(f"HTTP {r.status_code} (límite de tasa)")
            r.raise_for_status()
            payload = r.json()
            if payload.get('retCode') in RATE_LIMIT_RETCODES:
                raise RuntimeError(f"retCode {payload['retCode']} (límite de tasa)")
            if payload.get('retCode') != 0:
                raise ValueError(f"retCode {payload.get('retCode')}: {payload.get('retMsg')}")
            rows = payload.get('result', {}).get('list', [])
            bars = [{
                'time': datetime.fromtimestamp(int(x[0]) / 1000, tz=timezone.utc),
                'symbol': symbol, 'interval': interval,
                'open': float(x[1]), 'high': float(x[2]), 'low': float(x[3]),
                'close': float(x[4]), 'volume': float(x[5]),
            } for x in rows]
            bars.sort(key=lambda b: b['time'])
            return [b for b in bars if start <= b['time'] <= end]
        except ValueError:
            raise  # error de parámetros: reintentar no sirve
        except (httpx.HTTPError, RuntimeError) as e:
            backoff = min(60, 2 ** attempt)
            logger.warning(f"{symbol} {interval} intento {attempt}/{MAX_RETRIES}: {e}. Reintento en {backoff}s")
            await asyncio.sleep(backoff)
    raise RuntimeError(f"{symbol} {interval}: agotados {MAX_RETRIES} reintentos")


async def first_available_day(client, limiter, symbol: str, since: datetime, until: datetime) -> datetime | None:
    """Primer día con velas en [since, until] (una llamada diaria; la ventana es < 1000 días)."""
    days = await fetch_window(client, limiter, symbol, 'D', floor_to_interval(since, 'D'), until)
    return days[0]['time'] if days else None


async def active_series(pool, only: set[str] | None, intervals: set[str] | None) -> list[tuple[str, str]]:
    rows = await pool.fetch(
        "SELECT symbol, interval FROM collector_configs WHERE active AND broker = $1 ORDER BY symbol, interval",
        BROKER)
    out = [(r['symbol'], r['interval']) for r in rows
           if (not only or r['symbol'] in only) and (not intervals or r['interval'] in intervals)]
    # 1m al final: es lo más pesado y lo demás queda listo antes
    return sorted(out, key=lambda s: (s[1] == '1', s[0], interval_delta(s[1])))


async def backfill_series(pool, collector: OhlcvCollector, client, limiter, symbol: str, interval: str,
                          since: datetime, until: datetime, dry_run: bool) -> SeriesResult:
    res = SeriesResult(symbol, interval)
    step = interval_delta(interval)
    try:
        listed = await first_available_day(client, limiter, symbol, since, until)
    except Exception as e:
        res.errors.append(f"no se pudo determinar el inicio de la serie: {e}")
        return res
    if listed is None:
        res.errors.append('sin velas en Bybit para la ventana')
        return res
    res.first_available = max(floor_to_interval(since, interval), listed)

    total_windows = max(1, int((until - res.first_available) / (step * BYBIT_LIMIT)) + 1)
    if dry_run:
        res.windows = total_windows
        return res
    await fill_range(collector, client, limiter, res, res.first_available, until, total_windows)
    return res


async def fill_range(collector: OhlcvCollector, client, limiter, res: SeriesResult,
                     start: datetime, end: datetime, total_windows: int | None = None) -> None:
    """Descarga [start, end] en ventanas de BYBIT_LIMIT velas. Las ventanas fallidas o vacías
    se reintentan una vez al final; si siguen fallando quedan en res.errors (nunca en silencio)."""
    symbol, interval = res.symbol, res.interval
    step = interval_delta(interval)

    async def one(w_start: datetime, w_end: datetime) -> bool:
        try:
            bars = await fetch_window(client, limiter, symbol, interval, w_start, w_end)
        except Exception as e:
            logger.warning(f"{symbol} {interval} ventana {w_start:%Y-%m-%d %H:%M}: {e}")
            return False
        if not bars:
            logger.warning(f"{symbol} {interval} ventana {w_start:%Y-%m-%d %H:%M} vacía")
            return False
        good = [b for b in bars if valid_bar(b)]
        res.rejected += len(bars) - len(good)
        res.received += len(good)
        res.written += await collector.save_bars(good, broker=BROKER)
        res.windows += 1
        return True

    failed: list[tuple[datetime, datetime]] = []
    cursor, last_log = start, time.monotonic()
    while cursor <= end:
        w_end = min(end, cursor + step * (BYBIT_LIMIT - 1))
        if not await one(cursor, w_end):
            failed.append((cursor, w_end))
        cursor = w_end + step
        if time.monotonic() - last_log > 30:
            logger.info(f"{symbol} {interval}: {res.windows}/{total_windows or '?'} ventanas, "
                        f"recibidas={res.received} escritas={res.written} (hasta {w_end:%Y-%m-%d %H:%M})")
            last_log = time.monotonic()

    if failed:  # 2ª pasada tras una pausa: los fallos de red/tasa suelen ser transitorios
        logger.warning(f"{symbol} {interval}: reintentando {len(failed)} ventana(s) fallida(s) o vacía(s)")
        await asyncio.sleep(10)
        for w_start, w_end in failed:
            if not await one(w_start, w_end):
                res.errors.append(f"{w_start:%Y-%m-%d %H:%M} → {w_end:%Y-%m-%d %H:%M}: sin datos tras 2 pasadas")


async def find_gaps(pool, symbol: str, interval: str, since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
    """Tramos faltantes [desde, hasta] entre velas consecutivas de la DB."""
    step = interval_delta(interval)
    rows = await pool.fetch(
        """
        SELECT prev + $5 AS gap_start, time - $5 AS gap_end
        FROM (SELECT time, lag(time) OVER (ORDER BY time) AS prev
              FROM ohlcv_data WHERE broker = $1 AND symbol = $2 AND interval = $3 AND time >= $4) s
        WHERE prev IS NOT NULL AND time - prev > $5 AND time <= $6
        ORDER BY prev
        """,
        BROKER, symbol, interval, since, step, until + step)
    return [(r['gap_start'], r['gap_end']) for r in rows]


async def audit(pool, series: list[tuple[str, str]], since: datetime, now: datetime) -> int:
    """Cobertura y huecos por serie dentro de [since, última vela cerrada]. Devuelve series incompletas."""
    print(f"\nAUDITORÍA bybit  desde {since:%Y-%m-%d} hasta la última vela cerrada de cada serie")
    print(f"{'serie':16} {'desde':16} {'hasta':16} {'velas':>9} {'esperadas':>9} {'compl%':>7} {'huecos':>7} {'mayor hueco':>12}")
    incomplete = 0
    for symbol, interval in series:
        step = interval_delta(interval)
        until = floor_to_interval(now, interval) - step
        row = await pool.fetchrow(
            """
            WITH s AS (
                SELECT time, time - lag(time) OVER (ORDER BY time) AS gap
                FROM ohlcv_data
                WHERE broker = $1 AND symbol = $2 AND interval = $3 AND time >= $4 AND time <= $5
            )
            SELECT min(time) AS first_bar, max(time) AS last_bar, count(*) AS bars,
                   count(*) FILTER (WHERE gap > $6) AS gaps, max(gap) AS max_gap
            FROM s
            """,
            BROKER, symbol, interval, since, until, step)
        if not row['bars']:
            print(f"{symbol + ' ' + interval:16} SIN DATOS")
            incomplete += 1
            continue
        expected = int((row['last_bar'] - row['first_bar']) / step) + 1
        pct = row['bars'] / expected * 100
        max_gap = row['max_gap'] if row['max_gap'] and row['max_gap'] > step else timedelta(0)
        late_days = max(0.0, (row['first_bar'] - since).total_seconds() / 86400 - 1)
        bad = pct < 99.9 or row['gaps'] > 0 or row['last_bar'] < until - step or late_days > 0
        incomplete += bad
        note = f"  <-- revisar{f' (faltan {late_days:.0f} días al inicio; normal si la moneda se listó después)' if late_days > 0 else ''}" if bad else ''
        print(f"{symbol + ' ' + interval:16} {row['first_bar']:%Y-%m-%d %H:%M} {row['last_bar']:%Y-%m-%d %H:%M} "
              f"{row['bars']:>9} {expected:>9} {pct:>6.2f}% {row['gaps']:>7} {str(max_gap):>12}{note}")
    print(f"\nSeries incompletas: {incomplete}/{len(series)}")
    return incomplete


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--days', type=int, default=730, help='ventana hacia atrás (default 730 = 2 años)')
    p.add_argument('--since', help='inicio explícito YYYY-MM-DD (anula --days)')
    p.add_argument('--only', help='símbolos separados por coma')
    p.add_argument('--intervals', help="intervalos separados por coma (ej. '1,60')")
    p.add_argument('--rate', type=float, default=8.0, help='llamadas por segundo (default 8)')
    p.add_argument('--dry-run', action='store_true', help='solo planifica: llamadas y duración, sin escribir')
    p.add_argument('--audit', action='store_true', help='solo auditoría de la DB, sin llamar a la API')
    p.add_argument('--gaps', action='store_true', help='descarga solo los huecos reales de la DB')
    args = p.parse_args()

    now = datetime.now(timezone.utc)
    since = (datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc) if args.since
             else now - timedelta(days=args.days))
    only = {s.strip().upper() for s in args.only.split(',')} if args.only else None
    intervals = {s.strip() for s in args.intervals.split(',')} if args.intervals else None

    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=2)
    try:
        series = await active_series(pool, only, intervals)
        if not series:
            logger.error('No hay series activas de bybit que coincidan con el filtro')
            return 1

        if args.audit:
            incomplete = await audit(pool, series, since, now)
            return 1 if incomplete else 0

        collector = OhlcvCollector(pool)
        limiter = RateLimiter(args.rate)
        results: list[SeriesResult] = []
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=30) as client:
            for symbol, interval in series:
                until = floor_to_interval(now, interval) - interval_delta(interval)  # última vela cerrada
                if args.gaps:
                    gaps = await find_gaps(pool, symbol, interval, since, until)
                    res = SeriesResult(symbol, interval)
                    logger.info(f"=== {symbol} {interval}: {len(gaps)} hueco(s)")
                    for g_start, g_end in gaps:
                        res.first_available = res.first_available or g_start
                        if not args.dry_run:
                            await fill_range(collector, client, limiter, res, g_start, g_end)
                    results.append(res)
                    continue
                logger.info(f"=== {symbol} {interval}  {since:%Y-%m-%d} → {until:%Y-%m-%d %H:%M}")
                results.append(await backfill_series(pool, collector, client, limiter, symbol, interval,
                                                     since, until, args.dry_run))

        print(f"\n{'serie':16} {'disponible desde':17} {'ventanas':>8} {'recibidas':>10} {'escritas':>9} {'rechaz.':>7} errores")
        for r in results:
            first = f"{r.first_available:%Y-%m-%d}" if r.first_available else '-'
            print(f"{r.symbol + ' ' + r.interval:16} {first:17} {r.windows:>8} {r.received:>10} "
                  f"{r.written:>9} {r.rejected:>7} {len(r.errors)}")
            for e in r.errors[:3]:
                print(f"{'':18}{e}")
        calls = sum(r.windows for r in results) + len(results)
        if args.dry_run:
            print(f"\nPLAN: {calls} llamadas a la API ≈ {calls / args.rate / 60:.1f} min a {args.rate:g} llamadas/s "
                  f"(+ escritura en DB). Nada fue escrito.")
        else:
            print(f"\nTOTAL: {sum(r.written for r in results)} velas escritas en {(time.monotonic() - t0) / 60:.1f} min; "
                  f"series con errores: {sum(1 for r in results if r.errors)}")
        return 1 if any(r.errors for r in results) and not args.dry_run else 0
    finally:
        await pool.close()


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

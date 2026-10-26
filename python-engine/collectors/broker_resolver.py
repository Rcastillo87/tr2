"""
Selección de la fuente de velas (broker) dentro de ohlcv_data.

Dos necesidades distintas que NO deben compartir criterio:

- En vivo (paper, real, régimen): la fuente con la vela MÁS RECIENTE del
  intervalo que se opera. Si esa vela está desactualizada se devuelve None y el
  llamador no opera: es preferible perder una entrada a operar sobre datos viejos.
- Backtest: la fuente con MAYOR COBERTURA del rango pedido. Ante empate se
  prefiere el mercado que se opera en vivo (Bybit, perpetuos) para que backtest
  y vivo vean las mismas velas.
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import asyncpg

logger = logging.getLogger(__name__)

INTERVAL_MINUTES = {'1': 1, '5': 5, '15': 15, '60': 60, '120': 120, '240': 240, 'D': 1440}

# Antigüedad máxima tolerada de la última vela, medida en intervalos.
# H1 -> 3 h, 15m -> 45 min, H2 -> 6 h. La vela en formación cuenta como reciente.
LIVE_MAX_LAG_BARS = 3

# Mercado operado en vivo: desempata la selección de fuente del backtest.
LIVE_VENUE_BROKER = 'bybit'
# Dos fuentes con coberturas que difieren menos de esto se consideran empatadas.
COVERAGE_TIE_RATIO = 0.005
# Brokers de mercados con horario (sin velas en fin de semana): no se evalúan huecos.
# Vacío desde que se quitó IG; añadir aquí el broker de forex/oro que se integre.
SESSION_MARKET_BROKERS: frozenset[str] = frozenset()
# Completitud mínima (velas presentes / esperadas) para no reportar huecos.
MIN_COMPLETENESS = 0.98

_BROKER_CACHE_TTL_S = 600
_broker_cache: tuple[float, list[str]] = (0.0, [])


def interval_delta(interval: str) -> timedelta:
    try:
        return timedelta(minutes=INTERVAL_MINUTES[str(interval)])
    except KeyError:
        raise ValueError(f"Intervalo desconocido: {interval!r}") from None


def closed_bars(df, interval: str, now: datetime | None = None):
    """Solo velas cerradas (time + intervalo <= ahora), guarde o no el collector la vela en formación."""
    if df is None or len(df) == 0:
        return df
    import pandas as pd
    now = now or datetime.now(timezone.utc)
    times = pd.to_datetime(df['time'], utc=True)
    return df[(times + interval_delta(interval)) <= now].reset_index(drop=True)


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


async def list_brokers(pool: asyncpg.Pool) -> list[str]:
    """Brokers presentes en ohlcv_data (loose index scan, cacheado 10 min)."""
    global _broker_cache
    cached_at, brokers = _broker_cache
    if brokers and time.monotonic() - cached_at < _BROKER_CACHE_TTL_S:
        return brokers

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH RECURSIVE b(broker) AS (
                SELECT min(broker) FROM ohlcv_data
                UNION ALL
                SELECT (SELECT min(o.broker) FROM ohlcv_data o WHERE o.broker > b.broker)
                FROM b WHERE b.broker IS NOT NULL
            )
            SELECT broker FROM b WHERE broker IS NOT NULL
            """
        )
    brokers = [r['broker'] for r in rows]
    _broker_cache = (time.monotonic(), brokers)
    return brokers


# ─────────────────────────────── En vivo ───────────────────────────────

async def resolve_live_broker(pool: asyncpg.Pool, symbol: str, interval: str,
                              *, require_fresh: bool = True) -> str | None:
    """
    Fuente con la vela más reciente de (symbol, interval).

    Devuelve None (y registra ERROR) si no hay datos o si, con require_fresh,
    la última vela supera LIVE_MAX_LAG_BARS intervalos de antigüedad.
    """
    step = interval_delta(interval)
    brokers = await list_brokers(pool)
    if not brokers:
        logger.error("[DATA] ohlcv_data no contiene ningún broker")
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.broker,
                   (SELECT o.time FROM ohlcv_data o
                     WHERE o.broker = b.broker AND o.symbol = $2 AND o.interval = $3
                     ORDER BY o.time DESC LIMIT 1) AS last_bar
            FROM unnest($1::text[]) AS b(broker)
            """,
            brokers, symbol, str(interval),
        )

    candidates = [(r['broker'], _utc(r['last_bar'])) for r in rows if r['last_bar'] is not None]
    if not candidates:
        logger.error(f"[DATA] {symbol} {interval}: sin velas en ninguna fuente")
        return None

    broker, last_bar = max(candidates, key=lambda c: c[1])

    if require_fresh:
        lag = datetime.now(timezone.utc) - last_bar
        if lag > step * LIVE_MAX_LAG_BARS:
            logger.error(
                f"[DATA] {symbol} {interval}: última vela {last_bar:%Y-%m-%d %H:%M} UTC "
                f"(fuente {broker}, retraso {lag}). Sin nuevas entradas hasta que el "
                f"collector se ponga al día."
            )
            return None

    return broker


# ─────────────────────────────── Backtest ───────────────────────────────

@dataclass(frozen=True)
class SourceCoverage:
    """Cobertura real de una fuente para (symbol, interval) dentro de [start, end)."""
    broker: str
    symbol: str
    interval: str
    start: datetime | None        # rango pedido (None = sin límite)
    end: datetime | None
    first_bar: datetime
    last_bar: datetime
    bars: int

    @property
    def expected_bars(self) -> int:
        """Velas esperadas entre la primera y la última presentes (mide huecos internos;
        el inicio tardío y el final corto se reportan aparte en problems())."""
        step = interval_delta(self.interval)
        return max(1, int((self.last_bar + step - self.first_bar) / step))

    @property
    def completeness(self) -> float:
        return min(1.0, self.bars / self.expected_bars)

    def covers(self, start: datetime, end: datetime) -> bool:
        """True si la fuente cubre [start, end) completo y sin huecos relevantes."""
        step = interval_delta(self.interval)
        complete = self.broker in SESSION_MARKET_BROKERS or self.completeness >= MIN_COMPLETENESS
        return self.first_bar <= start + step and self.last_bar >= end - 2 * step and complete

    def problems(self) -> list[str]:
        """Diferencias entre lo pedido y lo que realmente hay (texto para el log del usuario)."""
        step = interval_delta(self.interval)
        label = f"{self.symbol} {self.interval}"
        out = []
        if self.start and self.first_bar > self.start + step:
            days = (self.first_bar - self.start).total_seconds() / 86400
            out.append(f"Aviso: {label} ({self.broker}) empieza el {self.first_bar:%Y-%m-%d %H:%M} UTC; "
                       f"pediste desde {self.start:%Y-%m-%d}. Faltan {days:.1f} días al inicio.")
        if self.end and self.last_bar < self.end - 2 * step:
            days = (self.end - self.last_bar).total_seconds() / 86400
            out.append(f"Aviso: {label} ({self.broker}) termina el {self.last_bar:%Y-%m-%d %H:%M} UTC; "
                       f"faltan {days:.1f} días al final del rango pedido.")
        if self.broker not in SESSION_MARKET_BROKERS and self.completeness < MIN_COMPLETENESS:
            missing = self.expected_bars - self.bars
            out.append(f"Aviso: {label} ({self.broker}) tiene {missing} velas faltantes "
                       f"({(1 - self.completeness) * 100:.1f}%) dentro de los datos disponibles: huecos.")
        return out

    def as_dict(self) -> dict:
        return {
            "broker": self.broker, "interval": self.interval, "bars": self.bars,
            "expected_bars": self.expected_bars, "completeness": round(self.completeness, 4),
            "first_bar": self.first_bar.isoformat(), "last_bar": self.last_bar.isoformat(),
        }


async def coverage_by_broker(pool: asyncpg.Pool, symbol: str, interval: str,
                             start: datetime | None = None, end: datetime | None = None) -> list[SourceCoverage]:
    """Cobertura de cada fuente disponible para (symbol, interval) en [start, end)."""
    start, end = _utc(start), _utc(end)
    query = """
        SELECT broker, min(time) AS first_bar, max(time) AS last_bar, count(*) AS bars
        FROM ohlcv_data
        WHERE symbol = $1 AND interval = $2
    """
    args: list = [symbol, str(interval)]
    if start is not None:
        args.append(start)
        query += f" AND time >= ${len(args)}"
    if end is not None:
        args.append(end)
        query += f" AND time < ${len(args)}"
    query += " GROUP BY broker"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)

    return [
        SourceCoverage(r['broker'], symbol, str(interval), start, end,
                       _utc(r['first_bar']), _utc(r['last_bar']), int(r['bars']))
        for r in rows if r['bars']
    ]


def pick_best_source(candidates: list[SourceCoverage]) -> SourceCoverage | None:
    """Mayor cobertura; empate (< COVERAGE_TIE_RATIO) -> el mercado operado en vivo."""
    if not candidates:
        return None
    best_bars = max(c.bars for c in candidates)
    tied = [c for c in candidates if c.bars >= best_bars * (1 - COVERAGE_TIE_RATIO)]
    return next((c for c in tied if c.broker == LIVE_VENUE_BROKER), max(tied, key=lambda c: c.bars))


async def resolve_backtest_source(pool: asyncpg.Pool, symbol: str, interval: str,
                                  start: datetime | None, end: datetime | None) -> SourceCoverage | None:
    return pick_best_source(await coverage_by_broker(pool, symbol, interval, start, end))

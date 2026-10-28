"""
Funding de Bybit (perpetuos lineales USDT) para el backtest.

El funding se toma SIEMPRE de Bybit (donde se opera), aunque las velas del backtest vengan de Binance Vision.
Se descarga a demanda solo lo que falta (los bordes del tramo ya cubierto) y queda en la DB:
  funding_rates     una fila por liquidación (rate > 0: el long paga al short)
  funding_coverage  tramo ya descargado por símbolo (entre liquidaciones no hay filas: sin esto no se
                    distingue "no hubo funding" de "no se descargó")
El tramo cubierto solo se extiende de forma contigua: un tramo descargado sin contacto con el cubierto
guarda sus filas pero no se marca como cubierto (se vuelve a pedir el borde la próxima vez).
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np

logger = logging.getLogger(__name__)

BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
PAGE_LIMIT = 200                    # máximo de /v5/market/funding/history
RETRIES = 3
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
RETRY_CODES = {10006, 10016, 10018}  # límite de peticiones / error interno de Bybit: reintentar
SETTLE_LAG = timedelta(minutes=5)    # una liquidación recién hecha puede tardar en publicarse
FAIL_COOLDOWN = timedelta(minutes=10)  # tras un fallo de Bybit no se reintenta el símbolo en este proceso
_FAILED: dict[str, datetime] = {}


class FundingUnavailable(Exception):
    pass


@dataclass
class FundingData:
    symbol: str
    times: np.ndarray            # datetime64[ns] UTC sin tz, ordenado
    rates: np.ndarray            # float64
    covered_from: datetime | None
    covered_to: datetime | None

    def as_dict(self) -> dict:
        return {
            'source': 'bybit',
            'settlements': int(len(self.times)),
            'covered_from': self.covered_from.isoformat() if self.covered_from else None,
            'covered_to': self.covered_to.isoformat() if self.covered_to else None,
        }


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _ms(dt: datetime) -> int:
    return int(_utc(dt).timestamp() * 1000)


def _floor_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _has_settlement(lo: datetime, hi: datetime, lo_inclusive: bool) -> bool:
    """¿Puede haber una liquidación en el tramo? Caen en horas en punto (cada 1, 4 u 8 h)."""
    return hi >= lo and (_floor_hour(hi) > lo or (lo_inclusive and _floor_hour(lo) == lo))


def _to_download(start: datetime, end: datetime, cov_from: datetime | None, cov_to: datetime | None) -> list[tuple]:
    """Tramos a descargar. Siempre pegados al tramo cubierto, para que este crezca sin huecos."""
    if cov_from is None:
        return [(start, end)] if _has_settlement(start, end, True) else []
    parts = []
    if start < cov_from and _has_settlement(start, cov_from, True):
        parts.append((start, cov_from))
    if end > cov_to and _has_settlement(cov_to, end, False):
        parts.append((cov_to, end))
    return parts


def _gaps(start: datetime, end: datetime, cov_from: datetime | None, cov_to: datetime | None) -> list[tuple]:
    """Partes de [start, end] sin funding descargado (para el aviso)."""
    if cov_from is None or cov_to < start or cov_from > end:
        return [(start, end)] if _has_settlement(start, end, True) else []
    parts = []
    if start < cov_from and _has_settlement(start, cov_from, True):
        parts.append((start, cov_from))
    if end > cov_to and _has_settlement(cov_to, end, False):
        parts.append((cov_to, end))
    return parts


async def _get(client: httpx.AsyncClient, params: dict) -> dict:
    delay = 1.0
    for attempt in range(1, RETRIES + 1):
        try:
            r = await client.get(f"{BYBIT_BASE_URL}/v5/market/funding/history", params=params)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            data = r.json()
            code = data.get('retCode')
            if code == 0:
                return data
            if code not in RETRY_CODES:
                raise FundingUnavailable(f"Bybit retCode {code}: {data.get('retMsg')}")
            last = f"retCode {code}"
        except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as e:
            last = str(e) or type(e).__name__
        if attempt < RETRIES:
            await asyncio.sleep(delay)
            delay *= 2
    raise FundingUnavailable(f"Bybit sin respuesta tras {RETRIES} intentos ({last})")


async def fetch_bybit_funding(client: httpx.AsyncClient, symbol: str, start: datetime, end: datetime) -> list[tuple]:
    """Liquidaciones de Bybit en [start, end], paginando hacia atrás (vale para intervalos de 8 h, 4 h o 1 h)."""
    start_ms, end_ms = _ms(start), _ms(end)
    out: dict[int, float] = {}
    while end_ms >= start_ms:
        data = await _get(client, {'category': 'linear', 'symbol': symbol, 'startTime': start_ms,
                                   'endTime': end_ms, 'limit': PAGE_LIMIT})
        rows = (data.get('result') or {}).get('list') or []
        if not rows:
            break
        stamps = []
        for row in rows:
            ts = int(row['fundingRateTimestamp'])
            stamps.append(ts)
            if start_ms <= ts <= end_ms:
                out[ts] = float(row['fundingRate'])
        oldest = min(stamps)
        if len(rows) < PAGE_LIMIT or oldest <= start_ms:
            break
        end_ms = oldest - 1
    return [(datetime.fromtimestamp(ts / 1000, tz=timezone.utc), rate) for ts, rate in sorted(out.items())]


async def _coverage(pool, symbol: str) -> tuple:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT covered_from, covered_to FROM funding_coverage WHERE symbol = $1", symbol)
    return (_utc(row['covered_from']), _utc(row['covered_to'])) if row else (None, None)


async def _store(pool, symbol: str, lo: datetime, hi: datetime, rows: list[tuple]) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            if rows:
                await conn.executemany(
                    "INSERT INTO funding_rates (symbol, funding_time, rate) VALUES ($1, $2, $3)"
                    " ON CONFLICT (symbol, funding_time) DO UPDATE SET rate = EXCLUDED.rate",
                    [(symbol, t, r) for t, r in rows])
            # solo extiende el tramo cubierto si el nuevo lo toca (nunca deja huecos marcados como cubiertos)
            await conn.execute(
                "INSERT INTO funding_coverage (symbol, covered_from, covered_to) VALUES ($1, $2, $3)"
                " ON CONFLICT (symbol) DO UPDATE SET"
                "   covered_from = LEAST(funding_coverage.covered_from, EXCLUDED.covered_from),"
                "   covered_to = GREATEST(funding_coverage.covered_to, EXCLUDED.covered_to), updated_at = now()"
                " WHERE EXCLUDED.covered_from <= funding_coverage.covered_to"
                "   AND EXCLUDED.covered_to >= funding_coverage.covered_from",
                symbol, lo, hi)


async def load_funding(pool, symbol: str, start: datetime, end: datetime,
                       client: httpx.AsyncClient | None = None, now: datetime | None = None) -> tuple:
    """
    (FundingData, avisos) de [start, end]. Descarga de Bybit lo que falte. Si Bybit no responde, usa lo que
    ya hay en la DB y avisa qué tramo queda sin funding (ese tramo es optimista).
    """
    start, end = _utc(start), _utc(end)
    settled = _utc(now or datetime.now(timezone.utc)) - SETTLE_LAG
    hi_req = min(end, settled)
    warnings: list[str] = []

    cov_from, cov_to = await _coverage(pool, symbol)
    missing = _to_download(start, hi_req, cov_from, cov_to) if hi_req > start else []
    failed_at = _FAILED.get(symbol)
    if missing and failed_at and datetime.now(timezone.utc) - failed_at < FAIL_COOLDOWN:
        warnings.append(f"Aviso: funding de {symbol}: Bybit falló hace menos de "
                        f"{FAIL_COOLDOWN.seconds // 60} min; se usa solo lo guardado.")
        missing = []
    if missing:
        own = client is None
        client = client or httpx.AsyncClient(timeout=TIMEOUT)
        try:
            for lo, hi in missing:
                try:
                    rows = await fetch_bybit_funding(client, symbol, lo, hi)
                except FundingUnavailable as e:
                    _FAILED[symbol] = datetime.now(timezone.utc)
                    logger.warning(f"[FUNDING] {symbol} {lo:%Y-%m-%d %H:%M} → {hi:%Y-%m-%d %H:%M}: {e}")
                    warnings.append(f"Aviso: funding de {symbol} no descargado de Bybit ({e}).")
                    continue
                await _store(pool, symbol, lo, hi, rows)
                _FAILED.pop(symbol, None)
                logger.info(f"[FUNDING] {symbol}: {len(rows)} liquidaciones {lo:%Y-%m-%d %H:%M} → {hi:%Y-%m-%d %H:%M}")
        finally:
            if own:
                await client.aclose()
        cov_from, cov_to = await _coverage(pool, symbol)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT funding_time, rate FROM funding_rates WHERE symbol = $1"
            " AND funding_time >= $2 AND funding_time <= $3 ORDER BY funding_time", symbol, start, end)
    times = np.array([_utc(r['funding_time']).replace(tzinfo=None) for r in rows], dtype='datetime64[ns]')
    rates = np.array([float(r['rate']) for r in rows], dtype=float)

    gaps = _gaps(start, hi_req, cov_from, cov_to) if hi_req > start else []
    if gaps:
        txt = ', '.join(f"{lo:%Y-%m-%d %H:%M} → {hi:%Y-%m-%d %H:%M}" for lo, hi in gaps)
        warnings.append(f"Aviso: sin funding de Bybit para {symbol} en {txt} UTC: "
                        f"los trades en ese tramo no descuentan funding (optimista).")
    return FundingData(symbol, times, rates, cov_from, cov_to), warnings


async def _backfill(symbols: list[str], since: datetime) -> int:
    """Precarga el funding de los símbolos (los del collector si no se indican) desde `since` hasta ahora."""
    from pathlib import Path

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    from db import close_pools, get_pool   # después del .env: db.py arma el DSN al importarse

    pool = await get_pool('backtest')
    errors = 0
    try:
        if not symbols:
            async with pool.acquire() as conn:
                symbols = [r['symbol'] for r in await conn.fetch(
                    "SELECT DISTINCT symbol FROM collector_configs ORDER BY symbol")]
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for sym in symbols:
                t0 = datetime.now(timezone.utc)
                f, w = await load_funding(pool, sym, since, datetime.now(timezone.utc), client=client)
                secs = (datetime.now(timezone.utc) - t0).total_seconds()
                mean = float(np.mean(f.rates)) * 100 if len(f.rates) else 0.0
                print(f"{sym:<10} {len(f.times):>5} liquidaciones · media {mean:+.4f} % · "
                      f"{f.covered_from:%Y-%m-%d} → {f.covered_to:%Y-%m-%d %H:%M} · {secs:.1f}s"
                      if f.covered_from else f"{sym:<10} sin cobertura")
                for x in w:
                    errors += 1
                    print(f"           {x}")
    finally:
        await close_pools()
    return errors


if __name__ == '__main__':
    import argparse
    import sys
    ap = argparse.ArgumentParser(description='Precarga el funding de Bybit en la DB')
    ap.add_argument('symbols', nargs='*')
    ap.add_argument('--since', default='2024-06-01')
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    sys.exit(1 if asyncio.run(_backfill(a.symbols, datetime.fromisoformat(a.since).replace(tzinfo=timezone.utc))) else 0)

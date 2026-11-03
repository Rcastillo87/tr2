"""
GET a la API pública de Bybit con reintentos ACOTADOS para la descarga automática de velas (C-02).

La corrida del collector tiene ~75 s para 84 series (4 en paralelo), así que el presupuesto por petición es corto:
  - hasta `attempts` intentos (3) con espera 1 s, 2 s + azar (las series en paralelo no reintentan a la vez);
  - Retry-After de Bybit se respeta hasta `max_retry_after` (5 s); si pide más, la serie se deja para el minuto siguiente;
  - se reintenta: red / timeout, HTTP 429, HTTP 5xx y retCode de límite de tasa (10006, 10018);
  - NO se reintenta: HTTP 403 (en Bybit = IP bloqueada unos minutos; insistir lo empeora) ni otros retCode
    (error de parámetros).
El backfill manual (cli/backfill_bybit.py) mantiene su política larga: es una herramienta sin presupuesto de tiempo.
"""
import asyncio
import logging
import random

import httpx

logger = logging.getLogger(__name__)

RATE_LIMIT_RETCODES = frozenset({10006, 10018})


class BybitRateLimited(RuntimeError):
    """Bybit limita o bloquea la IP (403, o 429 / retCode de límite agotando los reintentos). `blocked` = 403."""

    def __init__(self, message: str, blocked: bool = False):
        super().__init__(message)
        self.blocked = blocked


class BybitRequestError(RuntimeError):
    """Error que reintentar no arregla (parámetros, símbolo inexistente, 4xx distinto de 403/429)."""


def _retry_after(r: httpx.Response) -> float | None:
    try:
        return float(r.headers.get('Retry-After'))
    except (TypeError, ValueError):
        return None


async def get_json(client: httpx.AsyncClient, url: str, params: dict, *, attempts: int = 3,
                   base_delay: float = 1.0, max_retry_after: float = 5.0,
                   sleep=asyncio.sleep, jitter=random.random) -> dict:
    """JSON de Bybit con retCode == 0, o excepción (BybitRateLimited, BybitRequestError, RuntimeError)."""
    last: Exception | None = None
    rate_limited = False
    for attempt in range(1, attempts + 1):
        wait = base_delay * 2 ** (attempt - 1) + jitter() * 0.25
        try:
            r = await client.get(url, params=params)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last, rate_limited = RuntimeError(f'red: {e!r}'[:200]), False
        else:
            if r.status_code == 403:
                raise BybitRateLimited('HTTP 403: Bybit bloqueó la IP temporalmente', blocked=True)
            if r.status_code == 429:
                ra = _retry_after(r)
                if ra is not None and ra > max_retry_after:
                    raise BybitRateLimited(f'HTTP 429 con Retry-After {ra:g} s (más que el presupuesto)')
                last, rate_limited = RuntimeError('HTTP 429 (límite de tasa)'), True
                if ra is not None:
                    wait = ra
            elif r.status_code >= 500:
                last, rate_limited = RuntimeError(f'HTTP {r.status_code}'), False
            elif r.status_code >= 400:
                raise BybitRequestError(f'HTTP {r.status_code}: {r.text[:120]}')
            else:
                payload = r.json()
                code = payload.get('retCode', 0)
                if code == 0:
                    return payload
                if code in RATE_LIMIT_RETCODES:
                    last, rate_limited = RuntimeError(f'retCode {code} (límite de tasa)'), True
                else:   # error de Bybit: no confundir con "sin velas"
                    raise BybitRequestError(f"Bybit retCode={code} {payload.get('retMsg')}")
        if attempt < attempts:
            logger.warning(f"[BYBIT] {params.get('symbol')} {params.get('interval')} intento {attempt}/{attempts}: "
                           f"{last}. Reintento en {wait:.1f} s")
            await sleep(wait)
    if rate_limited:
        raise BybitRateLimited(f'{last} tras {attempts} intentos')
    raise RuntimeError(f'{last} tras {attempts} intentos')

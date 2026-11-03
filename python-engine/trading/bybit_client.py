"""
Cliente Bybit — Precios en tiempo real (público, sin auth)
"""

import hashlib
import hmac
import time
import httpx
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BYBIT_BASE_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')


# Permisos de la clave API que TR2 exige (PROMPT_MAESTRO §5: Contratos → Órdenes + Posiciones; nunca retiros).
REQUIRED_CONTRACT_PERMISSIONS = ('Order', 'Position')
PERMISSION_TEXTS = {
    'read_only':        'es de solo lectura',
    'missing_order':    'no tiene Contratos → Órdenes',
    'missing_position': 'no tiene Contratos → Posiciones',
    'withdraw':         'tiene permiso de retiro',
}


def api_permission_problems(info: dict | None) -> list[str]:
    """
    Problemas de una clave para operar en TR2 a partir del `result` de GET /v5/user/query-api ([] = apta).
    Códigos: read_only, missing_order, missing_position, withdraw (ver PERMISSION_TEXTS).
    """
    info = info or {}
    perms = info.get('permissions') or {}
    contract = perms.get('ContractTrade') or []
    problems = []
    if str(info.get('readOnly', 1)) != '0':
        problems.append('read_only')
    for perm, code in zip(REQUIRED_CONTRACT_PERMISSIONS, ('missing_order', 'missing_position')):
        if perm not in contract:
            problems.append(code)
    if 'Withdraw' in (perms.get('Wallet') or []):
        problems.append('withdraw')
    return problems


def describe_permission_problems(problems: list[str]) -> str:
    return ', '.join(PERMISSION_TEXTS.get(p, p) for p in problems)


def bybit_sign(api_key, api_secret, payload_str, recv_window='10000'):
    """
    Firma un pedido a la API V5 de Bybit (HMAC-SHA256). Unico lugar donde
    vive esta logica - antes estaba duplicada en broker.py (_sign_bybit)
    y en real_trader.py (BybitClient._sign / _sign_body), cada uno con
    su propia copia de la formula de firma.

    payload_str: para GET, el query string ordenado (k=v&k2=v2...).
                 para POST, el body JSON compacto (mismo string que se envia).
    Devuelve los headers listos para usar en el pedido (falta agregar
    Content-Type si es un POST con body).
    """
    timestamp = str(int(time.time() * 1000))
    param_str = timestamp + api_key + recv_window + payload_str
    signature = hmac.new(
        api_secret.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return {
        'X-BAPI-API-KEY':     api_key,
        'X-BAPI-TIMESTAMP':   timestamp,
        'X-BAPI-SIGN':        signature,
        'X-BAPI-RECV-WINDOW': recv_window,
    }


async def get_current_price(symbol: str) -> float | None:
    """Obtiene el precio actual (last price) de un símbolo en Bybit."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f'{BYBIT_BASE_URL}/v5/market/tickers',
                params={'category': 'linear', 'symbol': symbol}
            )
            r.raise_for_status()
            data = r.json()
            tickers = data.get('result', {}).get('list', [])

            if not tickers:
                return None

            return float(tickers[0]['lastPrice'])

    except Exception as e:
        logger.error(f"Error obteniendo precio de {symbol}: {e}")
        return None


async def get_current_prices(symbols: list[str]) -> dict[str, float]:
    """Obtiene precios actuales para varios símbolos."""
    prices = {}
    for symbol in symbols:
        price = await get_current_price(symbol)
        if price is not None:
            prices[symbol] = price
    return prices

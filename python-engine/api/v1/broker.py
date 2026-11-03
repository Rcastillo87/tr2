"""
API endpoint para validar credenciales de broker (Bybit).
Hace una llamada autenticada real al exchange para confirmar que
la API key y secret son válidas y tienen los permisos necesarios.
"""
import httpx
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import os

from trading.bybit_client import bybit_sign, api_permission_problems, describe_permission_problems

logger = logging.getLogger(__name__)
router = APIRouter()

BYBIT_MAINNET_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
BYBIT_DEMO_URL = os.getenv('BYBIT_DEMO_URL', 'https://api-demo.bybit.com')  # Bybit Demo Trading (precios reales)
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', '')


def _sign_bybit_get(api_key: str, api_secret: str, params: dict) -> dict:
    """Firma un GET a Bybit V5 usando la funcion compartida bybit_sign."""
    query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    return bybit_sign(api_key, api_secret, query_string, recv_window='5000')


async def _query_api_key(base_url: str, api_key: str, api_secret: str) -> dict | None:
    """`result` de GET /v5/user/query-api (permisos de la clave). None si no se pudo leer."""
    headers = _sign_bybit_get(api_key, api_secret, {})
    headers['Content-Type'] = 'application/json'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f'{base_url}/v5/user/query-api', params={}, headers=headers)
        data = r.json()
    except Exception as e:
        logger.error(f'Error leyendo permisos de la clave Bybit: {e}')
        return None
    return (data.get('result') or None) if data.get('retCode') == 0 else None


class ValidateCredentialsRequest(BaseModel):
    broker:       str
    account_type: str = 'real'
    api_key:      str
    api_secret:   str


@router.post('/broker/validate-credentials')
async def validate_credentials(
    request: ValidateCredentialsRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    if request.broker.lower() != 'bybit':
        raise HTTPException(status_code=400, detail=f'Broker no soportado: {request.broker}')

    # Usar URL correcta segun tipo de cuenta
    base_url = BYBIT_DEMO_URL if request.account_type == 'demo' else BYBIT_MAINNET_URL

    try:
        params = {'accountType': 'UNIFIED'}
        headers = _sign_bybit_get(request.api_key, request.api_secret, params)
        headers['Content-Type'] = 'application/json'

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f'{base_url}/v5/account/wallet-balance',
                params=params,
                headers=headers,
            )

        data = r.json()
        ret_code = data.get('retCode', -1)

        if ret_code == 0:
            # REAL-09: además de leer el saldo, la clave debe poder operar contratos y NO tener retiros
            info = await _query_api_key(base_url, request.api_key, request.api_secret)
            if info is None:
                return {'valid': False, 'message': 'No se pudieron leer los permisos de la clave en Bybit. Intenta de nuevo.'}
            problems = api_permission_problems(info)
            if problems:
                hint = (' Por seguridad TR2 no acepta claves con retiros: crea una clave sin ese permiso.'
                        if 'withdraw' in problems else '')
                return {'valid': False, 'problems': problems,
                        'message': f'La clave {describe_permission_problems(problems)}. Necesita Contratos → '
                                   f'Órdenes y Posiciones, sin retiros.{hint}'}

            # Credenciales válidas — extraer balance total si está disponible
            total_equity = None
            try:
                accounts = data['result']['list']
                if accounts:
                    total_equity = float(accounts[0].get('totalEquity', 0))
            except Exception:
                pass

            return {
                'valid':        True,
                'message':      'Credenciales válidas.',
                'total_equity': total_equity,
            }

        elif ret_code == 10003:
            return {'valid': False, 'message': 'API Key inválida o no existe.'}
        elif ret_code == 10004:
            return {'valid': False, 'message': 'Firma inválida. Verifica el API Secret.'}
        elif ret_code == 10005:
            return {'valid': False, 'message': 'La API Key no tiene permisos suficientes. Asegúrate de habilitar "Read" y "Trade".'}
        elif ret_code == 33004:
            return {'valid': False, 'message': 'API Key expirada.'}
        else:
            return {'valid': False, 'message': f'Error de Bybit (código {ret_code}): {data.get("retMsg", "Error desconocido")}'}

    except httpx.TimeoutException:
        return {'valid': False, 'message': 'Timeout conectando a Bybit. Intenta de nuevo.'}
    except Exception as e:
        logger.error(f'Error validando credenciales Bybit: {e}')
        return {'valid': False, 'message': 'Error de conexión con Bybit.'}


class AccountInfoRequest(BaseModel):
    broker:       str
    account_type: str = 'real'
    api_key:      str
    api_secret:   str


@router.post('/broker/account-info')
async def account_info(
    request: AccountInfoRequest,
    x_internal_api_key: str = Header(None, alias='X-Internal-API-Key'),
):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail='Unauthorized')

    base_url = BYBIT_DEMO_URL if request.account_type == 'demo' else BYBIT_MAINNET_URL

    try:
        params  = {}
        headers = _sign_bybit_get(request.api_key, request.api_secret, params)
        headers['Content-Type'] = 'application/json'

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f'{base_url}/v5/user/query-api',
                params=params,
                headers=headers,
            )

        data     = r.json()
        ret_code = data.get('retCode', -1)

        if ret_code != 0:
            return {'success': False, 'message': data.get('retMsg', 'Error desconocido')}

        result      = data.get('result', {})
        expired_at  = result.get('expiredAt', '')
        read_only   = result.get('readOnly', 1)
        permissions = result.get('permissions', {})

        days_remaining = None
        if expired_at:
            from datetime import datetime, timezone
            try:
                exp = datetime.fromisoformat(expired_at.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                days_remaining = max(0, (exp - now).days)
            except Exception:
                pass

        contract_perms = permissions.get('ContractTrade', [])
        unified_perms  = permissions.get('UnifiedTrade', [])   # clave antigua de Bybit (ya no viene)
        problems = api_permission_problems(result)
        can_trade = not ({'read_only', 'missing_order', 'missing_position'} & set(problems))

        return {
            'success':        True,
            'expired_at':     expired_at,
            'days_remaining': days_remaining,
            'read_only':      bool(read_only),
            'can_trade':      can_trade,
            'problems':       problems,
            'permissions': {
                'contract': contract_perms,
                'unified':  unified_perms,
                'wallet':   permissions.get('Wallet', []),
            },
        }

    except httpx.TimeoutException:
        return {'success': False, 'message': 'Timeout conectando a Bybit.'}
    except Exception as e:
        logger.error(f'Error obteniendo info de cuenta Bybit: {e}')
        return {'success': False, 'message': 'Error de conexión.'}

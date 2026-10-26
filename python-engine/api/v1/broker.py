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

from trading.bybit_client import bybit_sign

logger = logging.getLogger(__name__)
router = APIRouter()

BYBIT_MAINNET_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
BYBIT_TESTNET_URL = os.getenv('BYBIT_TESTNET_URL', 'https://api-testnet.bybit.com')
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', '')


def _sign_bybit_get(api_key: str, api_secret: str, params: dict) -> dict:
    """Firma un GET a Bybit V5 usando la funcion compartida bybit_sign."""
    query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    return bybit_sign(api_key, api_secret, query_string, recv_window='5000')


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
    base_url = BYBIT_TESTNET_URL if request.account_type == 'demo' else BYBIT_MAINNET_URL

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

    base_url = BYBIT_TESTNET_URL if request.account_type == 'demo' else BYBIT_MAINNET_URL

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
        unified_perms  = permissions.get('UnifiedTrade', [])
        can_trade = 'Order' in contract_perms or 'Order' in unified_perms

        return {
            'success':        True,
            'expired_at':     expired_at,
            'days_remaining': days_remaining,
            'read_only':      bool(read_only),
            'can_trade':      can_trade,
            'permissions': {
                'contract': contract_perms,
                'unified':  unified_perms,
            },
        }

    except httpx.TimeoutException:
        return {'success': False, 'message': 'Timeout conectando a Bybit.'}
    except Exception as e:
        logger.error(f'Error obteniendo info de cuenta Bybit: {e}')
        return {'success': False, 'message': 'Error de conexión.'}

"""
Endpoint para calcular el cambio REAL de balance en un periodo, sumando
todo el transaction-log de Bybit (trades + funding settlements + cualquier
otro movimiento de cuenta), en vez de depender de la suma de net_pnl
guardada localmente en real_trades — que no incluye funding fees ni
otros eventos de cuenta, y por eso puede divergir bastante del cambio
real de balance.
"""
import logging
import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from trading.bybit_client import bybit_sign

logger = logging.getLogger(__name__)
router = APIRouter()

BYBIT_MAINNET_URL = os.getenv('BYBIT_BASE_URL', 'https://api.bybit.com')
BYBIT_TESTNET_URL = os.getenv('BYBIT_TESTNET_URL', 'https://api-testnet.bybit.com')


class PeriodPnlRequest(BaseModel):
    account_type:  str = 'real'
    api_key:       str
    api_secret:    str
    start_time_ms: int
    end_time_ms:   int | None = None


@router.post('/real/period-pnl')
async def period_pnl(request: PeriodPnlRequest):
    """Suma el campo 'change' de todo el transaction-log de Bybit en el
    rango pedido — es el cambio de balance real, ground truth, sin importar
    si vino de un trade, un funding fee, o cualquier otro evento de cuenta."""
    base_url = BYBIT_TESTNET_URL if request.account_type == 'demo' else BYBIT_MAINNET_URL

    total_change = 0.0
    cursor = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for _ in range(10):  # tope de seguridad de paginas
                params = {
                    'accountType': 'UNIFIED',
                    'category':    'linear',
                    'startTime':   str(request.start_time_ms),
                    'limit':       '50',
                }
                if request.end_time_ms:
                    params['endTime'] = str(request.end_time_ms)
                if cursor:
                    params['cursor'] = cursor

                query_string = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
                headers = bybit_sign(request.api_key, request.api_secret, query_string, recv_window='5000')
                headers['Content-Type'] = 'application/json'

                # IMPORTANTE: pasar el query string ya armado dentro de la URL,
                # NO como params= separado — httpx reordena params= segun el
                # orden de inserccion del dict, que no coincide con el orden
                # alfabetico usado para firmar, y Bybit rechaza la firma.
                r = await client.get(
                    f'{base_url}/v5/account/transaction-log?{query_string}',
                    headers=headers,
                )
                data = r.json()
                if data.get('retCode') != 0:
                    logger.error(f"[PERIOD_PNL] Error de Bybit: {data.get('retMsg')}")
                    raise HTTPException(status_code=502, detail=data.get('retMsg', 'Error de Bybit'))

                items = data.get('result', {}).get('list', [])
                for item in items:
                    total_change += float(item.get('change', 0) or 0)

                cursor = data.get('result', {}).get('nextPageCursor')
                if not cursor or not items:
                    break
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PERIOD_PNL] Excepcion: {e}")
        raise HTTPException(status_code=502, detail='Error de conexion con Bybit.')

    return {'status': 'ok', 'period_pnl': round(total_change, 8)}

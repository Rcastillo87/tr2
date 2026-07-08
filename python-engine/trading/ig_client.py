"""
Cliente IG Group — REST API estándar (no DMA/FIX)
Patrón calcado de BybitClient (real_trader.py), adaptado a auth por sesión.

⚠️ VERIFICAR contra la documentación oficial de IG antes de usar en real:
   - Nombres exactos de campos en el body de /positions/otc
   - Version header correcto por endpoint (varía: v1, v2, v3 según endpoint)
   - Formato exacto de 'epic' por instrumento (ej. forex EUR/USD suele ser
     'CS.D.EURUSD.CFD.IP', pero necesita confirmarse en Market Search)
"""

import httpx
import logging
import os
import time
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

IG_DEMO_URL = os.getenv('IG_DEMO_URL', 'https://demo-api.ig.com/gateway/deal')
IG_LIVE_URL = os.getenv('IG_LIVE_URL', 'https://api.ig.com/gateway/deal')


class IGAPIError(Exception):
    """Error de API de IG — nunca debe interpretarse como 'sin posición'."""
    pass


class IGClient:

    def __init__(self, api_key: str, username: str, password: str, account_type: str = 'demo'):
        self.api_key    = api_key
        self.username   = username
        self.password   = password
        self.base_url   = IG_DEMO_URL if account_type == 'demo' else IG_LIVE_URL
        self._cst        = None
        self._sec_token   = None
        self._session_at  = 0
        self._session_ttl = 6 * 3600

    def _base_headers(self, version: str = '2') -> dict:
        return {
            'X-IG-API-KEY': self.api_key,
            'Content-Type':  'application/json; charset=UTF-8',
            'Accept':        'application/json; charset=UTF-8',
            'Version':       version,
        }

    async def _ensure_session(self):
        if self._cst and self._sec_token and (time.time() - self._session_at) < self._session_ttl:
            return
        await self._login()

    async def _login(self):
        body = {'identifier': self.username, 'password': self.password}
        headers = self._base_headers(version='2')
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(f'{self.base_url}/session', json=body, headers=headers)
            if r.status_code != 200:
                logger.error(f"[IG] login error: HTTP {r.status_code} body={r.text}")
                raise IGAPIError(f"login failed HTTP {r.status_code}")
            self._cst       = r.headers.get('CST')
            self._sec_token = r.headers.get('X-SECURITY-TOKEN')
            self._session_at = time.time()
            if not self._cst or not self._sec_token:
                raise IGAPIError("login ok pero faltan headers CST/X-SECURITY-TOKEN")
            logger.info(f"[IG] sesión iniciada OK (account_type={'demo' if 'demo' in self.base_url else 'live'})")
        except httpx.RequestError as e:
            logger.error(f"[IG] login network exception: {e}")
            raise IGAPIError(f"network error: {e}") from e

    def _auth_headers(self, version: str = '2') -> dict:
        headers = self._base_headers(version=version)
        headers['CST']              = self._cst
        headers['X-SECURITY-TOKEN'] = self._sec_token
        return headers

    async def get_balance(self) -> float | None:
        await self._ensure_session()
        headers = self._auth_headers(version='1')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f'{self.base_url}/accounts', headers=headers)
            if r.status_code != 200:
                logger.error(f"[IG] get_balance HTTP {r.status_code}: {r.text}")
                return None
            data = r.json()
            accounts = data.get('accounts', [])
            for acc in accounts:
                if acc.get('preferred'):
                    return float(acc.get('balance', {}).get('available', 0))
            return None
        except Exception as e:
            logger.error(f"[IG] get_balance exception: {e}")
            return None

    async def get_market_price(self, epic: str, require_open: bool = True) -> float | None:
        """
        require_open: si True (default), devuelve None cuando el mercado
        no esta TRADEABLE en vez de un precio potencialmente obsoleto
        (relevante para forex/indices, que no son 24/7 como cripto).
        """
        await self._ensure_session()
        headers = self._auth_headers(version='3')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f'{self.base_url}/markets/{epic}', headers=headers)
            if r.status_code != 200:
                logger.error(f"[IG] get_market_price HTTP {r.status_code}: {r.text}")
                return None
            data = r.json()
            snapshot = data.get('snapshot', {})
            market_status = snapshot.get('marketStatus')
            if require_open and market_status != 'TRADEABLE':
                logger.warning(f"[IG] {epic} mercado no tradeable (status={market_status})")
                return None
            bid   = snapshot.get('bid')
            offer = snapshot.get('offer')
            if bid is not None and offer is not None:
                return (float(bid) + float(offer)) / 2
            return None
        except Exception as e:
            logger.error(f"[IG] get_market_price exception: {e}")
            return None

    async def is_market_open(self, epic: str) -> bool:
        """GET /markets/{epic} — True si marketStatus == TRADEABLE."""
        await self._ensure_session()
        headers = self._auth_headers(version='3')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f'{self.base_url}/markets/{epic}', headers=headers)
            if r.status_code != 200:
                return False
            data = r.json()
            return data.get('snapshot', {}).get('marketStatus') == 'TRADEABLE'
        except Exception as e:
            logger.error(f"[IG] is_market_open exception: {e}")
            return False

    async def get_min_deal_size(self, epic: str) -> float:
        await self._ensure_session()
        headers = self._auth_headers(version='3')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f'{self.base_url}/markets/{epic}', headers=headers)
            data = r.json()
            rules = data.get('dealingRules', {})
            min_size = rules.get('minDealSize', {}).get('value')
            return float(min_size) if min_size else 0.1
        except Exception:
            return 0.1

    async def place_market_order(self, epic: str, direction: str, size: float,
                                  currency_code: str = 'USD') -> dict | None:
        await self._ensure_session()
        body = {
            'epic':          epic,
            'expiry':        '-',
            'direction':     direction,
            'size':          str(size),
            'orderType':     'MARKET',
            'currencyCode':  currency_code,
            'forceOpen':     True,
            'guaranteedStop': False,
        }
        headers = self._auth_headers(version='2')
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(f'{self.base_url}/positions/otc', json=body, headers=headers)
            data = r.json()
            if r.status_code == 200:
                return data
            logger.error(f"[IG] place_market_order error: HTTP {r.status_code} body={data}")
            return None
        except Exception as e:
            logger.error(f"[IG] place_market_order exception: {e}")
            return None

    async def confirm_deal(self, deal_reference: str) -> dict | None:
        await self._ensure_session()
        headers = self._auth_headers(version='1')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f'{self.base_url}/confirms/{deal_reference}', headers=headers)
            if r.status_code == 200:
                return r.json()
            logger.error(f"[IG] confirm_deal HTTP {r.status_code}: {r.text}")
            return None
        except Exception as e:
            logger.error(f"[IG] confirm_deal exception: {e}")
            return None

    async def get_open_position(self, epic: str) -> dict | None:
        await self._ensure_session()
        headers = self._auth_headers(version='2')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f'{self.base_url}/positions', headers=headers)
        except httpx.RequestError as e:
            logger.error(f"[IG] get_open_position network exception: {e}")
            raise IGAPIError(f"network error: {e}") from e

        if r.status_code != 200:
            logger.error(f"[IG] get_open_position HTTP {r.status_code}: {r.text}")
            raise IGAPIError(f"HTTP {r.status_code}")

        data = r.json()
        for item in data.get('positions', []):
            market = item.get('market', {})
            if market.get('epic') == epic:
                return item
        return None

    async def set_trading_stop(self, deal_id: str, sl: float = None, tp: float = None,
                                trailing_stop: bool = False,
                                trailing_distance: float = None,
                                trailing_step: float = None) -> bool:
        await self._ensure_session()
        body = {}
        if sl is not None:
            body['stopLevel'] = sl
        if tp is not None:
            body['limitLevel'] = tp
        if trailing_stop:
            body['trailingStop']          = True
            body['trailingStopDistance']  = trailing_distance
            body['trailingStep'] = trailing_step

        headers = self._auth_headers(version='2')
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.put(f'{self.base_url}/positions/otc/{deal_id}', json=body, headers=headers)
            data = r.json()
            if r.status_code == 200:
                logger.info(f"[IG] SL/TP actualizado: dealId={deal_id} SL={sl} TP={tp}")
                return True
            logger.error(f"[IG] set_trading_stop error: HTTP {r.status_code} body={data}")
            return False
        except Exception as e:
            logger.error(f"[IG] set_trading_stop exception: {e}")
            return False

    async def get_historical_prices(self, epic: str, resolution: str,
                                      start: str, end: str) -> dict:
        """
        GET /prices/{epic}/{resolution}/{start}/{end} (v2).
        start/end en formato 'YYYY-MM-DD HH:MM:SS' (con espacio, se URL-encodea aca).
        resolution: SECOND, MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR,
        HOUR_2, HOUR_3, HOUR_4, DAY, WEEK, MONTH (confirmar nombres exactos
        contra la API Reference completa si se usan valores no probados aun -
        MINUTE y HOUR ya se probaron y funcionan).

        Devuelve dict con 'prices' (lista de velas) y 'allowance' (cuota
        restante) - el caller debe revisar allowance antes de seguir pidiendo.
        Lanza IGAPIError en fallos de red/HTTP (igual que get_open_position -
        un error de API no debe interpretarse como "sin datos").
        """
        await self._ensure_session()
        headers = self._auth_headers(version='2')
        start_enc = quote(start)
        end_enc   = quote(end)
        url = f'{self.base_url}/prices/{epic}/{resolution}/{start_enc}/{end_enc}'
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url, headers=headers)
        except httpx.RequestError as e:
            logger.error(f"[IG] get_historical_prices network exception: {e}")
            raise IGAPIError(f"network error: {e}") from e

        if r.status_code != 200:
            logger.error(f"[IG] get_historical_prices HTTP {r.status_code}: {r.text}")
            raise IGAPIError(f"HTTP {r.status_code}: {r.text}")

        return r.json()

    async def close_position(self, deal_id: str, direction: str, size: float) -> dict | None:
        # CONFIRMADO EN DEMO (2026-07-07): requiere POST con header
        # '_method: DELETE' en vez de DELETE HTTP real. El body NO debe
        # incluir 'epic'/'expiry' junto con 'dealId' (mutuamente
        # excluyentes - error validation.mutual-exclusive-value.request).
        await self._ensure_session()
        body = {
            'dealId':    deal_id,
            'direction': direction,
            'size':      str(size),
            'orderType': 'MARKET',
        }
        headers = self._auth_headers(version='1')
        headers['_method'] = 'DELETE'
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(f'{self.base_url}/positions/otc', json=body, headers=headers)
            data = r.json()
            if r.status_code == 200:
                return data
            logger.error(f"[IG] close_position error: HTTP {r.status_code} body={data}")
            return None
        except Exception as e:
            logger.error(f"[IG] close_position exception: {e}")
            return None

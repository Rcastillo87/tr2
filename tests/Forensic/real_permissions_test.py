"""
REAL-09: la clave API debe poder operar contratos (Contratos → Órdenes + Posiciones, lectura y escritura) y NO tener
retiros. El alta de cuenta lo exige; las cuentas ya registradas se revisan una vez al día y solo se avisa (opción A).
Sin red: respuestas de Bybit simuladas con el formato de GET /v5/user/query-api.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_permissions_test.py
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/
logging.disable(logging.CRITICAL)

import real_parity_test as rp  # noqa: E402  (pool simulado)
import api.v1.broker as broker  # noqa: E402
import api.v1.real_trading as api  # noqa: E402
from trading.bybit_client import api_permission_problems  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def key(read_only=0, contract=('Order', 'Position'), wallet=('AccountTransfer',), days=85):
    exp = (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {'readOnly': read_only, 'expiredAt': exp, 'uta': 1,
            'permissions': {'ContractTrade': list(contract), 'Wallet': list(wallet), 'Spot': [], 'Options': []}}


# ─────────────── 1. Regla de permisos ───────────────
def rule_cases():
    cases = [
        ('clave correcta (Órdenes + Posiciones, sin retiros)', key(), []),
        ('readOnly como texto "0"', {**key(), 'readOnly': '0'}, []),
        ('solo lectura', key(read_only=1), ['read_only']),
        ('sin Posiciones', key(contract=('Order',)), ['missing_position']),
        ('sin Órdenes', key(contract=('Position',)), ['missing_order']),
        ('con retiro', key(wallet=('AccountTransfer', 'Withdraw')), ['withdraw']),
        ('cuenta principal con transferencias pero sin retiro', key(wallet=('AccountTransfer', 'SubMemberTransfer')), []),
        ('respuesta vacía', {}, ['read_only', 'missing_order', 'missing_position']),
    ]
    for label, info, exp in cases:
        got = api_permission_problems(info)
        check(f'R {label}: {exp or "apta"}', got == exp, got)


# ─────────────── 2. Alta de cuenta y endpoint de información ───────────────
class FakeHttp:
    """httpx.AsyncClient simulado: responde según la ruta."""
    routes = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *e):
        return False

    async def get(self, url, params=None, headers=None):
        for path, data in FakeHttp.routes.items():
            if url.endswith(path):
                if isinstance(data, Exception):
                    raise data

                class R:
                    status_code = 200

                    def json(self_):
                        return data
                return R()
        raise AssertionError(f'ruta no simulada: {url}')


WALLET_OK = {'retCode': 0, 'result': {'list': [{'totalEquity': '1000'}]}}


async def validate(query_api):
    FakeHttp.routes = {'/v5/account/wallet-balance': WALLET_OK, '/v5/user/query-api': query_api}
    req = broker.ValidateCredentialsRequest(broker='bybit', account_type='demo', api_key='k', api_secret='s')
    return await broker.validate_credentials(req, x_internal_api_key=broker.INTERNAL_API_KEY)


async def endpoint_cases():
    broker.httpx.AsyncClient = FakeHttp
    r = await validate({'retCode': 0, 'result': key()})
    check('A1 alta con clave correcta: válida', r.get('valid') is True, r)
    r = await validate({'retCode': 0, 'result': key(read_only=1)})
    check('A2 alta con clave de solo lectura: rechazada y lo explica',
          r.get('valid') is False and 'solo lectura' in r.get('message', ''), r)
    r = await validate({'retCode': 0, 'result': key(contract=('Order',))})
    check('A3 alta sin Contratos → Posiciones: rechazada', r.get('valid') is False and 'Posiciones' in r.get('message', ''), r)
    r = await validate({'retCode': 0, 'result': key(wallet=('Withdraw',))})
    check('A4 alta con permiso de retiro: rechazada por seguridad',
          r.get('valid') is False and 'retiro' in r.get('message', '') and 'seguridad' in r.get('message', ''), r)
    r = await validate({'retCode': 10002, 'retMsg': 'timestamp'})
    check('A5 no se pudieron leer los permisos: no registra a ciegas',
          r.get('valid') is False and 'Intenta de nuevo' in r.get('message', ''), r)
    r = await validate(RuntimeError('caída de red'))
    check('A6 red caída al leer permisos: no registra', r.get('valid') is False, r)
    FakeHttp.routes = {'/v5/account/wallet-balance': {'retCode': 10003, 'retMsg': 'invalid'}}
    req = broker.ValidateCredentialsRequest(broker='bybit', account_type='demo', api_key='k', api_secret='s')
    r = await broker.validate_credentials(req, x_internal_api_key=broker.INTERNAL_API_KEY)
    check('A7 clave inválida: el mensaje de siempre', r.get('valid') is False and 'inválida' in r.get('message', ''), r)

    FakeHttp.routes = {'/v5/user/query-api': {'retCode': 0, 'result': key(wallet=('AccountTransfer', 'Withdraw'))}}
    req = broker.AccountInfoRequest(broker='bybit', account_type='demo', api_key='k', api_secret='s')
    r = await broker.account_info(req, x_internal_api_key=broker.INTERNAL_API_KEY)
    check('I1 información de la clave: puede operar, informa el retiro y los permisos de Wallet',
          r.get('can_trade') is True and r.get('problems') == ['withdraw']
          and 'Withdraw' in r['permissions'].get('wallet', []), r)
    FakeHttp.routes = {'/v5/user/query-api': {'retCode': 0, 'result': key(read_only=1)}}
    r = await broker.account_info(req, x_internal_api_key=broker.INTERNAL_API_KEY)
    check('I2 clave de solo lectura: can_trade = False (antes miraba una clave que Bybit ya no envía)',
          r.get('can_trade') is False, r)


# ─────────────── 3. Revisión diaria de cuentas registradas (solo avisa) ───────────────
class KeyClient:
    def __init__(self, infos):
        self.infos, self.calls = list(infos), 0

    async def get_api_key_info(self):
        self.calls += 1
        v = self.infos.pop(0) if len(self.infos) > 1 else self.infos[0]
        return v


def evs(s):
    return [(a[2], json.loads(a[3])) for sql, a in s['exec'] if 'INSERT INTO broker_events' in sql]


async def daily_cases():
    api._perm_state.clear()
    api._perm_next_check.clear()
    t0 = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    s = {'exec': []}
    pool = rp.FakePool(s)
    c = KeyClient([key(wallet=('Withdraw',)), key(wallet=('Withdraw',)), key()])

    await api._track_permissions(pool, 11, c, now=t0)
    check('D1 primera revisión con retiro: abre incidente con el problema',
          evs(s) == [('api_permissions_bad', {'problems': ['withdraw']})], evs(s))
    await api._track_permissions(pool, 11, c, now=t0 + timedelta(hours=3))
    check('D2 dentro de las 24 h: no vuelve a consultar Bybit', c.calls == 1, c.calls)
    await api._track_permissions(pool, 11, c, now=t0 + timedelta(hours=24, minutes=1))
    check('D3 al día siguiente sigue mal: consulta pero no repite el aviso', c.calls == 2 and len(evs(s)) == 1, evs(s))
    await api._track_permissions(pool, 11, c, now=t0 + timedelta(hours=48, minutes=2))
    check('D4 clave reemplazada: cierra el incidente',
          [e[0] for e in evs(s)] == ['api_permissions_bad', 'api_permissions_ok'], evs(s))

    s = {'exec': []}
    pool = rp.FakePool(s)
    c = KeyClient([None])
    await api._track_permissions(pool, 12, c, now=t0)
    await api._track_permissions(pool, 12, c, now=t0 + timedelta(minutes=30))
    check('D5 Bybit no responde: sin avisos y no reintenta antes de 1 h', not evs(s) and c.calls == 1, (evs(s), c.calls))
    c.infos = [key()]
    await api._track_permissions(pool, 12, c, now=t0 + timedelta(hours=1, minutes=1))
    check('D6 a la hora reintenta; clave correcta tras arrancar: un cierre (Laravel lo ignora si no había incidente)',
          c.calls == 2 and [e[0] for e in evs(s)] == ['api_permissions_ok'], evs(s))

    class Boom:
        async def get_api_key_info(self):
            raise RuntimeError('fallo inesperado')
    s = {'exec': []}
    await api._track_permissions(rp.FakePool(s), 13, Boom(), now=t0)
    check('D7 excepción inesperada: no tumba el tick ni avisa', not evs(s))

    from trading.broker_events import EVENTS
    check('E1 api_permissions_bad y api_permissions_ok son eventos conocidos',
          {'api_permissions_bad', 'api_permissions_ok'} <= EVENTS)


async def main():
    rule_cases()
    await endpoint_cases()
    await daily_cases()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

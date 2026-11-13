"""
U-1 (p62, decisión del dueño 13-nov): las suscripciones de un usuario INACTIVO con operaciones vivas viajan al motor con
entries_allowed=false: se gestionan hasta terminar su ciclo (salida por señal opuesta incluida) sin entradas ni reversas.
Comprueba que /real/tick pasa a check_new_signals, por suscripción, entries = cuenta AND kill switch AND suscripción, y
que un payload sin el campo (Laravel anterior) sigue como antes (True). Sin DB ni Bybit.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_sub_entries_test.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/
os.environ.setdefault('INTERNAL_API_KEY', 'k')

import api.v1.real_trading as api  # noqa: E402

fails = 0
CALLS: dict = {}
KILL = [False]


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Client:
    async def check_auth(self):
        return True, ''


class Trader:
    def __init__(self, pool):
        self.pool = pool

    async def ensure_month_baseline(self, *a):
        return None

    async def get_circuit_breaker_errors(self, *a):
        return 0

    async def monitor_open_trades(self, *a):
        return {'checked': 0, 'closed': 0, 'be_activated': 0, 'errors': 0}

    async def check_new_signals(self, sub, strategy, client, entries_allowed=True):
        CALLS[sub['subscription_id']] = entries_allowed
        return 'ok'


class Risk:
    def __init__(self, pool):
        pass

    async def is_kill_switch_active(self):
        return KILL[0]


async def _noop(*a, **k):
    return None


class Pool:
    async def close(self):
        return None


async def _pool():
    return Pool()


api._build_broker_client = lambda account: Client()
api._track_auth = _noop
api._track_permissions = _noop
api.RiskManager = Risk
api.RealTrader = Trader
api.get_json_pool = _pool
api.instantiate_strategy = lambda sub: object()


def sub(i, **extra):
    return {'subscription_id': i, 'user_id': 1, 'broker_account_id': 11, 'strategy': f'S{i}', 'symbol': 'ETHUSDT',
            'interval': '240', 'config_params': {'x': 1}, **extra}


def req(subs, account_entries=True):
    return api.RealTickRequest(accounts=[{'id': 11, 'broker': 'bybit', 'account_type': 'demo', 'api_key': 'k',
                                          'api_secret': 's', 'entries_allowed': account_entries, 'subscriptions': subs}])


async def tick(r):
    CALLS.clear()
    api._account_locks.clear()
    await api.real_tick(r, api.INTERNAL_API_KEY)
    return dict(CALLS)


async def main():
    c = await tick(req([sub(1, entries_allowed=True), sub(2, entries_allowed=False)]))
    check('E1 suscripción normal con entradas; la del usuario inactivo SIN entradas', c == {1: True, 2: False}, c)

    c = await tick(req([sub(1), sub(2, entries_allowed=False)]))
    check('E2 payload sin el campo (Laravel anterior a p62) -> entradas como siempre', c.get(1) is True, c)

    c = await tick(req([sub(1, entries_allowed=True), sub(2, entries_allowed=False)], account_entries=False))
    check('E3 cuenta pausada -> ninguna suscripción con entradas', c == {1: False, 2: False}, c)

    KILL[0] = True
    c = await tick(req([sub(1, entries_allowed=True)]))
    KILL[0] = False
    check('E4 kill switch -> sin entradas aunque la suscripción las permita', c == {1: False}, c)

    check('E5 la suscripción sin entradas igual se procesa (para gestionar y salir por señal opuesta)',
          2 in (await tick(req([sub(2, entries_allowed=False)]))), CALLS)

    from fastapi.testclient import TestClient
    import main as engine_main
    h = TestClient(engine_main.app).get('/health').json()
    check('E6 /health anuncia sub_entries (Laravel solo envía suscripciones sin entradas si el motor la confirma)',
          'sub_entries' in (h.get('features') or []), h)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

"""
N-07: exclusión por cuenta entre el tick Real, el circuit breaker de pérdida máxima y la reconciliación.
- Los tres corren con el mismo turno exclusivo por cuenta: el circuit breaker y la reconciliación esperan al tick (con
  un plazo; si se agota, la cuenta se omite), y el tick se omite si otro proceso tiene la cuenta.
- Un cierre se reclama (open -> pending_close) de forma atómica: si otro ya lo reclamó, no se envía una segunda orden.
- Las UPDATE de estado de los cierres exigen el estado esperado (no pisan un cierre ya registrado).
- El monitor devuelve a 'open' un 'pending_close' sin confirmar cuya posición sigue viva (los reintentos siguen).
Sin DB ni Bybit reales. Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_concurrency_test.py
"""
import asyncio
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

logging.disable(logging.CRITICAL)
REAL_SLEEP = asyncio.sleep   # real_parity_test acelera asyncio.sleep al importarse; aquí los tiempos importan

import real_parity_test as rp  # noqa: E402  (fakes compartidos)
import api.v1.real_trading as api  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0
EVENTS: list = []
T0 = time.monotonic()


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def mark(what):
    EVENTS.append((what, time.monotonic() - T0))


def when(what):
    return next((t for w, t in EVENTS if w == what), None)


class NullPool:
    def acquire(self):
        class _C:
            async def __aenter__(self_):
                class _Conn:
                    async def fetch(self, *a):
                        return []

                    async def execute(self, *a):
                        return 'UPDATE 0'
                return _Conn()

            async def __aexit__(self_, *e):
                return False
        return _C()

    async def close(self):
        pass


async def _pool():
    return NullPool()


class FakeTrader:
    cb_delay = 0.0
    cb_raises = False

    def __init__(self, pool):
        self.pool = pool

    async def check_max_loss_circuit_breaker(self, account_id, client):
        mark(f'cb_start_{account_id}')
        if FakeTrader.cb_raises:
            raise RuntimeError('fallo simulado')
        await REAL_SLEEP(FakeTrader.cb_delay)
        mark(f'cb_end_{account_id}')
        return {'checked': 0, 'closed': 0, 'errors': 0}

    async def get_open_trades(self, account_id):
        return []


TICK_HOLD = 0.3


async def _fake_process_account(trader, account):
    mark(f'tick_start_{account.id}')
    await REAL_SLEEP(TICK_HOLD)
    mark(f'tick_end_{account.id}')
    return f'account_{account.id}_bybit', {'ok': True}


async def _fake_recover(trader, client, account, pool, results):
    mark(f'rec_start_{account.id}')


api.get_json_pool = _pool
api.RealTrader = FakeTrader
api._build_broker_client = lambda account: object()
api._process_account = _fake_process_account
api._recover_pending_opens = _fake_recover


def req(*ids):
    return api.RealTickRequest(accounts=[{'id': i, 'broker': 'bybit', 'account_type': 'demo', 'api_key': 'k',
                                          'api_secret': 's', 'subscriptions': []} for i in ids])


KEY = api.INTERNAL_API_KEY


async def reset():
    EVENTS.clear()
    api._account_locks.clear()
    FakeTrader.cb_delay, FakeTrader.cb_raises = 0.0, False


async def later(coro, delay=0.05):
    await REAL_SLEEP(delay)
    return await coro


async def endpoints():
    # L1. El circuit breaker espera a que termine el tick de la misma cuenta
    await reset()
    await asyncio.gather(api.real_tick(req(11), KEY), later(api.circuit_breaker_max_loss(req(11), KEY)))
    te, cs = when('tick_end_11'), when('cb_start_11')
    check('L1: circuit breaker de la cuenta 11 empieza después de que termina su tick',
          te is not None and cs is not None and cs >= te, (te, cs))

    # L2. La reconciliación también espera al tick
    await reset()
    await asyncio.gather(api.real_tick(req(11), KEY), later(api.reconcile(req(11), KEY)))
    te, rs = when('tick_end_11'), when('rec_start_11')
    check('L2: reconciliación de la cuenta 11 empieza después de que termina su tick',
          te is not None and rs is not None and rs >= te, (te, rs))

    # L3. Con el circuit breaker en curso, el tick de esa cuenta se omite (no corre en paralelo)
    await reset()
    FakeTrader.cb_delay = 0.3
    _, tick = await asyncio.gather(api.circuit_breaker_max_loss(req(11), KEY), later(api.real_tick(req(11), KEY)))
    check('L3: tick con el circuit breaker en curso -> omitido, sin procesar la cuenta',
          when('tick_start_11') is None and 'omitido' in str(tick), (when('tick_start_11'), tick.get('results')))

    # L4. Plazo agotado: el circuit breaker omite la cuenta (no queda esperando más que su job)
    await reset()
    wait0 = getattr(api, 'CIRCUIT_BREAKER_LOCK_WAIT', None)
    api.CIRCUIT_BREAKER_LOCK_WAIT = 0.05
    try:
        _, cb = await asyncio.gather(api.real_tick(req(11), KEY), later(api.circuit_breaker_max_loss(req(11), KEY), 0.02))
    finally:
        if wait0 is not None:
            api.CIRCUIT_BREAKER_LOCK_WAIT = wait0
    check('L4: plazo agotado -> circuit breaker omite la cuenta (skipped) y no la revisa a medias',
          when('cb_start_11') is None and 'skipped' in str(cb.get('results', {}).get('account_11')), cb.get('results'))
    check('L4: plazos de espera menores que los timeouts HTTP de los jobs (25 s y 90 s)',
          0 < (wait0 or 0) < 25 and 0 < getattr(api, 'RECONCILE_LOCK_WAIT', 0) < 90,
          (wait0, getattr(api, 'RECONCILE_LOCK_WAIT', None)))

    # L5. Cuentas distintas no se bloquean entre sí
    await reset()
    FakeTrader.cb_delay = 0.0
    await asyncio.gather(api.real_tick(req(11), KEY), later(api.circuit_breaker_max_loss(req(12), KEY)))
    te, cs = when('tick_end_11'), when('cb_start_12')
    check('L5: circuit breaker de la cuenta 12 no espera al tick de la 11',
          te is not None and cs is not None and cs < te, (te, cs))

    # L6. Un error dentro del turno libera la cuenta
    await reset()
    FakeTrader.cb_raises = True
    await api.circuit_breaker_max_loss(req(11), KEY)
    FakeTrader.cb_raises = False
    await api.real_tick(req(11), KEY)
    check('L6: tras un error del circuit breaker, el tick siguiente procesa la cuenta', when('tick_start_11') is not None,
          EVENTS)


class ClaimConn(rp.FakeConn):
    async def execute(self, sql, *a):
        self.s['exec'].append((sql, a))
        if "SET status = 'pending_close'" in sql and self.s.get('already_claimed'):
            return 'UPDATE 0'
        return 'UPDATE 1'


class ClaimPool(rp.FakePool):
    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return ClaimConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


def sqls(s, needle):
    return [sql for sql, a in s['exec'] if needle in sql]


async def trader_rules():
    # C1. Otro proceso ya reclamó el cierre: no se envía una segunda orden
    s = {'exec': [], 'already_claimed': True}
    c = rp.FakeClient(position={'size': '1', 'avgPrice': '100'}, order_status='Filled', price=101.0)
    ok = await RealTrader(ClaimPool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    check('C1: cierre ya reclamado por otro -> False y ninguna orden enviada', ok is False and not c.orders, (ok, c.orders))
    claim = sqls(s, "SET status = 'pending_close'")
    check("C1: el reclamo exige status 'open'", bool(claim) and "status = 'open'" in claim[0].split('WHERE')[1], claim)

    # C2. Cierre normal: el registro final exige 'pending_close' (no pisa un cierre ya registrado)
    s = {'exec': []}
    c = rp.FakeClient(position={'size': '1', 'avgPrice': '100'}, order_status='Filled', price=101.0)
    ok = await RealTrader(ClaimPool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    fin = [q for q in sqls(s, 'UPDATE real_trades') if 'close_order_id' in q]
    check("C2: cierre normal -> una orden y el UPDATE final exige status 'pending_close'",
          ok is True and len(c.orders) == 1 and bool(fin) and re.search(r"status\s*=\s*'pending_close'", fin[0].split('WHERE')[1]),
          (ok, len(c.orders), fin[0].split('WHERE')[1].strip() if fin else None))

    # C3. Monitor: 'pending_close' sin confirmar con la posición viva -> vuelve a 'open' y sigue gestionándose
    s = {'exec': []}
    t = dict(rp.trade(), status='pending_close')
    c = rp.FakeClient(position=rp.position(), price=100.5)
    await RealTrader(ClaimPool(s))._monitor_single_trade(t, c, {'BTCUSDT': 100.5}, 7)
    back = [(q, a) for q, a in s['exec'] if "SET status='open'" in q.replace(' = ', '=')]
    check("C3: monitor -> UPDATE status='open' solo si sigue 'pending_close'",
          bool(back) and "status='pending_close'" in back[0][0].split('WHERE')[1].replace(' ', ''), back)
    check('C3: sin orden de cierre (las reglas normales no cerraban)', not c.orders, c.orders)

    # C4. Monitor: posición cerrada y sin closed-pnl -> 'orphaned' solo si seguía abierto
    s = {'exec': []}
    c = rp.FakeClient(position=None, history=[])
    await RealTrader(ClaimPool(s))._monitor_single_trade(rp.trade(), c, {'BTCUSDT': 100.0}, 7)
    orph = sqls(s, "status = 'orphaned'")
    check("C4: monitor -> 'orphaned' exige status open/pending_close",
          bool(orph) and "status IN ('open', 'pending_close')" in orph[0].split('WHERE')[1], orph)

    # C5. Reconciliación: sus UPDATE de estado también exigen el estado esperado
    src = open(api.__file__, encoding='utf-8').read()
    m1 = re.search(r"SET status = 'orphaned',.*?WHERE id = \$1([^\"]*)\"\"\"", src, re.S)
    m2 = re.search(r"SET status='failed',\s*error_message='Orphaned sin posicion en Bybit'.*?WHERE id=\$1([^\"]*)\"\"\"", src, re.S)
    check("C5: reconciliación -> 'orphaned' exige open/pending_close",
          bool(m1) and "status IN ('open', 'pending_close')" in m1.group(1), m1.group(1) if m1 else None)
    check("C5: reconciliación -> 'failed' de un orphaned exige status 'orphaned'",
          bool(m2) and "status='orphaned'" in m2.group(1), m2.group(1) if m2 else None)


async def main():
    await endpoints()
    await trader_rules()
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return fails


if __name__ == '__main__':
    sys.exit(1 if asyncio.run(main()) else 0)

"""
Protección de posiciones abiertas (sin DB ni Bybit reales):
  - La apertura guarda el orderLinkId en la fila ANTES de enviar la orden, y la orden lleva ese mismo id.
  - Chequeo de liquidación: si el SL queda más allá del precio de liquidación, se cierra y se avisa.
  - Conciliación de 'pending_open' interrumpidos (reinicio del motor a mitad de una apertura).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_recovery_test.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (fakes compartidos; anula las esperas)
import api.v1.real_trading as api  # noqa: E402
import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import BybitAPIError, RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def events(s):
    return [(a[2], a[1], json.loads(a[3])) for sql, a in s['exec'] if 'INSERT INTO broker_events' in sql]


SUB = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 7, 'user_id': 1, 'subscription_id': 1,
       'paper_strategy_config_id': 9, 'strategy': 'T', 'broker': 'bybit', 'config_params': dict(rp.P)}


class OpenTrader(RealTrader):
    """get_open_trades devuelve la fila recién abierta (para el cierre por riesgo de liquidación)."""

    async def get_open_trades(self, account_id):
        return [dict(rp.trade(), id=77, entry_price=100.2, status='open')]


async def part_open():
    strat = rt_mod.build_strategy({**rp.P, 'symbol': 'BTCUSDT', 'interval': '60'})

    # R1. orderLinkId guardado antes de enviar y usado en la orden
    s = {'exec': []}
    c = rp.FakeClient(fill_on_check=2)
    ok = await RealTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING', c)
    link = s['insert'][-2] if s.get('insert') else None   # el snapshot sigue siendo el último
    sent = c.orders[0][4].get('link_id') if c.orders else None
    check('R1: la fila pending_open guarda el orderLinkId', ok and isinstance(link, str) and link.startswith('tr2-'), link)
    check('R1: la orden lleva ese mismo orderLinkId', sent == link, (sent, link))

    # R2. SL más allá de la liquidación (50x): se abre, se cierra de inmediato (reduceOnly) y se avisa
    s = {'exec': []}
    pos = {'size': '1', 'avgPrice': '100.2', 'liqPrice': '99.5', 'leverage': '50'}
    c = rp.FakeClient(position=pos, order_status='Filled', price=99.9)
    ok = await OpenTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING', c)
    ev = events(s)
    close_orders = [o for o in c.orders if o[4].get('reduce_only')]
    opened = [a for sql, a in s['exec'] if "SET status = 'open'" in sql]
    check('R2: riesgo de liquidación -> open_trade devuelve False', ok is False, ok)
    check('R2: se cierra con reduceOnly', len(close_orders) == 1 and close_orders[0][0] == 'Sell', c.orders)
    check('R2: aviso liquidation_risk (cerrada, con SL, liquidación y apalancamiento)',
          [e[0] for e in ev] == ['liquidation_risk'] and ev[0][2].get('closed') is True
          and ev[0][2].get('liq_price') == 99.5 and ev[0][2].get('leverage') == 50.0, ev)
    check('R2: guarda el apalancamiento real', opened and opened[0][-1] == 50.0, opened[0][-1] if opened else '')

    # R3. Liquidación lejos del SL: apertura normal, sin aviso
    s = {'exec': []}
    c = rp.FakeClient(position={'size': '1', 'avgPrice': '100.2', 'liqPrice': '50', 'leverage': '2'})
    ok = await OpenTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING', c)
    check('R3: liquidación lejos -> abre normal, sin cierre ni aviso',
          ok is True and not events(s) and not [o for o in c.orders if o[4].get('reduce_only')], events(s))

    # R4. Sin liqPrice (margen cruzado sin liquidación calculable) y short
    check('R4: sin liqPrice -> sin riesgo', RealTrader._sl_beyond_liquidation('long', 99.0, 0) is False)
    check('R4: short con SL sobre la liquidación -> riesgo', RealTrader._sl_beyond_liquidation('short', 101.0, 100.8) is True)
    check('R4: short con margen suficiente -> sin riesgo', RealTrader._sl_beyond_liquidation('short', 101.0, 103.0) is False)


# ─────────────────────────── conciliación de pending_open ───────────────────────────
class RecConn(rp.FakeConn):
    async def fetch(self, sql, *a):
        return self.s.get('pending', []) if "status = 'pending_open'" in sql else []

    async def fetchrow(self, sql, *a):
        return None

    async def fetchval(self, sql, *a):
        if 'id<>$3' in sql:
            return self.s.get('other')
        return await super().fetchval(sql, *a)


class RecPool(rp.FakePool):
    async def close(self):
        return None

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return RecConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


class RecClient(rp.FakeClient):
    """order: orden devuelta por orderLinkId (dict, None o 'ERR'); positions: respuestas de get_open_position."""

    def __init__(self, order=None, positions=(), **kw):
        super().__init__(**kw)
        self.order, self.positions, self.link_queries = order, list(positions), []

    async def get_order_by_link_id(self, symbol, link_id):
        self.link_queries.append(link_id)
        if self.order == 'ERR':
            raise BybitAPIError('caída simulada')
        return self.order

    async def get_open_position(self, symbol):
        self.checks += 1
        return self.positions.pop(0) if self.positions else None


def pending(link='tr2-abc'):
    return dict(rp.trade(), id=31, status='pending_open', order_link_id=link,
                entry_time=datetime.now(timezone.utc) - timedelta(minutes=10),
                snapshot=dict(rp.P), config_snapshot=dict(rp.P))


async def reconcile(s, client, settle=True):
    class _Trader(RealTrader):
        async def get_open_trades(self, account_id):
            return []

        async def settle_exchange_close(self, *a, **k):
            return settle

    pool = RecPool(s)

    async def _pool():
        return pool

    api.get_json_pool = _pool
    api.RealTrader = _Trader
    api._build_broker_client = lambda acc: client
    acc = api.AccountPayload(id=7, broker='bybit', account_type='demo', api_key='k', api_secret='s', subscriptions=[])
    return await api.reconcile(api.RealTickRequest(accounts=[acc]), x_internal_api_key=api.INTERNAL_API_KEY)


def sqls(s):
    return [sql for sql, _ in s['exec']]


async def part_reconcile():
    LIVE = {'size': '1', 'avgPrice': '100.3', 'side': 'Buy'}
    FILLED = {'orderId': 'OID9', 'orderStatus': 'Filled', 'avgPrice': '100.3'}

    s = {'exec': [], 'pending': [pending()]}
    c = RecClient(order=FILLED, positions=[LIVE])
    await reconcile(s, c)
    ev = events(s)
    check('P1: orden ejecutada y posición viva -> adoptada (kind=pending)',
          [e[0] for e in ev] == ['reconcile_adopted'] and ev[0][2].get('kind') == 'pending' and ev[0][2].get('protected') is True, ev)
    check('P1: consultó SU orden por orderLinkId', c.link_queries == ['tr2-abc'], c.link_queries)
    check('P1: queda open con SL de la estrategia y order_id de Bybit',
          any("status='open'" in q and 'original_sl' in q for q in sqls(s)) and any('SET order_id' in q for q in sqls(s)), sqls(s))

    s = {'exec': [], 'pending': [pending()]}
    c = RecClient(order=None, positions=[LIVE])
    await reconcile(s, c)
    check('P2: la orden no existe en Bybit -> failed + reconcile_discarded, sin mirar posiciones',
          [e[0] for e in events(s)] == ['reconcile_discarded'] and any("status='failed'" in q for q in sqls(s)) and c.checks == 0,
          (events(s), c.checks))

    s = {'exec': [], 'pending': [pending()]}
    c = RecClient(order='ERR')
    await reconcile(s, c)
    check('P3: Bybit no responde -> no se toca nada', not events(s) and not any('UPDATE real_trades' in q for q in sqls(s)), sqls(s))

    s = {'exec': [], 'pending': [pending()]}
    c = RecClient(order=FILLED, positions=[None])
    await reconcile(s, c, settle=True)
    check('P4: ejecutada y ya cerrada (tocó el SL) -> se liquida con Bybit',
          [e[0] for e in events(s)] == ['reconcile_closed'] and any("SET status='open', entry_price" in q for q in sqls(s)), events(s))

    s = {'exec': [], 'pending': [pending()]}
    c = RecClient(order=FILLED, positions=[None])
    await reconcile(s, c, settle=None)
    check('P5: ejecutada y cerrada sin closed-pnl aún -> orphaned (la conciliación lo reintenta)',
          not events(s) and any("status='orphaned'" in q and 'apertura interrumpida' in q for q in sqls(s)), sqls(s))

    s = {'exec': [], 'pending': [pending(link=None)]}
    c = RecClient(positions=[None])
    await reconcile(s, c)
    check('P6: fila antigua sin orderLinkId y sin posición -> failed',
          [e[0] for e in events(s)] == ['reconcile_discarded'] and not c.link_queries, events(s))

    s = {'exec': [], 'pending': [pending(link=None)], 'other': 12}
    c = RecClient(positions=[LIVE])
    await reconcile(s, c)
    check('P7: sin orderLinkId y la posición ya la gestiona otro trade -> failed (no se duplica)',
          [e[0] for e in events(s)] == ['reconcile_discarded'], events(s))

    s = {'exec': [], 'pending': [pending(link=None)]}
    c = RecClient(positions=[LIVE])
    await reconcile(s, c)
    check('P8: sin orderLinkId, posición viva y sin otro trade -> adoptada',
          [e[0] for e in events(s)] == ['reconcile_adopted'], events(s))


async def main():
    await part_open()
    await part_reconcile()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

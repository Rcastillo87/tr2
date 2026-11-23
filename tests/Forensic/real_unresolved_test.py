"""
Ciclo 5 · P0 (p95): ninguna posición viva queda fuera del control de TR2 (sin DB ni Bybit reales).
  C5-14  orden 'Cancelled' con parte ejecutada (cumExecQty > 0): nunca 'failed'; se adopta con el tamaño real o se liquida.
  C5-15  apertura ejecutada que no se pudo guardar: open_trade no informa «abierta» y avisa.
  C5-16  'orphaned' cuenta en el máximo de operaciones; con una operación en estado dudoso la cuenta no abre (D-50).
  C5-17  adopción sin SL/TP confirmado por Bybit: protected=False (nunca «protegida» sin confirmar).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_unresolved_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (fakes compartidos; anula las esperas)
import real_recovery_test as rr  # noqa: E402  (fakes de la conciliación)
import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


LIVE_PART = {'size': '0.4', 'avgPrice': '100.3', 'side': 'Buy'}
CANCELLED_PART = {'orderId': 'OID7', 'orderStatus': 'Cancelled', 'avgPrice': '100.3', 'cumExecQty': '0.4'}
CANCELLED_NONE = {'orderId': 'OID8', 'orderStatus': 'Cancelled', 'avgPrice': '0', 'cumExecQty': '0'}


def updates(s, needle):
    return [(q, a) for q, a in s['exec'] if needle in q]


async def part_recovery():
    # C5-14: pending_open cuya orden quedó Cancelled tras llenarse en parte; la posición sigue viva
    s = {'exec': [], 'pending': [rr.pending()]}
    c = rr.RecClient(order=CANCELLED_PART, positions=[LIVE_PART])
    await rr.reconcile(s, c)
    ev = rr.events(s)
    adopt = updates(s, "SET status='open', entry_price=$1, sl=$2")
    check('U1: Cancelled con 0,4 ejecutado y posición viva -> adoptada (no failed)',
          [e[0] for e in ev] == ['reconcile_adopted'] and not updates(s, "status='failed'"), ev)
    check('U1: guarda el tamaño real de Bybit (0,4), no el pedido', adopt and 0.4 in adopt[0][1], adopt[0][1] if adopt else '')
    check('U1: consultó la posición (antes no la miraba por estar Cancelled)', c.checks >= 1, c.checks)

    s = {'exec': [], 'pending': [rr.pending()]}
    c = rr.RecClient(order=CANCELLED_PART, positions=[None])
    await rr.reconcile(s, c, settle=True)
    check('U2: Cancelled con parte ejecutada y posición ya cerrada -> se liquida con Bybit (no failed)',
          [e[0] for e in rr.events(s)] == ['reconcile_closed'] and not updates(s, "status='failed'"), rr.events(s))

    s = {'exec': [], 'pending': [rr.pending()]}
    c = rr.RecClient(order=CANCELLED_NONE, positions=[None])
    await rr.reconcile(s, c)
    check('U3: Cancelled sin nada ejecutado -> failed (como siempre)',
          [e[0] for e in rr.events(s)] == ['reconcile_discarded'] and updates(s, "status='failed'"), rr.events(s))

    # C5-17: Bybit no acepta el SL/TP al adoptar
    class NoStop(rr.RecClient):
        async def set_trading_stop(self, symbol, sl, tp=None, **k):
            return False
    s = {'exec': [], 'pending': [rr.pending()]}
    c = NoStop(order={'orderId': 'OID9', 'orderStatus': 'Filled', 'avgPrice': '100.3', 'cumExecQty': '1'},
               positions=[{'size': '1', 'avgPrice': '100.3', 'side': 'Buy'}])
    await rr.reconcile(s, c)
    ev = rr.events(s)
    check('U4: adopción sin SL/TP confirmado -> protected=False (el monitor reintenta y avisa)',
          [e[0] for e in ev] == ['reconcile_adopted'] and ev[0][2].get('protected') is False
          and updates(s, "SET status='open', entry_price=$1, sl=$2"), ev)
    s = {'exec': [], 'pending': [rr.pending()]}
    c = rr.RecClient(order={'orderId': 'OID9', 'orderStatus': 'Filled', 'avgPrice': '100.3', 'cumExecQty': '1'},
                     positions=[{'size': '1', 'avgPrice': '100.3', 'side': 'Buy'}])
    await rr.reconcile(s, c)
    check('U4b: con SL/TP aceptado -> protected=True', rr.events(s)[0][2].get('protected') is True, rr.events(s))


class OrphanConn(rr.RecConn):
    async def fetch(self, sql, *a):
        if "rt.status = 'orphaned'" in sql:
            return self.s.get('orphans', [])
        return await super().fetch(sql, *a)


class OrphanPool(rr.RecPool):
    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return OrphanConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


async def part_orphan():
    # C5-14: 'orphaned' de apertura sin posición, pero su orden se ejecutó en parte: se liquida, no failed
    orphan = dict(rr.pending(), status='orphaned', error_message='No confirmada tras 3 verificaciones (38s)')
    s = {'exec': [], 'pending': [], 'orphans': [orphan]}
    c = rr.RecClient(order=CANCELLED_PART, positions=[None])
    rr.RecPool, saved = OrphanPool, rr.RecPool
    try:
        await rr.reconcile(s, c, settle=True)
    finally:
        rr.RecPool = saved
    check('U5: orphaned sin posición con la orden ejecutada en parte -> se liquida con Bybit (no failed)',
          [e[0] for e in rr.events(s)] == ['reconcile_closed'] and not updates(s, "status='failed'"), rr.events(s))
    s = {'exec': [], 'pending': [], 'orphans': [dict(orphan)]}
    c = rr.RecClient(order=CANCELLED_NONE, positions=[None])
    rr.RecPool = OrphanPool
    try:
        await rr.reconcile(s, c)
    finally:
        rr.RecPool = saved
    check('U5b: orphaned sin posición y orden sin ejecutar -> failed (como siempre)',
          updates(s, "status='failed'") and [e[0] for e in rr.events(s)] == ['reconcile_discarded'], rr.events(s))


async def part_open():
    strat = rt_mod.build_strategy({**rp.P, 'symbol': 'BTCUSDT', 'interval': '60'})

    # C5-14 en la apertura: Bybit muestra la orden Cancelled con parte ejecutada pero todavía no la posición
    class PartClient(rp.FakeClient):
        async def get_order(self, symbol, order_id=None, link_id=None):
            return {'orderStatus': 'Cancelled', 'avgPrice': '100.3', 'cumExecQty': '0.4'}
    s = {'exec': []}
    c = PartClient(position=None)
    ok = await RealTrader(rp.FakePool(s)).open_trade(rr.SUB, strat, 'long', 100.0, 'RANGING', c)
    ev = [e[0] for e in rr.events(s)]
    check('U6: apertura Cancelled con parte ejecutada y sin posición visible -> orphaned (no failed ni open_rejected)',
          ok is False and updates(s, "status='orphaned'") and not updates(s, "status='failed'") and 'open_rejected' not in ev,
          (ev, [q[:60] for q, _ in s['exec'] if 'UPDATE real_trades' in q]))

    class DeadClient(rp.FakeClient):
        async def get_order(self, symbol, order_id=None, link_id=None):
            return {'orderStatus': 'Cancelled', 'avgPrice': '0', 'cumExecQty': '0'}
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).open_trade(rr.SUB, strat, 'long', 100.0, 'RANGING', DeadClient(position=None))
    check('U6b: Cancelled sin nada ejecutado -> failed + open_rejected (como siempre)',
          ok is False and updates(s, "status='failed'") and 'open_rejected' in [e[0] for e in rr.events(s)])

    # C5-15: la posición se abrió en Bybit pero la fila no pasa a 'open' (4 intentos)
    class FailOpenConn(rp.FakeConn):
        async def execute(self, sql, *a):
            if "SET status = 'open'" in sql:
                raise RuntimeError('base caída')
            return await super().execute(sql, *a)

    class FailOpenPool(rp.FakePool):
        def acquire(self):
            pool = self

            class _C:
                async def __aenter__(self_):
                    return FailOpenConn(pool.s)

                async def __aexit__(self_, *e):
                    return False
            return _C()
    s = {'exec': []}
    ok = await RealTrader(FailOpenPool(s)).open_trade(rr.SUB, strat, 'long', 100.0, 'RANGING',
                                                      rp.FakeClient(position={'size': '1', 'avgPrice': '100.2'}))
    ev = rr.events(s)
    check('U7: ejecutada en Bybit y sin poder guardarla -> no devuelve «abierta» y avisa open_unconfirmed',
          ok is False and [e[0] for e in ev] == ['open_unconfirmed'] and 'base' in (ev[0][2].get('reason') or ''), (ok, ev))


class LimitConn:
    def __init__(self, s):
        self.s = s

    async def fetchrow(self, sql, *a):
        if 'FROM broker_accounts' in sql:
            return {'max_monthly_loss_pct': 10, 'max_open_trades': self.s.get('max', 3), 'month_start_balance': None,
                    'month_start_at': None}
        if "status = 'orphaned'" in sql:
            self.s['unresolved_sql'] = sql
            return self.s.get('unresolved')
        return None

    async def fetchval(self, sql, *a):
        self.s.setdefault('count_sql', sql)
        return self.s.get('count', 0)


class LimitPool:
    def __init__(self, s):
        self.s = s

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return LimitConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


async def part_limits():
    s = {'count': 1}
    r = await RealTrader(LimitPool(s)).entry_limit_reason(7)
    check('U8: sin operaciones dudosas y bajo el máximo -> puede abrir', r is None, r)
    check('U9: las orphaned cuentan en el máximo de operaciones abiertas', "'orphaned'" in s.get('count_sql', ''), s.get('count_sql'))
    s = {'count': 1, 'unresolved': {'id': 44, 'symbol': 'ETHUSDT', 'status': 'orphaned'}}
    r = await RealTrader(LimitPool(s)).entry_limit_reason(7)
    check('U10: con una operación en estado dudoso la cuenta no abre (D-50) y dice cuál',
          r is not None and '#44' in r and 'ETHUSDT' in r and 'sin confirmar' in r, r)
    check('U11: estado dudoso = orphaned o pending_open de más de 3 min (misma regla en Laravel)',
          "status = 'orphaned'" in s['unresolved_sql'] and "interval '3 minutes'" in s['unresolved_sql'])


def part_static():
    model = (ROOT / 'app' / 'Models' / 'RealTrade.php').read_text(encoding='utf-8')
    tick = (ROOT / 'app' / 'Jobs' / 'RealTradingTickJob.php').read_text(encoding='utf-8')
    wd = (ROOT / 'app' / 'Console' / 'Commands' / 'CollectorWatchdog.php').read_text(encoding='utf-8')
    check('S1: Laravel: misma regla de estado dudoso (orphaned o pending_open > 3 min)',
          'function scopeUnresolved' in model and "PENDING_OPEN_STALE_MIN = 3" in model and rt_mod.UNRESOLVED_SQL.count('3 minutes') == 1)
    check('S2: el tick adelanta la conciliación (a lo sumo una por minuto) si hay operaciones dudosas',
          "RealTrade::query()->unresolved()->exists() && Cache::add('real_reconcile_early', 1, 55)" in tick
          and 'RealTradingReconcileJob::dispatch()' in tick)
    check('S3: el vigilante avisa al admin si una sigue dudosa más de 15 min y cierra el aviso al resolverse',
          "openIncident('real_unresolved'" in wd and "resolveIncident('real_unresolved'" in wd and "'real_unresolved_min'] ?? 15" in wd)


async def main():
    await part_recovery()
    await part_orphan()
    await part_open()
    await part_limits()
    part_static()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

"""
R-09 (p69): cierres hechos por Bybit (SL/TP/trailing nativos) que detecta el monitor.
- M: el closed-pnl se busca desde la APERTURA. Con updated_at, una escritura posterior al cierre dejaba el tramo
  fuera y el trade quedaba 'orphaned' (6 de 6 cierres de Bybit en producción, 09–17-nov). Un tramo de una operación
  anterior del mismo símbolo y precio (antes de la apertura) no se mezcla.
- C: la conciliación de un 'orphaned' de cierre ya no pone la etiqueta fija 'reconciled_sl_tp_bybit': el motivo sale
  del precio de salida contra SL/TP (la misma regla del monitor) y queda 'close_recovered' en el historial.
Sin DB ni Bybit. Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_close_detect_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (fakes compartidos; anula las esperas)
import real_recovery_test as rr  # noqa: E402
import api.v1.real_trading as api  # noqa: E402
from trading.real_trader import RealTrader, epoch_ms  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def rec(t, exit_price, size=1.0, pnl=-1.2, entry=100.0):
    ms = epoch_ms(t)
    return {'avgEntryPrice': str(entry), 'createdTime': str(ms), 'updatedTime': str(ms), 'closedSize': str(size),
            'cumExitValue': str(exit_price * size), 'closedPnl': str(pnl)}


class SinceClient(rp.FakeClient):
    """Como Bybit: devuelve solo los tramos con createdTime >= since (y mismo precio de entrada)."""

    def __init__(self, records, **kw):
        super().__init__(position=None, **kw)
        self.records, self.since = records, []

    async def get_closed_pnl_history(self, symbol, entry, since, limit=20):
        self.since.append(since)
        return [r for r in self.records if int(r['createdTime']) >= since
                and abs(float(r['avgEntryPrice']) - entry) / entry <= 0.0005]


def closed(s):
    return [a for sql, a in s['exec'] if "SET status='closed'" in sql]


def orphaned(s):
    return [a for sql, a in s['exec'] if "status = 'orphaned'" in sql]


async def monitor(trade, client):
    s = {'exec': []}
    out = await RealTrader(rp.FakePool(s))._monitor_single_trade(trade, client, {'BTCUSDT': 98.9}, 1)
    return s, out


async def part_monitor():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    entry_t = now - timedelta(hours=1)
    close_t = now - timedelta(minutes=30)

    # M1. Escritura posterior al cierre (updated_at después del tramo): igual se encuentra y se cierra con su motivo
    tr = dict(rp.trade(), entry_time=entry_t, updated_at=now)
    c = SinceClient([rec(close_t, 98.9)])
    s, out = await monitor(tr, c)
    cl = closed(s)
    check('M1 updated_at posterior al cierre -> se liquida (no queda orphaned)', cl and not orphaned(s) and out['closed'] == 1,
          {'closed': len(cl), 'orphaned': len(orphaned(s))})
    check('M1 motivo según el precio: 98,9 <= SL 99 en un long -> stop_loss', cl and cl[0][1] == 'stop_loss', cl[0][1] if cl else '')
    check('M2 busca desde la apertura', c.since and c.since[0] == epoch_ms(entry_t), (c.since[:1], epoch_ms(entry_t)))

    # M3. Tramo de una operación ANTERIOR del mismo símbolo y precio (antes de la apertura): no se suma
    tr = dict(rp.trade(), entry_time=entry_t, updated_at=close_t)
    c = SinceClient([rec(entry_t - timedelta(hours=3), 104.5, pnl=4.4), rec(close_t, 104.1, pnl=4.0)])
    s, _ = await monitor(tr, c)
    cl = closed(s)
    check('M3 el cierre anterior no se mezcla: precio 104,1 y motivo take_profit_1',
          cl and abs(cl[0][0] - 104.1) < 1e-9 and cl[0][1] == 'take_profit_1', (cl[0][0], cl[0][1]) if cl else '')

    # M4. Bybit aún sin el tramo: orphaned (como antes), para la conciliación
    tr = dict(rp.trade(), entry_time=entry_t, updated_at=close_t)
    s, out = await monitor(tr, SinceClient([]))
    check('M4 sin closed-pnl todavía -> orphaned (la conciliación lo recupera)', orphaned(s) and not closed(s))


async def part_reconcile():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = dict(rp.trade(), id=85, status='orphaned', entry_time=now - timedelta(hours=2),
               error_message='Posicion cerrada en Bybit, no se pudo obtener pnl real (closed-pnl vacio tras reintento)',
               snapshot=dict(rp.P))
    seen = {}

    class OrphConn(rr.RecConn):
        async def fetch(self, sql, *a):
            return [row] if "rt.status = 'orphaned'" in sql else []

    class OrphPool(rr.RecPool):
        def acquire(self):
            pool = self

            class _C:
                async def __aenter__(self_):
                    return OrphConn(pool.s)

                async def __aexit__(self_, *e):
                    return False
            return _C()

    class _Trader(RealTrader):
        async def get_open_trades(self, account_id):
            return []

        async def settle_exchange_close(self, trade, client, account_id, since_time_ms, exit_reason=None):
            seen.update(exit_reason=exit_reason, since=since_time_ms)
            return True

    s = {'exec': []}
    pool = OrphPool(s)

    async def _pool():
        return pool

    api.get_json_pool, api.RealTrader, api._build_broker_client = _pool, _Trader, (lambda acc: rp.FakeClient())
    acc = api.AccountPayload(id=7, broker='bybit', account_type='demo', api_key='k', api_secret='s', subscriptions=[])
    await api.reconcile(api.RealTickRequest(accounts=[acc]), x_internal_api_key=api.INTERNAL_API_KEY)
    check('C1 orphaned de cierre: sin etiqueta fija (el motivo sale del precio)', 'exit_reason' in seen and seen['exit_reason'] is None, seen)
    check('C2 busca desde la apertura', seen.get('since') == epoch_ms(row['entry_time']))
    audit = s.get('audit') or []
    check("C3 queda 'close_recovered' en el historial", any(e.get('action') == 'close_recovered' for e in audit),
          [e.get('action') for e in audit])


asyncio.run(part_monitor())
asyncio.run(part_reconcile())
print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

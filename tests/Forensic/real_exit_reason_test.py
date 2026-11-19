"""
R-16 (p70): motivo de salida de los cierres hechos por Bybit según la ORDEN de cierre (historial de órdenes:
stopOrderType / createType), no solo por precio. En producción 6 de 10 cierres quedaban 'closed_other': TP/SL
ejecutados con deslizamiento (p. ej. #92 short: salida 0,13080 con TP 0,1307109) y el trailing nativo (su SL móvil no
está en la DB). Sin dato de Bybit se usa la regla por precio de siempre. Incluye el endpoint de reclasificación de los
históricos y la ventana de tiempo del closed-pnl (Bybit responde 7 días si no se le pasa).
Sin DB ni Bybit. Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_exit_reason_test.py
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
import trading.real_trader as rt  # noqa: E402
from trading.real_trader import RealTrader, epoch_ms  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


ctr = getattr(rt, 'close_trigger_reason', None)
lco = getattr(rt, 'last_close_order_id', None)
check('E0 existen close_trigger_reason y last_close_order_id', ctr is not None and lco is not None)
if ctr is None or lco is None:
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)

# ── Tabla de motivos ──
cases = [({'stopOrderType': 'TakeProfit'}, False, 'take_profit_1'),
         ({'stopOrderType': 'PartialTakeProfit'}, False, 'take_profit_1'),
         ({'stopOrderType': 'StopLoss'}, False, 'stop_loss'),
         ({'stopOrderType': 'PartialStopLoss'}, False, 'stop_loss'),
         ({'stopOrderType': 'StopLoss'}, True, 'trailing_stop'),
         ({'stopOrderType': 'TrailingStop'}, False, 'trailing_stop'),
         ({'stopOrderType': 'UNKNOWN', 'createType': 'CreateByTakeProfit'}, False, 'take_profit_1'),
         ({'stopOrderType': '', 'createType': 'CreateByTrailingStop'}, False, 'trailing_stop'),
         ({'stopOrderType': '', 'createType': 'CreateByTrailingProfit'}, False, 'trailing_stop'),   # el que manda Bybit (#93)
         ({'stopOrderType': 'UNKNOWN', 'createType': 'CreateByUser'}, False, None),
         (None, False, None)]
bad = [(o, t, ctr(o, t), want) for o, t, want in cases if ctr(o, t) != want]
check('E1 stopOrderType/createType -> motivo (StopLoss con trailing del bot = trailing_stop; manual/desconocido = None)', not bad, bad)
check('E2 orderId del último tramo', lco([{'orderId': 'A', 'updatedTime': '100'}, {'orderId': 'B', 'updatedTime': '300'},
                                         {'orderId': 'C', 'updatedTime': '200'}]) == 'B' and lco([]) is None)

now = datetime.now(timezone.utc).replace(tzinfo=None)


def rec(t, exit_price, order_id='OC1', entry=100.0):
    ms = epoch_ms(t)
    return {'orderId': order_id, 'avgEntryPrice': str(entry), 'createdTime': str(ms), 'updatedTime': str(ms),
            'closedSize': '1', 'cumExitValue': str(exit_price), 'closedPnl': '-0.5'}


class OrderClient(rp.FakeClient):
    def __init__(self, records, order, **kw):
        super().__init__(position=None, **kw)
        self.records, self.order, self.asked = records, order, []

    async def get_closed_pnl_history(self, symbol, entry, since, limit=20, end_time_ms=None):
        return [r for r in self.records if int(r['createdTime']) >= since]

    async def get_close_order(self, symbol, order_id, around_ms):
        self.asked.append((order_id, around_ms))
        return self.order


def closed(s):
    return [a for sql, a in s['exec'] if "SET status='closed'" in sql]


async def settle(trade, client):
    s = {'exec': []}
    out = await RealTrader(rp.FakePool(s)).settle_exchange_close(trade, client, 1, epoch_ms(trade['entry_time']))
    return s, out


async def part_settle():
    entry_t, close_t = now - timedelta(hours=2), now - timedelta(minutes=5)
    # S1 (#92): short, salida 0,1308 apenas por encima del TP 0,1307109 (TP a mercado con deslizamiento)
    tr = dict(rp.trade(), side='short', entry_price=0.13687, sl=0.14029175, tp=0.13071085, entry_time=entry_t)
    c = OrderClient([rec(close_t, 0.1308, entry=0.13687)], {'stopOrderType': 'TakeProfit', 'createType': 'CreateByTakeProfit'})
    s, _ = await settle(tr, c)
    cl = closed(s)
    check('S1 TP ejecutado con deslizamiento (#92) -> take_profit_1 (por precio era closed_other)', cl and cl[0][1] == 'take_profit_1',
          cl[0][1] if cl else '')
    check('S1 consulta la orden del último tramo cerca de la hora del cierre',
          c.asked and c.asked[0][0] == 'OC1' and abs(c.asked[0][1] - epoch_ms(close_t)) < 2000, c.asked)
    src = [e for e in (s.get('audit') or []) if e.get('action') == 'exit_reason_source']
    check("S1 deja 'exit_reason_source' (bybit, con stopOrderType) en el historial",
          src and src[-1]['data'].get('source') == 'bybit' and src[-1]['data'].get('stop_order_type') == 'TakeProfit', src)

    # S2 (#93): short, salida entre SL y TP: trailing nativo
    tr = dict(rp.trade(), side='short', entry_price=1931.01, sl=1931.01, tp=1873.0797, entry_time=entry_t)
    s, _ = await settle(tr, OrderClient([rec(close_t, 1895.12, entry=1931.01)], {'stopOrderType': 'TrailingStop'}))
    cl = closed(s)
    check('S2 trailing nativo (#93) -> trailing_stop', cl and cl[0][1] == 'trailing_stop', cl[0][1] if cl else '')

    # S3 Bybit sin dato (cierre manual): regla por precio, igual que antes
    tr = dict(rp.trade(), entry_time=entry_t)    # long, SL 99, TP 104
    s, _ = await settle(tr, OrderClient([rec(close_t, 101.0)], {'stopOrderType': 'UNKNOWN', 'createType': 'CreateByUser'}))
    cl = closed(s)
    src = [e for e in (s.get('audit') or []) if e.get('action') == 'exit_reason_source']
    check('S3 cierre manual (sin TP/SL/trailing en la orden) -> closed_other por precio, fuente price',
          cl and cl[0][1] == 'closed_other' and src and src[-1]['data'].get('source') == 'price', (cl[0][1] if cl else '', src))

    # S4 Cliente sin la consulta (compatibilidad) y SL por precio
    s, _ = await settle(dict(rp.trade(), entry_time=entry_t), rp.FakeClient(history=[rec(close_t, 98.8)]))
    cl = closed(s)
    check('S4 sin consulta de órdenes -> regla por precio (98,8 <= SL 99 -> stop_loss)', cl and cl[0][1] == 'stop_loss',
          cl[0][1] if cl else '')


# ── Endpoint de reclasificación de los históricos ──
async def part_reclassify():
    rows = [
        {'id': 92, 'symbol': 'ENAUSDT', 'side': 'short', 'entry_price': 0.13687, 'entry_time': now - timedelta(days=5),
         'exit_time': now - timedelta(days=5) + timedelta(hours=10), 'exit_price': 0.1308, 'trailing_applied': False},
        {'id': 94, 'symbol': 'DOGEUSDT', 'side': 'short', 'entry_price': 0.06459, 'entry_time': now - timedelta(days=5),
         'exit_time': now - timedelta(days=5) + timedelta(hours=2), 'exit_price': 0.064, 'trailing_applied': False},
    ]
    orders = {'ENAUSDT': {'stopOrderType': 'TakeProfit'}, 'DOGEUSDT': {'stopOrderType': 'UNKNOWN', 'createType': 'CreateByUser'}}

    class RConn(rr.RecConn):
        async def fetch(self, sql, *a):
            return rows if "exit_reason = 'closed_other'" in sql else []

    class RPool(rr.RecPool):
        def acquire(self):
            pool = self

            class _C:
                async def __aenter__(self_):
                    return RConn(pool.s)

                async def __aexit__(self_, *e):
                    return False
            return _C()

    class RClient(rp.FakeClient):
        windows = []

        async def get_closed_pnl_history(self, symbol, entry, since, limit=20, end_time_ms=None):
            RClient.windows.append((since, end_time_ms))
            r = next(x for x in rows if x['symbol'] == symbol)
            return [rec(r['exit_time'], float(r['exit_price']), order_id='O-' + symbol, entry=float(r['entry_price']))]

        async def get_close_order(self, symbol, order_id, around_ms):
            return orders[symbol]

    async def run(apply):
        s = {'exec': []}
        pool = RPool(s)

        async def _pool():
            return pool
        api.get_json_pool, api.RealTrader, api._build_broker_client = _pool, RealTrader, (lambda acc: RClient())
        acc = api.AccountPayload(id=11, broker='bybit', account_type='demo', api_key='k', api_secret='s', subscriptions=[])
        out = await api.reclassify_exits(api.ReclassifyRequest(accounts=[acc], apply=apply), x_internal_api_key=api.INTERNAL_API_KEY)
        return s, out

    s, out = await run(False)
    res = {r['trade_id']: r for r in out['results']}
    upd = [a for sql, a in s['exec'] if 'SET exit_reason' in sql]
    check('R1 sin apply: propone #92 -> take_profit_1, #94 sin dato; no escribe nada',
          res[92]['to'] == 'take_profit_1' and res[94]['to'] is None and not upd, (res, upd))
    check('R2 el closed-pnl se pide con ventana hasta el cierre (Bybit da 7 días sin ventana)',
          RClient.windows and all(w[1] is not None and w[1] - w[0] <= 7 * 86_400_000 for w in RClient.windows), RClient.windows)
    s, out = await run(True)
    upd = [a for sql, a in s['exec'] if 'SET exit_reason' in sql]
    audit = s.get('audit') or []
    check('R3 con apply: actualiza solo #92 (la de dato de Bybit) y solo si sigue closed_other',
          upd == [('take_profit_1', 92)] and any("exit_reason = 'closed_other'" in sql for sql, a in s['exec'] if 'SET exit_reason' in sql), upd)
    check("R4 deja 'exit_reason_corrected' con la orden de Bybit en el historial",
          any(e.get('action') == 'exit_reason_corrected' and e['data'].get('to') == 'take_profit_1'
              and e['data'].get('stop_order_type') == 'TakeProfit' for e in audit), [e.get('action') for e in audit])


# ── Ventana del closed-pnl en el cliente real ──
async def part_window():
    seen = []

    class Resp:
        def json(self):
            return {'retCode': 0, 'result': {'list': []}}

    class AC:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            seen.append(url)
            return Resp()

    orig = rt.httpx.AsyncClient
    rt.httpx.AsyncClient = AC
    try:
        c = rt.BybitClient(api_key='k', api_secret='s', account_type='demo')
        end = epoch_ms(now)
        await c.get_closed_pnl_history('ETHUSDT', 100.0, end - 20 * 86_400_000, limit=50, end_time_ms=end)
        await c.get_closed_pnl_history('ETHUSDT', 100.0, end - 3600_000)
    finally:
        rt.httpx.AsyncClient = orig
    import urllib.parse as up
    q1 = dict(up.parse_qsl(up.urlparse(seen[0]).query)) if seen else {}
    q2 = dict(up.parse_qsl(up.urlparse(seen[1]).query)) if len(seen) > 1 else {}
    check('W1 con end_time_ms: startTime/endTime dentro de 7 días (operación de más de 7 días: los últimos 7)',
          'startTime' in q1 and int(q1['endTime']) - int(q1['startTime']) <= 7 * 86_400_000, q1)
    check('W2 sin end_time_ms: igual que antes (sin ventana)', 'startTime' not in q2 and 'endTime' not in q2, q2)


asyncio.run(part_settle())
asyncio.run(part_reclassify())
asyncio.run(part_window())
print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

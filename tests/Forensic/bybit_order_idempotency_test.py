"""
Órdenes idempotentes en Bybit (orderLinkId, reduceOnly, firma por intento).
Sin red y sin órdenes reales: Bybit simulado con httpx.MockTransport.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/bybit_order_idempotency_test.py
"""
import asyncio
import hashlib
import hmac
import itertools
import json
import os
import re
import sys
from urllib.parse import parse_qsl

sys.path.insert(0, os.getcwd())  # ejecutar desde python-engine/

import httpx  # noqa: E402

import trading.bybit_client as bc_mod  # noqa: E402
import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import BybitAPIError, BybitClient  # noqa: E402

_real_sleep = asyncio.sleep


async def _no_sleep(*_a, **_k):
    await _real_sleep(0)

asyncio.sleep = _no_sleep  # las esperas entre reintentos no hacen falta en el test


class _Clock:  # timestamps distintos y crecientes en cada firma
    _t = itertools.count(1_800_000_000)

    @classmethod
    def time(cls):
        return float(next(cls._t))

bc_mod.time = _Clock

KEY, SECRET = 'clave_prueba', 'secreto_prueba'
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class FakeBybit:
    """
    Bybit simulado. `posts` es la secuencia de comportamientos de cada POST /v5/order/create:
      ok        -> crea la orden y responde retCode 0
      lost      -> crea la orden pero la respuesta se pierde (timeout)
      timeout   -> timeout SIN crear la orden
      reject    -> retCode != 0, no crea nada
    Un orderLinkId repetido siempre se rechaza (como Bybit). `query_fail` hace fallar las consultas de órdenes;
    `hidden_queries` oculta las órdenes durante las primeras N consultas (retraso de visibilidad).
    """

    def __init__(self, posts, query_fail=False, history_fail=False, hidden_queries=0):
        self.posts, self.query_fail, self.history_fail, self.hidden = list(posts), query_fail, history_fail, hidden_queries
        self.orders = {}           # orderLinkId -> orden creada
        self.post_bodies, self.post_ts, self.queries, self.tickers, self.bad_sign = [], [], [], 0, 0

    def _sign_ok(self, req, payload):
        ts, sign = req.headers['X-BAPI-TIMESTAMP'], req.headers['X-BAPI-SIGN']
        expected = hmac.new(SECRET.encode(), (ts + KEY + req.headers['X-BAPI-RECV-WINDOW'] + payload).encode(),
                            hashlib.sha256).hexdigest()
        return sign == expected

    def handler(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == '/v5/market/tickers':
            self.tickers += 1
            return httpx.Response(200, json={'retCode': 0, 'result': {'list': [{'lastPrice': '100'}]}})

        if path == '/v5/order/create':
            payload = req.content.decode()
            if not self._sign_ok(req, payload):
                self.bad_sign += 1
            body = json.loads(payload)
            self.post_bodies.append(body)
            self.post_ts.append(req.headers['X-BAPI-TIMESTAMP'])
            action = self.posts.pop(0) if self.posts else 'ok'
            link = body['orderLinkId']
            if link in self.orders:
                return httpx.Response(200, json={'retCode': 110072, 'retMsg': 'OrderLinkedID is duplicate'})
            if action == 'reject':
                return httpx.Response(200, json={'retCode': 110017, 'retMsg': 'rechazada (simulada)'})
            if action == 'timeout':
                raise httpx.ReadTimeout('timeout simulado', request=req)
            oid = f'OID{len(self.orders) + 1}'
            self.orders[link] = {'orderId': oid, 'orderLinkId': link, 'orderStatus': 'Filled', 'avgPrice': '100'}
            if action == 'lost':
                raise httpx.ReadTimeout('respuesta perdida (simulada)', request=req)
            return httpx.Response(200, json={'retCode': 0, 'result': {'orderId': oid, 'orderLinkId': link}})

        if path in ('/v5/order/realtime', '/v5/order/history'):
            q = req.url.query.decode()
            params = dict(parse_qsl(q))
            if not self._sign_ok(req, q):
                self.bad_sign += 1
            self.queries.append((path, params))
            if self.query_fail or (self.history_fail and path.endswith('history')):
                return httpx.Response(200, json={'retCode': 10016, 'retMsg': 'error interno (simulado)'})
            if self.hidden > 0:
                self.hidden -= 1
                found = None
            elif 'orderLinkId' in params:
                found = self.orders.get(params['orderLinkId'])
            else:
                found = next((o for o in self.orders.values() if o['orderId'] == params.get('orderId')), None)
            return httpx.Response(200, json={'retCode': 0, 'result': {'list': [found] if found else []}})

        return httpx.Response(404, json={'retCode': -1, 'retMsg': f'ruta no simulada {path}'})


def run(fake, coro_factory):
    real_client = httpx.AsyncClient

    def patched(*a, **k):
        k['transport'] = httpx.MockTransport(fake.handler)
        return real_client(*a, **k)

    rt_mod.httpx.AsyncClient = patched
    try:
        return asyncio.run(coro_factory(BybitClient(KEY, SECRET, 'demo')))
    finally:
        rt_mod.httpx.AsyncClient = real_client


def links(fake):
    return {b['orderLinkId'] for b in fake.post_bodies}


# 1. Apertura normal
f = FakeBybit(['ok'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Buy', 0.01))
b = f.post_bodies[0]
check('apertura: 1 envío y orderId devuelto', len(f.post_bodies) == 1 and r == {'orderId': 'OID1', 'orderLinkId': b['orderLinkId']}, r)
check('apertura: lleva orderLinkId válido (<=36, [A-Za-z0-9_-])',
      bool(re.fullmatch(r'[A-Za-z0-9_-]{1,36}', b['orderLinkId'])), b['orderLinkId'])
check('apertura: SL/TP provisionales y sin reduceOnly',
      b.get('stopLoss') == '98.0' and b.get('takeProfit') == '104.0' and 'reduceOnly' not in b, b)
check('apertura: firmas válidas', f.bad_sign == 0, f.bad_sign)

# 2. Bybit la crea pero la respuesta se pierde -> se consulta y NO se reenvía
f = FakeBybit(['lost'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Buy', 0.01))
check('respuesta perdida: una sola orden creada, sin reenvío', len(f.post_bodies) == 1 and len(f.orders) == 1, len(f.post_bodies))
check('respuesta perdida: devuelve la orden que sí existía', r and r['orderId'] == 'OID1' and not r.get('unconfirmed'), r)
check('respuesta perdida: consultó por orderLinkId',
      any(q[1].get('orderLinkId') == f.post_bodies[0]['orderLinkId'] for q in f.queries), f.queries)

# 3. Timeout sin crear -> se verifica que no existe y se reenvía con el MISMO id y firma nueva
f = FakeBybit(['timeout', 'ok'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Sell', 0.01))
check('timeout sin crear: reenvía y crea 1 orden', len(f.post_bodies) == 2 and len(f.orders) == 1 and r['orderId'] == 'OID1', r)
check('timeout sin crear: mismo orderLinkId en ambos envíos', len(links(f)) == 1, links(f))
check('timeout sin crear: firma nueva por intento (timestamps distintos y válidos)',
      len(set(f.post_ts)) == 2 and f.bad_sign == 0, (f.post_ts, f.bad_sign))

# 4. Timeout y la consulta también falla -> estado desconocido, NO se reenvía
f = FakeBybit(['lost'], query_fail=True)
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Buy', 0.01))
check('estado desconocido: no reenvía', len(f.post_bodies) == 1, len(f.post_bodies))
check('estado desconocido: unconfirmed con orderLinkId y sin orderId',
      r and r.get('unconfirmed') and r['orderId'] is None and r['orderLinkId'] == f.post_bodies[0]['orderLinkId'], r)

# 5. Rechazos definitivos -> 3 intentos, None, sin consultas innecesarias
f = FakeBybit(['reject', 'reject', 'reject'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Buy', 0.01))
check('rechazo x3: None, 3 envíos, 0 órdenes', r is None and len(f.post_bodies) == 3 and not f.orders, (r, len(f.post_bodies)))
check('rechazo x3: sin consultas de orden', not f.queries, f.queries)

# 6. Rechazo, rechazo y respuesta perdida en el último -> verificación final la encuentra
f = FakeBybit(['reject', 'reject', 'lost'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Buy', 0.01))
check('perdida en el último intento: verificación final devuelve la orden', r and r['orderId'] == 'OID1', r)

# 7. Retraso de visibilidad: la consulta no la ve, se reenvía y Bybit rechaza el id duplicado -> 1 sola orden
f = FakeBybit(['lost'], hidden_queries=2)
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Buy', 0.01))
check('retraso de visibilidad: Bybit rechaza el duplicado, 1 sola orden', len(f.orders) == 1, len(f.orders))
check('retraso de visibilidad: devuelve la orden creada', r and r['orderId'] == 'OID1', r)

# 8. Cierre: reduceOnly, sin SL/TP provisionales, sin pedir precio
f = FakeBybit(['ok'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Sell', 0.01, reduce_only=True))
b = f.post_bodies[0]
check('cierre: reduceOnly=true', b.get('reduceOnly') is True, b)
check('cierre: sin stopLoss/takeProfit', 'stopLoss' not in b and 'takeProfit' not in b, b)
check('cierre: no consulta el precio', f.tickers == 0, f.tickers)

# 9. Cierre con la posición ya cerrada -> Bybit rechaza el reduceOnly: nada se abre
f = FakeBybit(['reject', 'reject', 'reject'])
r = run(f, lambda c: c.place_market_order('BTCUSDT', 'Sell', 0.01, reduce_only=True))
check('cierre sin posición: None y ninguna orden creada', r is None and not f.orders, r)

# 10. get_order por orderLinkId
f = FakeBybit(['ok'])
async def _go(c):
    res = await c.place_market_order('BTCUSDT', 'Buy', 0.01)
    return res, await c.get_order('BTCUSDT', link_id=res['orderLinkId'])
res, order = run(f, _go)
check('get_order por orderLinkId', order and order['orderId'] == 'OID1', order)
check('get_order sin ids devuelve None', run(FakeBybit([]), lambda c: c.get_order('BTCUSDT')) is None)

# 11. get_order_by_link_id: si history falla y realtime no la ve -> desconocido (excepción), nunca "no existe"
f = FakeBybit([], history_fail=True)
async def _q(c):
    try:
        return await c.get_order_by_link_id('BTCUSDT', 'tr2-x')
    except BybitAPIError:
        return 'ERR'
check('consulta parcial -> BybitAPIError (no "no existe")', run(f, _q) == 'ERR')
check('consulta completa vacía -> None', run(FakeBybit([]), lambda c: c.get_order_by_link_id('BTCUSDT', 'tr2-x')) is None)

print(f"\n{'TODO OK' if not fails else f'{fails} FALLOS'}")
sys.exit(1 if fails else 0)

"""
R-15 (p66): /v1/prices (precios del dashboard) pide los símbolos a Bybit EN PARALELO y con una sola conexión.
Antes iba de a uno: 11 monedas × ~0,3 s = 3,3–4,9 s medidos en producción el 13-nov, y el dashboard (espera 3 s) se
quedaba sin precios. Bybit simulado (sin red): cada pedido tarda 0,3 s.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/live_prices_parallel_test.py
"""
import asyncio
import logging
import os
import sys
import time

sys.path.insert(0, os.getcwd())   # python-engine/
logging.disable(logging.CRITICAL)

import httpx  # noqa: E402
import trading.bybit_client as bc  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


DELAY = 0.3
SYMS = ['1000PEPEUSDT', 'BTCUSDT', 'DOGEUSDT', 'ENAUSDT', 'ETHUSDT', 'LINKUSDT', 'NEARUSDT', 'SOLUSDT', 'SUIUSDT',
        'XRPUSDT', 'ZECUSDT']
PRICE = {s: float(i + 1) for i, s in enumerate(SYMS)}
stats = {'clients': 0, 'requests': 0, 'max_parallel': 0, 'now': 0}


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError('error', request=None, response=None)

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, *a, **k):
        stats['clients'] += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        stats['requests'] += 1
        stats['now'] += 1
        stats['max_parallel'] = max(stats['max_parallel'], stats['now'])
        try:
            await asyncio.sleep(DELAY)
        finally:
            stats['now'] -= 1
        s = params['symbol']
        if s == 'FALLAUSDT':
            return FakeResponse(500, {})
        if s == 'NOEXISTEUSDT':
            return FakeResponse(200, {'result': {'list': []}})
        return FakeResponse(200, {'result': {'list': [{'lastPrice': str(PRICE[s])}]}})


bc.httpx.AsyncClient = FakeClient


def run(symbols):
    for k in ('clients', 'requests', 'max_parallel'):
        stats[k] = 0
    t = time.perf_counter()
    out = asyncio.run(bc.get_current_prices(symbols))
    return out, time.perf_counter() - t


out, dur = run(SYMS)
check('P1 11 monedas: todos los precios correctos', out == PRICE, out)
check(f'P2 11 monedas en < 1 s (en serie serían ~{DELAY * len(SYMS):.1f} s; el dashboard espera 3 s)', dur < 1.0, f'{dur:.2f} s')
check('P3 pedidos en paralelo (los 11 a la vez) y una sola conexión', stats['max_parallel'] == len(SYMS) and stats['clients'] == 1,
      dict(stats))

out, _ = run(['BTCUSDT', 'FALLAUSDT', 'NOEXISTEUSDT', 'ETHUSDT'])
check('P4 un símbolo con error y otro inexistente se omiten; los demás llegan', out == {'BTCUSDT': PRICE['BTCUSDT'], 'ETHUSDT': PRICE['ETHUSDT']}, out)

out, _ = run(['BTCUSDT', 'BTCUSDT', 'ETHUSDT'])
check('P5 símbolos repetidos: un pedido por símbolo', stats['requests'] == 2 and out == {'BTCUSDT': 1.0 * PRICE['BTCUSDT'], 'ETHUSDT': PRICE['ETHUSDT']},
      stats['requests'])

out, _ = run([])
check('P6 lista vacía: {} sin pedidos', out == {} and stats['requests'] == 0)

stats['requests'] = 0
p = asyncio.run(bc.get_current_price('SOLUSDT'))
q = asyncio.run(bc.get_current_price('FALLAUSDT'))
check('P7 get_current_price (Paper) sigue igual: precio o None', p == PRICE['SOLUSDT'] and q is None, (p, q))

print('RESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

"""
C-02: la descarga automática de velas reintenta de forma ACOTADA ante fallos transitorios de Bybit (red, 429, 5xx,
límite de tasa), no reintenta lo que no sirve (403, parámetros) y corta la corrida si Bybit limita la IP.
Sin red: Bybit simulado con httpx.MockTransport; las esperas se registran, no se duermen.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_retry_test.py
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import httpx  # noqa: E402

import collectors.bybit_http as bh  # noqa: E402
import collectors.ohlcv_collector as oc  # noqa: E402

fails = 0
URL = 'https://api.bybit.com/v5/market/kline'
OK_EMPTY = {'retCode': 0, 'result': {'list': []}}


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def scripted(*responses):
    """Transporte que responde en orden (httpx.Response o Exception); el último se repite."""
    calls = []

    def handler(request):
        calls.append(request)
        r = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r
    return httpx.MockTransport(handler), calls


async def run(*responses, **kw):
    transport, calls = scripted(*responses)
    waits = []

    async def fake_sleep(s):
        waits.append(round(s, 3))
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            out = await bh.get_json(client, URL, {'symbol': 'BTCUSDT', 'interval': '1'}, sleep=fake_sleep,
                                    jitter=lambda: 0.0, **kw)
            return out, None, len(calls), waits
        except Exception as e:  # noqa: BLE001 - se clasifica en cada caso
            return None, e, len(calls), waits


def R(status, json=None, headers=None):
    return httpx.Response(status, json=json if json is not None else {}, headers=headers)


async def http_cases():
    out, err, n, w = await run(R(429), R(200, OK_EMPTY))
    check('H1 429 transitorio: reintenta y descarga (2 peticiones, espera 1 s)', out == OK_EMPTY and n == 2 and w == [1.0],
          (err, n, w))
    out, err, n, w = await run(R(429, headers={'Retry-After': '3'}), R(200, OK_EMPTY))
    check('H2 429 con Retry-After 3 s: espera lo que pide Bybit', out == OK_EMPTY and w == [3.0], (err, w))
    out, err, n, w = await run(R(429, headers={'Retry-After': '30'}))
    check('H3 Retry-After 30 s (más que el presupuesto): no espera, la serie queda para el minuto siguiente',
          isinstance(err, bh.BybitRateLimited) and n == 1 and w == [], (err, n, w))
    out, err, n, w = await run(R(503), R(502), R(200, OK_EMPTY))
    check('H4 5xx: reintenta (esperas 1 s y 2 s)', out == OK_EMPTY and n == 3 and w == [1.0, 2.0], (err, n, w))
    out, err, n, w = await run(httpx.ConnectError('caída'), R(200, OK_EMPTY))
    check('H5 red caída: reintenta', out == OK_EMPTY and n == 2, (err, n))
    out, err, n, w = await run(httpx.ReadTimeout('lento'), httpx.ReadTimeout('lento'), httpx.ReadTimeout('lento'))
    check('H6 timeout persistente: 3 intentos y error (no límite de tasa)',
          type(err) is RuntimeError and n == 3 and w == [1.0, 2.0], (err, n, w))
    out, err, n, w = await run(R(403))
    check('H7 403 (IP bloqueada): NO reintenta y lo marca como bloqueo',
          isinstance(err, bh.BybitRateLimited) and err.blocked and n == 1, (err, n))
    out, err, n, w = await run(R(200, {'retCode': 10001, 'retMsg': 'params error'}))
    check('H8 retCode de parámetros: NO reintenta', isinstance(err, bh.BybitRequestError) and n == 1, (err, n))
    out, err, n, w = await run(R(200, {'retCode': 10006, 'retMsg': 'Too many visits'}), R(200, OK_EMPTY))
    check('H9 retCode 10006 (límite de tasa): reintenta', out == OK_EMPTY and n == 2, (err, n))
    out, err, n, w = await run(R(429), R(429), R(429))
    check('H10 429 persistente: 3 intentos y BybitRateLimited',
          isinstance(err, bh.BybitRateLimited) and not err.blocked and n == 3, (err, n))
    out, err, n, w = await run(R(404, {'x': 1}))
    check('H11 otro 4xx: NO reintenta', isinstance(err, bh.BybitRequestError) and n == 1, (err, n))
    # Peor caso real: 3 timeouts del cliente de la corrida + esperas máximas (1 + 2 s + azar 0,25 por espera)
    worst = 3 * oc.RUN_HTTP_TIMEOUT_S + (1.0 + 0.25) + (2.0 + 0.25)
    check(f'H12 peor caso por petición ({worst:g} s) cabe en la corrida de 75 s con margen', worst <= 40, worst)


# ─────────────── Corrida completa: corte por límite de tasa ───────────────
class Coll(oc.OhlcvCollector):
    def __init__(self, configs, behavior):
        self.configs, self.behavior, self.done = configs, behavior, []

    async def get_active_configs(self):
        return self.configs

    async def update(self, symbol, interval, broker, client=None, **kw):
        self.done.append(symbol)
        r = self.behavior(symbol)
        if isinstance(r, Exception):
            raise r
        return r


async def run_cases():
    cfg = [(f'S{i:02d}', '60', 'bybit') for i in range(12)]
    oc.COLLECT_CONCURRENCY = 1   # orden determinista para la prueba

    seen = {}

    class TimeoutColl(Coll):
        async def update(self, symbol, interval, broker, client=None, **kw):
            seen['timeout'] = client.timeout.read
            return 1
    await TimeoutColl(cfg[:1], lambda s: 1).run_all({})
    check('C0 la corrida usa el timeout corto (10 s) en cada petición', seen.get('timeout') == 10.0, seen)

    c = Coll(cfg, lambda s: bh.BybitRateLimited('HTTP 403', blocked=True) if s == 'S02' else 5)
    errors = {}
    res = await c.run_all(errors)
    skipped = [k for k, v in errors.items() if v.startswith('omitida')]
    check('C1 un 403 corta el resto de la corrida (sin más peticiones a Bybit)',
          c.done == ['S00', 'S01', 'S02'] and len(skipped) == 9 and c.last_abort_reason, (c.done, len(skipped)))
    check('C2 lo ya descargado queda bien', res['S00/60'] == 5 and res['S01/60'] == 5 and res['S02/60'] == -1)

    c = Coll(cfg, lambda s: bh.BybitRateLimited('429 tras 3 intentos') if s in ('S03', 'S04', 'S05') else 5)
    errors = {}
    await c.run_all(errors)
    check('C3 tres series seguidas limitadas cortan la corrida', c.done == ['S00', 'S01', 'S02', 'S03', 'S04', 'S05']
          and c.last_abort_reason, c.done)

    c = Coll(cfg, lambda s: bh.BybitRateLimited('429') if s in ('S03', 'S05') else 5)
    await c.run_all({})
    check('C4 limitadas sueltas (no seguidas): no corta', len(c.done) == 12 and c.last_abort_reason is None, c.done)

    c = Coll(cfg, lambda s: RuntimeError('HTTP 502 tras 3 intentos') if s in ('S01', 'S02', 'S03', 'S04') else 5)
    await c.run_all({})
    check('C5 fallos que no son límite de tasa: no cortan la corrida', len(c.done) == 12 and c.last_abort_reason is None)

    # Descarga real de una serie con el transporte simulado: un 429 no hace fallar la serie
    transport, calls = scripted(R(429), R(200, OK_EMPTY))

    async def no_sleep(*a, **k):
        return None
    real_sleep = asyncio.sleep
    bh.asyncio.sleep = no_sleep
    try:
        col = oc.OhlcvCollector.__new__(oc.OhlcvCollector)
        async with httpx.AsyncClient(transport=transport) as client:
            bars = await col.fetch_from_bybit('BTCUSDT', '1', 0, 120, client=client)
        check('F1 fetch_from_bybit con un 429 transitorio: la serie no falla', bars == [] and len(calls) == 2, len(calls))
    finally:
        bh.asyncio.sleep = real_sleep


async def main():
    await http_cases()
    await run_cases()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

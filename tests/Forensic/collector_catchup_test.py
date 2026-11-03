"""
C-05: la carga inicial de una serie nueva y la puesta al día de una serie atrasada avanzan HACIA ADELANTE por ventanas,
guardando cada una al llegar, con presupuesto de tiempo por corrida. Una interrupción se retoma sin huecos ni repetidos,
y las series al día se actualizan primero (agregar una moneda ya no detiene al resto).
Sin base de datos ni red: base en memoria, Bybit simulado y reloj controlable.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_catchup_test.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import httpx  # noqa: E402

import collectors.ohlcv_collector as oc  # noqa: E402
from collectors.broker_resolver import interval_delta  # noqa: E402

fails = 0
M = timedelta(minutes=1)


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def floor(t, step):
    return oc._floor(t, step)


class Clock:
    """Reloj monotónico simulado: cada consulta a Bybit avanza `per_request` segundos."""
    def __init__(self, per_request=0.5):
        self.t, self.per_request = 0.0, per_request

    def __call__(self):
        return self.t


class World:
    def __init__(self, clock):
        self.db, self.requests, self.clock, self.fail_at = {}, [], clock, None
        self.listed = {}   # (symbol, interval) -> primera vela que tiene Bybit

    def truth(self, symbol, interval, t):
        p = 100 + (int(t.timestamp()) // 60 % 89) * 0.1
        return dict(open=p, high=p + 0.5, low=p - 0.5, close=p + 0.2, volume=1.0)


class Conn:
    def __init__(self, w):
        self.w = w

    async def execute(self, sql, times, broker, symbol, interval, o, h, lo, c, v):
        d = self.w.db.setdefault((symbol, interval), {})
        for t, *vals in zip(times, o, h, lo, c, v):
            d[t] = vals
        return f'INSERT 0 {len(times)}'

    async def fetchrow(self, sql, broker, symbol, interval):
        d = self.w.db.get((symbol, interval))
        return {'last_time': max(d)} if d else None


class Pool:
    def __init__(self, w):
        self.w = w

    def acquire(self):
        w = self.w

        class _C:
            async def __aenter__(self):
                return Conn(w)

            async def __aexit__(self, *e):
                return False
        return _C()


def transport(w):
    def handler(request):
        q = request.url.params
        w.requests.append((q['symbol'], q['interval']))
        w.clock.t += w.clock.per_request
        if w.fail_at is not None and len(w.requests) == w.fail_at:
            return httpx.Response(400, json={})    # error que no se reintenta: corta esta corrida
        key, interval = (q['symbol'], q['interval']), q['interval']
        step = interval_delta(interval)
        end = datetime.fromtimestamp(int(q['end']) / 1000, tz=timezone.utc)
        start = datetime.fromtimestamp(int(q['start']) / 1000, tz=timezone.utc) if 'start' in q else end - step * 999
        first = w.listed.get(key) or w.listed.get((q['symbol'], '1'))
        if interval == 'D' and first:
            first = floor(first, timedelta(days=1))
        now_bar = floor(datetime.now(timezone.utc), step)
        t, rows = max(floor(start, step), first or start), []
        while t <= min(end, now_bar) and len(rows) < int(q['limit']):
            rows.append(t)
            t += step
        rows = rows[-int(q['limit']):]
        lst = [[str(int(x.timestamp() * 1000))] + [str(v) for v in w.truth(q['symbol'], interval, x).values()]
               for x in reversed(rows)]
        return httpx.Response(200, json={'retCode': 0, 'result': {'list': lst}})
    return httpx.MockTransport(handler)


def collector(w):
    c = oc.OhlcvCollector.__new__(oc.OhlcvCollector)
    c.pool = Pool(w)
    return c


def complete(w, symbol, interval='1'):
    """¿La base tiene exactamente las velas de Bybit desde el listado hasta hoy, sin huecos ni repetidas?"""
    step = interval_delta(interval)
    d = w.db.get((symbol, interval), {})
    first = w.listed[(symbol, interval)]
    expected = []
    t = first
    while t <= floor(datetime.now(timezone.utc), step):
        expected.append(t)
        t += step
    return sorted(d) == expected, len(d), len(expected)


async def main():
    clock = Clock()
    oc.time.monotonic = clock   # la corrida y catch_up usan este reloj
    real_sleep = asyncio.sleep

    # Moneda nueva de 1m listada hace 3 días (~4.320 velas): con 730 días de historia pedidos
    w = World(clock)
    now = datetime.now(timezone.utc)
    w.listed[('NEWUSDT', '1')] = floor(now - timedelta(days=3), timedelta(days=1))
    c = collector(w)
    async with httpx.AsyncClient(transport=transport(w)) as client:
        saved1 = await c.initial_load('NEWUSDT', '1', client=client, deadline=clock() + 2.0)   # ~4 consultas
        n_after_1 = len(w.db.get(('NEWUSDT', '1'), {}))
        check('L1 carga inicial con presupuesto: guarda por ventanas y se detiene a tiempo (no todo de golpe)',
              0 < n_after_1 < 4320 and c.catching_up.get('NEWUSDT/1', {}).get('behind_hours'), (saved1, n_after_1))
        check('L2 salta el tiempo antes del listado con una sola consulta diaria (no ~1.000 ventanas vacías)',
              len(w.requests) <= 5, len(w.requests))
        sizes = []
        orig_save = oc.OhlcvCollector.save_bars

        async def spy(self, bars, broker='bybit'):
            sizes.append(len(bars))
            return await orig_save(self, bars, broker)
        oc.OhlcvCollector.save_bars = spy
        for _ in range(10):   # corridas siguientes: retoman desde la última vela
            await c.update('NEWUSDT', '1', client=client, deadline=clock() + 2.0)
        oc.OhlcvCollector.save_bars = orig_save
        ok, have, exp = complete(w, 'NEWUSDT')
        check('L3 en varias corridas queda completa, continua desde el listado y sin repetidas', ok, (have, exp))
        check('L4 nunca guarda más de una ventana por vez (memoria acotada)', sizes and max(sizes) <= oc.BYBIT_LIMIT,
              max(sizes) if sizes else None)
        check('L5 al terminar deja de figurar como «poniéndose al día»', 'NEWUSDT/1' not in c.catching_up, c.catching_up)

    # Interrupción a mitad de la carga: lo guardado se conserva y la corrida siguiente retoma sin huecos
    w = World(clock)
    w.listed[('INTUSDT', '1')] = floor(now - timedelta(days=3), timedelta(days=1))
    c = collector(w)
    async with httpx.AsyncClient(transport=transport(w)) as client:
        w.fail_at = 5   # 1 vacía (hace 730 días) + diaria + 2 ventanas buenas + falla
        try:
            await c.initial_load('INTUSDT', '1', client=client)
        except Exception:   # noqa: BLE001 - se espera el corte
            pass
        kept = len(w.db.get(('INTUSDT', '1'), {}))
        check('I1 corte a mitad: lo ya descargado quedó guardado (antes se perdía todo)', kept == 2 * oc.BYBIT_LIMIT, kept)
        w.fail_at = None
        for _ in range(6):
            await c.update('INTUSDT', '1', client=client)
        ok, have, exp = complete(w, 'INTUSDT')
        check('I2 la corrida siguiente retoma desde la última vela: completa y sin huecos', ok, (have, exp))

    # Serie al día: una sola consulta, como siempre
    w = World(clock)
    w.listed[('BTCUSDT', '1')] = floor(now - timedelta(days=3), timedelta(days=1))
    w.db[('BTCUSDT', '1')] = {floor(now, M) - 2 * M: [1, 1, 1, 1, 1]}
    c = collector(w)
    async with httpx.AsyncClient(transport=transport(w)) as client:
        await c.update('BTCUSDT', '1', client=client)
    check('N1 serie al día: 1 sola consulta (el caso normal no cambia)', len(w.requests) == 1, len(w.requests))

    # Corrida completa: primero las series al día; la nueva usa el tiempo que sobra
    w = World(clock)
    for sym in ('AAAUSDT', 'BBBUSDT', 'CCCUSDT'):
        w.listed[(sym, '1')] = floor(now - timedelta(days=3), timedelta(days=1))
        w.db[(sym, '1')] = {floor(now, M) - 2 * M: [1, 1, 1, 1, 1]}
    w.listed[('NEWUSDT', '1')] = floor(now - timedelta(days=30), timedelta(days=1))   # ~43.000 velas: no cabe en una corrida
    c = collector(w)
    cfgs = [('NEWUSDT', '1', 'bybit'), ('AAAUSDT', '1', 'bybit'), ('BBBUSDT', '1', 'bybit'), ('CCCUSDT', '1', 'bybit')]

    async def _cfgs():
        return cfgs
    c.get_active_configs = _cfgs
    orig_client = oc.httpx.AsyncClient
    oc.httpx.AsyncClient = lambda **kw: orig_client(transport=transport(w), **kw)
    try:
        res = await c.run_all({})
    finally:
        oc.httpx.AsyncClient = orig_client
    order = [s for s, _ in w.requests]
    first_new = order.index('NEWUSDT') if 'NEWUSDT' in order else 99
    check('R1 la corrida actualiza primero las 3 series al día y después la nueva',
          set(order[:3]) == {'AAAUSDT', 'BBBUSDT', 'CCCUSDT'} and first_new == 3, order[:6])
    check('R2 las series al día quedan actualizadas aunque haya una carga en curso',
          all(res[f'{s}/1'] >= 1 for s in ('AAAUSDT', 'BBBUSDT', 'CCCUSDT')), res)
    check('R3 la nueva avanza dentro de su presupuesto y figura como «poniéndose al día»',
          'NEWUSDT/1' in c.catching_up and res['NEWUSDT/1'] > 0, c.catching_up)

    # Presupuesto de la corrida agotado: las atrasadas esperan a la próxima sin bloquear
    w = World(clock)
    w.listed[('NEWUSDT', '1')] = floor(now - timedelta(days=3), timedelta(days=1))
    c = collector(w)
    c.get_active_configs = _cfgs.__class__(lambda: None) if False else None
    cfgs2 = [('NEWUSDT', '1', 'bybit')]

    async def _cfgs2():
        return cfgs2
    c.get_active_configs = _cfgs2
    clock.per_request = 100.0   # cada consulta "tarda" 100 s: la corrida se queda sin tiempo enseguida
    oc.httpx.AsyncClient = lambda **kw: orig_client(transport=transport(w), **kw)
    try:
        await c.run_all({})
        first_run = len(w.requests)
    finally:
        oc.httpx.AsyncClient = orig_client
        clock.per_request = 0.5
    check('T1 una consulta lenta no alarga la corrida: la serie atrasada para y sigue la próxima vez',
          first_run <= 3 and c.catching_up.get('NEWUSDT/1'), (first_run, c.catching_up))

    asyncio.sleep = real_sleep
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

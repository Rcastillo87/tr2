"""
C-03: auditoría histórica rotativa del collector. Compara vela por vela TODO el histórico contra Bybit por porciones
(cursor por serie entre noches), repara con el UPSERT (nunca borra), reporta sobrantes y respeta presupuesto y tiempo.
Sin base de datos ni red: base y Bybit simulados con el mismo histórico.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_audit_test.py
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import httpx  # noqa: E402

import cli.collector_audit as ca  # noqa: E402
import cli.collector_repair as cr  # noqa: E402
from cli.collector_validate import FIELDS  # noqa: E402

fails = 0
NOW = datetime(2026, 11, 3, 9, 0, 30, tzinfo=timezone.utc)
H = timedelta(hours=1)


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def series_bars(n, step, end):
    """n velas que terminan en la última cerrada antes de `end`, con precios deterministas."""
    last = end.replace(minute=0, second=0, microsecond=0) - step
    out = {}
    for k in range(n):
        t = last - step * (n - 1 - k)
        p = 100 + (k % 97) * 0.5
        out[t] = dict(open=p, high=p + 1, low=p - 1, close=p + 0.25, volume=10 + k % 7)
    return out


class World:
    """Bybit (verdad) y la base (local) para varias series."""
    def __init__(self):
        self.truth, self.local, self.requests, self.max_end = {}, {}, 0, None

    def add(self, symbol, interval, n, step):
        bars = series_bars(n, step, NOW)
        self.truth[(symbol, interval)] = bars
        self.local[(symbol, interval)] = {t: dict(v) for t, v in bars.items()}


class Conn:
    def __init__(self, w):
        self.w = w

    async def fetchval(self, sql, symbol, interval):
        d = self.w.local.get((symbol, interval))
        return min(d) if d else None

    async def fetch(self, sql, symbol, interval, start, end):
        d = self.w.local.get((symbol, interval), {})
        return [dict(time=t, **v) for t, v in sorted(d.items()) if start <= t <= end]


class Collector:
    def __init__(self, w, write=True):
        self.w, self.write = w, write

    async def save_bars(self, bars, broker='bybit'):
        if not self.write:
            return 0
        n = 0
        for b in bars:
            d = self.w.local.setdefault((b['symbol'], b['interval']), {})
            new = {f: b[f] for f in FIELDS}
            if d.get(b['time']) != new:
                d[b['time']] = new
                n += 1
        return n


def transport(w, status=None):
    def handler(request):
        w.requests += 1
        if status:
            return httpx.Response(status, json={})
        q = request.url.params
        key = (q['symbol'], q['interval'])
        start = datetime.fromtimestamp(int(q['start']) / 1000, tz=timezone.utc)
        end = datetime.fromtimestamp(int(q['end']) / 1000, tz=timezone.utc)
        w.max_end = max(w.max_end or end, end)
        rows = [t for t in sorted(w.truth.get(key, {}), reverse=True) if start <= t <= end][:int(q['limit'])]
        lst = [[str(int(t.timestamp() * 1000))] + [str(w.truth[key][t][f]) for f in FIELDS] for t in rows]
        return httpx.Response(200, json={'retCode': 0, 'result': {'list': lst}})
    return httpx.MockTransport(handler)


async def no_pace():
    return None


async def audit(w, series, cursor, budget=100, repair=True, deadline=None, clock=None, status=None, write=True):
    async with httpx.AsyncClient(transport=transport(w, status)) as client:
        kw = dict(budget=budget, repair=repair, deadline=deadline, pace=no_pace)
        if clock:
            kw['clock'] = clock
        return await ca.run_audit(Conn(w), Collector(w, write), client, series, NOW, 300, cursor, **kw)


async def main():
    # Serie H1 con 3.500 velas: 3.200 auditables (fuera de las últimas 300) = 4 ventanas (1000+1000+1000+200)
    w = World()
    w.add('BTCUSDT', '60', 3500, H)
    times = sorted(w.local[('BTCUSDT', '60')])
    old_corrupt, old_missing, old_extra = times[150], times[1200], times[2100] + timedelta(minutes=30)
    w.local[('BTCUSDT', '60')][old_corrupt]['close'] = 999.0           # precio corrupto en una vela vieja
    del w.local[('BTCUSDT', '60')][old_missing]                         # vela vieja faltante
    w.local[('BTCUSDT', '60')][old_extra] = dict(open=1, high=1, low=1, close=1, volume=1)   # sobra (fuera de horario)

    cursor = {}
    r = await audit(w, [('BTCUSDT', '60')], cursor, budget=2)
    check('A1 presupuesto: 2 consultas y se detiene por presupuesto', r['requests'] == 2 and r['stopped'] == 'presupuesto',
          (r['requests'], r['stopped']))
    check('A2 vela vieja corrupta (hoy la validación la da por OK): detectada y reparada',
          r['diff'] == 1 and w.local[('BTCUSDT', '60')][old_corrupt]['close'] == w.truth[('BTCUSDT', '60')][old_corrupt]['close'],
          (r['diff'], r['series']['BTCUSDT|60']['diff_example']))
    check('A3 vela vieja faltante: reparada', r['missing'] == 1 and old_missing in w.local[('BTCUSDT', '60')], r['missing'])
    nxt = r['series']['BTCUSDT|60']['next']
    check('A4 el cursor avanza 2 ventanas (2.000 velas)', nxt == (times[0] + H * 2000).isoformat(), nxt)

    r = await audit(w, [('BTCUSDT', '60')], cursor, budget=10)
    check('A5 noche siguiente: sigue desde el cursor, termina la vuelta (2 ventanas) y encuentra el sobrante',
          r['windows'] == 2 and r['extra'] == 1 and r['requests'] == 2, (r['windows'], r['extra'], r['requests']))
    check('A6 sobrante reportado pero NO borrado', old_extra in w.local[('BTCUSDT', '60')])
    c = cursor['BTCUSDT|60']
    check('A7 vuelta completa: registra la fecha y vuelve a empezar', c.get('last_cycle_done') == NOW.isoformat(), c)
    recent_start = times[-300]
    check('A8 nunca consulta la zona de recientes (la cubre el chequeo de las últimas 300)',
          w.max_end is not None and w.max_end < recent_start, (w.max_end, recent_start))
    r2 = await audit(w, [('BTCUSDT', '60')], cursor, budget=1)
    check('A8b tras la vuelta, la noche siguiente empieza desde la vela más vieja',
          r2['windows'] == 1 and cursor['BTCUSDT|60']['next'] == (times[0] + H * 1000).isoformat(), cursor['BTCUSDT|60'])
    check('A9 tras la vuelta, la base coincide con Bybit en todo el histórico auditable',
          all(w.local[('BTCUSDT', '60')].get(t) == v for t, v in w.truth[('BTCUSDT', '60')].items() if t < recent_start))

    # Reparto por turnos entre series
    w2 = World()
    w2.add('BTCUSDT', '60', 3500, H)
    w2.add('ETHUSDT', '60', 3500, H)
    r = await audit(w2, [('BTCUSDT', '60'), ('ETHUSDT', '60')], {}, budget=4)
    check('R1 por turnos: 2 ventanas por serie con presupuesto 4',
          r['series']['BTCUSDT|60']['windows'] == 2 and r['series']['ETHUSDT|60']['windows'] == 2, r['requests'])

    # Simulación (--dry-run): encuentra pero no escribe
    w3 = World()
    w3.add('BTCUSDT', '60', 1500, H)
    t0 = sorted(w3.local[('BTCUSDT', '60')])[10]
    w3.local[('BTCUSDT', '60')][t0]['high'] = 5000.0
    r = await audit(w3, [('BTCUSDT', '60')], {}, repair=False)
    check('D1 simulación: detecta la diferencia y no escribe', r['diff'] == 1 and r['repaired'] == 0
          and w3.local[('BTCUSDT', '60')][t0]['high'] == 5000.0, r['diff'])

    # Escritura fallida: queda como "sin reparar"
    r = await audit(w3, [('BTCUSDT', '60')], {}, write=False)
    check('D2 si el UPSERT no escribe: cuenta como sin reparar', r['unrepaired'] == 1, r['unrepaired'])

    # Tiempo agotado y límite de tasa
    r = await audit(w3, [('BTCUSDT', '60')], {}, deadline=5.0, clock=lambda: 10.0)
    check('T1 tiempo agotado: no consulta y lo dice', r['requests'] == 0 and r['stopped'] == 'tiempo', r['stopped'])
    w4 = World()
    w4.add('BTCUSDT', '60', 1500, H)
    r = await audit(w4, [('BTCUSDT', '60')], {}, status=403)
    check('T2 Bybit bloquea (403): se detiene sin insistir', r['stopped'] == 'límite de tasa de Bybit' and w4.requests == 1,
          (r['stopped'], w4.requests))

    # Serie sin histórico fuera de la zona de recientes: no se cuelga
    w5 = World()
    w5.add('BTCUSDT', 'D', 200, timedelta(days=1))
    r = await audit(w5, [('BTCUSDT', 'D')], {}, budget=50)
    check('T3 serie corta (todo dentro de las últimas 300): termina sin consultar', r['requests'] == 0, r)

    # Cursor en disco (escritura atómica)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'cursor.json'
        ca.save_cursor({'BTCUSDT|60': {'next': NOW.isoformat()}}, p)
        check('P1 cursor: se guarda y se lee igual', ca.load_cursor(p) == {'BTCUSDT|60': {'next': NOW.isoformat()}})
        check('P2 cursor ilegible o ausente: empieza de cero', ca.load_cursor(Path(d) / 'no.json') == {})

    # Integración en la reparación diaria: una serie con diferencias sin reparar cuenta como falla
    async def fake_run_audit(conn, collector, client, series, now, n, cursor, **kw):
        return dict(budget=kw['budget'], requests=3, stopped='presupuesto', repair=kw['repair'], windows=3,
                    compared=3000, missing=0, diff=1, extra=0, repaired=0, unrepaired=1, errors=0,
                    series={'BTCUSDT|60': dict(windows=3, diff=1, unrepaired=1)})

    class FakePool:
        def acquire(self):
            class _C:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *e):
                    return False
            return _C()

        async def close(self):
            pass

    async def fake_create_pool(*a, **k):
        return FakePool()
    cr.run_audit, cr.asyncpg.create_pool = fake_run_audit, fake_create_pool
    cr.load_cursor, cr.save_cursor = (lambda: {}), (lambda c: None)
    base = dict(series=[dict(symbol='BTCUSDT', interval='60', ok=True, bars=3500),
                        dict(symbol='ETHUSDT', interval='60', ok=True, bars=3500)])
    res = await cr._audit(base, 300, None, False, 1500, 1e18)
    btc = next(s for s in res['series'] if s['symbol'] == 'BTCUSDT')
    check('I1 reparación diaria: serie con diferencia sin reparar queda como falla y el resumen lo refleja',
          btc['ok'] is False and res['summary']['ok'] == 1 and res['audit']['unrepaired'] == 1, res['summary'])
    check('I2 presupuesto por defecto 1.500 (configurable con COLLECTOR_AUDIT_BUDGET)', ca.AUDIT_BUDGET == 1500)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

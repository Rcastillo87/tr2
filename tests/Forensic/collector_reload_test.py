"""
C-10: «Recargar completo» ya no vacía la serie. Re-verifica TODO el histórico contra Bybit en segundo plano, corrige con
el UPSERT del collector y elimina solo velas sobrantes confirmadas por Bybit, al final y solo si la verificación terminó
completa. Una recarga a la vez; el avance se consulta por estado.
Sin base de datos ni red: base en memoria (que acepta el UPSERT y el DELETE del collector) y Bybit simulado.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_reload_test.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import httpx  # noqa: E402
from fastapi import HTTPException  # noqa: E402

import api.v1.collector as api  # noqa: E402
import cli.collector_audit as ca  # noqa: E402
import collectors.ohlcv_collector as oc  # noqa: E402
from cli.collector_validate import FIELDS  # noqa: E402

fails = 0
NOW = datetime(2026, 11, 3, 9, 0, 30, tzinfo=timezone.utc)
H, D = timedelta(hours=1), timedelta(days=1)
KEY = ('BTCUSDT', '60')


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def build_truth(days=150):
    """Serie H1 en Bybit desde el listado (hace `days` días, a las 00:00) hasta la última vela cerrada."""
    first = (NOW - D * days).replace(hour=0, minute=0, second=0, microsecond=0)
    last = NOW.replace(minute=0, second=0, microsecond=0) - H
    out, t, k = {}, first, 0
    while t <= last:
        p = 100 + (k % 97) * 0.5
        out[t] = dict(open=p, high=p + 1, low=p - 1, close=p + 0.25, volume=10.0 + k % 7)
        t, k = t + H, k + 1
    return out


class World:
    def __init__(self):
        self.truth = build_truth()
        self.local = {t: dict(v) for t, v in self.truth.items()}
        self.min_len = len(self.local)
        self.fail_at, self.status, self.empty_window, self.requests = None, None, None, 0
        self.write_ok, self.gate = True, None
        self.deletions, self.fail_delete_after, self.deleted_rows = [], None, 0


class Conn:
    """Base en memoria: UPSERT del collector y el borrado de delete_bars (DELETE … RETURNING, transacción con
    rollback real y registro en ohlcv_deletions, p44 N-11)."""

    def __init__(self, w):
        self.w = w

    def transaction(self):
        w = self.w

        class _T:
            async def __aenter__(self_):
                self_.snap = (dict(w.local), list(w.deletions))
                return self_

            async def __aexit__(self_, et, e, tb):
                if et is not None:                 # rollback
                    w.local, w.deletions = dict(self_.snap[0]), list(self_.snap[1])
                return False
        return _T()

    async def fetchval(self, sql, *args):
        return min(self.w.local) if self.w.local else None

    async def fetch(self, sql, *args):
        w = self.w
        if len(args) == 4 and isinstance(args[3], list):     # SELECT de las velas a borrar (delete_bars)
            _broker, _symbol, _interval, times = args
            return [dict(time=t, **w.local[t]) for t in sorted(times) if t in w.local]
        symbol, interval, start, end = args
        return [dict(time=t, **v) for t, v in sorted(w.local.items()) if start <= t <= end]

    async def execute(self, sql, *args):
        w = self.w
        if 'INSERT INTO ohlcv_deletions' in sql:
            w.deletions.append(args)
            return 'INSERT 0 1'
        if sql.lstrip().upper().startswith('DELETE'):       # delete_bars (broker, …) o el camino anterior a p44
            times = args[-1]
            n = 0
            for t in times:
                if w.local.pop(t, None) is not None:
                    n += 1
                    w.deleted_rows += 1
                    if w.fail_delete_after is not None and w.deleted_rows >= w.fail_delete_after:
                        raise asyncio.CancelledError()   # corte a mitad del borrado (acumulado entre lotes)
            w.min_len = min(w.min_len, len(w.local))
            return f'DELETE {n}'
        if not w.write_ok:
            return 'INSERT 0 0'
        times, _broker, _symbol, _interval, o, h, lo, c, v = args
        n = 0
        for row in zip(times, o, h, lo, c, v):
            new = dict(zip(FIELDS, map(float, row[1:])))
            if w.local.get(row[0]) != new:
                w.local[row[0]], n = new, n + 1
        return f'INSERT 0 {n}'


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

    async def close(self):
        return None


def transport(w):
    async def handler(request):
        w.requests += 1
        w.min_len = min(w.min_len, len(w.local))
        if w.gate is not None:
            await w.gate.wait()
        if w.status:
            return httpx.Response(w.status, json={})
        q = request.url.params
        start = datetime.fromtimestamp(int(q['start']) / 1000, tz=timezone.utc)
        end = datetime.fromtimestamp(int(q['end']) / 1000, tz=timezone.utc)
        if q['interval'] == 'D':
            day0 = min(w.truth).replace(hour=0)
            rows, t = [], max(day0, start)
            while t <= end and len(rows) < int(q['limit']):
                rows.append((t, dict(open=1, high=1, low=1, close=1, volume=1)))
                t += D
        else:
            if w.fail_at is not None and w.requests >= w.fail_at:
                return httpx.Response(400, json={})   # error que no se reintenta: corta la recarga
            if w.empty_window is not None and start <= w.empty_window <= end:
                rows = []
            else:
                rows = [(t, w.truth[t]) for t in sorted(w.truth) if start <= t <= end][:int(q['limit'])]
        lst = [[str(int(t.timestamp() * 1000))] + [str(v[f]) for f in FIELDS] for t, v in reversed(rows)]
        return httpx.Response(200, json={'retCode': 0, 'result': {'list': lst}})
    return httpx.MockTransport(handler)


async def no_pace():
    return None


async def reverify(w, progress=None):
    pool = Pool(w)
    collector = oc.OhlcvCollector(pool)
    async with httpx.AsyncClient(transport=transport(w)) as client:
        return await ca.reverify_series(pool, collector, client, 'BTCUSDT', '60', 730, now=NOW, pace=no_pace,
                                        progress=progress)


def damage(w):
    times = sorted(w.local)
    corrupt, missing = times[100], times[2000]
    extra = times[1500] + timedelta(minutes=30)          # fila que Bybit no tiene
    forming = NOW.replace(minute=0, second=0, microsecond=0)   # vela en formación: la maneja la corrida de cada minuto
    w.local[corrupt]['close'] = 999.0
    del w.local[missing]
    w.local[extra] = dict(open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0)
    w.local[forming] = dict(open=5.0, high=5.0, low=5.0, close=5.0, volume=5.0)
    w.min_len = len(w.local)
    return corrupt, missing, extra, forming


async def main():
    # Recarga completa sobre una serie con una vela corrupta, una faltante, una sobrante y la vela en formación
    w = World()
    corrupt, missing, extra, forming = damage(w)
    before = len(w.local)
    seen = []
    r = await reverify(w, progress=seen.append)
    check('R1 termina completa y compara toda la serie', r['complete'] and not r['stopped'] and r['compared'] == len(w.truth),
          (r['complete'], r['stopped'], r['compared'], len(w.truth)))
    check('R2 vela corrupta corregida', w.local[corrupt] == w.truth[corrupt] and r['diff'] == 1, r['diff'])
    check('R3 vela faltante agregada', w.local.get(missing) == w.truth[missing] and r['missing'] == 1, r['missing'])
    check('R4 sobrante confirmada por Bybit: eliminada solo al final', extra not in w.local and r['extra_deleted'] == 1,
          r['extra_deleted'])
    check('R5 la vela en formación no se toca', w.local.get(forming) == dict(open=5.0, high=5.0, low=5.0, close=5.0, volume=5.0))
    check('R6 la base queda igual a Bybit en todo lo cerrado',
          all(w.local.get(t) == v for t, v in w.truth.items()) and set(w.local) - set(w.truth) == {forming})
    check('R7 la serie nunca bajó de su tamaño mientras corría (nunca se vació)', w.min_len >= before - 1 and
          w.min_len >= len(w.truth) - 1, (w.min_len, before))
    check('R8 avance por ventana (windows / total_windows)', len(seen) >= 2 and seen[0]['windows'] == 1
          and seen[-1]['windows'] == r['total_windows'] == r['windows'], (len(seen), r['windows'], r['total_windows']))

    # Corte a mitad (Bybit falla en la 3.ª ventana): nada se pierde ni se elimina, lo corregido queda
    w = World()
    corrupt, missing, extra, forming = damage(w)
    before = len(w.local)
    w.fail_at = 4   # 1 consulta diaria + 2 ventanas buenas + la que falla
    r = await reverify(w)
    check('C1 corte a mitad: se detiene, lo informa y no queda como completa', not r['complete'] and r['stopped']
          and r['windows'] == 2, (r['complete'], r['stopped'], r['windows']))
    check('C2 corte a mitad: ninguna vela se perdió y la sobrante NO se eliminó',
          extra in w.local and w.min_len >= before and r['extra_deleted'] == 0, (w.min_len, before))
    check('C3 lo corregido antes del corte quedó guardado', w.local[corrupt] == w.truth[corrupt])

    # Bybit bloquea (403): igual que un corte
    w = World()
    _, _, extra, _ = damage(w)
    before = len(w.local)
    w.status = 403
    r = await reverify(w)
    check('C4 Bybit bloquea: se detiene sin borrar nada', not r['complete'] and r['stopped'] is not None
          and len(w.local) == before and extra in w.local, r['stopped'])

    # Una ventana que Bybit devuelve vacía no borra lo que la base tiene en ese rango
    w = World()
    times = sorted(w.truth)
    w.empty_window = times[1200]
    before = len(w.local)
    r = await reverify(w)
    check('V1 ventana vacía en Bybit: no se elimina nada de ese rango (queda reportado)',
          len(w.local) == before and r['extra_deleted'] == 0 and r['extra_kept'] >= 1000, (r['extra_kept'], r['extra_deleted']))

    # Si el UPSERT no pudo corregir algo, tampoco se eliminan sobrantes
    w = World()
    _, _, extra, _ = damage(w)
    w.write_ok = False
    r = await reverify(w)
    check('V2 diferencias sin corregir: no se elimina ningún sobrante y se informa',
          extra in w.local and r['unrepaired'] >= 1 and r['extra_deleted'] == 0 and r['stopped'], r['stopped'])

    # ─────────────── Endpoint del motor: segundo plano, una a la vez, estado ───────────────
    w = World()
    forming = damage(w)[3]
    del w.local[forming]   # el endpoint usa la hora real: la vela «en formación» del fixture ya estaría cerrada
    w.gate = asyncio.Event()
    orig_pool, orig_client, orig_pace = api.get_pool, api.httpx.AsyncClient, ca.AUDIT_PACE_S

    async def fake_pool():
        return Pool(w)
    api.get_pool = fake_pool
    api.httpx.AsyncClient = lambda **kw: orig_client(transport=transport(w))
    ca.AUDIT_PACE_S = 0
    try:
        try:
            await api.collector_reload('BTCUSDT', '60', 'bybit', confirm=False)
            check('E1 sin confirm: rechazada', False)
        except HTTPException as e:
            check('E1 sin confirm: rechazada', e.status_code == 400)
        try:
            await api.collector_reload('BTCUSDT', '7', 'bybit', confirm=True)
            check('E2 intervalo inválido: rechazado', False)
        except HTTPException as e:
            check('E2 intervalo inválido: rechazado', e.status_code == 400)

        t0 = asyncio.get_running_loop().time()
        res = await api.collector_reload('BTCUSDT', '60', 'bybit', confirm=True)
        check('E3 responde enseguida (segundo plano), sin esperar la descarga',
              res['status'] == 'started' and res['running'] and asyncio.get_running_loop().time() - t0 < 1, res['status'])
        try:
            await api.collector_reload('ETHUSDT', '60', 'bybit', confirm=True)
            check('E4 segunda recarga mientras corre la primera: 409', False)
        except HTTPException as e:
            check('E4 segunda recarga mientras corre la primera: 409', e.status_code == 409 and 'BTCUSDT' in e.detail, e.detail)
        st = await api.collector_reload_status()
        check('E5 el estado dice que está en curso', st['running'] and 'task' not in st, st.get('running'))
        w.gate.set()
        for _ in range(200):
            await asyncio.sleep(0.01)
            st = await api.collector_reload_status()
            if not st['running']:
                break
        r = st.get('result') or {}
        check('E6 al terminar: estado con el resultado (comparadas, corregidas, sobrantes eliminadas)',
              not st['running'] and r.get('complete') and r.get('repaired') == 2 and r.get('extra_deleted') == 1
              and st['finished_at'], (st['running'], {k: r.get(k) for k in ('complete', 'repaired', 'extra_deleted')}))
        res = await api.collector_reload('BTCUSDT', '60', 'bybit', confirm=True)
        check('E7 terminada la anterior, se puede iniciar otra', res['status'] == 'started')
        await asyncio.sleep(0.2)
    finally:
        api.get_pool, api.httpx.AsyncClient, ca.AUDIT_PACE_S = orig_pool, orig_client, orig_pace

    # Pantalla y Laravel: ya no promete borrar ni espera 600 s
    root = os.path.dirname(os.getcwd())
    blade = open(os.path.join(root, 'resources/views/data-collector/index.blade.php'), encoding='utf-8').read()
    ctrl = open(os.path.join(root, 'app/Http/Controllers/CollectorConfigController.php'), encoding='utf-8').read()
    reload_fn = ctrl[ctrl.index('public function reload('):ctrl.index('public function reloadStatus(')]
    check('U1 el diálogo ya no dice «Borrar TODO» y explica que la serie no se borra',
          'Borrar TODO' not in blade and 'La serie no se borra' in blade)
    check('U2 Laravel ya no espera 600 s a la recarga', 'timeout(600)' not in reload_fn and 'timeout(15)' in reload_fn)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

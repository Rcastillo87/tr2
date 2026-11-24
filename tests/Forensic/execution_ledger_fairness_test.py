"""
C6-01: la cola del libro de ejecuciones (process_pending) no deja atrás a las operaciones nuevas.
Antes: se tomaban las 20 pendientes más antiguas y se descartaban DESPUÉS las que esperaban su reintento (10 min):
con 20 o más esperando, una operación nueva no entraba nunca a la selección (hasta que las viejas salían, ~24 h).
Ahora las que esperan se descartan en la consulta.
A. Base simulada que aplica el SQL (exclusión y LIMIT):
   F1 25 antiguas esperando + 1 nueva -> la nueva se procesa en el primer ciclo;
   F2 siguen siendo 2 por ciclo y en orden de antigüedad entre las que están listas;
   F3 varias que alternan entre error y recuperación: la que falla espera 10 min, la que se recupera sale de la espera,
      y nada queda sin atender;
   F4 una excepción del libro no frena el ciclo y deja esa operación en espera;
   F5 la memoria de esperas se limpia (lo vencido hace más de 2 días se olvida).
B. Con PostgreSQL de pruebas (C5-04; si no, SKIP), en una transacción revertida con las migraciones del libro: la
   consulta real corre con la lista vacía y con ids.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/execution_ledger_fairness_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tests/Forensic/ (C5-04: barrera de base)
import trading.execution_ledger as led  # noqa: E402
from test_db import require_test_db, test_dsn  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Conn:
    def __init__(self, s):
        self.s = s

    async def fetch(self, sql, *a):
        self.s['sql'] = sql
        ids = sorted(self.s['pending'])
        if '$3::bigint[]' in sql:                   # la exclusión ocurre en la consulta
            ids = [i for i in ids if i not in set(a[2])]
        return [{'id': i} for i in ids[:a[1]]]


class Pool:
    def __init__(self, s):
        self.s = s

    def acquire(self):
        s = self.s

        class A:
            async def __aenter__(self_):
                return Conn(s)

            async def __aexit__(self_, *e):
                return False
        return A()


def fake_record(s):
    async def record(pool, trader, client, trade):
        tid = trade['id']
        s['done'].append(tid)
        out = s['outcome'].get(tid, 'ok')
        if out == 'raise':
            raise RuntimeError('fallo simulado del libro')
        if out == 'error':
            return {'id': tid, 'error': 'Bybit no respondió (simulado)'}
        s['pending'].discard(tid)                  # verificada: sale de la cola
        return {'id': tid, 'status': 'ok'}
    return record


async def main():
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # F1: 25 antiguas esperando su reintento + 1 nueva
    led._RETRY_AT.clear()
    s = {'pending': set(range(1, 26)) | {30}, 'done': [], 'outcome': {}}
    for i in range(1, 26):
        led._RETRY_AT[i] = now + timedelta(minutes=8)
    led.record_trade = fake_record(s)
    await led.process_pending(Pool(s), None, None, 11)
    check('F1: con 25 antiguas esperando, la nueva se procesa en el primer ciclo', s['done'] == [30], s['done'])
    check('F1: las que esperan se descartan en la consulta', 'NOT (id = ANY($3::bigint[]))' in s.get('sql', ''))

    # F2: 2 por ciclo, por antigüedad entre las listas
    led._RETRY_AT.clear()
    s = {'pending': {5, 6, 7, 40}, 'done': [], 'outcome': {}}
    led._RETRY_AT[5] = now + timedelta(minutes=3)
    led.record_trade = fake_record(s)
    await led.process_pending(Pool(s), None, None, 11)
    check('F2: 2 por ciclo y las más antiguas listas primero (la 5 espera)', s['done'] == [6, 7], s['done'])

    # F3: alternan error y recuperación
    led._RETRY_AT.clear()
    s = {'pending': {1, 2, 3}, 'done': [], 'outcome': {1: 'error', 2: 'ok', 3: 'ok'}}
    led.record_trade = fake_record(s)
    await led.process_pending(Pool(s), None, None, 11)
    check('F3: la que falla queda esperando 10 min y la que se recupera sale', s['done'] == [1, 2]
          and 1 in led._RETRY_AT and 2 not in led._RETRY_AT and abs((led._RETRY_AT[1] - now).total_seconds() - 600) < 120,
          (s['done'], led._RETRY_AT))
    s['done'].clear()
    await led.process_pending(Pool(s), None, None, 11)
    check('F3: el ciclo siguiente atiende a la que faltaba (la 3), sin esperar a la 1', s['done'] == [3], s['done'])
    led._RETRY_AT[1] = now - timedelta(seconds=1)  # venció su espera
    s['outcome'][1] = 'ok'
    s['done'].clear()
    await led.process_pending(Pool(s), None, None, 11)
    check('F3: vencida la espera, la 1 se vuelve a pedir, se recupera y sale de la memoria de esperas',
          s['done'] == [1] and not s['pending'] and 1 not in led._RETRY_AT, (s['done'], s['pending'], led._RETRY_AT))

    # F4: una excepción no frena el ciclo
    led._RETRY_AT.clear()
    s = {'pending': {1, 2}, 'done': [], 'outcome': {1: 'raise'}}
    led.record_trade = fake_record(s)
    await led.process_pending(Pool(s), None, None, 11)
    check('F4: una excepción del libro no frena el ciclo y deja esa operación esperando', s['done'] == [1, 2]
          and 1 in led._RETRY_AT and 2 not in led._RETRY_AT, (s['done'], led._RETRY_AT))

    # F5: limpieza de la memoria de esperas
    led._RETRY_AT.clear()
    led._RETRY_AT.update({100: now - timedelta(days=3), 101: now - timedelta(hours=1), 102: now + timedelta(minutes=5)})
    s = {'pending': set(), 'done': [], 'outcome': {}}
    await led.process_pending(Pool(s), None, None, 11)
    check('F5: lo vencido hace más de 2 días se olvida; lo reciente se conserva', 100 not in led._RETRY_AT
          and 101 in led._RETRY_AT and 102 in led._RETRY_AT, sorted(led._RETRY_AT))


asyncio.run(main())

if require_test_db('B'):   # C5-04: nunca la base de producción
    import asyncpg

    async def db():
        c = await asyncpg.connect(test_dsn())
        tr = c.transaction()
        await tr.start()   # independiente del estado de la base de pruebas: migraciones del libro dentro y se revierte
        try:
            mig = os.path.join(os.path.dirname(led.__file__), '..', '..', 'database', 'sql-migrations')
            for name in ('2026_11_20_02_real_trade_executions.up.sql', '2026_11_20_03_real_trades_funding.up.sql'):
                await c.execute(open(os.path.join(mig, name), encoding='utf-8').read())
            # la consulta se arma con f-string: se reconstruye con TRADE_COLS, como hace el código
            src = open(led.__file__, encoding='utf-8').read()
            i = src.index('SELECT {TRADE_COLS}', src.index('async def process_pending'))
            j = src.find('""", account_id, limit, waiting)', i)
            if j < 0:
                check('B1: la consulta real corre en PostgreSQL con la lista de esperas', False, 'consulta sin la lista de esperas')
            else:
                query = 'SELECT ' + led.TRADE_COLS + src[i + len('SELECT {TRADE_COLS}'):j]
                r1 = await c.fetch(query, -1, 2, [])
                r2 = await c.fetch(query, -1, 2, [1, 2, 3])
                check('B1: la consulta real corre en PostgreSQL con la lista de esperas vacía y con ids', r1 == [] and r2 == [])
        finally:
            await tr.rollback()
            await c.close()

    asyncio.run(db())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

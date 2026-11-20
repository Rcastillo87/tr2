"""
MEJ-004 (p89): libro de ejecuciones de Bybit por operación Real (`trading/execution_ledger.py`).
A. Puro: lectura de cada parte de Bybit, resumen por pata (cantidad, precio promedio ponderado, comisión, maker) y
   controles contra lo registrado (cantidad = tamaño: R-10; precio promedio = entrada / salida).
B. Con PostgreSQL (DB_* en el entorno; si no, SKIP) y un Bybit simulado: cierre del bot y cierre de Bybit en dos
   tramos (completa close_order_id: R-23), llenado parcial avisado, Bybit sin respuesta no escribe nada, sin partes 24 h
   después → 'missing', sin duplicados, vista previa sin escribir, selección del tick (no toma 'historical') y la
   migración marca 'historical' solo la primera vez.
C. Estático: el tick lo llama sin poder frenarse; el comando de historial muestra antes de guardar.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/execution_ledger_test.py
"""
import asyncio
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())
ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


try:
    from trading import execution_ledger as led
except ImportError as e:
    check('existe trading/execution_ledger.py', False, f'no ({e})')
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)

T0 = datetime(2026, 11, 14, 2, 22, 17)
MS = lambda t: int((t - datetime(1970, 1, 1)).total_seconds() * 1000)  # noqa: E731


def ex(eid, oid, price, qty, t, fee=0.01, maker='false', etype='Trade', stop=''):
    return {'execId': eid, 'orderId': oid, 'symbol': 'LINKUSDT', 'side': 'Sell', 'execPrice': str(price),
            'execQty': str(qty), 'execValue': str(price * qty), 'execFee': str(fee), 'feeRate': '0.00055',
            'isMaker': maker, 'execType': etype, 'stopOrderType': stop, 'execTime': str(MS(t))}


# ── A. Puro ──
r = led.parse_execution(ex('e1', 'o1', 14.2, 3, T0, maker=True), 'open')
check('A1: lee una parte (precio, cantidad, comisión, maker, hora UTC)',
      r['exec_price'] == 14.2 and r['exec_qty'] == 3 and r['exec_fee'] == 0.01 and r['is_maker'] is True
      and r['exec_time'] == T0 and r['leg'] == 'open', r)
check('A2: isMaker en texto ("true") también cuenta', led.parse_execution(ex('e2', 'o1', 1, 1, T0, maker='true'), 'open')['is_maker'])
check('A3: sin execId o sin precio: se descarta', led.parse_execution({'orderId': 'o', 'execPrice': '1'}, 'open') is None)
rows = [led.parse_execution(e, 'open') for e in (ex('a', 'o1', 10.0, 6, T0, fee=0.033), ex('b', 'o1', 10.5, 4, T0, fee=0.023, maker=True),
                                                  ex('f', 'o1', 0, 0, T0, fee=0.5, etype='Funding'))]
s = led.leg_summary(rows)
check('A4: resumen: precio promedio ponderado, cantidad, comisión y maker (sin contar el funding)',
      s['parts'] == 2 and s['qty'] == 10 and abs(s['vwap'] - 10.2) < 1e-12 and abs(s['fee'] - 0.056) < 1e-12 and s['maker'] == 1, s)
check('A5: sin partes: None', led.leg_summary([]) is None)
tr = dict(size=10, original_size=None, entry_price=10.2, exit_price=9.8)
check('A6: todo coincide: sin diferencias', led.leg_checks(tr, s, dict(s, vwap=9.8)) == [])
c = led.leg_checks(dict(tr, size=12), s, None)
check('A7: llenado parcial (10 de 12): se avisa (R-10)', len(c) == 1 and 'llenó 10' in c[0] and 'registra 12' in c[0], c)
c = led.leg_checks(dict(tr, entry_price=10.0), s, None)
check('A8: precio promedio distinto al registrado: se avisa', len(c) == 1 and 'precio promedio' in c[0], c)
check('A9: el precio de Bybit redondeado al paso (0,005 %) no es diferencia',
      led.leg_checks(dict(tr, entry_price=10.2 * (1 + 5e-5)), s, None) == [])

# ── C. Estático ──
api = (ROOT / 'python-engine' / 'api' / 'v1' / 'real_trading.py').read_text(encoding='utf-8')
check('C1: el tick lo llama después de las señales, dentro de try/except (nunca frena la gestión)',
      bool(re.search(r'account_results\["signals"\] = signal_results\s*\n\s*#[^\n]*\n\s*try:\s*\n\s*account_results\["executions"\] = '
                     r'len\(await execution_ledger\.process_pending\(trader\.pool, trader, client, account\.id\)\)\s*\n\s*except Exception', api)))
check('C2: endpoint del historial solo con la clave interna y con vista previa (apply por defecto False)',
      "@router.post('/real/executions/backfill')" in api and 'class ExecutionsBackfillRequest(BaseModel):\n    accounts: list[AccountPayload]\n    apply: bool = False' in api)
cmd = (ROOT / 'app' / 'Console' / 'Commands' / 'RealExecutionsBackfill.php').read_text(encoding='utf-8') \
    if (ROOT / 'app' / 'Console' / 'Commands' / 'RealExecutionsBackfill.php').exists() else ''
check('C3: comando real:executions-backfill con --apply y respuesta del motor sin datos sensibles en el log',
      "'real:executions-backfill {--apply" in cmd and "'/v1/real/executions/backfill'" in cmd and 'SafeLogBody::of(' in cmd)

# ── B. Con PostgreSQL ──
# B aplica DOWN/UP de la migración: solo en una base de pruebas (nombre terminado en «test»), nunca en producción.
if not os.getenv('DB_HOST'):
    print('SKIP B: sin DB_* en el entorno')
elif not (os.getenv('DB_NAME') or '').endswith('test'):
    print(f"SKIP B: DB_NAME={os.getenv('DB_NAME')!r} no es una base de pruebas")
else:
    import asyncpg
    from db import DB_DSN
    UP = (ROOT / 'database' / 'sql-migrations' / '2026_11_20_02_real_trade_executions.up.sql').read_text(encoding='utf-8')
    DOWN = (ROOT / 'database' / 'sql-migrations' / '2026_11_20_02_real_trade_executions.down.sql').read_text(encoding='utf-8')

    class FakeClient:
        def __init__(self, execs, history=(), fail=False):
            self.execs, self.history, self.fail, self.windows = execs, list(history), fail, []

        async def get_executions(self, symbol, oid, start_ms, end_ms):
            self.windows.append((oid, start_ms, end_ms))
            return None if self.fail else [e for e in self.execs.get(oid, []) if start_ms <= int(e['execTime']) <= end_ms]

        async def get_closed_pnl_history(self, symbol, entry, since_ms, limit=20, end_time_ms=None):
            return self.history

    class FakeTrader:
        def __init__(self):
            self.audit = []

        async def log_audit(self, tid, action, data):
            self.audit.append((tid, action, data))

    async def main():
        pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)
        c = await pool.acquire()
        uid = 99089
        try:
            await c.execute(DOWN)
            await c.execute("DELETE FROM real_trades WHERE user_id = $1", uid)
            await c.execute("DELETE FROM users WHERE id = $1", uid)
            await c.execute("""INSERT INTO users (id, name, email, password, role, is_active, created_at, updated_at)
                               VALUES ($1, 't', 'ledger@test.local', 'x', 'admin', true, now(), now())""", uid)

            async def trade(tid, status='closed', size=10, entry=10.2, exit_=9.8, close_oid=None, exit_t=T0 + timedelta(hours=2),
                            oid='o-open'):
                await c.execute("""INSERT INTO real_trades (id, user_id, strategy, symbol, interval, side, entry_price, sl, tp,
                    be_level, size, entry_time, exit_time, exit_price, status, order_id, close_order_id, broker_account_id)
                    VALUES ($1, $2, 's', 'LINKUSDT', '240', 'short', $3, 11, 9, 10, $4, $5, $6, $7, $8, $9, $10, NULL)""",
                                tid, uid, entry, size, T0, exit_t if status == 'closed' else None, exit_ if status == 'closed' else None,
                                status, oid, close_oid)
            await trade(1)   # existía antes de la migración
            await c.execute(UP)
            hist = await c.fetchval("SELECT executions_status FROM real_trades WHERE id = 1")
            await trade(2)
            await c.execute(UP)   # repetir la migración
            again = await c.fetch("SELECT id, executions_status FROM real_trades WHERE user_id = $1 ORDER BY id", uid)
            check('B1: la migración marca «historical» lo que ya existía y repetirla no marca lo nuevo',
                  hist == 'historical' and [(r['id'], r['executions_status']) for r in again] == [(1, 'historical'), (2, None)],
                  [dict(r) for r in again])

            async def row(tid):
                r = await c.fetchrow("""SELECT id, symbol, side, status, size, original_size, entry_price, exit_price,
                    entry_time, exit_time, order_id, close_order_id, executions_status FROM real_trades WHERE id = $1""", tid)
                return dict(r)

            # cierre del bot (close_order_id guardado)
            await c.execute("UPDATE real_trades SET close_order_id = 'o-close' WHERE id = 2")
            execs = {'o-open': [ex('x1', 'o-open', 10.0, 6, T0), ex('x2', 'o-open', 10.5, 4, T0)],
                     'o-close': [ex('x3', 'o-close', 9.8, 10, T0 + timedelta(hours=2), stop='')]}
            cl, trd = FakeClient(execs), FakeTrader()
            out = await led.record_trade(pool, trd, cl, await row(2))
            n = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 2")
            st = await c.fetchval("SELECT executions_status FROM real_trades WHERE id = 2")
            check('B2: cierre del bot: guarda 3 partes, estado «ok», sin diferencias y con su entrada en el historial',
                  n == 3 and st == 'ok' and out['checks'] == [] and trd.audit and trd.audit[0][1] == 'executions_recorded', (n, st, out['checks']))
            check('B3: pide cada orden con una ventana de ± 1 h alrededor de su hora',
                  ('o-open', MS(T0) - 3_600_000, MS(T0) + 3_600_000) in cl.windows, cl.windows[:1])
            out = await led.record_trade(pool, trd, cl, await row(2))
            n2 = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 2")
            check('B4: repetir no duplica partes', n2 == 3, n2)

            # cierre de Bybit en dos tramos, sin close_order_id (R-23)
            await trade(3, close_oid=None)
            ex3 = {'o-open': execs['o-open'], 't1': [ex('y1', 't1', 9.9, 4, T0 + timedelta(hours=1), stop='TakeProfit')],
                   't2': [ex('y2', 't2', 9.7, 6, T0 + timedelta(hours=2), stop='TakeProfit')]}
            hist3 = [{'orderId': 't1', 'createdTime': str(MS(T0 + timedelta(hours=1)))},
                     {'orderId': 't2', 'createdTime': str(MS(T0 + timedelta(hours=2)))}]
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex3, hist3), await row(3))
            r3 = await row(3)
            check('B5: cierre de Bybit en 2 tramos: guarda las partes de los dos y completa close_order_id con el último (R-23)',
                  r3['close_order_id'] == 't2' and r3['executions_status'] == 'ok' and out['close']['parts'] == 2
                  and abs(out['close']['vwap'] - 9.78) < 1e-9, (r3['close_order_id'], out['close']))

            # llenado parcial: Bybit llenó 6 de 10
            await trade(4, close_oid='o-close')
            ex4 = {'o-open': [execs['o-open'][0]], 'o-close': execs['o-close']}
            trd4 = FakeTrader()
            out = await led.record_trade(pool, trd4, FakeClient({k: [dict(e, execId=e['execId'] + '-4') for e in v] for k, v in ex4.items()}),
                                         await row(4))
            check('B6: llenado parcial: el control lo dice y queda en el historial',
                  any('llenó 6' in x for x in out['checks']) and trd4.audit and trd4.audit[0][2]['checks'] == out['checks'], out['checks'])

            # Bybit no responde: no se escribe nada
            await trade(5, close_oid='o-close')
            out = await led.record_trade(pool, FakeTrader(), FakeClient({}, fail=True), await row(5))
            n5 = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 5")
            check('B7: Bybit sin respuesta: error, nada guardado y sigue pendiente', out['error'] and n5 == 0
                  and (await row(5))['executions_status'] is None, out)

            # sin partes del cierre 24 h después
            await trade(6, close_oid='o-gone', exit_t=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2))
            ex6 = {'o-open': [dict(e, execId=e['execId'] + '-6') for e in execs['o-open']]}
            trd6 = FakeTrader()
            out = await led.record_trade(pool, trd6, FakeClient(ex6), await row(6))
            check('B8: sin las partes del cierre 24 h después: «missing» y aviso en el historial',
                  (await row(6))['executions_status'] == 'missing' and trd6.audit[0][1] == 'executions_missing', out)

            # vista previa
            await trade(7, close_oid='o-close')
            ex7 = {k: [dict(e, execId=e['execId'] + '-7') for e in v] for k, v in execs.items()}
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex7), await row(7), apply=False)
            n7 = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 7")
            check('B9: vista previa: muestra el resumen y no escribe nada', out['status'] == 'ok' and out['open']['parts'] == 2
                  and n7 == 0 and (await row(7))['executions_status'] is None, (out['status'], n7))

            # selección del tick
            await c.execute("UPDATE real_trades SET broker_account_id = NULL WHERE user_id = $1", uid)
            ba = await c.fetchval("""INSERT INTO broker_accounts (user_id, broker, account_type, label, api_key, api_secret, status,
                created_at, updated_at) VALUES ($1, 'bybit', 'demo', 't', 'k', 's', 'active', now(), now()) RETURNING id""", uid)
            await c.execute("UPDATE real_trades SET broker_account_id = $1 WHERE user_id = $2", ba, uid)
            await trade(8, status='open', oid='o-8')
            await c.execute("UPDATE real_trades SET broker_account_id = $1 WHERE id = 8", ba)
            picked = []

            async def spy(pool_, trader_, client_, t, apply=True, now=None):
                picked.append(t['id'])
                return {}
            orig = led.record_trade
            led.record_trade = spy
            try:
                await led.process_pending(pool, FakeTrader(), FakeClient({}), ba, limit=10)
            finally:
                led.record_trade = orig
            check('B10: el tick toma las pendientes (5, 7 y la abierta 8), no las «historical» (1) ni las resueltas',
                  picked == [5, 7, 8], picked)
        finally:
            for q in ("DELETE FROM real_trades WHERE user_id = $1", "DELETE FROM broker_accounts WHERE user_id = $1",
                      "DELETE FROM users WHERE id = $1"):
                await c.execute(q, uid)
            await c.execute(DOWN)
            await pool.release(c)
            await pool.close()

    asyncio.run(main())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

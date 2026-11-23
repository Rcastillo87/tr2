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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tests/Forensic/ (C5-04: barrera de base)
from test_db import require_test_db, test_dsn  # noqa: E402
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

# R-24: separar comisión y funding (positivo = pagado). Cifras de #92 ENAUSDT: comisiones 21,1188 y funding cobrado 1,0761
sp, note = led.split_costs(-10, -30.0427, 21.1188, -30.0427)
check('A10: separa: comisión = la de las partes y funding = bruto − neto − comisión (cobrado = negativo)',
      note is None and sp == {'commission': 21.1188, 'funding': -1.0761}, (sp, note))
sp, note = led.split_costs(-10, -30.0427, 21.1188, -30.5427)
check('A11: neto registrado distinto del de Bybit: no separa y dice por qué', sp is None and 'neto registrado' in note, note)
sp, note = led.split_costs(-10, -30.0427, 21.1188, None)
check('A12: sin closed-pnl de Bybit: no separa', sp is None and 'closed-pnl' in note, note)
sp, note = led.split_costs(-10, -30.0427, 21.1188, -30.0477)
check('A13: diferencia de redondeo del neto (0,005): sí separa', sp is not None and note is None, note)

# C5-01 (p99): comisión desconocida ≠ 0; pata completa
rows_nf = [led.parse_execution(ex('n1', 'o1', 10.0, 6, T0), 'open'),
           led.parse_execution(dict(ex('n2', 'o1', 10.0, 4, T0), execFee=None), 'open')]
s_nf = led.leg_summary(rows_nf)
check('A14: una parte sin comisión: la comisión de la pata es desconocida (None), no 0,006',
      s_nf['fee'] is None and s_nf['fee_unknown'] == 1, s_nf)
c = led.leg_checks(dict(tr, entry_price=10.0), s_nf, None)
check('A15: y queda como diferencia («no informó la comisión»)', any('no informó la comisión de 1' in x for x in c), c)
check('A16: pata completa = cantidad del tamaño y comisiones conocidas', led.leg_ok(tr, s) and not led.leg_ok(tr, s_nf)
      and not led.leg_ok(dict(tr, size=12), s) and not led.leg_ok(tr, None))
check('A17: a la base va el número como lo dio Bybit (15.91, no 15.910000000000000142…)',
      str(led._dec(15.91)) == '15.91' and led._dec(None) is None)


# Cliente de Bybit (C5-01): paginación que se agota y «no sé» ≠ «no hay»
def client_cases():
    import trading.real_trader as rt

    class Resp:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    def mk(pages, fail_at=None):
        cl = rt.BybitClient('k', 's', 'demo')
        calls = []

        async def signed_get(path, params, timeout=10):
            calls.append((path, dict(params)))
            i = len(calls) - 1
            if fail_at is not None and i == fail_at:
                return Resp({'retCode': 10006, 'retMsg': 'Too many visits'})
            lst, cur = pages[min(i, len(pages) - 1)]
            return Resp({'retCode': 0, 'result': {'list': lst, 'nextPageCursor': cur}})
        cl._signed_get = signed_get
        return cl, calls
    e = lambda i: {'execId': f'x{i}', 'orderId': 'o1'}   # noqa: E731
    cl, calls = mk([([e(1)], 'c1'), ([e(2)], '')])
    got = asyncio.run(cl.get_executions('LINKUSDT', 'o1', 0, 1000))
    check('K1: execution/list en 2 páginas: junta las dos y manda el cursor', [x['execId'] for x in got] == ['x1', 'x2']
          and calls[1][1].get('cursor') == 'c1', (got, calls))
    cl, calls = mk([([e(1)], 'sigue')])
    got = asyncio.run(cl.get_executions('LINKUSDT', 'o1', 0, 1000))
    check('K2: execution/list con cursor después de 10 páginas: «no sé» (None), no una lista incompleta',
          got is None and len(calls) == rt.MAX_PAGES, (got, len(calls)))
    h = lambda t, o: {'orderId': o, 'avgEntryPrice': '10.0', 'createdTime': str(t), 'closedPnl': '1'}   # noqa: E731
    cl, calls = mk([([h(5000, 't1')], 'c1'), ([h(6000, 't2'), dict(h(6000, 'otra'), avgEntryPrice='20')], '')])
    got = asyncio.run(cl.get_closed_pnl_history('LINKUSDT', 10.0, 1000, limit=100, end_time_ms=9000, strict=True))
    check('K3: closed-pnl estricto en 2 páginas: junta las dos y filtra los de otra entrada',
          [x['orderId'] for x in got] == ['t1', 't2'] and calls[0][0] == '/v5/position/closed-pnl'
          and calls[1][1].get('cursor') == 'c1' and 'cursor' not in calls[0][1], (got, calls))
    cl, calls = mk([([h(5000, 't1')], 'c1'), ([], '')], fail_at=1)
    got = asyncio.run(cl.get_closed_pnl_history('LINKUSDT', 10.0, 1000, limit=100, end_time_ms=9000, strict=True))
    check('K4: closed-pnl estricto con error de Bybit en la página 2: «no sé» (None), no «no hay cierres»', got is None, got)
    cl, calls = mk([([h(5000, 't1')], 'sigue')])
    got = asyncio.run(cl.get_closed_pnl_history('LINKUSDT', 10.0, 1000, limit=100, end_time_ms=9000, strict=True))
    check('K5: closed-pnl estricto con páginas sin leer: None', got is None and len(calls) == rt.MAX_PAGES, len(calls))
    src = (ROOT / 'python-engine' / 'trading' / 'execution_ledger.py').read_text(encoding='utf-8')
    check('K6: el libro pide el closed-pnl siempre en modo estricto', src.count('get_closed_pnl_history(') == 2
          and src.count('strict=True') == 2, src.count('strict=True'))


client_cases()

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
cs = (ROOT / 'app' / 'Console' / 'Commands' / 'RealCostsSplit.php')
cs = cs.read_text(encoding='utf-8') if cs.exists() else ''
check('C4: R-24: endpoint /real/costs/split con vista previa y comando real:costs-split con --apply',
      "@router.post('/real/costs/split')" in api and "funding IS NULL" in api and "'real:costs-split {--apply" in cs
      and "'/v1/real/costs/split'" in cs and 'SafeLogBody::of(' in cs)
check('C5: el tick y los dos endpoints leen las columnas de costos (TRADE_COLS con pnl, net_pnl, commission, funding)',
      'pnl, net_pnl, commission, funding' in led.TRADE_COLS and api.count('execution_ledger.TRADE_COLS') == 2
      and 'SELECT {TRADE_COLS}' in (ROOT / 'python-engine' / 'trading' / 'execution_ledger.py').read_text(encoding='utf-8'))

# ── B. Con PostgreSQL ──
# B aplica DOWN/UP de la migración: solo en una base de pruebas (nombre terminado en «test»), nunca en producción.
if not require_test_db('B'):   # C5-04: nunca la base de producción
    pass
else:
    import asyncpg
    DB_DSN = test_dsn()
    UP = (ROOT / 'database' / 'sql-migrations' / '2026_11_20_02_real_trade_executions.up.sql').read_text(encoding='utf-8')
    DOWN = (ROOT / 'database' / 'sql-migrations' / '2026_11_20_02_real_trade_executions.down.sql').read_text(encoding='utf-8')
    F_UP = (ROOT / 'database' / 'sql-migrations' / '2026_11_20_03_real_trades_funding.up.sql').read_text(encoding='utf-8')
    F_DOWN = (ROOT / 'database' / 'sql-migrations' / '2026_11_20_03_real_trades_funding.down.sql').read_text(encoding='utf-8')

    class FakeClient:
        def __init__(self, execs, history=(), fail=False):
            self.execs, self.history, self.fail, self.windows = execs, None if history is None else list(history), fail, []

        async def get_executions(self, symbol, oid, start_ms, end_ms):
            self.windows.append((oid, start_ms, end_ms))
            return None if self.fail else [e for e in self.execs.get(oid, []) if start_ms <= int(e['execTime']) <= end_ms]

        async def get_closed_pnl_history(self, symbol, entry, since_ms, limit=20, end_time_ms=None, strict=False):
            return None if self.history is None else self.history

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
            await c.execute(F_DOWN)
            await c.execute(F_UP)
            await c.execute(F_UP)   # repetir la migración no falla
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
            await trade(3, close_oid=None, exit_=9.78)   # precio promedio de los 2 tramos (C5-01: «ok» solo si cuadra)
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

            # R-24: cierre del bot con neto de Bybit: separa comisión y funding
            async def full(tid):
                return dict(await c.fetchrow(f"SELECT {led.TRADE_COLS} FROM real_trades WHERE id = $1", tid))
            ex9 = {k: [dict(e, execId=e['execId'] + '-9') for e in v] for k, v in execs.items()}   # comisiones 0,01 × 3
            # bruto (10,2 − 9,8) × 10 = 4; funding pagado 0,2; neto de Bybit 4 − 0,03 − 0,2 = 3,77; registrado: comisión 0,23
            await trade(9, close_oid='o-close')
            await c.execute("UPDATE real_trades SET pnl = 4, net_pnl = 3.77, commission = 0.23 WHERE id = 9")
            h9 = [{'orderId': 'o-close', 'closedPnl': '3.77', 'createdTime': str(MS(T0 + timedelta(hours=2)))},
                  {'orderId': 'otra', 'closedPnl': '99', 'createdTime': str(MS(T0 + timedelta(hours=2)))}]
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex9, h9), await full(9), apply=False)
            r9 = await full(9)
            check('B11: vista previa de R-24: muestra el reparto y no escribe', out['split'] == {
                'commission': 0.03, 'funding': 0.2, 'commission_before': 0.23} and r9['funding'] is None
                and float(r9['commission']) == 0.23, (out['split'], r9['funding']))
            trd9 = FakeTrader()
            out = await led.record_trade(pool, trd9, FakeClient(ex9, h9), await full(9))
            r9 = await full(9)
            check('B12: separa: comisión 0,03 (la de las partes) y funding 0,2 pagado; bruto y neto sin cambio; en el historial',
                  float(r9['commission']) == 0.03 and float(r9['funding']) == 0.2 and float(r9['pnl']) == 4
                  and float(r9['net_pnl']) == 3.77 and ('costs_split' in [a[1] for a in trd9.audit]), (dict(r9), trd9.audit))
            trd9b = FakeTrader()
            await led.record_trade(pool, trd9b, FakeClient(ex9, h9), await full(9))
            check('B13: repetir no vuelve a separar ni repite el historial', trd9b.audit == [] and float((await full(9))['funding']) == 0.2,
                  trd9b.audit)

            # neto estimado (sin closed-pnl al cerrar): no se separa
            await trade(10, close_oid='o-close')
            await c.execute("UPDATE real_trades SET pnl = 4, net_pnl = 3.9889, commission = 0.0111 WHERE id = 10")
            ex10 = {k: [dict(e, execId=e['execId'] + '-10') for e in v] for k, v in execs.items()}
            trd10 = FakeTrader()
            out = await led.record_trade(pool, trd10, FakeClient(ex10, h9), await full(10))
            r10 = await full(10)
            check('B14: neto registrado distinto del de Bybit: no toca comisión ni funding y lo deja en el historial',
                  r10['funding'] is None and float(r10['commission']) == 0.0111 and 'neto registrado' in (out['split_note'] or '')
                  and any(a[1] == 'costs_split' and 'neto registrado' in (a[2]['note'] or '') for a in trd10.audit), out['split_note'])

            # lectura vieja (funding NULL en memoria, ya separado en la base): no se pisa
            await trade(11, close_oid='o-close')
            await c.execute("UPDATE real_trades SET pnl = 4, net_pnl = 3.77, commission = 0.23 WHERE id = 11")
            stale = await full(11)
            await c.execute("UPDATE real_trades SET commission = 0.05, funding = 0.18 WHERE id = 11")
            ex11 = {k: [dict(e, execId=e['execId'] + '-11') for e in v] for k, v in execs.items()}
            await led.record_trade(pool, FakeTrader(), FakeClient(ex11, h9), stale)
            r11 = await full(11)
            check('B15: con una lectura vieja no pisa un reparto ya guardado (UPDATE solo si funding IS NULL)',
                  float(r11['commission']) == 0.05 and float(r11['funding']) == 0.18, (r11['commission'], r11['funding']))

            # ── C5-01 (p99) ──
            async def full_b(tid):
                return dict(await c.fetchrow(f"SELECT {led.TRADE_COLS} FROM real_trades WHERE id = $1", tid))
            recent = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
            old_t = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)

            def close_at(eid, t, **kw):   # la parte del cierre a la hora del cierre del trade
                return dict(ex(eid, 'o-close', 9.8, 10, t), **kw)
            # llenado parcial reciente: no queda «ok» ni separa costos; sigue pendiente
            await trade(12, close_oid='o-close', exit_t=recent)
            await c.execute("UPDATE real_trades SET broker_account_id = $1, pnl = 4, net_pnl = 3.77, commission = 0.23 WHERE id = 12", ba)
            ex12 = {'o-open': [dict(execs['o-open'][0], execId='z1')], 'o-close': [close_at('z3', recent)]}
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex12, h9), await full_b(12))
            r12 = await full_b(12)
            check('B16: cantidad que no cuadra (6 de 10), cierre reciente: NO queda «ok», no separa costos y sigue pendiente',
                  r12['executions_status'] is None and r12['funding'] is None and out['split'] is None and out['checks'], (r12['executions_status'], out['checks']))
            # Bybit entrega después la parte que faltaba: se vuelve a pedir la apertura y queda «ok» con costos
            ex12b = {'o-open': [dict(execs['o-open'][0], execId='z1'), dict(execs['o-open'][1], execId='z2')],
                     'o-close': ex12['o-close']}
            cl12 = FakeClient(ex12b, h9)
            out = await led.record_trade(pool, FakeTrader(), cl12, await full_b(12))
            r12 = await full_b(12)
            n12 = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 12")
            check('B17: la pata guardada incompleta se vuelve a pedir: 3 partes sin duplicar, «ok» y costos separados',
                  r12['executions_status'] == 'ok' and n12 == 3 and float(r12['funding']) == 0.2
                  and any(w[0] == 'o-open' for w in cl12.windows) and not any(w[0] == 'o-close' for w in cl12.windows),
                  (r12['executions_status'], n12, cl12.windows))
            ev12 = await c.fetchval("SELECT count(*) FROM broker_events WHERE trade_id = 12")
            check('B17b: una que termina cuadrando no avisa al dueño', ev12 == 0, ev12)
            # 24 h después sigue sin cuadrar: «mismatch», historial y aviso al dueño (una vez)
            await trade(13, close_oid='o-close', exit_t=old_t)
            await c.execute("UPDATE real_trades SET broker_account_id = $1 WHERE id = 13", ba)
            ex13 = {'o-open': [dict(execs['o-open'][0], execId='m1')], 'o-close': [close_at('m3', old_t)]}
            trd13 = FakeTrader()
            await led.record_trade(pool, trd13, FakeClient(ex13, h9), await full_b(13))
            ev = await c.fetch("SELECT event, data FROM broker_events WHERE trade_id = 13")
            await led.record_trade(pool, FakeTrader(), FakeClient(ex13, h9), await full_b(13))
            ev2 = await c.fetchval("SELECT count(*) FROM broker_events WHERE trade_id = 13")
            check('B18: 24 h sin cuadrar: «mismatch», «executions_mismatch» en el historial y un solo aviso con la diferencia',
                  (await full_b(13))['executions_status'] == 'mismatch' and trd13.audit[-1][1] == 'executions_mismatch'
                  and [r['event'] for r in ev] == ['executions_mismatch'] and 'llenó 6' in str(ev[0]['data']) and ev2 == 1,
                  ((await full_b(13))['executions_status'], [a[1] for a in trd13.audit], [dict(r) for r in ev], ev2))
            # cierre de Bybit (sin close_order_id) y closed-pnl con error: «no sé», ni «missing» aunque pasaron 24 h
            await trade(14, close_oid=None, exit_t=old_t)
            ex14 = {'o-open': [dict(e, execId=e['execId'] + '-14') for e in execs['o-open']]}
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex14, None), await full_b(14))
            check('B19: closed-pnl con error: error y sigue pendiente (no «missing», no «no hay cierres»)',
                  out['error'] and 'órdenes de cierre' in out['error'] and (await full_b(14))['executions_status'] is None, out)
            # comisión que Bybit no informa: no «ok» ni costos; cuando la informa, se completa la parte guardada
            await trade(15, close_oid='o-close', exit_t=recent)
            await c.execute("UPDATE real_trades SET pnl = 4, net_pnl = 3.77, commission = 0.23 WHERE id = 15")
            ex15 = {'o-open': [dict(e, execId=e['execId'] + '-15') for e in execs['o-open']],
                    'o-close': [close_at('x3-15', recent, execFee=None)]}
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex15, h9), await full_b(15))
            r15 = await full_b(15)
            check('B20: sin comisión de Bybit: no «ok», no separa costos (antes contaba 0)',
                  r15['executions_status'] is None and r15['funding'] is None and out['close']['fee'] is None, (r15['executions_status'], out['close']))
            ex15['o-close'] = [close_at('x3-15', recent)]
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex15, h9), await full_b(15))
            r15 = await full_b(15)
            fee15 = await c.fetchval("SELECT exec_fee FROM real_trade_executions WHERE exec_id = 'x3-15'")
            n15 = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 15")
            check('B21: Bybit informa la comisión después: se completa la parte (sin duplicar), «ok» y costos separados',
                  r15['executions_status'] == 'ok' and fee15 is not None and float(fee15) == 0.01 and n15 == 3
                  and float(r15['funding']) == 0.2, (r15['executions_status'], fee15, n15))
            # todo cuadra pero closed-pnl con error al separar: no queda «ok» todavía
            await trade(16, close_oid='o-close', exit_t=recent)
            await c.execute("UPDATE real_trades SET pnl = 4, net_pnl = 3.77, commission = 0.23 WHERE id = 16")
            ex16 = {'o-open': [dict(e, execId=e['execId'] + '-16') for e in execs['o-open']], 'o-close': [close_at('x3-16', recent)]}
            out = await led.record_trade(pool, FakeTrader(), FakeClient(ex16, None), await full_b(16))
            check('B22: partes completas pero closed-pnl con error: sigue pendiente (se reintenta), sin costos',
                  (await full_b(16))['executions_status'] is None and out['error'] and 'closed-pnl' in out['error']
                  and (await full_b(16))['funding'] is None, out)
            n16 = await c.fetchval("SELECT count(*) FROM real_trade_executions WHERE real_trade_id = 16")
            check('B23: y las partes ya leídas quedan guardadas (no se vuelven a pedir)', n16 == 3, n16)
            # el tick no vuelve a pedir antes de 10 min una que quedó sin verificar
            await c.execute("UPDATE real_trades SET broker_account_id = $1 WHERE id IN (14, 16)", ba)
            led._RETRY_AT.clear()
            seen = []
            orig = led.record_trade

            async def spy2(pool_, trader_, client_, t, apply=True, now=None):
                seen.append(t['id'])
                return {'error': 'x', 'status': None} if t['id'] in (14, 16) else {'status': 'ok'}
            led.record_trade = spy2
            try:
                await led.process_pending(pool, FakeTrader(), FakeClient({}), ba, limit=10)
                first = list(seen)
                seen.clear()
                await led.process_pending(pool, FakeTrader(), FakeClient({}), ba, limit=10)
            finally:
                led.record_trade = orig
            check('B24: una sin verificar espera 10 min (el tick no la repite cada minuto ni acapara el turno)',
                  14 in first and 16 in first and 14 not in seen and 16 not in seen, (first, seen))
        finally:
            await c.execute("DELETE FROM broker_events WHERE broker_account_id IN (SELECT id FROM broker_accounts WHERE user_id = $1)", uid)
            for q in ("DELETE FROM real_trades WHERE user_id = $1", "DELETE FROM broker_accounts WHERE user_id = $1",
                      "DELETE FROM users WHERE id = $1"):
                await c.execute(q, uid)
            await c.execute(DOWN)
            await c.execute(F_DOWN)
            await pool.release(c)
            await pool.close()

    asyncio.run(main())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

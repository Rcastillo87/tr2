"""
Avisos de broker (broker_events) y gestión de cuentas pausadas.
  A. emit_event contra la base REAL dentro de una transacción que se revierte (no deja filas ni avisos).
  B. Puntos de emisión del motor con pool y Bybit simulados (sin órdenes reales).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/broker_events_test.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/
from test_db import require_test_db, test_dsn  # noqa: E402  (C5-04: barrera de base)

from dotenv import load_dotenv  # noqa: E402

load_dotenv('.env')

import asyncpg  # noqa: E402

import real_parity_test as rp  # noqa: E402  (fakes compartidos; también anula las esperas)
import api.v1.real_trading as api  # noqa: E402
import trading.real_trader as rt_mod  # noqa: E402
from trading.broker_events import emit_event  # noqa: E402
from trading.real_trader import BybitAPIError, RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def events(s):
    """Eventos registrados en el pool simulado: [(evento, trade_id, data)]."""
    return [(a[2], a[1], json.loads(a[3])) for sql, a in s['exec'] if 'INSERT INTO broker_events' in sql]


# ─────────────────────────── A. Base real (transacción revertida) ───────────────────────────
class _TxPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _C:
            async def __aenter__(self_):
                return conn

            async def __aexit__(self_, *e):
                return False
        return _C()


class _BrokenPool:
    def acquire(self):
        raise RuntimeError('pool caído (simulado)')


async def part_a():
    conn = await asyncpg.connect(test_dsn())
    tx = conn.transaction()
    await tx.start()
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.broker_events') IS NOT NULL")
        check('A: tabla broker_events existe (migración aplicada)', exists)
        if not exists:
            return
        before = await conn.fetchval("SELECT count(*) FROM broker_events")
        ok = await emit_event(_TxPool(conn), 999999, 'open_rejected', 123, symbol='BTCUSDT', reason='prueba', nada=None)
        row = await conn.fetchrow("SELECT * FROM broker_events ORDER BY id DESC LIMIT 1")
        data = json.loads(row['data']) if isinstance(row['data'], str) else row['data']
        check('A: emit_event inserta la fila', ok and row['broker_account_id'] == 999999 and row['trade_id'] == 123
              and row['event'] == 'open_rejected' and row['processed_at'] is None, dict(row))
        check('A: data jsonb sin claves nulas', data == {'symbol': 'BTCUSDT', 'reason': 'prueba'}, data)
        bad = await emit_event(_TxPool(conn), 999999, 'evento_inventado')
        after = await conn.fetchval("SELECT count(*) FROM broker_events")
        check('A: evento desconocido no se registra', bad is False and after == before + 1, (bad, after - before))
        idx = await conn.fetchval("SELECT indexdef FROM pg_indexes WHERE indexname = 'broker_events_pending_idx'")
        check('A: índice parcial de pendientes', bool(idx) and 'processed_at IS NULL' in idx, idx)
    finally:
        await tx.rollback()
        await conn.close()
    check('A: pool caído -> False sin excepción', await emit_event(_BrokenPool(), 1, 'account_paused', reason='x') is False)


# ─────────────────────────── B. Emisión en el motor (simulado) ───────────────────────────
SUB = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 7, 'user_id': 1, 'subscription_id': 1,
       'paper_strategy_config_id': 9, 'strategy': 'T', 'broker': 'bybit', 'config_params': dict(rp.P)}


class RejectingClient(rp.FakeClient):
    async def place_market_order(self, symbol, side, qty, sl=None, tp=None, **k):
        self.orders.append((side, qty, sl, tp, k))
        self.last_order_error = 'Insufficient balance (code 110007)'
        return None


class SeqPositionClient(rp.FakeClient):
    """get_open_position devuelve en orden los valores de `seq` (dict, None o 'ERR')."""

    def __init__(self, seq, **kw):
        super().__init__(**kw)
        self.seq = list(seq)

    async def get_open_position(self, symbol):
        p = self.seq.pop(0) if self.seq else None
        if p == 'ERR':
            raise BybitAPIError('caída simulada')
        return p


async def part_b():
    strat = rt_mod.build_strategy({**rp.P, 'symbol': 'BTCUSDT', 'interval': '60'})

    # B1. Apertura rechazada por Bybit -> open_rejected con el motivo de Bybit
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING', RejectingClient())
    ev = events(s)
    check('B1: apertura rechazada -> open_rejected', not ok and len(ev) == 1 and ev[0][0] == 'open_rejected'
          and ev[0][2].get('reason') == 'Insufficient balance (code 110007)' and ev[0][2].get('strategy') == 'T', ev)

    # B2. Orden terminada en Rejected -> open_rejected
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING',
                                                     rp.FakeClient(fill_on_check=99, order_status='Rejected'))
    ev = events(s)
    check('B2: orden Rejected -> open_rejected', not ok and [e[0] for e in ev] == ['open_rejected']
          and 'Rejected' in ev[0][2].get('reason', ''), ev)

    # B3. Apertura sin confirmar -> orphaned + open_unconfirmed
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING',
                                                     rp.FakeClient(fill_on_check=99, order_status='New'))
    check('B3: sin confirmar -> open_unconfirmed', not ok and [e[0] for e in events(s)] == ['open_unconfirmed'], events(s))

    # B4. Apertura normal -> ningún evento
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).open_trade(SUB, strat, 'long', 100.0, 'RANGING', rp.FakeClient(fill_on_check=2))
    check('B4: apertura normal -> sin eventos', ok and not events(s), events(s))

    # B5. Cierre rechazado con la posición viva -> vuelve a open + close_failed; nunca status 'error'
    s = {'exec': []}
    c = SeqPositionClient([rp.position(), rp.position()])
    c.place_market_order = RejectingClient.place_market_order.__get__(c)
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    sqls = [sql for sql, _ in s['exec']]
    ev = events(s)
    check('B5: cierre rechazado + posición viva -> close_failed', ok is False and [e[0] for e in ev] == ['close_failed']
          and 'Insufficient' in ev[0][2].get('reason', ''), ev)
    check('B5: vuelve a open (no queda status error)', any("SET status='open'" in q for q in sqls)
          and not any("status = 'error'" in q for q in sqls), sqls)

    # B6. Cierre rechazado porque ya estaba en cero (110017) -> se liquida con Bybit, sin aviso
    s = {'exec': []}
    hist = [{'closedSize': '1', 'cumExitValue': '101.0', 'closedPnl': '0.89'}]
    c = SeqPositionClient([rp.position(), None], history=hist)
    c.place_market_order = RejectingClient.place_market_order.__get__(c)
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    check('B6: rechazo con posición ya en cero -> liquidado, sin aviso', ok is True and not events(s)
          and rp.closes(s), (ok, events(s)))

    # B7. Cierre sin confirmar y Bybit caído -> close_unconfirmed
    s = {'exec': []}
    c = SeqPositionClient([rp.position(), 'ERR'], order_status='New')
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    check('B7: cierre sin confirmar + Bybit caído -> close_unconfirmed',
          ok is False and [e[0] for e in events(s)] == ['close_unconfirmed'], events(s))

    # B8. Circuit breaker -> account_paused
    s = {'exec': []}
    await RealTrader(rp.FakePool(s)).pause_account(7, '3 errores criticos en las ultimas 2h')
    ev = events(s)
    check('B8: pausa -> account_paused con motivo', [e[0] for e in ev] == ['account_paused']
          and '3 errores' in ev[0][2]['reason'], ev)


# ─────────────────────────── C. Claves API y cuentas pausadas (_process_account) ───────────────────────────
class FakeTrader:
    def __init__(self, s, errors=0, last_errors=None):
        self.pool, self.s, self.errors, self.last_errors = rp.FakePool(s), s, errors, last_errors or []
        self.calls = []

    async def get_circuit_breaker_errors(self, account_id):
        self.calls.append('cb')
        return self.errors

    async def get_last_error_messages(self, account_id):
        return self.last_errors

    async def pause_account(self, account_id, reason):
        self.calls.append('pause')

    async def ensure_month_baseline(self, account_id, client):
        return None

    async def ensure_loss_pause_end(self, account_id, client):   # D-66 (p111): paso nuevo del ciclo
        return None

    async def clear_non_critical_errors(self, account_id):
        self.calls.append('clear')

    async def monitor_open_trades(self, account_id, client):
        self.calls.append('monitor')
        return {'checked': 1, 'closed': 0, 'be_activated': 0, 'errors': 0}

    async def check_new_signals(self, sub, strategy, client, entries_allowed=True):
        self.calls.append('signals' if entries_allowed else 'signals_no_entries')
        return 'sin señal'


class AuthClient:
    def __init__(self, ok, reason=''):
        self.ok, self.reason = ok, reason

    async def check_auth(self):
        return self.ok, self.reason


class _NoKill:
    def __init__(self, pool):
        pass

    async def is_kill_switch_active(self):
        return False


def account(entries=True, subs=True):
    sub = {'subscription_id': 1, 'user_id': 1, 'broker_account_id': 7, 'strategy': 'T', 'symbol': 'BTCUSDT',
           'interval': '60', 'config_params': dict(rp.P)}
    return api.AccountPayload(id=7, broker='bybit', account_type='demo', api_key='k', api_secret='s',
                              subscriptions=[sub] if subs else [], entries_allowed=entries)


async def run_account(client, **kw):
    s = {'exec': []}
    tr = FakeTrader(s, **{k: v for k, v in kw.items() if k in ('errors', 'last_errors')})
    api._build_broker_client = lambda acc: client
    key, res = await api._process_account(tr, account(**{k: v for k, v in kw.items() if k in ('entries',)}))
    return tr, res, events(s)


async def part_c():
    api.RiskManager = _NoKill
    api._auth_state.clear()

    tr, res, ev = await run_account(AuthClient(False, 'API key is invalid. (code 10003)'))
    check('C1: claves rechazadas -> error, no monitorea ni opera', 'error' in res and not tr.calls, (res, tr.calls))
    check('C1: emite api_auth_failed una vez', [e[0] for e in ev] == ['api_auth_failed'], ev)
    tr, res, ev = await run_account(AuthClient(False, 'API key is invalid. (code 10003)'))
    check('C2: sigue fallando -> sin evento repetido', not ev, ev)
    tr, res, ev = await run_account(AuthClient(None, 'timeout'))
    check('C3: estado desconocido (red) -> sin evento y sigue operando', not ev and 'monitor' in tr.calls, (ev, tr.calls))
    tr, res, ev = await run_account(AuthClient(True))
    check('C4: claves aceptadas de nuevo -> api_auth_ok', [e[0] for e in ev] == ['api_auth_ok'], ev)
    tr, res, ev = await run_account(AuthClient(True))
    check('C5: sigue OK -> sin evento', not ev, ev)

    tr, res, ev = await run_account(AuthClient(True), entries=False)
    check('C6: cuenta pausada -> monitorea, no evalúa circuit breaker; señales solo sin entradas (salida opuesta)',
          tr.calls == ['monitor', 'signals_no_entries'] and 'pausada' in str(res.get('entries')), (tr.calls, res))

    tr, res, ev = await run_account(AuthClient(True), errors=3, last_errors=['error grave desconocido'])
    check('C7: circuit breaker crítico -> pausa y AÚN monitorea, sin entradas',
          tr.calls == ['cb', 'pause', 'monitor', 'signals_no_entries'] and 'pausada' in str(res.get('entries')),
          (tr.calls, res))

    tr, res, ev = await run_account(AuthClient(True), errors=3, last_errors=['Orden rechazada por Bybit (qty)'])
    check('C8: errores no críticos -> limpia y opera normal', tr.calls == ['cb', 'clear', 'monitor', 'signals'], tr.calls)


# ─────────────────────────── D. Conciliación ───────────────────────────
class ReconcileConn(rp.FakeConn):
    async def fetch(self, sql, *a):
        return self.s.get('orphans', []) if "status = 'orphaned'" in sql else []

    async def execute(self, sql, *a):
        if 'INSERT INTO broker_events' in sql and a[2] in self.s.get('fail_events', ()):
            raise RuntimeError('base caída simulada')
        return await super().execute(sql, *a)

    async def fetchrow(self, sql, *a):
        if "'manual_position_closed'" in sql:   # último aviso manual de la moneda (D-61)
            return self.s.get('manual_last')
        if 'FROM real_trades' in sql and self.s.get('bot_row'):
            return {'id': 9}
        return None

    async def fetchval(self, sql, *a):
        if 'INSERT INTO real_trades' in sql:
            return 55
        if "event = 'manual_position_ignored'" in sql:   # consulta anterior a D-61 (moneda, lado y precio)
            m = self.s.get('manual_last')
            return 1 if m and m['event'] == 'manual_position_ignored' and m['side'] == a[2] \
                and m.get('avg_price') == a[3] else None
        return await super().fetchval(sql, *a)


class ReconcilePool(rp.FakePool):
    async def close(self):
        return None

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return ReconcileConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


async def run_reconcile(s, open_trades, client, settle=True):
    class _Trader(RealTrader):
        async def get_open_trades(self, account_id):
            return open_trades

        async def settle_exchange_close(self, *a, **k):
            return settle

        async def has_open_trade(self, *a):
            return bool(s.get('bot_has'))

    pool = ReconcilePool(s)

    async def _pool():
        return pool

    api.get_json_pool = _pool
    api.RealTrader = _Trader
    api._build_broker_client = lambda acc: client
    req = api.RealTickRequest(accounts=[account()])
    return await api.reconcile(req, x_internal_api_key=api.INTERNAL_API_KEY)


async def part_d():
    old = dict(rp.trade(), entry_time=datetime.now(timezone.utc) - timedelta(hours=2))

    s = {'exec': []}
    await run_reconcile(s, [old], SeqPositionClient([None, None]))
    check('D1: cerrada en Bybit -> reconcile_closed', [e[0] for e in events(s)] == ['reconcile_closed'], events(s))

    orphan = dict(old, status='orphaned', error_message='No confirmada tras 3 verificaciones (38s)',
                  snapshot=dict(rp.P), config_snapshot=dict(rp.P))
    s = {'exec': [], 'orphans': [orphan]}
    await run_reconcile(s, [], SeqPositionClient([rp.position(), None]))
    ev = events(s)
    check('D2: huérfana con posición -> reconcile_adopted protegida',
          [e[0] for e in ev] == ['reconcile_adopted'] and ev[0][2].get('protected') is True
          and ev[0][2].get('kind') == 'orphaned', ev)

    s = {'exec': [], 'orphans': [orphan]}
    await run_reconcile(s, [], SeqPositionClient([None, None]))
    check('D3: huérfana sin posición -> reconcile_discarded', [e[0] for e in events(s)] == ['reconcile_discarded'], events(s))

    s = {'exec': []}
    res = await run_reconcile(s, [], SeqPositionClient([dict(rp.position(), side='Buy')]))
    ev = events(s)
    check('D4: posición en Bybit sin registro (manual) -> NO se adopta: aviso manual_position_ignored (D-18)',
          [e[0] for e in ev] == ['manual_position_ignored'] and ev[0][1] is None and ev[0][2].get('side') == 'long'
          and ev[0][2].get('symbol'), ev)
    check('D4b: no se crea fila en real_trades ni se le pone SL/TP del bot',
          not any('INSERT INTO real_trades' in sql for sql, a in s['exec']) and not s.get('tpsl_calls')
          and (res.get('results') or {}).get('manual_ignored'), ((res.get('results') or {}).get('manual_ignored'), [sql[:40] for sql, a in s['exec']]))
    manual = dict(rp.position(), side='Buy')
    price = str(manual.get('avgPrice') or manual.get('entryPrice') or '')
    seen = {'event': 'manual_position_ignored', 'side': 'long', 'avg_price': price}
    s = {'exec': [], 'manual_last': seen}
    await run_reconcile(s, [], SeqPositionClient([manual]))
    check('D5: la misma posición manual en el siguiente ciclo -> sin aviso repetido', events(s) == [], events(s))

    # C5-11 / D-61: una posición manual es la misma mientras siga abierta del mismo lado
    s = {'exec': [], 'manual_last': seen}
    await run_reconcile(s, [], SeqPositionClient([dict(manual, avgPrice='12345.5', size='0.5')]))
    check('D6: se agregó a la misma manual (otro precio y tamaño) -> sin aviso repetido', events(s) == [], events(s))

    s = {'exec': [], 'manual_last': seen}
    await run_reconcile(s, [], SeqPositionClient([None]))
    ev = events(s)
    check('D7: la manual ya no está -> manual_position_closed con su moneda y lado',
          [e[0] for e in ev] == ['manual_position_closed'] and ev[0][2].get('side') == 'long'
          and ev[0][2].get('symbol') and ev[0][1] is None, ev)

    s = {'exec': [], 'manual_last': {'event': 'manual_position_closed', 'side': 'long'}}
    res = await run_reconcile(s, [], SeqPositionClient([manual]))
    ev = events(s)
    check('D8: nueva manual después de cerrarse, mismo lado y precio -> aviso nuevo',
          [e[0] for e in ev] == ['manual_position_ignored'] and ev[0][2].get('avg_price') == price
          and (res.get('results') or {}).get('manual_ignored'), ev)

    s = {'exec': [], 'manual_last': seen}
    await run_reconcile(s, [], SeqPositionClient([dict(manual, side='Sell')]))
    ev = events(s)
    check('D9: la manual pasó a otro lado entre conciliaciones -> cierre de la anterior y aviso de la nueva',
          [(e[0], e[2].get('side')) for e in ev] == [('manual_position_closed', 'long'), ('manual_position_ignored', 'short')], ev)

    s = {'exec': [], 'manual_last': seen, 'bot_has': True}
    res = await run_reconcile(s, [], SeqPositionClient([manual]))
    check('D10: la posición ahora es del bot -> la manual se da por cerrada; no se cuenta como manual',
          [e[0] for e in events(s)] == ['manual_position_closed'] and not (res.get('results') or {}).get('manual_ignored'),
          (events(s), res.get('results')))

    s = {'exec': [], 'manual_last': seen, 'bot_row': True}
    res = await run_reconcile(s, [], SeqPositionClient([manual]))
    check('D10b: la posición tiene fila del bot en la cuenta (otra suscripción) -> no es manual: la manual se da por cerrada',
          [e[0] for e in events(s)] == ['manual_position_closed'] and not (res.get('results') or {}).get('manual_ignored'),
          (events(s), res.get('results')))

    s = {'exec': [], 'manual_last': seen}
    res = await run_reconcile(s, [], SeqPositionClient(['ERR']))
    check('D11: error de Bybit -> «no sé»: no se da por cerrada', events(s) == []
          and (res.get('results') or {}).get('errors'), (events(s), res.get('results')))

    s = {'exec': [], 'manual_last': {'event': 'manual_position_closed', 'side': 'long'}}
    await run_reconcile(s, [], SeqPositionClient([None]))
    check('D12: ya cerrada y sigue sin posición -> sin aviso repetido', events(s) == [], events(s))

    s = {'exec': [], 'manual_last': seen, 'fail_events': ('manual_position_closed',)}
    await run_reconcile(s, [], SeqPositionClient([dict(manual, side='Sell')]))
    check('D13: no se pudo registrar el cierre -> tampoco se avisa la nueva (se reintenta en la próxima)',
          events(s) == [], events(s))

    acts = getattr(api, 'manual_position_actions', None)
    check('D14: regla pura (sin aviso previo, misma, cerrada, nueva, otro lado)', acts is not None
          and acts(None, None, None) == [] and acts(None, None, 'long') == ['ignored']
          and acts('manual_position_ignored', 'long', 'long') == []
          and acts('manual_position_ignored', 'long', None) == ['closed']
          and acts('manual_position_closed', 'long', 'long') == ['ignored']
          and acts('manual_position_closed', 'long', None) == []
          and acts('manual_position_ignored', 'long', 'short') == ['closed', 'ignored'])


async def main():
    if require_test_db('A'):   # C5-04: nunca la base de producción
        await part_a()
    await part_b()
    await part_c()
    await part_d()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

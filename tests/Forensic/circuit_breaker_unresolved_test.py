"""
C6-03 (D-68): el circuit breaker de pérdida máxima también cubre las operaciones Real en estado dudoso
(pending_open viejo u orphaned) cuya posición sigue viva en Bybit.
- Con certeza de que la posición es la de la operación (lado, tamaño ≤ pedido, sin otra operación viva en la moneda,
  no huérfana de cierre): misma regla que las abiertas, con la entrada de Bybit y su SL (o 2 % si no lo tiene); si pasa
  el tope, cierre reduce-only del tamaño de Bybit, historial y aviso.
- Sin certeza: nunca cierra; aviso «sin poder protegerse» una sola vez.
- Error de Bybit = «no sé» (no cierra ni avisa); sin posición = nada; sin cierres duplicados.
- Las abiertas siguen igual. Laravel: el job elige también las cuentas con dudosas; textos de los avisos.
Base y Bybit simulados (sin red ni PostgreSQL).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/circuit_breaker_unresolved_test.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import BybitAPIError, RealTrader, UNRESOLVED_SQL  # noqa: E402

_UNPROTECTED_NOTIFIED = getattr(rt_mod, '_UNPROTECTED_NOTIFIED', set())   # con el código anterior no existe

ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Conn:
    def __init__(self, s):
        self.s = s

    async def fetch(self, sql, *a):
        if UNRESOLVED_SQL in sql:
            self.s['unresolved_sql'] = sql
            return self.s.get('unresolved', [])
        if "status IN ('pending_open', 'open', 'pending_close', 'orphaned')" in sql:
            return self.s.get('live', [])
        if 'FROM real_trades rt' in sql:           # get_open_trades
            return self.s.get('open', [])
        return []

    async def fetchval(self, sql, *a):
        if 'SELECT audit_log' in sql:
            return []
        return None

    async def fetchrow(self, sql, *a):
        return None

    async def execute(self, sql, *a):
        self.s['exec'].append((sql, a))
        return 'UPDATE 1'

    def transaction(self):
        class T:
            async def __aenter__(self_):
                return self_

            async def __aexit__(self_, *e):
                return False
        return T()


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


class Client:
    def __init__(self, positions, fail=False):
        self.positions, self.fail, self.orders = positions, fail, []

    async def get_open_position(self, symbol):
        if self.fail:
            raise BybitAPIError('Bybit sin respuesta (simulado)')
        return self.positions.get(symbol)

    async def place_market_order(self, symbol, side, qty, reduce_only=False):
        self.orders.append((symbol, side, qty, reduce_only))
        self.positions.pop(symbol, None)            # cerrada en Bybit
        return {'orderId': f'oid{len(self.orders)}', 'orderLinkId': 'x'}


def events(s):
    return [(a[2], json.loads(a[3]) if isinstance(a[3], str) else a[3]) for sql, a in s['exec']
            if 'INSERT INTO broker_events' in sql]


def audits(s):
    out = []
    for sql, a in s['exec']:
        if 'SET audit_log' in sql:
            out += [e['action'] for e in a[0]]
    return out


def dud(id_=9, symbol='ADAUSDT', side='long', size=40.0, status='pending_open', msg=None):
    return {'id': id_, 'symbol': symbol, 'side': side, 'size': size, 'status': status, 'error_message': msg}


def pos(side='Buy', size=40.0, avg=1.0, mark=0.97, sl='0.98'):
    return {'side': side, 'size': str(size), 'avgPrice': str(avg), 'markPrice': str(mark), 'stopLoss': sl}


async def run(s, client):
    _UNPROTECTED_NOTIFIED.clear() if s.get('fresh', True) else None
    res = await RealTrader(Pool(s)).check_max_loss_circuit_breaker(11, client)
    return res


async def main():
    # U1: pending_open viva, identificable; SL provisional en Bybit 0,98 (2 %); tope 1,2 × 2 % = 2,4 % desde 0,98
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()]}
    c = Client({'ADAUSDT': pos(mark=0.955)})          # (0,98 − 0,955)/0,98 = 2,55 % > 2,4 %
    r = await run(s, c)
    ev = events(s)
    check('U1: dudosa viva y suya que pierde de más -> cierre reduce-only con el tamaño de Bybit',
          c.orders == [('ADAUSDT', 'Sell', 40.0, True)] and r['closed'] == 1, (c.orders, r))
    check('U1: aviso de pérdida máxima marcado como operación sin confirmar, e historial',
          [e[0] for e in ev] == ['max_loss_close'] and ev[0][1].get('unresolved') is True
          and 'circuit_breaker_unresolved_close' in audits(s), (ev, audits(s)))
    check('U1: la consulta de dudosas es la regla de D-50 (pending_open de más de 3 min u orphaned)',
          UNRESOLVED_SQL in s.get('unresolved_sql', ''))

    # U2: huérfana de apertura sin SL en Bybit -> referencia 2 % desde la entrada de Bybit
    s = {'exec': [], 'unresolved': [dud(status='orphaned', msg='[huerfana:apertura] x')], 'live': [dud(status='orphaned')]}
    c = Client({'ADAUSDT': pos(sl='', mark=0.955)})
    r = await run(s, c)
    check('U2: huérfana de apertura sin SL en Bybit -> usa 2 % desde la entrada y cierra', c.orders and r['closed'] == 1, (c.orders, r))

    s = {'exec': [], 'unresolved': [dud(side='short')], 'live': [dud(side='short')]}
    c = Client({'ADAUSDT': pos(side='Sell', sl='1.02', mark=1.046)})   # (1,046 − 1,02)/1,02 = 2,55 % > 2,4 %
    r = await run(s, c)
    check('U2b: también en corto (cierra comprando)', c.orders == [('ADAUSDT', 'Buy', 40.0, True)], c.orders)

    # U2c: la referencia es el SL que tiene la posición en Bybit (aquí 1 %, más ajustado que el provisional)
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()]}
    c = Client({'ADAUSDT': pos(sl='0.99', mark=0.975)})   # (0,99 − 0,975)/0,99 = 1,52 % > 1,2 × 1 %
    await run(s, c)
    check('U2c: usa el SL que la posición tiene en Bybit como referencia', len(c.orders) == 1, c.orders)

    # U3: dentro del tope -> no cierra
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()]}
    c = Client({'ADAUSDT': pos(mark=0.965)})          # 1,5 % < 2,4 %
    r = await run(s, c)
    check('U3: pérdida dentro del tope -> no cierra ni avisa', not c.orders and not events(s) and r['closed'] == 0, r)

    # U4–U7: sin certeza -> nunca cierra; aviso una vez
    cases = [
        ('U4: lado distinto', dud(), pos(side='Sell', mark=1.05, sl='1.02'), [dud()]),
        ('U5: tamaño en Bybit mayor que el pedido', dud(size=40.0), pos(size=80.0, mark=0.9), [dud()]),
        ('U6: otra operación del bot viva en la moneda', dud(), pos(mark=0.9), [dud(), dud(id_=12, status='open')]),
        ('U7: huérfana de cierre con la posición viva', dud(status='orphaned', msg='[huerfana:cierre] x (no se pudo obtener pnl real)'),
         pos(mark=0.9), [dud(status='orphaned')]),
    ]
    for name, t, p, live in cases:
        s = {'exec': [], 'unresolved': [t], 'live': live}
        c = Client({'ADAUSDT': p})
        r = await run(s, c)
        ev = events(s)
        check(f'{name} -> NO cierra y avisa «sin poder protegerse»', not c.orders
              and [e[0] for e in ev] == ['unresolved_unprotected'] and ev[0][1].get('reason') and r.get('unidentified') == 1,
              (c.orders, ev))
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()], 'fresh': True}
    c = Client({'ADAUSDT': pos(side='Sell', mark=1.05, sl='1.02')})
    await run(s, c)
    s['exec'].clear()
    s['fresh'] = False
    await run(s, c)
    check('U4b: el aviso «sin poder protegerse» no se repite cada minuto', not events(s), events(s))

    # U8: Bybit sin respuesta -> «no sé»
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()]}
    c = Client({}, fail=True)
    r = await run(s, c)
    check('U8: Bybit sin respuesta -> no cierra ni avisa; cuenta el error', not c.orders and not events(s) and r['errors'] == 1, r)

    # U9: sin posición viva -> nada (la conciliación la resuelve)
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()]}
    c = Client({})
    r = await run(s, c)
    check('U9: sin posición en Bybit -> nada', not c.orders and not events(s) and r['closed'] == 0, r)

    # U10: sin cierres duplicados (la segunda corrida ya no ve posición)
    s = {'exec': [], 'unresolved': [dud()], 'live': [dud()]}
    c = Client({'ADAUSDT': pos(mark=0.955)})
    await run(s, c)
    await run(s, c)
    check('U10: dos corridas seguidas -> una sola orden de cierre', len(c.orders) == 1, c.orders)

    # U11: sin dudosas -> no se consulta nada más (las abiertas siguen igual)
    s = {'exec': [], 'unresolved': [], 'live': []}
    c = Client({'ADAUSDT': pos(mark=0.5)})
    r = await run(s, c)
    check('U11: sin dudosas -> no consulta Bybit por ellas', not c.orders and 'unresolved_checked' not in r, r)

    # U12: regla pura
    f = getattr(RealTrader, 'identify_unresolved_position', lambda *a: 'falta')
    check('U12: identificación con certeza (lado, tamaño ≤ pedido, sola en la moneda, no huérfana de cierre)',
          f(dud(), pos(), 0) is None and f(dud(), pos(size=20.0), 0) is None and f(dud(size=0), pos(), 0)
          and f(dud(), pos(side='Sell'), 0) and f(dud(), pos(), 1) and f(dud(), pos(size=40.0001), 0))

    # U13: Laravel
    job = (ROOT / 'app' / 'Jobs' / 'CircuitBreakerMaxLossJob.php').read_text(encoding='utf-8')
    check('U13: el job también elige las cuentas con dudosas (misma regla de 3 min)',
          "->orWhereExists(" in job and "where('real_trades.status', 'orphaned')" in job
          and "where('real_trades.status', 'pending_open')" in job and 'RealTrade::PENDING_OPEN_STALE_MIN' in job)
    msg = (ROOT / 'app' / 'Services' / 'BrokerEventMessages.php').read_text(encoding='utf-8')
    check('U13b: textos de los avisos (sin confirmar; no se cierra sola)',
          "'unresolved_unprotected' => [" in msg and 'No se cierra sola' in msg and "! empty($data['unresolved'])" in msg)


asyncio.run(main())
print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

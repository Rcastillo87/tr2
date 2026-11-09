"""
N-06 + N-16: liquidación de un cierre Real normal (orden reduceOnly confirmada Filled).
- Con el closed-pnl de Bybit de esa orden: neto = closedPnl (ya descuenta comisiones de entrada/salida y funding),
  costos = bruto - neto, hora = la del cierre en Bybit. Se reintenta unos segundos porque Bybit lo indexa después.
- Sin closed-pnl: comisión taker estimada y hora = ejecución de la orden (updatedTime), nunca la hora del proceso.
- pnl_pct es NETO sobre el saldo previo (como Paper), en este camino y en el de posición ya cerrada en Bybit.
- Si Bybit informa openFee/closeFee, la auditoría separa comisiones y funding.
Sin DB ni Bybit reales. Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_close_accounting_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (fakes compartidos)
from trading.real_trader import RealTrader  # noqa: E402

fails = 0
FILL_MS = int(datetime(2026, 11, 9, 15, 0, 7, tzinfo=timezone.utc).timestamp() * 1000)     # ejecución de la orden
BYBIT_MS = int(datetime(2026, 11, 9, 15, 0, 9, tzinfo=timezone.utc).timestamp() * 1000)    # cierre en closed-pnl


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Client(rp.FakeClient):
    """Orden Filled a 101 con updatedTime; el closed-pnl aparece a partir del intento `ready_on` (0 = nunca)."""

    def __init__(self, history, ready_on=1, side_price=101.0):
        super().__init__(position={'size': '1', 'avgPrice': '100'}, order_status='Filled', price=side_price)
        self.hist, self.ready_on, self.pnl_calls = history, ready_on, 0

    async def get_order(self, symbol, order_id=None, link_id=None):
        return {'orderStatus': 'Filled', 'avgPrice': str(self.price), 'updatedTime': str(FILL_MS)}

    async def get_closed_pnl_history(self, symbol, entry, since, limit=20):
        self.pnl_calls += 1
        return self.hist if self.ready_on and self.pnl_calls >= self.ready_on else []


def close_row(s):
    """Argumentos del UPDATE final del cierre normal: (order_id, exit_price, reason, exit_time, pnl, pnl_pct, net, commission, ...)."""
    rows = [a for sql, a in s['exec'] if 'close_order_id' in sql and 'UPDATE real_trades' in sql]
    return tuple(rows[0]) + (None,) * 10 if rows else (None,) * 12


def audit_closed(s):
    for sql, a in s['exec']:
        if 'audit_log = $1' in sql and a and isinstance(a[0], list):
            for e in a[0]:
                if e.get('action') == 'closed':
                    return e['data']
    return {}


def H(net, **extra):
    return [dict({'closedSize': '1', 'cumExitValue': '101', 'closedPnl': str(net), 'avgEntryPrice': '100',
                  'updatedTime': str(BYBIT_MS)}, **extra)]


async def run(client, trade=None):
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).close_trade(trade or rp.trade(), 'time_exit', client, 7)
    return ok, s


async def main():
    # A1. closed-pnl disponible al primer intento: neto, costos y hora de Bybit; pnl_pct neto
    ok, s = await run(Client(H(0.83)))
    r = close_row(s)
    check('A1: cierra (True)', ok is True, ok)
    check('A1: pnl bruto 1.0 y neto de Bybit 0.83', r[4] == 1.0 and r[6] == 0.83, (r[4], r[6]))
    check('A1: costos = bruto - neto = 0.17 (comisiones + funding reales)', r[7] is not None and abs(r[7] - 0.17) < 1e-9, r[7])
    check('A1: exit_time = hora del cierre en Bybit (15:00:09), no la del proceso',
          r[3] == datetime(2026, 11, 9, 15, 0, 9), r[3])
    check('A1: pnl_pct NETO sobre el saldo previo (0.83/1000*100 = 0.083)', r[5] == 0.083, r[5])
    check("A1: auditoría marca las cifras como 'bybit'", audit_closed(s).get('figures') == 'bybit', audit_closed(s))

    # A2. Bybit lo indexa en el segundo intento: se espera y se usa
    c = Client(H(0.80), ready_on=2)
    ok, s = await run(c)
    r = close_row(s)
    check('A2: closed-pnl al 2.º intento -> neto 0.80 de Bybit (2 consultas)', r[6] == 0.80 and c.pnl_calls == 2,
          (r[6], c.pnl_calls))

    # A3. Nunca aparece: comisión estimada, hora = ejecución de la orden, intentos acotados
    c = Client(H(0.83), ready_on=0)
    ok, s = await run(c)
    r = close_row(s)
    est = round((100 + 101) * 1 * 0.00055, 6)
    check('A3: sin closed-pnl -> cierra igual (True) con comisión estimada', ok is True and r[7] == est, (ok, r[7], est))
    check('A3: exit_time = ejecución de la orden (15:00:07), no la del proceso', r[3] == datetime(2026, 11, 9, 15, 0, 7), r[3])
    check('A3: consultas acotadas (3) y auditoría marca estimado',
          c.pnl_calls == 3 and audit_closed(s).get('figures') == 'estimado', (c.pnl_calls, audit_closed(s).get('figures')))

    # A4. Bybit informa openFee/closeFee: la auditoría separa comisiones y funding
    ok, s = await run(Client(H(0.83, openFee='0.055', closeFee='0.0555')))
    a = audit_closed(s)
    check('A4: auditoría con fees 0.1105 y funding 0.0595 (= costos - fees)',
          a.get('fees') == 0.1105 and a.get('funding') == 0.0595, {k: a.get(k) for k in ('commission', 'fees', 'funding')})

    # A5. Short: signos correctos y neto de Bybit
    t = dict(rp.trade(sl=101.0, tp=96.0), side='short')
    ok, s = await run(Client([{'closedSize': '1', 'cumExitValue': '99', 'closedPnl': '0.89', 'updatedTime': str(BYBIT_MS)}],
                              side_price=99.0), t)
    r = close_row(s)
    check('A5: short 100 -> 99: bruto +1.0, neto 0.89, pnl_pct 0.089', r[4] == 1.0 and r[6] == 0.89 and r[5] == 0.089,
          (r[4], r[6], r[5]))

    # A6. Posición ya cerrada en Bybit (camino de settle): pnl_pct también neto
    s = {'exec': []}
    c = rp.FakeClient(position=None, history=H(-1.12))
    c.history[0]['cumExitValue'] = '99'
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    rows = [a for sql, a in s['exec'] if 'UPDATE real_trades' in sql and "status='closed'" in sql.replace(' ', '')]
    check('A6: ya cerrada en Bybit -> pnl_pct neto (-1.12/1000*100 = -0.112)', bool(rows) and rows[0][3] == -0.112,
          rows[0][:6] if rows else None)

    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return fails


if __name__ == '__main__':
    sys.exit(1 if asyncio.run(main()) else 0)

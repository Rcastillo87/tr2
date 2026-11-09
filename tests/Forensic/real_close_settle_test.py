"""
N-05: close_trade() con la posición ya cerrada en Bybit (SL/TP nativo, liquidación o cierre manual entre el monitor y
la orden de cierre) liquida con los números de Bybit (closed-pnl): precio, PnL neto, comisión y hora. Si Bybit todavía
no indexó el cierre, el trade NO se cierra sin cifras: queda como está y el próximo ciclo (o la reconciliación) lo
liquida. Sin DB ni Bybit reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_close_settle_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (fakes compartidos)
from trading.real_trader import BybitAPIError, RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def closes(s):
    """Las UPDATE que cierran la fila: (sql, args)."""
    return [(sql, a) for sql, a in s['exec']
            if 'UPDATE real_trades' in sql and "status='closed'" in sql.replace(' ', '')]


def close_args(s):
    """Argumentos de la primera UPDATE de cierre, rellenados con None (el código viejo pasa menos)."""
    cl = closes(s)
    return tuple(cl[0][1]) + (None,) * 10 if cl else (None,) * 10


def audits(s):
    return [sql for sql, a in s['exec'] if 'audit_log' in sql]


class SinceClient(rp.FakeClient):
    """Registra el 'since' con el que se consulta el closed-pnl."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.since = None

    async def get_closed_pnl_history(self, symbol, entry, since, limit=20):
        self.since = since
        return self.history


class DownClient(rp.FakeClient):
    async def get_open_position(self, symbol):
        raise BybitAPIError('timeout')


CLOSE_MS = int(datetime(2026, 11, 9, 14, 7, tzinfo=timezone.utc).timestamp() * 1000)
HIST = [{'closedSize': '1', 'cumExitValue': '99.0', 'closedPnl': '-1.11', 'avgEntryPrice': '100',
         'updatedTime': str(CLOSE_MS)}]


async def main():
    # S1. Posición ya cerrada en Bybit por su SL nativo: liquida con closed-pnl (precio, neto, hora, motivo)
    s = {'exec': []}
    t = rp.trade()
    c = SinceClient(position=None, history=HIST)
    ok = await RealTrader(rp.FakePool(s)).close_trade(t, 'time_exit', c, 7)
    cl = closes(s)
    args = close_args(s)
    check('S1: devuelve True (cerrado y liquidado)', ok is True, ok)
    check('S1: una sola UPDATE de cierre', len(cl) == 1, [x[0][:60] for x in cl])
    check('S1: con precio de salida de Bybit (99.0)', args[0] == 99.0, args[:1])
    check('S1: motivo deducido del precio (stop_loss), no el del llamador ni "reconciled"',
          args[1] == 'stop_loss', args[1:2])
    check('S1: PnL bruto -1.0 y neto de Bybit -1.11', args[2] == -1.0 and args[4] == -1.11, args[2:5])
    check('S1: comisión = bruto - neto (0.11)', args[5] is not None and abs(args[5] - 0.11) < 1e-9, args[5:6])
    check('S1: hora del cierre = la de Bybit', args[8] == datetime(2026, 11, 9, 14, 7), args[8:9])
    check('S1: la UPDATE exige status abierto (no pisa un cierre concurrente)',
          bool(cl) and "status IN ('open','pending_close')" in cl[0][0], cl[0][0][-80:] if cl else '')
    ems = int(t['entry_time'].timestamp() * 1000)
    check('S1: closed-pnl consultado desde la apertura del trade', c.since is not None and c.since <= ems, (c.since, ems))
    check('S1: ninguna orden enviada', not c.orders, c.orders)

    # S2. Bybit aún no indexó el cierre: NO se cierra sin cifras; devuelve False y queda auditado
    s = {'exec': []}
    c = SinceClient(position=None, history=[])
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'circuit_breaker_max_loss', c, 7)
    check('S2: devuelve False (pendiente de liquidar)', ok is False, ok)
    check('S2: ninguna UPDATE de cierre (nada de pnl NULL)', not closes(s), [x[0][:80] for x in closes(s)])
    check('S2: ninguna fila marcada reconciled', not [1 for sql, a in s['exec'] if 'reconciled' in sql], '')
    check('S2: deja rastro en la auditoría', bool(audits(s)), '')
    check('S2: ninguna orden enviada', not c.orders, c.orders)

    # S3. Short cerrado por su TP nativo: motivo take_profit_1 y PnL con signo de short
    s = {'exec': []}
    t = dict(rp.trade(sl=101.0, tp=96.0), side='short')
    h = [{'closedSize': '1', 'cumExitValue': '96.0', 'closedPnl': '3.89', 'updatedTime': str(CLOSE_MS)}]
    ok = await RealTrader(rp.FakePool(s)).close_trade(t, 'volatility_protection', SinceClient(position=None, history=h), 7)
    args = close_args(s)
    check('S3: short por TP -> take_profit_1, PnL +4.0, neto 3.89',
          ok is True and args[1] == 'take_profit_1' and args[2] == 4.0 and args[4] == 3.89, args[:5])

    # S4. Bybit no responde al consultar la posición: no cierra nada
    s = {'exec': []}
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'time_exit', DownClient(), 7)
    check('S4: Bybit caído -> False y sin UPDATE de cierre', ok is False and not closes(s), ok)

    # S5. Posición viva: camino normal (orden reduceOnly y cierre con su precio), sin cambios
    s = {'exec': []}
    c = rp.FakeClient(position={'size': '1', 'avgPrice': '100'}, order_status='Filled', price=101.0)
    ok = await RealTrader(rp.FakePool(s)).close_trade(rp.trade(), 'time_exit', c, 7)
    args = close_args(s)
    check('S5: posición viva -> orden reduceOnly Sell y cierre a 101.0 con motivo time_exit',
          ok is True and len(c.orders) == 1 and c.orders[0][0] == 'Sell' and c.orders[0][4].get('reduce_only')
          and args[1] == 101.0 and args[2] == 'time_exit', (c.orders, args[:3]))

    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return fails


if __name__ == '__main__':
    sys.exit(1 if asyncio.run(main()) else 0)

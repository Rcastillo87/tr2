"""
REAL-01: si Bybit no acepta el SL/TP de la estrategia, el dueño recibe un aviso (incidente) y queda en la auditoría;
cuando el monitor logra instalarlo (o se corrige a mano en Bybit) el incidente se cierra. Un aviso por incidente.
Sin base de datos ni Bybit: pool y cliente simulados, sin órdenes reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_protection_test.py
Antes del parche debe FALLAR (ningún aviso ni registro); después, todo PASS.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (pool/cliente simulados; anula las esperas)
import broker_events_test as be  # noqa: E402  (SUB y lector de eventos)
import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class StopClient(rp.FakeClient):
    """set_trading_stop responde según `results` (en orden; el último se repite)."""
    def __init__(self, results, **kw):
        super().__init__(**kw)
        self.results = list(results)

    async def set_trading_stop(self, symbol, sl, tp=None, **k):
        self.stops.append((sl, tp, k))
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


def actions(s):
    raw = s.get('audit')
    raw = json.loads(raw) if isinstance(raw, str) else (raw or [])
    return [e.get('action') for e in raw]


def evs(s):
    return [e[0] for e in be.events(s)]


async def tick(trade, client, s):
    """Un ciclo del monitor sobre el MISMO estado (audit_log persiste entre ciclos, como en la base)."""
    trader = RealTrader(rp.FakePool(s))
    return await trader._monitor_single_trade(trade, client, {'BTCUSDT': 100.0}, 7)


def fresh():
    return {'exec': [], 'audit': None, 'extremes': None}


async def main():
    strat = rt_mod.build_strategy({**rp.P, 'symbol': 'BTCUSDT', 'interval': '60'})

    # O1. Apertura con trading-stop rechazado: sigue 'open', auditoría y aviso con el SL/TP que faltó
    s = fresh()
    c = StopClient([False], fill_on_check=2)
    ok = await RealTrader(rp.FakePool(s)).open_trade(be.SUB, strat, 'long', 100.0, 'RANGING', c)
    final = [a for sql, a in s['exec'] if "SET status = 'open'" in sql]
    ev = be.events(s)
    check('O1 apertura con SL/TP rechazado: la posición queda open (existe en Bybit)', ok and bool(final), (ok, final))
    check('O1 auditoría sl_tp_final_failed', 'sl_tp_final_failed' in actions(s) and 'sl_tp_final_set' not in actions(s),
          actions(s))
    check('O1 aviso protection_failed con SL/TP de la estrategia, estrategia y etapa',
          [e[0] for e in ev] == ['protection_failed'] and ev[0][2].get('stage') == 'open'
          and abs(ev[0][2].get('sl') - final[0][3]) < 1e-9 and abs(ev[0][2].get('tp') - final[0][4]) < 1e-9
          and ev[0][2].get('strategy') == 'T' and ev[0][1] == 77, ev)

    # O2. Apertura normal: sl_tp_final_set y ningún aviso
    s = fresh()
    ok = await RealTrader(rp.FakePool(s)).open_trade(be.SUB, strat, 'long', 100.0, 'RANGING', StopClient([True], fill_on_check=2))
    check('O2 apertura normal: sl_tp_final_set y sin avisos', ok and 'sl_tp_final_set' in actions(s) and not evs(s),
          (actions(s), evs(s)))

    # M1. Monitor: Bybit con otro SL y trading-stop falla, sin incidente previo -> abre incidente (1 aviso)
    s = fresh()
    c = StopClient([False], position=rp.position(sl=98.0))
    out = await tick(rp.trade(), c, s)
    ev = be.events(s)
    check('M1 monitor no logra alinear: auditoría + protection_failed (etapa monitor, SL de Bybit)',
          actions(s) == ['sl_tp_realign_failed'] and [e[0] for e in ev] == ['protection_failed']
          and ev[0][2].get('stage') == 'monitor' and ev[0][2].get('exchange_sl') == 98.0 and ev[0][1] == 5, (actions(s), ev))
    check('M1 la posición sigue gestionándose (sin error ni cierre)', out['errors'] == 0 and out['closed'] == 0, out)

    # M2. Sigue fallando en los ciclos siguientes: ni aviso ni registro nuevos
    for _ in range(3):
        await tick(rp.trade(), c, s)
    check('M2 sigue fallando 3 ciclos más: sin avisos ni registros repetidos',
          evs(s) == ['protection_failed'] and actions(s) == ['sl_tp_realign_failed'] and len(c.stops) == 4,
          (evs(s), actions(s), len(c.stops)))

    # M3. Por fin lo instala: cierra el incidente (1 aviso)
    c.results = [True]
    await tick(rp.trade(), c, s)
    check('M3 lo instala: sl_tp_realigned + protection_restored',
          evs(s) == ['protection_failed', 'protection_restored'] and actions(s)[-1] == 'sl_tp_realigned', (evs(s), actions(s)))
    c2 = StopClient([True], position=rp.position())
    await tick(rp.trade(), c2, s)
    check('M3 ciclo siguiente con todo alineado: nada nuevo y sin llamar a Bybit',
          evs(s) == ['protection_failed', 'protection_restored'] and not c2.stops, (evs(s), c2.stops))

    # M4. Alinea sin incidente previo (corrección normal): sin avisos
    s = fresh()
    c = StopClient([True], position=rp.position(sl=98.0))
    await tick(rp.trade(), c, s)
    check('M4 alinea sin incidente abierto: sin avisos ni registro de incidente', not evs(s) and not actions(s) and c.stops,
          (evs(s), actions(s)))

    # M5. Incidente abierto en la apertura y el SL de Bybit ya coincide (corregido a mano): cierra el incidente
    s = fresh()
    s['audit'] = [{'action': 'opened'}, {'action': 'sl_tp_final_failed'}]
    c = StopClient([False], position=rp.position())
    await tick(rp.trade(), c, s)
    check('M5 corregido a mano en Bybit: protection_restored sin llamar a trading-stop',
          evs(s) == ['protection_restored'] and not c.stops and actions(s)[-1] == 'sl_tp_realigned', (evs(s), c.stops))

    # M6. Todo alineado y sin incidente: nada
    s = fresh()
    c = StopClient([True], position=rp.position())
    await tick(rp.trade(), c, s)
    check('M6 alineado y sin incidente: sin avisos ni llamadas', not evs(s) and not c.stops and not actions(s))

    # F1. Flujo completo: apertura falla -> monitor falla 2 ciclos -> lo instala. Exactamente 2 avisos.
    s = fresh()
    c = StopClient([False], fill_on_check=2)
    await RealTrader(rp.FakePool(s)).open_trade(be.SUB, strat, 'long', 100.0, 'RANGING', c)
    final = [a for sql, a in s['exec'] if "SET status = 'open'" in sql][0]
    t = rp.trade(sl=final[3], tp=final[4])
    cm = StopClient([False, False, True], position=rp.position(sl=98.0, tp=104.0))
    for _ in range(3):
        await tick(t, cm, s)
    check('F1 flujo completo: un aviso al fallar y uno al recuperar',
          evs(s) == ['protection_failed', 'protection_restored'], evs(s))
    check('F1 auditoría: falló al abrir, sin registros repetidos, realineado al final',
          [a for a in actions(s) if a.startswith('sl_tp')] == ['sl_tp_final_failed', 'sl_tp_realigned'], actions(s))

    # E1. El motor declara los dos eventos (si no, emit_event los descarta)
    from trading.broker_events import EVENTS
    check('E1 protection_failed y protection_restored son eventos conocidos',
          {'protection_failed', 'protection_restored'} <= EVENTS)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

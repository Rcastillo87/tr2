"""
19-nov (DOGEUSDT #99): Bybit guarda el SL/TP redondeado a su paso de precio (tickSize). La estrategia calculó
TP 0.0562272 y Bybit tenía 0.05622 (paso 0.00001). El monitor lo veía como desalineado cada minuto, pedía cambiarlo y
Bybit respondía 34040 «not modified»; el bot lo tomaba como fallo: falsa «protección fallida» al abrir y un ERROR en
engine.log por minuto (lo que además frenaba los instaladores).
Ahora: 34040 = ya vigente (éxito) y la alineación compara con la tolerancia de un paso de precio.
Sin Bybit: httpx y cliente simulados.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_tick_size_test.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402
import broker_events_test as be  # noqa: E402
import trading.real_trader as rt  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Http:
    """httpx.AsyncClient simulado: POST responde `post_answer`; GET (instruments-info) responde `get_answer`."""
    post_answer, get_answer, gets, posts = None, None, 0, []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *e):
        return False

    async def post(self, url, content=None, headers=None):
        Http.posts.append(json.loads(content))
        a = Http.post_answer

        class R:
            def json(self_):
                return a
        return R()

    async def get(self, url, params=None):
        Http.gets += 1
        a = Http.get_answer

        class R:
            def json(self_):
                return a
        return R()


DOGE_TRADE = dict(entry_price=0.05857, side='short', sl=0.0597414, tp=0.0562272, original_sl=0.0597414,
                  be_level=0.05704718, symbol='BTCUSDT')


class TickClient(rp.FakeClient):
    def __init__(self, tick, **kw):
        super().__init__(**kw)
        self.tick = tick


async def client_cases():
    rt.httpx.AsyncClient = Http
    c = rt.BybitClient('k', 's', 'demo')
    for code, want, name in ((0, True, 'S1 retCode 0 -> configurado'),
                             (34040, True, 'S2 retCode 34040 «not modified» -> ya vigente: éxito (antes: fallo)'),
                             (10001, False, 'S3 otro rechazo (10001) -> sigue siendo fallo')):
        Http.post_answer = {'retCode': code, 'retMsg': 'not modified' if code == 34040 else 'x'}
        got = await c.set_trading_stop('DOGEUSDT', 0.0597414, 0.0562272)
        check(name, got is want, got)

    rt._LOT_CACHE.clear()
    if hasattr(rt, '_TICK_CACHE'):
        rt._TICK_CACHE.clear()
    Http.gets = 0
    Http.get_answer = {'retCode': 0, 'result': {'list': [{'lotSizeFilter': {'minOrderQty': '1', 'qtyStep': '1'},
                                                           'priceFilter': {'tickSize': '0.00001'}}]}}
    getter = getattr(c, 'get_tick_size', None)
    tick = await getter('DOGEUSDT') if getter else None
    lot = await c.get_lot_size('DOGEUSDT')
    check('S4 paso de precio de instruments-info (0.00001) y el lote, con UNA sola consulta',
          tick == 0.00001 and lot == (1.0, 1.0) and Http.gets == 1, (tick, lot, Http.gets))
    Http.get_answer = {'retCode': 10002, 'retMsg': 'x'}
    tick = await getter('NEARUSDT') if getter else 'sin método'
    check('S5 sin dato de Bybit: None (se usa la tolerancia de siempre)', tick is None, tick)


async def tick_monitor(tick, ex_sl, ex_tp):
    s = {'exec': [], 'audit': None, 'extremes': None}
    t = rp.trade()
    t.update(DOGE_TRADE)
    c = TickClient(tick, position={'size': '1', 'avgPrice': '0.05857', 'stopLoss': str(ex_sl), 'takeProfit': str(ex_tp)})
    out = await RealTrader(rp.FakePool(s))._monitor_single_trade(t, c, {'BTCUSDT': 0.0585}, 7)
    return c, s, out


async def monitor_cases():
    c, s, out = await tick_monitor(0.00001, 0.05974, 0.05622)
    sent = [x for x in c.stops if x[0] == 0.0597414]
    check('M1 #99: Bybit 0.05974/0.05622 vs DB 0.0597414/0.0562272 con paso 0.00001 -> alineado: no pide cambios',
          sent == [] and not be.events(s), (c.stops, be.events(s)))
    c, s, out = await tick_monitor(0.00001, 0.05974, 0.05621)
    check('M2 TP de Bybit a 1 paso (0.05621) -> desalineado de verdad: pide alinear',
          any(x[0] == 0.0597414 for x in c.stops), c.stops)
    c, s, out = await tick_monitor(0.00001, 0.05980, 0.05622)
    check('M3 SL de Bybit 6 pasos más lejos -> pide alinear', any(x[0] == 0.0597414 for x in c.stops), c.stops)
    # 0.05603 y 0.05604: en coma flotante la diferencia sale 9.99…e-06, apenas menos que el paso
    t = rp.trade(); t.update(DOGE_TRADE, tp=0.05603)
    c = TickClient(0.00001, position={'size': '1', 'avgPrice': '0.05857', 'stopLoss': '0.0597414', 'takeProfit': '0.05604'})
    await RealTrader(rp.FakePool({'exec': [], 'audit': None, 'extremes': None}))._monitor_single_trade(
        t, c, {'BTCUSDT': 0.0585}, 7)
    check('M5 DB 0.05603 (en la grilla) y Bybit 0.05604: exactamente 1 paso (con coma flotante) -> pide alinear',
          len(c.stops) == 1, c.stops)
    c, s, out = await tick_monitor(None, 0.05974, 0.05622)
    check('M4 control sin paso conocido: tolerancia de siempre (0,01 % de la entrada) -> pide alinear como antes',
          any(x[0] == 0.0597414 for x in c.stops), c.stops)


async def main():
    await client_cases()
    await monitor_cases()
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

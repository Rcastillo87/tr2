"""
D-19 (dueño, 19-nov): con una posición abierta a mano en Bybit en una moneda suscrita, el bot NO abre en esa moneda.
Cuando la manual se cierra, el siguiente tick evalúa la señal de la última vela cerrada: abre solo si sigue vigente
(no recupera una señal vieja). D-18 (no adoptarla) lo prueba broker_events_test.py D4–D5. Sin DB ni Bybit.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/manual_position_test.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class T(RealTrader):
    bars_asked = 0

    async def get_open_trade_for_subscription(self, subscription_id):
        return None

    async def has_open_trade(self, subscription_id, symbol):
        return False

    async def get_bars(self, symbol, interval, *a, **k):
        T.bars_asked += 1
        return None          # «datos insuficientes»: basta para saber que pasó el control de posición


sub = {'symbol': 'SOLUSDT', 'interval': '60', 'broker_account_id': 11, 'subscription_id': 5}
strategy = rp.make_strategy() if hasattr(rp, 'make_strategy') else None


async def run(position):
    t = T(rp.FakePool({'exec': []}))
    return await t.check_new_signals(sub, strategy, rp.FakeClient(position=position))

manual = dict(rp.position(), side='Buy')
r = asyncio.run(run(manual))
check('M1 posición manual abierta en la moneda -> el bot no abre ni mira la señal',
      'posicion abierta en Bybit' in r and T.bars_asked == 0, r)
r = asyncio.run(run(None))
check('M2 la manual ya se cerró -> se evalúa la señal de la última vela cerrada (abre solo si sigue vigente)',
      'posicion abierta en Bybit' not in r and T.bars_asked == 1, r)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

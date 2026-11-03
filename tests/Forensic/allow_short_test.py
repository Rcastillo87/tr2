"""
allow_short en backtest, Paper y Real (BP-01 / REAL-03): con allow_short desactivado ningún módulo abre Short.
Sin base de datos ni Bybit: pools y cliente simulados, sin órdenes reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/allow_short_test.py
Antes del parche debe FALLAR (Paper y Real abren el Short); después, todo PASS.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import paper_opposite_test as po  # noqa: E402  (harness Paper: reloj, precio, pool en memoria)
import real_parity_test as rp  # noqa: E402     (harness Real: pool y cliente simulados)
import trading.real_trader as rt_mod  # noqa: E402
import backtesting.strategies.base_strategy as bs  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


NO_SHORT = dict(po.BASE, allow_short=False)


def sides(store):
    return [(t['side'], t['status']) for t in store.trades]


async def paper_cases():
    df = po.candles()
    start = 70

    # P1-P2. Paridad Paper vs motor con allow_short=False: mismos cierres, ningún Short
    for label, extra in (('close_on_opposite', dict(close_on_opposite=True)),
                         ('exit_on_opposite', dict(exit_on_opposite=True))):
        p = dict(NO_SHORT, **extra)
        eng = po.engine_trades(p, df, start)
        st = await po.simulate(p, df, start)
        pap = po.paper_closed(st)
        check(f'P1 paridad {label} sin short: mismos cierres que el motor ({len(eng)} operaciones)',
              len(eng) >= 3 and pap == eng, po.first_diff(pap, eng) if pap != eng else '')
        check(f'P2 paridad {label} sin short: ni Paper ni el motor abren Short',
              all(t['side'] == 'long' for t in st.trades) and all(x[0] == 'long' for x in eng),
              (sides(st), [x[0] for x in eng]))

    # P3. Sin posición y señal Short: no abre nada
    d = po.candles(n=75, seed=11, p_sig=0.0)
    d.loc[68, 'sig'] = -1
    st = await po.simulate(dict(NO_SHORT), d, 69, ticks=(2, 3))
    check('P3 señal short sin posición: no abre', st.trades == [], sides(st))

    # P4. Control: con allow_short=True la misma señal sí abre Short (la prueba distingue)
    st = await po.simulate(dict(po.BASE), d, 69, ticks=(2,))
    check('P4 control allow_short=True: abre el short', sides(st) == [('short', 'open')], sides(st))

    # P5. Long abierto + señal opuesta con close_on_opposite: cierra el long y NO reversa a Short
    d = po.candles(n=78, seed=12, p_sig=0.0)
    d.loc[68, 'sig'] = 1      # abre long en la vela 69
    d.loc[70, 'sig'] = -1     # opuesta -> cierra en la vela 71, sin reversa
    d.loc[73, 'sig'] = 1      # nueva señal larga -> abre long en la vela 74
    p = dict(NO_SHORT, close_on_opposite=True)
    store = po.Store()
    trader = po.mk_trader(p, store)
    for k in range(69, 72):
        for m in (2, 3, 4):
            await po.tick(trader, d, k, m)
    check('P5 close_on_opposite sin short: cierra el long por señal opuesta y no reversa',
          sides(store) == [('long', 'closed')] and store.trades[0]['exit_reason'] == 'opposite_signal', sides(store))
    for k in range(72, 76):
        for m in (2, 3, 4):
            await po.tick(trader, d, k, m)
    check('P6 después del cierre, la siguiente señal larga abre long (una sola vez)',
          sides(store) == [('long', 'closed'), ('long', 'open')], sides(store))
    eng = po.engine_trades(p, d, 69)
    check('P7 mismo caso en el motor: un solo cierre long por señal opuesta',
          eng == po.paper_closed(store), (eng, po.paper_closed(store)))

    # P8. allow_short llega como texto desde JSON ('false'): debe valer False, no bool('false') == True
    store = po.Store()
    trader = po.mk_trader(dict(po.BASE, allow_short='false'), store)
    d = po.candles(n=75, seed=11, p_sig=0.0)
    d.loc[68, 'sig'] = -1
    await po.tick(trader, d, 69)
    check("P8 allow_short='false' (texto): no abre short", store.trades == [], sides(store))


async def real_case(params, signal):
    code = f"class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = {signal}\n        return df\n"
    strat = rt_mod.build_strategy({**rp.P, **params, 'strategy_code': code, 'symbol': 'BTCUSDT', 'interval': '60'})
    tr = RealTrader(rp.FakePool({'exec': []}))
    opened = []

    async def _no_open(*a):
        return False

    async def _bars(symbol, interval, broker=None):
        return rp.bars()

    async def _no_limit(*a):
        return None

    async def _open(sub, strategy, side, *a, **k):
        opened.append(side)
        return True
    tr.has_open_trade, tr.get_bars, tr.open_trade, tr.entry_limit_reason = _no_open, _bars, _open, _no_limit
    client = rp.FakeClient()
    sub = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 7, 'subscription_id': 1, 'strategy': 'T'}
    msg = await tr.check_new_signals(sub, strat, client)
    return msg, opened, client


async def real_cases():
    msg, opened, client = await real_case({'allow_short': False}, -1)
    check('R1 Real allow_short=False + señal short: no abre ni envía orden',
          opened == [] and client.orders == [] and 'short no permitido' in msg, (msg, opened))
    msg, opened, _ = await real_case({'allow_short': 'false'}, -1)
    check("R2 Real allow_short='false' (texto): no abre", opened == [], (msg, opened))
    msg, opened, _ = await real_case({'allow_short': True}, -1)
    check('R3 control Real allow_short=True: abre el short', opened == ['short'], (msg, opened))
    msg, opened, _ = await real_case({'allow_short': False}, 1)
    check('R4 Real allow_short=False + señal long: el long sí abre', opened == ['long'], (msg, opened))
    msg, opened, _ = await real_case({}, -1)
    check('R5 Real sin allow_short en la config: default permite short (compatibilidad)', opened == ['short'],
          (msg, opened))


def flag_cases():
    as_flag = getattr(bs, 'as_flag', None)
    if as_flag is None:
        check('F1 as_flag existe en base_strategy', False, 'falta')
        return
    cases = [(None, True, True), (None, False, False), (False, True, False), (True, False, True),
             ('false', True, False), ('False', True, False), ('0', True, False), ('off', True, False),
             ('no', True, False), ('', True, False), ('true', False, True), ('1', False, True),
             (0, True, False), (1, False, True)]
    bad = [(v, d, as_flag(v, d)) for v, d, exp in cases if as_flag(v, d) is not exp]
    check('F1 as_flag interpreta texto/números/None como la UI los envía', not bad, bad)


async def main():
    flag_cases()
    await paper_cases()
    await real_cases()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

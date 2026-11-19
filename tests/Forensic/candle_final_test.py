"""
D-39 (dueño, 19-nov): Paper y Real deciden solo con la vela COMPLETA. El collector guarda la vela en formación y la
actualiza cada minuto; la que acaba de cerrar recibe su último minuto en la primera pasada del collector después del
cierre, en la misma sentencia que escribe la vela siguiente. Si la siguiente todavía no está en la base, la cerrada
puede no tener su último minuto: se espera al minuto siguiente.
Caso real (19-nov 16:00 UTC): Paper vio LINKUSDT H4 12:00 sin su último minuto (close 9,028 en vez de 9,019), la
estrategia dio venta y abrió #378; con la vela completa no había señal y Real (unos segundos después) no abrió.
Sin base ni Bybit: harnesses de paper_opposite_test y real_parity_test.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/candle_final_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import pandas as pd  # noqa: E402

import paper_opposite_test as po  # noqa: E402  (Paper: reloj, precio, velas y base simulados)
import real_parity_test as rp  # noqa: E402     (Real: pool y cliente simulados)
import trading.real_trader as rt_mod  # noqa: E402
import collectors.broker_resolver as br  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def h4(times):
    return pd.DataFrame({'time': times, 'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0, 'volume': 1.0})


def helper_cases():
    f = getattr(br, 'final_closed_bars', None)
    if f is None:
        check('H0 existe final_closed_bars', False, 'falta')
        return
    now = datetime(2026, 11, 19, 16, 0, 30, tzinfo=timezone.utc)
    t = [datetime(2026, 11, 19, 0, tzinfo=timezone.utc) + timedelta(hours=4 * i) for i in range(5)]   # 00 … 16
    closed, pend = f(h4(t[:4]), '240', now)          # hasta la de 12:00: la de 16:00 aún no está en la base
    check('H1 cerró la de 12:00 y la de 16:00 no está en la base -> pendiente 12:00',
          pend == t[3] and len(closed) == 4, (pend, len(closed)))
    closed, pend = f(h4(t[:5]), '240', now)          # el collector ya pasó: escribió la de 16:00 (en formación)
    check('H2 la de 16:00 ya está -> la de 12:00 es final (sin pendiente) y la de 16:00 no cuenta como cerrada',
          pend is None and len(closed) == 4, (pend, len(closed)))
    closed, pend = f(h4(t[:4]), '240', datetime(2026, 11, 19, 15, 59, tzinfo=timezone.utc))
    check('H3 a las 15:59 la de 12:00 sigue abierta: última cerrada la de 08:00, que tiene siguiente -> final',
          pend is None and len(closed) == 3, (pend, len(closed)))
    closed, pend = f(h4([]).iloc[0:0], '240', now)
    check('H4 sin velas: sin pendiente (decide «datos insuficientes»)', pend is None and len(closed) == 0)
    closed, pend = f(None, '240', now)
    check('H5 None: (None, None)', closed is None and pend is None)


# ───────────── Paper ─────────────
async def paper_cases():
    df = po.candles()
    k = next(i for i in range(70, len(df)) if df['sig'][i - 1] != 0)   # la vela k-1 cerró con señal
    side = 'long' if df['sig'][k - 1] > 0 else 'short'

    async def run(rows, minute):
        store = po.Store()
        tr = po.mk_trader(po.BASE, store)
        po.CLOCK[0] = df['time'][k].to_pydatetime() + timedelta(seconds=minute * 60 + 17)
        po.PRICE[0] = float(df['open'][k])

        async def _bars(symbol, interval, broker=None):
            return df.iloc[:rows].copy()
        tr.get_bars = _bars
        res = await tr.check_new_signals()
        return store, res

    store, res = await run(k, 0)   # 16:00:17 sin la vela siguiente en la base (como LINK en Paper)
    txt = ' '.join(str(v) for v in res.values())
    check('P1 Paper: la vela cerró pero la siguiente no está en la base -> no abre y espera',
          store.trades == [] and 'sin completar' in txt, (len(store.trades), txt[:140]))
    store, res = await run(k + 1, 1)   # minuto siguiente: el collector ya escribió la siguiente
    check(f'P2 Paper: al minuto siguiente, con la vela completa, abre la señal ({side})',
          len(store.trades) == 1 and store.trades[0].get('side') == side, [t.get('side') for t in store.trades])
    store, res = await run(k + 1, 0)   # control: la siguiente ya estaba a las 16:00:17 -> abre en el mismo minuto
    check('P3 Paper: si el collector ya pasó, abre en el mismo minuto (sin espera innecesaria)', len(store.trades) == 1,
          len(store.trades))

    # P4/P5. Filtro macro: la vela H4 que usa la tendencia macro también debe estar completa
    async def run_macro(with_next):
        store = po.Store()
        tr = po.mk_trader(dict(po.BASE, macro_trend_filter=True), store)
        clock = df['time'][k].to_pydatetime() + timedelta(seconds=17)
        po.CLOCK[0], po.PRICE[0] = clock, float(df['open'][k])
        last = clock.replace(hour=clock.hour - clock.hour % 4, minute=0, second=0) - timedelta(hours=4)
        t = [last - timedelta(hours=4 * i) for i in range(80)][::-1] + ([last + timedelta(hours=4)] if with_next else [])

        async def _bars(symbol, interval, broker=None):
            return h4(t) if interval == '240' else df.iloc[:k + 1].copy()
        tr.get_bars = _bars
        res = await tr.check_new_signals()
        return store, ' '.join(str(v) for v in res.values())

    store, txt = await run_macro(False)
    check('P4 Paper: filtro macro con la vela H4 sin completar -> espera', store.trades == [] and 'tendencia macro' in txt,
          txt[:140])
    store, txt = await run_macro(True)
    check('P5 Paper: filtro macro con la H4 completa -> no espera por la vela', 'sin completar' not in txt, txt[:140])


# ───────────── Real ─────────────
def code(signal):
    return f"class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = {signal}\n        return df\n"


async def real_case(main_rows, macro=None, btc=None):
    strat = rt_mod.build_strategy({**rp.P, 'strategy_code': code(-1), 'symbol': 'ETHUSDT', 'interval': '60'})
    if macro is not None:
        strat.macro_trend_filter = True
        strat.apply_macro_trend_filter = lambda d: d
    if btc is not None:
        strat.btc_filter_applies = lambda: True
        strat.apply_btc_trend_filter = lambda d: d
    tr = RealTrader(rp.FakePool({'exec': []}))
    opened = []

    async def _no(*a, **k):
        return None

    async def _false(*a, **k):
        return False

    async def _bars(symbol, interval, broker=None):
        if interval == '240':
            return (btc if symbol == 'BTCUSDT' else macro)()
        return main_rows()

    async def _open(sub, strategy, side, *a, **k):
        opened.append(side)
        return True
    tr.get_open_trade_for_subscription, tr.has_open_trade = _no, _false
    tr.get_bars, tr.open_trade, tr.entry_limit_reason = _bars, _open, _no
    client = rp.FakeClient()
    sub = {'symbol': 'ETHUSDT', 'interval': '60', 'broker_account_id': 7, 'subscription_id': 1, 'strategy': 'T'}
    return await tr.check_new_signals(sub, strat, client), opened, client


def h4_until():
    """Velas H4 hasta la última que ya cerró (incluida), sin la siguiente en la base."""
    now = datetime.now(timezone.utc)
    last = now.replace(hour=now.hour - now.hour % 4, minute=0, second=0, microsecond=0) - timedelta(hours=4)
    t = [last - timedelta(hours=4 * i) for i in range(80)][::-1]
    return lambda: h4(t)


def h4_with_next():
    f = h4_until()
    return lambda: pd.concat([f(), h4([f()['time'].iloc[-1] + timedelta(hours=4)])], ignore_index=True)


async def real_cases():
    full = rp.bars                                   # incluye la vela en formación (el collector ya pasó)
    without_next = lambda: rp.bars().iloc[:-1].copy()   # noqa: E731  la cerrada sin la siguiente en la base
    msg, opened, client = await real_case(without_next)
    check('R1 Real: la vela cerró pero la siguiente no está en la base -> no abre ni envía orden',
          opened == [] and client.orders == [] and 'sin completar' in msg, (msg, opened))
    check('R1 el motivo no se cuenta como «sin señal» en el resumen de Laravel', 'sin señal' not in msg, msg)
    msg, opened, _ = await real_case(full)
    check('R2 Real: con la vela completa abre la señal', opened == ['short'], (msg, opened))
    msg, opened, _ = await real_case(full, macro=h4_until())
    check('R3 Real: filtro macro con la vela H4 sin completar -> espera', opened == [] and 'tendencia macro' in msg,
          (msg, opened))
    msg, opened, _ = await real_case(full, macro=h4_with_next())
    check('R4 Real: filtro macro con la H4 completa -> abre', opened == ['short'], (msg, opened))
    msg, opened, _ = await real_case(full, btc=h4_until())
    check('R5 Real: filtro de BTC con la H4 de BTC sin completar -> espera', opened == [] and 'BTC' in msg,
          (msg, opened))
    msg, opened, _ = await real_case(full, btc=h4_with_next())
    check('R6 Real: filtro de BTC con la H4 completa -> abre', opened == ['short'], (msg, opened))


async def main():
    helper_cases()
    await paper_cases()
    await real_cases()
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

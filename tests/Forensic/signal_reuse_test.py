"""
Señal ya operada y hora de salida (NUEVO-03 / BP-08 / BP-05) — Paper y Real deben decidir las entradas como el motor:
la señal de la vela que cierra en T abre en T solo si en T no había posición y nadie entró desde T.
Sin base de datos ni Bybit: la consulta "señal ya operada" se ejecuta TAL CUAL (SQL real) sobre SQLite en memoria.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/signal_reuse_test.py
Antes del parche: FALLAN las sondas A y B (Paper y Real), los bordes, la hora de salida y la paridad con 1m.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import paper_opposite_test as po  # noqa: E402   (Paper: reloj, precio, pool en memoria con SQL real)
import real_opposite_test as ro  # noqa: E402    (Real: reloj, exchange y pool en memoria con SQL real)
import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def naive(t):
    t = pd.Timestamp(t).to_pydatetime()
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t


# ───────────── Paper con monitor (velas de 1m) sobre el pool en memoria de paper_opposite_test ─────────────
class MonitorConn(po.FakeConn):
    async def fetch(self, sql, *a):
        if "interval = '1'" in sql:                          # (symbol, desde, hasta, broker): 1m cerradas
            return [m for m in getattr(self.s, 'minutes', []) if a[1] < m['time'] <= a[2]]
        return await super().fetch(sql, *a)

    async def execute(self, sql, *a):
        if 'last_monitored_at = $6' in sql:                  # el monitor guarda el estado de la posición
            sl, be, tr, mp, ml, chk, tid, vw = a
            for t in self.s.trades:
                if t['id'] == tid:
                    t.update(sl=sl, be_activated=be, trailing_applied=tr, max_profit_pct=mp, max_loss_pct=ml,
                             last_monitored_at=chk, vol_widened=vw)
            return
        return await super().execute(sql, *a)


po.FakeConn = MonitorConn


async def paper_tick(trader, hours, k, minute):
    """Un ciclo de producción (monitor y luego señales) en el minuto `minute` de la vela k."""
    po.CLOCK[0] = hours['time'][k].to_pydatetime() + timedelta(minutes=minute)
    po.PRICE[0] = float(hours['open'][k]) if minute == 0 else float(hours['close'][k - 1])

    async def _bars(symbol, interval, broker=None):
        return hours.iloc[:k + 1].copy()
    trader.get_bars = _bars
    await trader.monitor_open_trades()
    return await trader.check_new_signals()


def market(n_hours=170, seed=11, p_sig=0.35, first_sig=66):
    """1m aleatorio (el minuto 0 de cada hora es plano: Paper entra al empezar la hora y no ve ese minuto) y su H1."""
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 2, 1, tzinfo=timezone.utc)
    rows, px = [], 100.0
    for h in range(n_hours):
        for m in range(60):
            t = t0 + timedelta(hours=h, minutes=m)
            if m == 0:
                rows.append((t, px, px, px, px))
                continue
            c = px * (1 + rng.normal(0, 0.0007))
            hi, lo = max(px, c) * (1 + abs(rng.normal(0, 0.0003))), min(px, c) * (1 - abs(rng.normal(0, 0.0003)))
            rows.append((t, px, hi, lo, c))
            px = c
    mins = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close'])
    g = mins.groupby(mins['time'].dt.floor('h'))
    hours = pd.DataFrame({'time': list(g.groups.keys()), 'open': g['open'].first().values,
                          'high': g['high'].max().values, 'low': g['low'].min().values,
                          'close': g['close'].last().values, 'volume': 1.0})
    sig = np.zeros(n_hours)
    for k in range(first_sig, n_hours):
        if rng.random() < p_sig:
            sig[k] = 1 if rng.random() < 0.5 else -1
    hours['sig'] = sig
    return hours, mins


def engine_run(params, hours, mins, start):
    s = po.pt.build_strategy(params)
    return po.BacktestEngine(s, hours, minute_df=mins, trade_from=hours['time'][start]).run()['trades']


def ev(side, entry, xp, reason, et):
    return (side, round(float(entry), 6), round(float(xp), 6), reason, naive(et).replace(minute=0, second=0, microsecond=0))


async def paper_parity(params, hours, mins, start, ticks=(0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)):
    store = po.Store()
    store.minutes = [{'time': r.time.to_pydatetime(), 'open': r.open, 'high': r.high, 'low': r.low, 'close': r.close}
                     for r in mins.itertuples()]
    trader = po.mk_trader(params, store)
    for k in range(start, len(hours)):
        for m in ticks:
            await paper_tick(trader, hours, k, m)
    return store


async def paper_section():
    print('── Paper ──')
    base = dict(po.BASE)

    # 1. Sonda A: abierto en la vela 69 y cerrado por SL dentro de ella; la vela 69 cierra con señal nueva.
    dfa = po.candles(n=75, seed=8, p_sig=0.0)
    dfa.loc[68, 'sig'] = 1
    dfa.loc[69, 'sig'] = 1
    st = po.Store()
    tr = po.mk_trader(base, st)
    await po.tick(tr, dfa, 69)
    st.trades[0].update(status='closed', exit_reason='stop_loss', exit_price=99.0,
                        exit_time=naive(dfa['time'][69]) + timedelta(minutes=30))
    await po.tick(tr, dfa, 70)
    check('sonda A: SL dentro de la vela y señal nueva al cerrarla -> Paper ENTRA en la vela siguiente (como el motor)',
          len(st.trades) == 2 and st.trades[1]['status'] == 'open', [(t['side'], t['status']) for t in st.trades])

    # 2. Sonda B: posición abierta en T con señal vieja de la misma dirección; SL a mitad de la vela siguiente.
    dfb = po.candles(n=80, seed=9, p_sig=0.0)
    dfb.loc[66, 'sig'] = 1
    dfb.loc[69, 'sig'] = 1
    st = po.Store()
    tr = po.mk_trader(base, st)
    await po.tick(tr, dfb, 67)
    await po.tick(tr, dfb, 70)
    st.trades[0].update(status='closed', exit_reason='stop_loss', exit_price=99.0,
                        exit_time=naive(dfb['time'][70]) + timedelta(minutes=5))
    res = await po.tick(tr, dfb, 70, 6)
    check('sonda B: señal vieja + SL a mitad de la vela siguiente -> Paper NO reabre (como el motor)',
          len(st.trades) == 1, list(res.values()))
    for m in (7, 30, 59):
        await po.tick(tr, dfb, 70, m)
    check('sonda B: tampoco reabre en el resto de esa vela', len(st.trades) == 1, len(st.trades))

    # 3. Bordes en T (cierre de la vela de la señal)
    for label, offset, expect in (('SL en el último minuto antes de T -> entra', -1, 2),
                                  ('SL en el minuto que empieza en T (abierta en T) -> no entra', 0, 1)):
        st = po.Store()
        tr = po.mk_trader(base, st)
        await po.tick(tr, dfa, 69)
        st.trades[0].update(status='closed', exit_reason='stop_loss', exit_price=99.0,
                            exit_time=naive(dfa['time'][70]) + timedelta(minutes=offset))
        await po.tick(tr, dfa, 70)
        check(f'borde: {label}', len(st.trades) == expect, len(st.trades))

    # 4. Una señal que ya abrió no se repite (regla de siempre), ni con varios ticks en la vela
    st = po.Store()
    tr = po.mk_trader(base, st)
    for m in (2, 3, 30):
        await po.tick(tr, dfa, 69, m)
    check('señal ya operada: 3 ticks en la vela, una sola entrada', len(st.trades) == 1, len(st.trades))

    # 5. Hora de salida = minuto del evento (BP-05), no la del proceso
    mins_t0 = naive(dfa['time'][69])
    st = po.Store()
    tr = po.mk_trader(base, st)
    await po.tick(tr, dfa, 69, 0)
    t = st.trades[0]
    hit = mins_t0 + timedelta(minutes=17)
    st.minutes = [{'time': (mins_t0 + timedelta(minutes=m)).replace(tzinfo=timezone.utc), 'open': 100.0,
                   'high': 100.1, 'low': (t['sl'] - 1 if m == 17 else 99.9), 'close': 100.0} for m in range(1, 40)]
    po.CLOCK[0] = (hit + timedelta(minutes=9)).replace(tzinfo=timezone.utc)    # el monitor lo procesa 9 min después
    await tr.monitor_open_trades()
    check('Paper: exit_time = minuto que tocó el SL (no la hora de proceso)',
          t['status'] == 'closed' and t['exit_time'] == hit, (t['status'], t.get('exit_time'), hit))

    # 6. Salida por señal opuesta: exit_time = cierre de la vela de la señal (T), como el motor
    p = dict(base, exit_on_opposite=True)
    d = po.candles(n=75, seed=3, p_sig=0.0)
    d.loc[68, 'sig'] = 1
    d.loc[70, 'sig'] = -1
    st = po.Store()
    tr = po.mk_trader(p, st)
    await po.tick(tr, d, 69)
    await po.tick(tr, d, 71, 3)
    T = naive(d['time'][71])
    check('Paper: salida por señal opuesta con exit_time = T (cierre de la vela de la señal)',
          st.trades[0]['status'] == 'closed' and st.trades[0]['exit_time'] == T, (st.trades[0].get('exit_time'), T))
    await po.tick(tr, d, 71, 4)
    check('exit_on_opposite: la señal consumida en la salida no abre en el tick siguiente', len(st.trades) == 1,
          len(st.trades))

    # 7. Paridad completa con velas de 1m (SL/TP dentro de la vela + señales frecuentes) contra el motor
    hours, mins = market()
    start = 70
    for label, extra in (('sin regla de opuesta', {}), ('close_on_opposite', dict(close_on_opposite=True)),
                         ('exit_on_opposite', dict(exit_on_opposite=True))):
        pp = dict(base, sl_pct=0.5, tp_pct=0.8, **extra)
        eng = engine_run(pp, hours, mins, start)
        st = await paper_parity(pp, hours, mins, start)
        e = [ev(x['side'], x['entry_price'], x['exit_price'], x['exit_reason'], x['entry_time']) for x in eng]
        pa = [ev(x['side'], x['entry_price'], x['exit_price'], x['exit_reason'], x['entry_time'])
              for x in st.trades if x['status'] == 'closed']
        reent = sum(1 for a, b in zip(eng, eng[1:]) if a['exit_reason'] in ('stop_loss', 'take_profit_1')
                    and naive(b['entry_time']) - naive(a['exit_time']) <= timedelta(hours=1))
        check(f'paridad 1m {label}: mismas operaciones que el motor ({len(e)}; {reent} entradas justo tras SL/TP)',
              len(e) >= 20 and reent >= 3 and pa == e, po.first_diff(pa, e) if pa != e else '')
        closed = [x for x in st.trades if x['status'] == 'closed']
        bad = []
        for x, y in zip(closed, eng):
            xt, et = x['exit_time'], naive(y['exit_time'])
            if x['exit_reason'] == 'opposite_signal':
                ok = xt == et
            else:   # motor y Paper guardan el minuto del evento (NUEVO-02): igual, y ese minuto toca el nivel
                row = mins[mins['time'] == pd.Timestamp(xt, tz='UTC')]
                lvl = y['exit_level']
                touch = (not row.empty and (row['low'].iloc[0] <= lvl + 1e-9 if (x['side'] == 'long') ==
                                            (x['exit_reason'] == 'stop_loss') else row['high'].iloc[0] >= lvl - 1e-9))
                ok = xt == et and touch
            if not ok:
                bad.append((x['id'], x['exit_reason'], xt, et))
        check(f'paridad 1m {label}: exit_time de Paper = hora del evento', not bad and closed, bad[:3])


async def real_section():
    print('── Real ──')
    base = dict(ro.BASE)

    def mk():
        st = ro.Store()
        ex = ro.Exchange(st)
        return st, ex, ro.mk_trader(st, ex)

    dfa = ro.one_shot(8, {68: 1, 69: 1}, n=75)
    st, ex, tr = mk()
    await ro.tick(tr, ex, dfa, 69, base)
    st.trades[0].update(status='closed', exit_reason='stop_loss', exit_price=99.0,
                        exit_time=naive(dfa['time'][69]) + timedelta(minutes=30))
    await ro.tick(tr, ex, dfa, 70, base)
    check('sonda A (Real): SL dentro de la vela y señal nueva al cerrarla -> entra en la vela siguiente',
          len(st.trades) == 2, ro.sides(st))

    dfb = ro.one_shot(9, {66: 1, 69: 1}, n=80)
    st, ex, tr = mk()
    await ro.tick(tr, ex, dfb, 67, base)
    await ro.tick(tr, ex, dfb, 70, base)
    st.trades[0].update(status='closed', exit_reason='stop_loss', exit_price=99.0,
                        exit_time=naive(dfb['time'][70]) + timedelta(minutes=5))
    for m in (6, 30):
        await ro.tick(tr, ex, dfb, 70, base, m)
    check('sonda B (Real): señal vieja + SL a mitad de la vela siguiente -> NO reabre', len(st.trades) == 1, ro.sides(st))

    st, ex, tr = mk()
    st.trades.append({'id': 99, 'subscription_id': 1, 'symbol': 'BTCUSDT', 'interval': '60', 'side': 'long',
                      'status': 'error', 'entry_time': naive(dfa['time'][68]) + timedelta(minutes=2),
                      'exit_time': None, 'exit_reason': None})
    st.nid = 100
    await ro.tick(tr, ex, dfa, 70, base)
    check('Real: una entrada fallida anterior (status error, sin exit_time) no bloquea la señal siguiente',
          len(st.trades) == 2, ro.sides(st))

    # Hora de salida de un cierre nativo (SL/TP en Bybit): la del closed-pnl, no la de detección
    class Client:
        def __init__(self, hist):
            self.hist = hist

        async def get_closed_pnl_history(self, *a, **k):
            return self.hist

        async def get_balance(self):
            return 1000.0

    class CapConn:
        def __init__(self, log):
            self.log = log

        async def execute(self, sql, *a):
            self.log.append((sql, a))
            return 'UPDATE 1'

    class CapPool:
        def __init__(self):
            self.log = []

        def acquire(self):
            log = self.log

            class _C:
                async def __aenter__(self):
                    return CapConn(log)

                async def __aexit__(self, *e):
                    return False
            return _C()

    trade = {'id': 5, 'symbol': 'BTCUSDT', 'side': 'long', 'entry_price': 100.0, 'size': 2.0, 'sl': 99.0,
             'tp': 102.0, 'balance_before': 1000.0, 'trailing_applied': False, 'strategy': 'T'}
    t1, t2 = datetime(2026, 3, 1, 10, 59, 50), datetime(2026, 3, 1, 10, 59, 58)
    ms = lambda t: str(int(t.replace(tzinfo=timezone.utc).timestamp() * 1000))  # noqa: E731
    hist = [{'closedSize': '1', 'cumExitValue': '99', 'closedPnl': '-1.1', 'createdTime': ms(t1), 'updatedTime': ms(t1)},
            {'closedSize': '1', 'cumExitValue': '99', 'closedPnl': '-1.1', 'createdTime': ms(t1), 'updatedTime': ms(t2)}]
    for label, h, want in (('2 tramos: hora del último tramo de Bybit', hist, t2),
                           ('sin hora en el closed-pnl: ahora (como antes)',
                            [dict(x, createdTime='', updatedTime=None) for x in hist], None)):
        pool = CapPool()
        trd = RealTrader(pool)
        await trd.settle_exchange_close(dict(trade), Client(h), 7, 0)
        upd = [(s, a) for s, a in pool.log if 'UPDATE real_trades' in s and "status='closed'" in s]
        got = upd[0][1][8] if upd and len(upd[0][1]) > 8 else 'sin parámetro'
        sql_ok = bool(upd) and 'COALESCE($9::timestamp, now())' in upd[0][0]
        check(f'Real cierre nativo: {label}', sql_ok and got == want, (got, want))


async def main():
    await paper_section()
    await real_section()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

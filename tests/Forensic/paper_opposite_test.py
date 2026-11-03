"""
Señal opuesta en Paper (BP-02): Paper debe comportarse como el motor de backtest. Sin base de datos: pool en memoria.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/paper_opposite_test.py
Antes del parche debe FALLAR en la paridad (Paper nunca cierra por señal opuesta); después, todo PASS.
Las líneas INFO son sondas informativas: no cuentan como fallo.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.getcwd())  # ejecutar desde python-engine/

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def _import_paper():
    for _ in range(12):
        try:
            import trading.paper_trader as m
            return m
        except ModuleNotFoundError as e:
            name = e.name or ''
            if name.split('.')[0] in ('trading', 'collectors', 'backtesting', 'indicators', 'db', ''):
                raise
            print(f"AVISO: módulo de terceros '{name}' no instalado aquí: se simula (solo lógica pura)")
            sys.modules[name] = mock.MagicMock()
    raise RuntimeError('no se pudo importar paper_trader')


pt = _import_paper()
from trading.paper_trader import PaperTrader  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def info(msg):
    print('INFO ' + msg)


# ───────────── reloj, precio y datos simulados ─────────────
CLOCK = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
PRICE = [100.0]


class FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):
        t = CLOCK[0]
        return t if tz is not None else t.replace(tzinfo=None)


async def _price(symbol):
    return PRICE[0]


async def _broker(*a, **k):
    return 'bybit'


async def _funding(pool, symbol, start, end, client=None, now=None):
    from collectors.funding_collector import FundingData
    return FundingData(symbol, np.array([], dtype='datetime64[ns]'), np.array([], dtype=float), start, end), []


pt.datetime = FakeDT
pt.get_current_price = _price
pt.resolve_live_broker = _broker
pt.load_funding = _funding

CODE = ("class Scripted(BaseStrategy):\n"
        "    def generate_signals(self, df):\n"
        "        df = df.copy()\n"
        "        df['signal'] = df['sig'].fillna(0).astype(int)\n"
        "        return df\n")
BASE = dict(symbol='BTCUSDT', interval='60', sl_pct=50.0, tp_pct=100.0, be_pct=90.0, max_duration=0,
            regime_filter=False, commission_pct=0.055, slippage_pct=0.05, strategy_code=CODE)


class Store:
    def __init__(self, kill=False):
        self.trades, self.kill, self.nid = [], kill, 1


class FakeConn:
    def __init__(self, s):
        self.s = s

    async def fetch(self, sql, *a):
        if 'FROM paper_trades' in sql and "status = 'open'" in sql:
            return [dict(t) for t in self.s.trades if t['status'] == 'open']
        return []

    async def fetchrow(self, sql, *a):
        if 'risk_controls' in sql:
            return {'id': 1} if self.s.kill else None
        if "status = 'open'" in sql and 'paper_strategy_config_id = $1' in sql:   # has_open_trade (código anterior)
            hit = [t for t in self.s.trades if t['paper_strategy_config_id'] == a[0] and t['status'] == 'open']
            return {'id': hit[0]['id']} if hit else None
        if 'FROM paper_trades' in sql and 'entry_time >=' in sql:
            cfg, cand = a[0], a[1]
            uses_consumed = "exit_reason = 'opposite_signal'" in sql and len(a) > 2   # la condición va EN el SQL
            cand_close = a[2] if uses_consumed else None
            hit = [t for t in self.s.trades if t['paper_strategy_config_id'] == cfg and (
                (t['entry_time'] >= cand if 'entry_time >= $2' in sql else False) or
                (uses_consumed and t.get('exit_reason') == 'opposite_signal'
                 and t.get('exit_time') is not None and t['exit_time'] >= cand_close))]
            return {'id': max(hit, key=lambda t: t['entry_time'])['id']} if hit else None
        return None

    async def execute(self, sql, *a):
        if 'INSERT INTO paper_trades' in sql:
            (name, cfg, sym, itv, side, entry, sl, tp, tp2, tp3, tp4, be, size, regime, et, snap) = a
            self.s.trades.append({'id': self.s.nid, 'strategy': name, 'paper_strategy_config_id': cfg,
                                  'config_snapshot': snap, 'symbol': sym, 'interval': itv, 'side': side,
                                  'entry_price': entry, 'sl': sl, 'tp': tp, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
                                  'be_level': be, 'be_activated': False, 'trailing_applied': False,
                                  'vol_widened': False, 'size': size, 'entry_time': et, 'regime': regime,
                                  'max_profit_pct': 0, 'max_loss_pct': 0, 'last_monitored_at': None,
                                  'status': 'open', 'exit_price': None, 'exit_reason': None, 'exit_time': None})
            self.s.nid += 1
        elif "status = 'closed'" in sql:
            xp, pnl, pct, reason, xt, mp, ml, com, tid, fund = a
            for t in self.s.trades:
                if t['id'] == tid:
                    t.update(status='closed', exit_price=xp, exit_reason=reason, exit_time=xt, pnl=pnl)


class FakePool:
    def __init__(self, s):
        self.s = s

    def acquire(self):
        s = self.s

        class _C:
            async def __aenter__(self):
                return FakeConn(s)

            async def __aexit__(self, *e):
                return False
        return _C()


def candles(n=160, seed=7, p_sig=0.22, first_sig=68):
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    close = 100 + np.cumsum(rng.normal(0, 0.4, n))
    open_ = np.concatenate([[100.0], close[:-1]])
    sig = np.zeros(n)
    for k in range(first_sig, n):
        if rng.random() < p_sig:
            sig[k] = 1 if rng.random() < 0.5 else -1
    return pd.DataFrame({'time': [t0 + timedelta(hours=i) for i in range(n)], 'open': open_,
                         'high': np.maximum(open_, close) + 0.3, 'low': np.minimum(open_, close) - 0.3,
                         'close': close, 'volume': 1.0, 'sig': sig})


def mk_trader(params, store):
    cfg = {'id': 1, 'display_name': 'T', 'symbol': 'BTCUSDT', 'interval': '60', 'params': json.dumps(params)}
    return PaperTrader(FakePool(store), {}, {1: cfg})


async def tick(trader, df, k, minute=2):
    """Un tick de paper en el minuto `minute` de la vela k: ve las velas hasta k (la k en formación)."""
    CLOCK[0] = df['time'][k].to_pydatetime() + timedelta(minutes=minute)
    PRICE[0] = float(df['open'][k])

    async def _bars(symbol, interval, broker=None):
        return df.iloc[:k + 1].copy()
    trader.get_bars = _bars
    return await trader.check_new_signals()


async def simulate(params, df, start, ticks=(2, 3, 4), kill=False):
    store = Store(kill=kill)
    trader = mk_trader(params, store)
    for k in range(start, len(df)):
        for m in ticks:
            await tick(trader, df, k, m)
    return store


def engine_trades(params, df, start):
    s = pt.build_strategy(params)
    r = BacktestEngine(s, df, trade_from=df['time'][start]).run()
    return [(t['side'], round(float(t['entry_price']), 6), round(float(t['exit_price']), 6), t['exit_reason'])
            for t in r['trades']]


def paper_closed(store):
    return [(t['side'], round(float(t['entry_price']), 6), round(float(t['exit_price']), 6), t['exit_reason'])
            for t in store.trades if t['status'] == 'closed']


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f'#{i}: paper={x} motor={y}'
    return f'longitudes distintas: paper={len(a)} motor={len(b)}'


async def main():
    df = candles()
    start = 70

    # 1-3. Paridad Paper vs motor, con 3 ticks por vela (como en producción, un tick por minuto)
    for label, extra in (('close_on_opposite (cierra y reversa)', dict(close_on_opposite=True)),
                         ('exit_on_opposite (solo cierra)', dict(exit_on_opposite=True)),
                         ('ambas activas (exit manda: solo cierra)', dict(close_on_opposite=True, exit_on_opposite=True))):
        p = dict(BASE, **extra)
        eng = engine_trades(p, df, start)
        st = await simulate(p, df, start)
        pap = paper_closed(st)
        check(f'paridad {label}: mismos cierres que el motor ({len(eng)} operaciones)',
              len(eng) >= 5 and pap == eng, first_diff(pap, eng) if pap != eng else '')
        open_now = [t for t in st.trades if t['status'] == 'open']
        check(f'paridad {label}: a lo sumo una posición abierta', len(open_now) <= 1, len(open_now))
        check(f'paridad {label}: todos los cierres son por señal opuesta', all(x[3] == 'opposite_signal' for x in pap))

    # 4. Sin la regla: Paper no cambia (la posición se mantiene; ningún cierre por señal opuesta)
    st = await simulate(dict(BASE), df, start)
    check('sin close/exit_on_opposite: Paper no cierra nada y mantiene su única posición',
          len(st.trades) == 1 and st.trades[0]['status'] == 'open', [t['status'] for t in st.trades])

    # 5. Reversa: cierre y entrada contraria con el MISMO precio base y slippage en contra
    p = dict(BASE, close_on_opposite=True)
    df2 = candles(n=75, seed=3, p_sig=0.0)
    df2.loc[68, 'sig'] = 1     # entrada larga en el open de la vela 69
    df2.loc[70, 'sig'] = -1    # opuesta -> sale y reversa en el open de la vela 71
    st = await simulate(p, df2, 69)
    tr = st.trades
    ok = (len(tr) == 2 and tr[0]['status'] == 'closed' and tr[1]['status'] == 'open' and tr[0]['side'] == 'long'
          and tr[1]['side'] == 'short')
    check('reversa: long cerrado + short abierto', ok, [(t['side'], t['status']) for t in tr])
    if ok:
        o71 = float(df2['open'][71])
        check('salida long = open·(1-slip) y entrada short = open·(1-slip)',
              abs(tr[0]['exit_price'] - o71 * 0.9995) < 1e-9 and abs(tr[1]['entry_price'] - o71 * 0.9995) < 1e-9,
              (tr[0]['exit_price'], tr[1]['entry_price'], o71 * 0.9995))

    # 6. La señal de la vela de entrada no cierra la posición recién abierta
    p = dict(BASE, close_on_opposite=True)
    df3 = candles(n=75, seed=4, p_sig=0.0)
    df3.loc[68, 'sig'] = 1     # abre long en la vela 69
    df3.loc[69, 'sig'] = -1    # señal opuesta de la vela 69 (cierra a las 70:00) -> sí cierra en la vela 70
    st = await simulate(p, df3, 69, ticks=(2,))
    # tick de la vela 69 -> abre; tick de la vela 70 -> la vela 69 cerró después de la entrada -> cierra y reversa
    check('opuesta de la vela de entrada, ya cerrada: cierra en la vela siguiente (como el motor)',
          len(st.trades) == 2 and st.trades[0]['status'] == 'closed', [(t['side'], t['status']) for t in st.trades])
    store = Store()
    trader = mk_trader(p, store)
    await tick(trader, df3, 69)            # abre long
    await tick(trader, df3, 69, 3)         # mismo tramo: la vela 68 (la que abrió) es la última cerrada
    check('en el mismo tramo no cierra con la señal que lo abrió',
          len(store.trades) == 1 and store.trades[0]['status'] == 'open')

    df3b = df3.copy()
    store = Store()
    trader = mk_trader(p, store)
    await tick(trader, df3b, 69)                         # abre long con la señal +1 de la vela 68
    df3b.loc[68, 'sig'] = -1                             # esa misma vela cambia de señal entre ticks (filtro actualizado)
    await tick(trader, df3b, 69, 3)
    check('la señal de la vela de entrada cambia a opuesta entre ticks: NO cierra (cerró antes de la entrada)',
          len(store.trades) == 1 and store.trades[0]['status'] == 'open', [(t['side'], t['status']) for t in store.trades])

    # 7. Misma dirección: no hace nada
    df4 = candles(n=75, seed=5, p_sig=0.0)
    df4.loc[68, 'sig'] = 1
    df4.loc[70, 'sig'] = 1
    st = await simulate(dict(BASE, close_on_opposite=True), df4, 69, ticks=(2,))
    check('misma dirección: sigue la posición, sin cierres', len(st.trades) == 1 and st.trades[0]['status'] == 'open')

    # 8. Reglas congeladas: manda el snapshot del trade, no la config viva
    df5 = candles(n=75, seed=6, p_sig=0.0)
    df5.loc[68, 'sig'] = 1
    df5.loc[70, 'sig'] = -1
    store = Store()
    trader = mk_trader(dict(BASE), store)              # config viva SIN regla
    await tick(trader, df5, 69)                         # abre long (snapshot sin regla)
    trader2 = mk_trader(dict(BASE, close_on_opposite=True), store)   # ahora la config viva la activa
    await tick(trader2, df5, 71)
    check('snapshot sin regla + config viva con regla: NO cierra (manda lo congelado)',
          len(store.trades) == 1 and store.trades[0]['status'] == 'open')
    store = Store()
    trader = mk_trader(dict(BASE, close_on_opposite=True), store)
    await tick(trader, df5, 69)                         # abre long con regla en el snapshot
    trader2 = mk_trader(dict(BASE), store)              # la config viva la apaga
    await tick(trader2, df5, 71)
    check('snapshot con regla + config viva sin regla: SÍ cierra (manda lo congelado)',
          store.trades[0]['status'] == 'closed' and store.trades[0]['exit_reason'] == 'opposite_signal')

    # 9. Sin precio: no se cierra y se reintenta
    store = Store()
    trader = mk_trader(dict(BASE, close_on_opposite=True), store)
    await tick(trader, df5, 69)
    PRICE_SAVE = PRICE[0]

    async def _noprice(symbol):
        return None
    pt.get_current_price = _noprice
    CLOCK[0] = df5['time'][71].to_pydatetime() + timedelta(minutes=2)

    async def _bars(symbol, interval, broker=None):
        return df5.iloc[:72].copy()
    trader.get_bars = _bars
    res = await trader.check_new_signals()
    pt.get_current_price = _price
    check('sin precio: la posición sigue abierta', len(store.trades) == 1 and store.trades[0]['status'] == 'open', list(res.values()))
    await tick(trader, df5, 71, 3)
    check('con precio de nuevo: cierra y reversa', len(store.trades) == 2 and store.trades[0]['status'] == 'closed')

    # 10. Kill switch: las posiciones abiertas se siguen gestionando (cierra, sin reversa); sin regla no se toca nada
    store = Store()
    trader = mk_trader(dict(BASE, close_on_opposite=True), store)
    await tick(trader, df5, 69)
    store.kill = True
    res = await tick(trader, df5, 71)
    check('kill switch + regla: cierra por señal opuesta pero NO reversa',
          len(store.trades) == 1 and store.trades[0]['status'] == 'closed', [(t['side'], t['status']) for t in store.trades])
    store = Store()
    trader = mk_trader(dict(BASE), store)
    store.kill = True
    res = await tick(trader, df5, 69)
    check('kill switch sin posiciones: no abre nada y mantiene el mensaje de siempre',
          not store.trades and any('KILL SWITCH' in v for v in res.values()), list(res.values()))

    # 11. Régimen no permitido: cierra por señal opuesta, pero no reversa (igual que el motor)
    prg = dict(BASE, close_on_opposite=True, regime_filter=True, allowed_regimes=['TRENDING'])
    store = Store()
    trader = mk_trader(dict(BASE, close_on_opposite=True), store)
    await tick(trader, df5, 69)
    trader2 = mk_trader(prg, store)                     # config viva: solo opera en TRENDING (el régimen sale RANGING)
    await tick(trader2, df5, 71)
    check('régimen no permitido: cierra por señal opuesta y no reversa',
          len(store.trades) == 1 and store.trades[0]['status'] == 'closed', [(t['side'], t['status']) for t in store.trades])

    # 12. Idempotencia dentro de la misma vela: el 2.º y 3.er tick no duplican nada
    store = Store()
    trader = mk_trader(dict(BASE, close_on_opposite=True), store)
    await tick(trader, df5, 69)
    for m in (2, 3, 4):
        await tick(trader, df5, 71, m)
    check('3 ticks en la vela de la reversa: 1 cierre + 1 apertura, sin duplicados',
          len(store.trades) == 2 and [t['status'] for t in store.trades] == ['closed', 'open'],
          [(t['side'], t['status']) for t in store.trades])

    # ───────── Sondas informativas sobre la lógica de entradas (NO se tocan en este parche) ─────────
    # A) trade abierto en la vela k y cerrado por SL dentro de la misma vela; señal nueva al cerrar k.
    #    El motor entra en el open de k+1; ¿Paper?
    dfa = candles(n=75, seed=8, p_sig=0.0)
    dfa.loc[68, 'sig'] = 1
    dfa.loc[69, 'sig'] = 1
    store = Store()
    trader = mk_trader(dict(BASE), store)
    await tick(trader, dfa, 69)                                   # abre long (señal de la vela 68)
    t = store.trades[0]
    t.update(status='closed', exit_reason='stop_loss', exit_price=99.0,
             exit_time=(dfa['time'][69].to_pydatetime() + timedelta(minutes=30)).replace(tzinfo=None))
    await tick(trader, dfa, 70)                                   # señal de la vela 69 (+1) y no hay posición
    info('sonda A (trade cerrado por SL dentro de la vela y señal nueva al cerrarla): '
         + ('Paper ENTRA (como el motor)' if len(store.trades) == 2 else
            'Paper NO entra, el motor sí entraría en el open siguiente'))

    # B) posición mantenida con señales de la misma dirección ignoradas y SL a mitad de la vela siguiente:
    #    el motor no usa esa señal vieja; ¿Paper reabre con ella?
    dfb = candles(n=80, seed=9, p_sig=0.0)
    dfb.loc[66, 'sig'] = 1
    dfb.loc[69, 'sig'] = 1
    store = Store()
    trader = mk_trader(dict(BASE), store)
    await tick(trader, dfb, 67)                                   # abre long
    await tick(trader, dfb, 70)                                   # la señal de la vela 69 (+1) se ignora: hay posición
    t = store.trades[0]
    t.update(status='closed', exit_reason='stop_loss', exit_price=99.0,
             exit_time=(dfb['time'][70].to_pydatetime() + timedelta(minutes=5)).replace(tzinfo=None))
    await tick(trader, dfb, 70, 6)                                # mismo tramo, minuto 6: sigue la señal vieja
    info('sonda B (SL a mitad de vela con una señal vieja de la misma dirección): '
         + ('Paper REABRE con la señal vieja, el motor no' if len(store.trades) == 2 else
            'Paper no reabre (como el motor)'))

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

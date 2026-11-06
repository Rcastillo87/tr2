"""
Señal opuesta en Real (BP-02): Real debe cerrar (y con close_on_opposite invertir) igual que el motor de backtest y Paper.
Sin base de datos ni Bybit: pool en memoria y exchange simulado, sin órdenes reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_opposite_test.py
Antes del parche debe FALLAR (Real nunca cierra por señal opuesta); después, todo PASS.
"""
import asyncio
import inspect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import sqlfake  # noqa: E402
import paper_opposite_test as po  # noqa: E402  (velas con señal guionada, estrategia Scripted, motor)
import real_parity_test as rp  # noqa: E402     (anula las esperas de asyncio.sleep, fuente de velas fija)
import trading.real_trader as rt_mod  # noqa: E402
import api.v1.real_trading as api  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


CLOCK = [datetime(2026, 1, 1, tzinfo=timezone.utc)]


class FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):
        t = CLOCK[0]
        return t if tz is not None else t.replace(tzinfo=None)


rt_mod.datetime = FakeDT
BASE = dict(po.BASE, max_duration=0)


# ───────────── base de datos y exchange simulados ─────────────
REAL_COLS = ('subscription_id', 'symbol', 'entry_time', 'exit_time', 'exit_reason', 'status')


class Store:
    def __init__(self):
        self.trades, self.nid, self.limit = [], 1, None


def _naive(t):
    return t.replace(tzinfo=None) if t.tzinfo else t


class Conn:
    def __init__(self, s):
        self.s = s

    async def fetchrow(self, sql, *a):
        t = self.s.trades
        if 'rt.subscription_id = $1' in sql and "rt.status = 'open'" in sql:   # get_open_trade_for_subscription
            hit = [x for x in t if x['subscription_id'] == a[0] and x['status'] == 'open']
            return dict(hit[-1]) if hit else None
        if 'FROM real_strategy_subscriptions' in sql:                          # has_open_trade (1)
            return {'broker_account_id': 7}
        if 'FROM real_trades' in sql and "status IN ('pending_open'" in sql:   # has_open_trade (2)
            hit = [x for x in t if x['symbol'] == a[1] and x['status'] in ('pending_open', 'open', 'pending_close',
                                                                            'orphaned')]
            return {'id': hit[0]['id']} if hit else None
        if 'FROM real_trades' in sql and 'entry_time >= $3' in sql:            # already_traded: SQL real
            return sqlfake.fetchrow(t, 'real_trades', sql, a, columns=REAL_COLS)
        return None

    async def fetch(self, sql, *a):
        return []

    async def fetchval(self, sql, *a):
        return None

    async def execute(self, sql, *a):
        return 'UPDATE 1'


class Pool:
    def __init__(self, s):
        self.s = s

    def acquire(self):
        s = self.s

        class _C:
            async def __aenter__(self):
                return Conn(s)

            async def __aexit__(self, *e):
                return False
        return _C()


class Exchange:
    """Bybit simulado: la posición viva es la del trade abierto; el precio es el open de la vela en curso."""
    def __init__(self, store, close_ok=True):
        self.s, self.price, self.close_ok, self.orders = store, 100.0, close_ok, []

    async def get_open_position(self, symbol):
        hit = [x for x in self.s.trades if x['symbol'] == symbol and x['status'] == 'open']
        return {'size': '1', 'avgPrice': str(hit[0]['entry_price'])} if hit else None

    async def get_market_price(self, symbol):
        return self.price


def mk_trader(store, ex):
    tr = RealTrader(Pool(store))

    async def _open(sub, strategy, side, price, regime, client, signal_sl_pct=None):
        ex.orders.append(('open', side))
        store.trades.append({'id': store.nid, 'subscription_id': sub['subscription_id'], 'symbol': sub['symbol'],
                             'interval': sub['interval'], 'side': side, 'entry_price': price, 'status': 'open',
                             'entry_time': _naive(CLOCK[0]), 'exit_time': None, 'exit_reason': None,
                             'exit_price': None, 'config_snapshot': json.dumps(sub['config_params'])})
        store.nid += 1
        return True

    async def _close(trade, reason, client, account_id, **k):
        ex.orders.append(('close', trade['side']))
        if not ex.close_ok:
            return False
        for x in store.trades:
            if x['id'] == trade['id']:
                x.update(status='closed', exit_reason=reason, exit_price=ex.price, exit_time=_naive(CLOCK[0]))
        return True

    async def _limit(account_id):
        return store.limit
    tr.open_trade, tr.close_trade, tr.entry_limit_reason = _open, _close, _limit
    return tr


def sub_for(params):
    return {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 7, 'subscription_id': 1, 'strategy': 'T',
            'config_params': params}


async def tick(tr, ex, df, k, params, minute=2, entries_allowed=True):
    CLOCK[0] = df['time'][k].to_pydatetime() + timedelta(minutes=minute)
    ex.price = float(df['open'][k])

    async def _bars(symbol, interval, broker=None):
        return df.iloc[:k + 1].copy()
    tr.get_bars = _bars
    strat = rt_mod.build_strategy({**params, 'symbol': 'BTCUSDT', 'interval': '60'})
    if 'entries_allowed' not in inspect.signature(tr.check_new_signals).parameters:   # código anterior al parche
        return await tr.check_new_signals(sub_for(params), strat, ex) if entries_allowed else 'sin parámetro'
    return await tr.check_new_signals(sub_for(params), strat, ex, entries_allowed=entries_allowed)


async def simulate(params, df, start, ticks=(2, 3, 4), live_params=None):
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    for k in range(start, len(df)):
        for m in ticks:
            await tick(tr, ex, df, k, live_params or params, m)
    return store, ex


def engine_events(params, df, start):
    s = po.pt.build_strategy(params)
    r = po.BacktestEngine(s, df, trade_from=df['time'][start]).run()
    # end_of_data (BP-04): el motor cierra al final del rango lo que Real sigue teniendo abierto
    return [(t['side'], _naive(pd_ts(t['entry_time'])), _naive(pd_ts(t['exit_time'])), t['exit_reason'])
            for t in r['trades'] if t['exit_reason'] != 'end_of_data']


def pd_ts(t):
    return po.pd.Timestamp(t).to_pydatetime()


def real_events(store, df):
    """(lado, vela de entrada, vela de salida, motivo): el tick ocurre dentro de la vela; se compara la vela."""
    def bar(t):
        return t.replace(minute=0, second=0, microsecond=0)
    return [(x['side'], bar(x['entry_time']), bar(x['exit_time']), x['exit_reason'])
            for x in store.trades if x['status'] == 'closed']


def sides(store):
    return [(x['side'], x['status']) for x in store.trades]


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f'#{i}: real={x} motor={y}'
    return f'longitudes distintas: real={len(a)} motor={len(b)}'


def one_shot(seed, sigs, n=78):
    d = po.candles(n=n, seed=seed, p_sig=0.0)
    for k, v in sigs.items():
        d.loc[k, 'sig'] = v
    return d


async def main():
    df = po.candles()
    start = 70

    # 1-3. Paridad Real vs motor (vela de entrada, vela de salida, lado y motivo), 3 ticks por vela
    for label, extra in (('close_on_opposite (cierra y reversa)', dict(close_on_opposite=True)),
                         ('exit_on_opposite (solo cierra)', dict(exit_on_opposite=True)),
                         ('ambas activas (exit manda)', dict(close_on_opposite=True, exit_on_opposite=True)),
                         ('close_on_opposite sin short', dict(close_on_opposite=True, allow_short=False))):
        p = dict(BASE, **extra)
        eng = engine_events(p, df, start)
        st, ex = await simulate(p, df, start)
        rea = real_events(st, df)
        check(f'paridad {label}: mismos eventos que el motor ({len(eng)} operaciones)',
              len(eng) >= 5 and rea == eng, first_diff(rea, eng) if rea != eng else '')
        open_now = [x for x in st.trades if x['status'] == 'open']
        check(f'paridad {label}: nunca más de una posición', len(open_now) <= 1, len(open_now))

    # 4. Sin la regla: Real no cierra nada
    st, ex = await simulate(dict(BASE), df, start)
    check('sin close/exit_on_opposite: mantiene su única posición',
          sides(st) == [(st.trades[0]['side'], 'open')] if st.trades else False, sides(st))

    # 5. Reversa: cierra el long y abre el short en la misma vela; la reversa sale después del cierre
    p = dict(BASE, close_on_opposite=True)
    d = one_shot(3, {68: 1, 70: -1}, n=75)
    st, ex = await simulate(p, d, 69)
    check('reversa: long cerrado por señal opuesta + short abierto',
          sides(st) == [('long', 'closed'), ('short', 'open')] and st.trades[0]['exit_reason'] == 'opposite_signal',
          sides(st))
    check('reversa: orden de operaciones open long -> close long -> open short',
          ex.orders == [('open', 'long'), ('close', 'long'), ('open', 'short')], ex.orders)

    # 6. La señal de la vela de entrada: con la vela ya cerrada después de la entrada, sí cierra (como el motor)
    d = one_shot(4, {68: 1, 69: -1}, n=75)
    st, ex = await simulate(p, d, 69, ticks=(2,))
    check('opuesta de la vela de entrada ya cerrada: cierra en la vela siguiente',
          len(st.trades) == 2 and st.trades[0]['status'] == 'closed', sides(st))
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    d2 = d.copy()
    await tick(tr, ex, d2, 69, p)                 # abre long con la señal +1 de la vela 68
    d2.loc[68, 'sig'] = -1                         # esa vela cambia a opuesta entre ticks
    await tick(tr, ex, d2, 69, p, 3)
    check('la señal que abrió el trade cambia a opuesta: NO cierra (cerró antes de la entrada)',
          sides(store) == [('long', 'open')], sides(store))

    # 7. Misma dirección: no hace nada
    st, ex = await simulate(p, one_shot(5, {68: 1, 70: 1}, n=75), 69, ticks=(2,))
    check('misma dirección: sigue la posición, sin cierres', sides(st) == [('long', 'open')], sides(st))

    # 8. Reglas congeladas: manda el snapshot del trade, no la config viva
    d = one_shot(6, {68: 1, 70: -1}, n=75)
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    await tick(tr, ex, d, 69, dict(BASE))                              # abre sin regla en el snapshot
    await tick(tr, ex, d, 71, dict(BASE, close_on_opposite=True))      # la config viva la activa
    check('snapshot sin regla + config viva con regla: NO cierra', sides(store) == [('long', 'open')], sides(store))
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    await tick(tr, ex, d, 69, dict(BASE, close_on_opposite=True))      # abre con la regla en el snapshot
    await tick(tr, ex, d, 71, dict(BASE))                              # la config viva la apaga
    check('snapshot con regla + config viva sin regla: SÍ cierra',
          store.trades[0]['status'] == 'closed' and store.trades[0]['exit_reason'] == 'opposite_signal', sides(store))

    # 9. Cierre no confirmado en Bybit: no reversa y reintenta el próximo ciclo
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    await tick(tr, ex, d, 69, p)
    ex.close_ok = False
    msg = await tick(tr, ex, d, 71, p)
    check('cierre no confirmado: posición sigue abierta y NO se abre la contraria',
          sides(store) == [('long', 'open')] and 'no confirmado' in msg, (sides(store), msg))
    ex.close_ok = True
    await tick(tr, ex, d, 71, p, 3)
    check('cierre confirmado en el ciclo siguiente: cierra y reversa',
          sides(store) == [('long', 'closed'), ('short', 'open')], sides(store))

    # 10. Cuenta pausada / kill switch (entries_allowed=False): cierra sin reversa; sin posición no hace nada
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    await tick(tr, ex, d, 69, p)
    msg = await tick(tr, ex, d, 71, p, entries_allowed=False)
    check('entradas bloqueadas + regla: cierra por señal opuesta pero NO reversa',
          sides(store) == [('long', 'closed')] and 'sin reversa' in msg, (sides(store), msg))
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    msg = await tick(tr, ex, d, 69, p, entries_allowed=False)
    check('entradas bloqueadas sin posición: no abre', store.trades == [] and ex.orders == [], (sides(store), msg))

    # 11. Límite de riesgo alcanzado: cierra sin reversa
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    await tick(tr, ex, d, 69, p)
    store.limit = 'máximo de trades abiertos (1/1)'
    msg = await tick(tr, ex, d, 71, p)
    check('límite de riesgo: cierra por señal opuesta y NO reversa',
          sides(store) == [('long', 'closed')] and 'límite de riesgo' in msg, (sides(store), msg))

    # 12. exit_on_opposite: la señal consumida no reabre en los ticks siguientes; la siguiente señal sí abre
    pe = dict(BASE, exit_on_opposite=True)
    d = one_shot(7, {68: 1, 70: -1, 73: -1})
    store = Store()
    ex = Exchange(store)
    tr = mk_trader(store, ex)
    for k in range(69, 73):
        for m in (2, 3, 4):
            await tick(tr, ex, d, k, pe, m)
    check('exit_on_opposite: cierra y la señal consumida no reabre en los ticks siguientes',
          sides(store) == [('long', 'closed')], sides(store))
    for k in range(73, 76):
        for m in (2, 3, 4):
            await tick(tr, ex, d, k, pe, m)
    check('exit_on_opposite: la siguiente señal (short) sí abre una vez', sides(store) == [('long', 'closed'),
          ('short', 'open')], sides(store))

    # 13. Banderas en texto ("false") no activan la regla
    st, ex = await simulate(dict(BASE, close_on_opposite='false'), one_shot(3, {68: 1, 70: -1}, n=75), 69)
    check("close_on_opposite='false' (texto): no cierra", sides(st) == [('long', 'open')], sides(st))

    # 14. Orquestación: cuenta pausada o kill switch -> check_new_signals con entries_allowed=False
    await orchestration()

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


async def orchestration():
    class Tr:
        def __init__(self):
            self.flags = []
            self.pool = None

        async def ensure_month_baseline(self, *a):
            return None

        async def get_circuit_breaker_errors(self, *a):
            return 0

        async def monitor_open_trades(self, *a):
            return {'checked': 0, 'closed': 0}

        async def check_new_signals(self, sub, strategy, client, entries_allowed=True):
            self.flags.append(entries_allowed)
            return 'ok'

    class Auth:
        async def check_auth(self):
            return True, ''

    def kill_mgr(active):
        class _K:
            def __init__(self, pool):
                pass

            async def is_kill_switch_active(self):
                return active
        return _K

    async def _track(*a, **k):
        return None
    api._track_auth = _track
    api._build_broker_client = lambda acc: Auth()

    def account(entries):
        sub = {'subscription_id': 1, 'user_id': 1, 'broker_account_id': 7, 'strategy': 'T', 'symbol': 'BTCUSDT',
               'interval': '60', 'config_params': dict(rp.P)}
        return api.AccountPayload(id=7, broker='bybit', account_type='demo', api_key='k', api_secret='s',
                                  subscriptions=[sub], entries_allowed=entries)
    for label, entries, kill, exp in (('cuenta activa', True, False, [True]),
                                      ('cuenta pausada', False, False, [False]),
                                      ('kill switch', True, True, [False])):
        api.RiskManager = kill_mgr(kill)
        tr = Tr()
        _, res = await api._process_account(tr, account(entries))
        check(f'orquestación {label}: evalúa señales con entries_allowed={exp[0]}', tr.flags == exp, (tr.flags, res))


if __name__ == '__main__':
    asyncio.run(main())

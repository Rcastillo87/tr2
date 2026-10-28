"""
Límites de riesgo por cuenta (pérdida del mes y trades abiertos), sin DB ni Bybit reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/risk_limits_test.py
"""
import asyncio
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (fakes compartidos; anula las esperas)
import trading.real_trader as rt_mod  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def events(s):
    return [(a[2], json.loads(a[3])) for sql, a in s['exec'] if 'INSERT INTO broker_events' in sql]


MONTH, SINCE = RealTrader._month_start()


class RiskConn(rp.FakeConn):
    async def fetchrow(self, sql, *a):
        if 'FROM broker_accounts' in sql:
            return self.s.get('acc')
        return await super().fetchrow(sql, *a)

    async def fetchval(self, sql, *a):
        if 'month_start_at FROM broker_accounts' in sql:
            return self.s.get('month_at')
        if 'count(*) FROM real_trades' in sql:
            self.s['count_q'] = sql
            return self.s.get('open', 0)
        if 'SUM(COALESCE(net_pnl' in sql:
            self.s['sum_args'] = a
            return self.s.get('pnl', 0)
        return await super().fetchval(sql, *a)

    async def execute(self, sql, *a):
        self.s['exec'].append((sql, a))
        if 'UPDATE broker_accounts SET month_start_balance' in sql:
            return self.s.get('update_result', 'UPDATE 1')
        return 'UPDATE 1'


class RiskPool(rp.FakePool):
    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return RiskConn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()


def acc(max_loss=5.0, max_open=3, base=1000.0, month=MONTH):
    return {'max_monthly_loss_pct': max_loss, 'max_open_trades': max_open, 'month_start_balance': base, 'month_start_at': month}


class EquityClient(rp.FakeClient):
    def __init__(self, equity=1234.5, **kw):
        super().__init__(**kw)
        self.equity, self.equity_calls = equity, 0

    async def get_equity(self):
        self.equity_calls += 1
        return self.equity


async def reason(s, account_id=7):
    rt_mod._MONTHLY_NOTIFIED.clear() if s.pop('clear', False) else None
    return await RealTrader(RiskPool(s)).entry_limit_reason(account_id)


async def main():
    # Mes en Bogotá
    d, utc = RealTrader._month_start(datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc))   # 31-oct 22:00 en Bogotá
    check('mes en hora de Bogotá (1-nov 03:00 UTC aún es octubre)', d == date(2026, 10, 1) and utc == datetime(2026, 10, 1, 5, 0), (d, utc))
    d, utc = RealTrader._month_start(datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc))
    check('el mes empieza a las 00:00 de Bogotá = 05:00 UTC', d == date(2026, 11, 1) and utc == datetime(2026, 11, 1, 5, 0), (d, utc))

    # L1. Todo por debajo de los máximos
    s = {'exec': [], 'acc': acc(), 'open': 1, 'pnl': -20.0, 'clear': True}
    check('L1: por debajo de los máximos -> puede abrir', await reason(s) is None)
    check('L1: suma desde el inicio del mes (UTC)', s.get('sum_args', (None, None))[1] == SINCE, s.get('sum_args'))
    check('L1: cuenta pending_open + open + pending_close', "'pending_open', 'open', 'pending_close'" in s.get('count_q', ''))

    # L2. Pérdida del mes = máximo (-50 de 1000 = -5 %) -> bloquea y avisa una sola vez
    s = {'exec': [], 'acc': acc(), 'open': 0, 'pnl': -50.0, 'clear': True}
    r = await reason(s)
    ev = events(s)
    check('L2: pérdida del mes en el máximo -> bloquea', r is not None and 'pérdida del mes' in r, r)
    check('L2: aviso monthly_limit_reached con % y máximo',
          [e[0] for e in ev] == ['monthly_limit_reached'] and ev[0][1] == {'pct': -5.0, 'limit': 5.0}, ev)
    s2 = {'exec': [], 'acc': acc(), 'open': 0, 'pnl': -80.0}
    r2 = await reason(s2)
    check('L2: siguiente intento en el mismo mes -> bloquea sin repetir aviso', r2 is not None and not events(s2), events(s2))

    # L3. Ganancias y pérdidas se compensan (neto): -40 de 1000 = -4 % < 5 %
    s = {'exec': [], 'acc': acc(), 'open': 0, 'pnl': -40.0, 'clear': True}
    check('L3: neto del mes -4 % con máximo 5 % -> puede abrir', await reason(s) is None)

    # L4. Máximo de trades abiertos
    s = {'exec': [], 'acc': acc(max_open=3), 'open': 3, 'pnl': 10.0, 'clear': True}
    r = await reason(s)
    check('L4: 3 de 3 trades abiertos -> bloquea, sin aviso', r is not None and 'trades abiertos (3/3)' in r and not events(s), r)

    # L5. Sin saldo inicial del mes (aún no tomado) -> no evalúa el mensual, sí los abiertos
    s = {'exec': [], 'acc': acc(base=None, month=None), 'open': 0, 'pnl': -999.0, 'clear': True}
    check('L5: sin saldo inicial -> no bloquea por el mensual', await reason(s) is None and 'sum_args' not in s)
    s = {'exec': [], 'acc': acc(month=date(2026, 1, 1)), 'open': 0, 'pnl': -999.0, 'clear': True}
    check('L5: saldo inicial de otro mes -> no se usa', await reason(s) is None and 'sum_args' not in s)

    # L6. Límite editado por el dueño (10 %)
    s = {'exec': [], 'acc': acc(max_loss=10.0), 'open': 0, 'pnl': -60.0, 'clear': True}
    check('L6: máximo 10 % y pérdida 6 % -> puede abrir', await reason(s) is None)

    # B1. Saldo inicial del mes: se toma una vez por mes
    s = {'exec': [], 'month_at': date(2026, 9, 1)}
    c = EquityClient(equity=1234.5)
    await RealTrader(RiskPool(s)).ensure_month_baseline(7, c)
    upd = [a for sql, a in s['exec'] if 'month_start_balance' in sql]
    check('B1: mes nuevo -> guarda el patrimonio como saldo inicial', upd and upd[0][0] == 1234.5 and upd[0][1] == MONTH, upd)
    check('B1: cambio de mes -> aviso monthly_limit_reset', [e[0] for e in events(s)] == ['monthly_limit_reset'], events(s))

    s = {'exec': [], 'month_at': MONTH}
    c = EquityClient()
    await RealTrader(RiskPool(s)).ensure_month_baseline(7, c)
    check('B2: mismo mes -> no consulta Bybit ni escribe', c.equity_calls == 0 and not s['exec'], (c.equity_calls, s['exec']))

    s = {'exec': [], 'month_at': None}
    c = EquityClient()
    await RealTrader(RiskPool(s)).ensure_month_baseline(7, c)
    check('B3: cuenta recién conectada -> guarda saldo, sin aviso de reinicio',
          any('month_start_balance' in sql for sql, _ in s['exec']) and not events(s), events(s))

    s = {'exec': [], 'month_at': None}
    await RealTrader(RiskPool(s)).ensure_month_baseline(7, EquityClient(equity=None))
    check('B4: Bybit sin patrimonio -> no escribe (reintenta el próximo ciclo)', not s['exec'])

    # S1. check_new_signals respeta el límite antes de abrir
    code = "class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 1\n        return df\n"
    params = {**rp.P, 'strategy_code': code}
    strat = rt_mod.build_strategy({**params, 'symbol': 'BTCUSDT', 'interval': '60'})
    s = {'exec': [], 'acc': acc(max_open=1), 'open': 1, 'pnl': 0.0, 'clear': True}
    tr = RealTrader(RiskPool(s))

    async def _no_open(*a):
        return False

    async def _bars(symbol, interval, broker=None):
        return rp.bars()
    opened = []

    async def _open(*a, **k):
        opened.append(1)
        return True
    tr.has_open_trade, tr.get_bars, tr.open_trade = _no_open, _bars, _open
    rt_mod._MONTHLY_NOTIFIED.clear()
    sub = {'symbol': 'BTCUSDT', 'interval': '60', 'broker_account_id': 7, 'subscription_id': 1, 'strategy': 'T'}
    msg = await tr.check_new_signals(sub, strat, rp.FakeClient())
    check('S1: señal con el límite alcanzado -> no abre y lo explica', 'límite de riesgo' in msg and not opened, msg)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

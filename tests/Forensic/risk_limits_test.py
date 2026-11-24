"""
Límites de riesgo por cuenta (pérdida del mes y trades abiertos), sin DB ni Bybit reales.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/risk_limits_test.py
"""
import asyncio
from pathlib import Path
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
        if 'SELECT loss_paused_until FROM broker_accounts' in sql:
            return self.s.get('paused_until')
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
        if 'SET loss_paused_until' in sql:
            return self.s.get('pause_update', 'UPDATE 1')
        if 'SET loss_period_start' in sql:
            return self.s.get('resume_update', 'UPDATE 1')
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


def acc(max_loss=5.0, max_open=3, base=1000.0, month=MONTH, loss_on=True, open_on=True, pause_days=None,
        paused_until=None, period_start=None, period_balance=None):
    # D-66 (p111): columnas nuevas con sus valores por defecto de la base (límites activos, sin pausa ni período)
    return {'max_monthly_loss_pct': max_loss, 'max_open_trades': max_open, 'month_start_balance': base, 'month_start_at': month,
            'monthly_loss_enabled': loss_on, 'open_trades_limit_enabled': open_on, 'loss_pause_days': pause_days,
            'loss_paused_until': paused_until, 'loss_period_start': period_start, 'loss_period_balance': period_balance}


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

    # L5. C5-18 / D-51 (p96): sin saldo inicial del mes el límite mensual no se puede aplicar -> no abre
    #     (antes dejaba abrir sin límite mensual hasta que Bybit diera el patrimonio)
    s = {'exec': [], 'acc': acc(base=None, month=None), 'open': 0, 'pnl': -999.0, 'clear': True}
    r = await reason(s)
    check('L5: sin saldo inicial del mes -> no abre y lo explica', r is not None and 'sin saldo inicial del mes' in r
          and 'sum_args' not in s, r)
    s = {'exec': [], 'acc': acc(month=date(2026, 1, 1)), 'open': 0, 'pnl': 0.0, 'clear': True}
    r = await reason(s)
    check('L5: saldo inicial de otro mes -> no se usa y no abre', r is not None and 'sin saldo inicial del mes' in r
          and 'sum_args' not in s, r)
    s = {'exec': [], 'acc': acc(base=0.0), 'open': 0, 'pnl': 0.0, 'clear': True}
    check('L5: saldo inicial en 0 (inválido) -> no abre', (await reason(s) or '').startswith('sin saldo inicial del mes'))
    s = {'exec': [], 'acc': acc(max_loss=0.0, base=None, month=None), 'open': 0, 'pnl': 0.0, 'clear': True}
    check('L7: sin límite mensual (0 %) -> no exige saldo inicial y puede abrir', await reason(s) is None)
    s = {'exec': [], 'acc': None, 'open': 0, 'pnl': 0.0, 'clear': True}
    r = await reason(s)
    check('L8: cuenta que no está en la base -> no abre (antes: podía)', r is not None and 'cuenta no encontrada' in r, r)
    wd = (Path(__file__).resolve().parents[2] / 'app' / 'Console' / 'Commands' / 'CollectorWatchdog.php').read_text(encoding='utf-8')
    check('L9: el vigilante avisa si una cuenta activa con límite mensual sigue sin saldo inicial pasados 10 min del día 1',
          "openIncident('real_month_baseline'" in wd and "resolveIncident('real_month_baseline'" in wd
          and "'real_baseline_grace_min'] ?? 10" in wd and "now('America/Bogota')->startOfMonth()" in wd)

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

    # ── D-66 (p111): pausa de N días al llegar al límite, conteo de cero al reanudar, «sin límite» ──
    from datetime import timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    os.environ.pop('RISK_LIMIT_OPTIONS_ENABLED', None)

    s = {'exec': [], 'acc': acc(pause_days=3), 'open': 0, 'pnl': -50.0, 'clear': True}
    r = await reason(s)
    upd = [a for sql, a in s['exec'] if 'SET loss_paused_until' in sql]
    ev = events(s)
    check('P1: llega al límite con pausa de 3 días -> no abre y lo explica', r is not None and 'pausa de 3 día(s) hasta el' in r, r)
    check('P1: guarda la pausa hasta ahora + 3 días (solo si no había otra) y borra el período',
          len(upd) == 1 and abs((upd[0][0] - now).total_seconds() - 3 * 86400) < 120 and upd[0][1] == 7
          and any('loss_paused_until IS NULL' in sql and 'loss_period_start = NULL' in sql for sql, _ in s['exec']), upd)
    check('P1: aviso monthly_limit_reached con los días y hasta cuándo',
          [e[0] for e in ev] == ['monthly_limit_reached'] and ev[0][1].get('pause_days') == 3 and ev[0][1].get('paused_until'), ev)
    s = {'exec': [], 'acc': acc(pause_days=3), 'open': 0, 'pnl': -50.0, 'clear': True, 'pause_update': 'UPDATE 0'}
    r = await reason(s)
    check('P2: otra corrida ya la pausó -> sigue sin abrir y sin aviso repetido', r is not None and 'pausa' in r and not events(s), events(s))
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=now + timedelta(days=1)), 'open': 0, 'pnl': 30.0, 'clear': True}
    r = await reason(s)
    check('P3: durante la pausa no abre aunque el resultado mejore', r is not None and r.startswith('pausa por pérdida máxima hasta el'), r)
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=now + timedelta(days=20), month=None, base=None), 'open': 0, 'pnl': 0.0, 'clear': True}
    r = await reason(s)
    check('P3b: la pausa se respeta aunque cambie el mes (sin saldo del mes nuevo igual dice pausa)',
          r is not None and r.startswith('pausa por pérdida máxima'), r)
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=now - timedelta(minutes=1)), 'open': 0, 'pnl': 0.0, 'clear': True}
    r = await reason(s)
    check('P4: terminó la pausa pero aún sin la base nueva -> no abre (espera el patrimonio)', r is not None and 'terminó la pausa' in r, r)
    start = now - timedelta(hours=1)
    if start <= SINCE:
        start = SINCE + timedelta(minutes=1)
    s = {'exec': [], 'acc': acc(pause_days=3, period_start=start, period_balance=2000.0), 'open': 0, 'pnl': -50.0, 'clear': True}
    r = await reason(s)
    check('P5: tras reanudar cuenta desde el inicio del período con su base (-50/2000 = -2,5 %) -> puede abrir',
          r is None and s.get('sum_args', (None, None))[1] == start, (r, s.get('sum_args')))
    s = {'exec': [], 'acc': acc(pause_days=3, period_start=start, period_balance=2000.0), 'open': 0, 'pnl': -100.0, 'clear': True}
    r = await reason(s)
    check('P5b: vuelve a perder el máximo desde el período -> otra pausa, y lo dice («pérdida desde el»)',
          r is not None and r.startswith('pérdida desde el') and 'pausa de 3 día(s)' in r, r)
    s = {'exec': [], 'acc': acc(pause_days=3, period_start=SINCE - timedelta(days=1), period_balance=2000.0), 'open': 0, 'pnl': -10.0, 'clear': True}
    await reason(s)
    check('P6: período del mes anterior -> en el mes nuevo cuenta desde el día 1 con el saldo del mes',
          s.get('sum_args', (None, None))[1] == SINCE, s.get('sum_args'))
    s = {'exec': [], 'acc': acc(loss_on=False, pause_days=3, base=None, month=None,
                                paused_until=now + timedelta(days=1)), 'open': 0, 'pnl': -900.0, 'clear': True}
    r = await reason(s)
    check('P7: pérdida «sin límite» -> abre aunque pierda, sin pedir saldo del mes y sin pausa', r is None and not s['exec'], r)
    s = {'exec': [], 'acc': acc(open_on=False), 'open': 12, 'pnl': 0.0, 'clear': True}
    check('P8: trades abiertos «sin límite» -> abre con 12 de 3', await reason(s) is None)
    s = {'exec': [], 'acc': acc(open_on=True), 'open': 3, 'pnl': 0.0, 'clear': True, 'acc_override': None}
    check('P8b: con el límite activo sigue bloqueando 3 de 3', 'trades abiertos (3/3)' in (await reason(s) or ''))
    os.environ['RISK_LIMIT_OPTIONS_ENABLED'] = 'false'
    s = {'exec': [], 'acc': acc(loss_on=False, open_on=False, pause_days=3), 'open': 0, 'pnl': -50.0, 'clear': True}
    r = await reason(s)
    check('P9: interruptor general apagado -> como antes: bloquea por pérdida del mes, sin pausa', r is not None
          and r.startswith('pérdida del mes') and 'pausa' not in r and not [1 for sql, _ in s['exec'] if 'loss_paused_until' in sql], r)
    s = {'exec': [], 'acc': acc(open_on=False), 'open': 3, 'pnl': 0.0, 'clear': True}
    check('P9b: interruptor apagado -> «sin límite» de trades no vale', 'trades abiertos (3/3)' in (await reason(s) or ''))
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=now - timedelta(minutes=5))}
    c = EquityClient(equity=1500.0)
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, c)
    check('P9c: interruptor apagado -> no reanuda ni consulta Bybit', c.equity_calls == 0 and not s['exec'])
    os.environ.pop('RISK_LIMIT_OPTIONS_ENABLED', None)

    until = now - timedelta(minutes=5)
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=until)}
    c = EquityClient(equity=1500.0)
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, c)
    upd = [a for sql, a in s['exec'] if 'SET loss_period_start' in sql]
    check('R1: terminó la pausa -> nueva base = patrimonio de ahora, desde ahora, y quita la pausa (solo esa pausa)',
          len(upd) == 1 and upd[0][1] == 1500.0 and abs((upd[0][0] - now).total_seconds()) < 120 and upd[0][2:] == (7, until)
          and any('loss_paused_until = NULL' in sql and 'AND loss_paused_until = $4' in sql for sql, _ in s['exec']), upd)
    check('R1: aviso loss_pause_ended', [e[0] for e in events(s)] == ['loss_pause_ended'], events(s))
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=until)}
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, EquityClient(equity=None))
    check('R2: sin patrimonio de Bybit -> no reanuda (próximo ciclo)', not s['exec'])
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=now + timedelta(hours=2))}
    c = EquityClient(equity=1500.0)
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, c)
    check('R3: pausa en curso -> ni consulta Bybit ni escribe', c.equity_calls == 0 and not s['exec'])
    s = {'exec': [], 'acc': acc(pause_days=3, paused_until=until), 'resume_update': 'UPDATE 0'}
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, EquityClient(equity=1500.0))
    check('R4: otra corrida ya reanudó -> sin aviso repetido', not events(s), events(s))
    s = {'exec': [], 'acc': acc(pause_days=3), 'open': 0, 'pnl': -50.0, 'clear': True}
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, EquityClient())
    check('R5: en el ciclo (sin esperar una señal) llega al límite -> la pausa empieza ya',
          any('SET loss_paused_until' in sql for sql, _ in s['exec']) and [e[0] for e in events(s)] == ['monthly_limit_reached'], events(s))
    s = {'exec': [], 'acc': acc(pause_days=None), 'open': 0, 'pnl': -50.0, 'clear': True}
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, EquityClient())
    check('R6: sin pausa configurada (hasta fin de mes) -> el ciclo no cambia nada (como antes)', not s['exec'])
    s = {'exec': [], 'acc': acc(loss_on=False, pause_days=3, paused_until=until)}
    c = EquityClient(equity=1500.0)
    await RealTrader(RiskPool(s)).ensure_loss_pause_end(7, c)
    check('R7: pérdida «sin límite» -> el ciclo no pausa ni reanuda', c.equity_calls == 0 and not s['exec'])
    s = {'exec': [], 'month_at': date(2026, 9, 1), 'paused_until': now + timedelta(days=2)}
    await RealTrader(RiskPool(s)).ensure_month_baseline(7, EquityClient(equity=1234.5))
    check('M1: cambio de mes durante una pausa -> guarda el saldo del mes pero NO avisa «vuelve a abrir»',
          any('month_start_balance' in sql for sql, _ in s['exec']) and not events(s), events(s))
    rp_src = (Path(__file__).resolve().parents[2] / 'python-engine' / 'api' / 'v1' / 'real_trading.py').read_text(encoding='utf-8')
    check('M2: cada ciclo de la cuenta revisa el fin de la pausa después del saldo del mes',
          rp_src.index('ensure_month_baseline(account.id, client)') < rp_src.index('ensure_loss_pause_end(account.id, client)'))
    check('L9b: el vigilante no exige saldo del mes a cuentas con la pérdida «sin límite»',
          "->where('monthly_loss_enabled', true)" in wd)

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

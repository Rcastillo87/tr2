"""
Hueco dentro del 1m en Paper (BP-03): el monitor no salta minutos faltantes. Se detiene antes del hueco y espera la
reparación; si el hueco tiene más de PAPER_MINUTE_GAP_WAIT_HOURS (26 h), lo evalúa con la vela completa del intervalo
operado y SL primero (como el backtest sin 1m). Sin base de datos: pool en memoria.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/minute_gap_test.py
Antes del parche: FALLAN los casos de hueco (Paper salta el hueco en silencio).
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/

import numpy as np  # noqa: E402

import trading.paper_trader as pt  # noqa: E402
from trading.paper_trader import PaperTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


UTC = timezone.utc
CLOCK = [datetime(2026, 3, 2, 12, 0, tzinfo=UTC)]


class FakeDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return CLOCK[0] if tz is not None else CLOCK[0].replace(tzinfo=None)


async def _broker(*a, **k):
    return 'bybit'


async def _price(symbol):
    return 100.0


async def _funding(pool, symbol, start, end, client=None, now=None):
    from collectors.funding_collector import FundingData
    return FundingData(symbol, np.array([], dtype='datetime64[ns]'), np.array([], dtype=float), start, end), []


pt.datetime, pt.resolve_live_broker, pt.get_current_price, pt.load_funding = FakeDT, _broker, _price, _funding

LOGS: list = []


class _Cap(logging.Handler):
    def emit(self, record):
        LOGS.append((record.levelname, record.getMessage()))


logging.getLogger(pt.__name__).addHandler(_Cap())

CODE = "class T(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 0\n        return df\n"
P = dict(symbol='BTCUSDT', interval='60', sl_pct=1.0, tp_pct=2.0, be_pct=1.5, max_duration=0, regime_filter=False,
         commission_pct=0.0, slippage_pct=0.0, strategy_code=CODE)
ENTRY = datetime(2026, 3, 2, 10, 0)    # sin tz, como la base


class Conn:
    def __init__(self, s):
        self.s = s

    async def fetch(self, sql, *a):
        if "interval = '1'" in sql:                             # (symbol, desde, hasta, broker)
            return [m for m in self.s['minutes'] if a[1] < m['time'] <= a[2]]
        if 'FROM ohlcv_data' in sql and 'interval = $3' in sql:  # velas de respaldo (broker, symbol, interval, desde, hasta)
            self.s['backup_queries'] += 1
            return [c for c in self.s['candles'] if a[3] < c['time'] < a[4]]
        if 'FROM paper_trades' in sql:
            return [dict(self.s['trade'])] if self.s['trade']['status'] == 'open' else []
        return []

    async def fetchrow(self, sql, *a):
        return None

    async def fetchval(self, sql, *a):                          # última vela de 1m de la fuente (N-02)
        self.s['tail_queries'] = self.s.get('tail_queries', 0) + 1
        return max((m['time'] for m in self.s['minutes']), default=None)

    async def execute(self, sql, *a):
        t = self.s['trade']
        if 'last_monitored_at = $6' in sql:
            t.update(sl=a[0], be_activated=a[1], trailing_applied=a[2], last_monitored_at=a[5])
        elif "status = 'closed'" in sql:
            t.update(status='closed', exit_price=a[0], exit_reason=a[3], exit_time=a[4])


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


def mm(t, low=99.6, high=100.4, close=100.0):
    return {'time': t.replace(tzinfo=UTC) if t.tzinfo is None else t, 'open': 100.0, 'high': high, 'low': low,
            'close': close}


def minutes(start, end, skip=(), touch=None):
    """1m de [start, end) sin los minutos de `skip`; `touch` = {minuto: low} para tocar el SL."""
    out, t = [], start
    while t < end:
        if t not in skip:
            out.append(mm(t, low=(touch or {}).get(t, 99.6)))
        t += timedelta(minutes=1)
    return out


def hour(t, low=99.5, high=100.5):
    return {'time': t.replace(tzinfo=UTC), 'open': 100.0, 'high': high, 'low': low, 'close': 100.0}


def store(mins, candles=()):
    trade = {'id': 7, 'strategy': 'T', 'paper_strategy_config_id': 1, 'config_snapshot': json.dumps(P),
             'symbol': 'BTCUSDT', 'interval': '60', 'side': 'long', 'entry_price': 100.0, 'sl': 99.0, 'tp': 102.0,
             'tp2': None, 'tp3': None, 'tp4': None, 'be_level': 101.5, 'be_activated': False,
             'trailing_applied': False, 'vol_widened': False, 'size': 1.0, 'entry_time': ENTRY, 'regime': 'RANGING',
             'max_profit_pct': 0, 'max_loss_pct': 0, 'last_monitored_at': None, 'status': 'open'}
    return {'trade': trade, 'minutes': list(mins), 'candles': list(candles), 'backup_queries': 0}


async def monitor(s, now):
    CLOCK[0] = now
    LOGS.clear()
    return await PaperTrader(Pool(s), {}, {}).monitor_open_trades()


def errors():
    return [m for lvl, m in LOGS if lvl == 'ERROR' and 'faltan velas de 1m' in m]


async def main():
    # 1. Regla pura
    t0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    seq = [mm(t0 + timedelta(minutes=k)) for k in (1, 2, 3, 6, 7)]
    if not hasattr(pt, 'split_at_minute_gap'):   # código anterior al parche: se marca y siguen los casos del monitor
        check('split_at_minute_gap existe', False, 'no existe (código anterior)')
        pt.split_at_minute_gap = lambda bars, after: (bars, None)
    run, gap = pt.split_at_minute_gap(seq, t0)
    check('split: corta en el primer hueco y lo informa (10:04–10:06)',
          len(run) == 3 and gap == (t0 + timedelta(minutes=4), t0 + timedelta(minutes=6)), (len(run), gap))
    run, gap = pt.split_at_minute_gap(seq[:3], t0)
    check('split: sin hueco (el final sin velas no es hueco)', len(run) == 3 and gap is None, gap)
    run, gap = pt.split_at_minute_gap(seq, t0 + timedelta(seconds=40))   # punto de control con segundos (entrada)
    check('split: punto de control con segundos (entrada a las 10:00:40)', len(run) == 3, len(run))
    run, gap = pt.split_at_minute_gap([mm(t0 + timedelta(minutes=2))], t0)
    check('split: falta el primer minuto -> hueco desde el inicio', run == [] and gap[0] == t0 + timedelta(minutes=1), gap)

    # 2. Hueco reciente: no se salta; el punto de control queda antes del hueco y queda ERROR en el log
    now = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    gap_mins = {datetime(2026, 3, 2, 10, 40, tzinfo=UTC) + timedelta(minutes=k) for k in range(5)}   # 10:40–10:44
    s = store(minutes(t0 + timedelta(minutes=1), now - timedelta(minutes=1), skip=gap_mins))
    await monitor(s, now)
    chk = s['trade']['last_monitored_at']
    check('hueco reciente: el punto de control queda en 10:39 (no lo salta)',
          s['trade']['status'] == 'open' and chk == datetime(2026, 3, 2, 10, 39), chk)
    check('hueco reciente: ERROR en el log con el tramo faltante',
          len(errors()) == 1 and '10:40–10:45' in errors()[0], errors())
    check('hueco reciente: no se consultan velas de respaldo', s['backup_queries'] == 0, s['backup_queries'])

    # 3. La reparación llena el hueco y en él estaba el SL: se cierra en ese minuto
    s['minutes'] = minutes(t0 + timedelta(minutes=1), now + timedelta(minutes=10),
                           touch={datetime(2026, 3, 2, 10, 42, tzinfo=UTC): 98.9})
    await monitor(s, now + timedelta(minutes=5))
    tr = s['trade']
    check('hueco reparado con el SL adentro: cierra por SL en 10:42 (antes se perdía)',
          tr['status'] == 'closed' and tr['exit_reason'] == 'stop_loss'
          and tr.get('exit_time') == datetime(2026, 3, 2, 10, 42), (tr['status'], tr.get('exit_reason'), tr.get('exit_time')))

    # 4. Hueco permanente (> 26 h): vela H1 completa con SL primero
    late = datetime(2026, 3, 3, 13, 0, tzinfo=UTC)          # 26 h 20 min después del hueco
    base = minutes(t0 + timedelta(minutes=1), late - timedelta(minutes=1), skip=gap_mins)
    s = store(base, candles=[hour(datetime(2026, 3, 2, 10, 0), low=98.5)])
    await monitor(s, late)
    tr = s['trade']
    check('hueco permanente: la vela 10:00 toca el SL -> stop_loss al precio del SL',
          tr['status'] == 'closed' and tr['exit_reason'] == 'stop_loss' and abs(tr['exit_price'] - 99.0) < 1e-9,
          (tr['status'], tr.get('exit_reason'), tr.get('exit_price')))
    check('hueco permanente: exit_time = inicio de la vela (desde la entrada), como el backtest sin 1m',
          tr.get('exit_time') == datetime(2026, 3, 2, 10, 0), tr.get('exit_time'))
    check('hueco permanente: ERROR explica el respaldo con vela completa',
          any('completa(s) de 60 y SL primero' in m for m in errors()), errors())

    s = store(base, candles=[hour(datetime(2026, 3, 2, 10, 0))])        # la vela no toca nada
    await monitor(s, late)
    chk = s['trade']['last_monitored_at']
    check('hueco permanente sin toque: sigue con los minutos posteriores (punto de control al final)',
          s['trade']['status'] == 'open' and chk == datetime(2026, 3, 3, 12, 58), chk)

    after = {datetime(2026, 3, 2, 10, 50, tzinfo=UTC): 98.0}            # SL en un minuto posterior, dentro de la vela
    s = store(minutes(t0 + timedelta(minutes=1), late - timedelta(minutes=1), skip=gap_mins, touch=after),
              candles=[hour(datetime(2026, 3, 2, 10, 0), low=99.5)])       # vela sin el toque (imposible en datos reales)
    await monitor(s, late)
    check('hueco permanente: los minutos ya cubiertos por la vela no se evalúan dos veces',
          s['trade']['status'] == 'open', s['trade']['status'])

    s = store(base, candles=[])                                         # tampoco hay vela de respaldo
    await monitor(s, late)
    check('hueco permanente sin vela de respaldo: sigue esperando (no salta), con ERROR',
          s['trade']['status'] == 'open' and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 10, 39)
          and any('sin velas 60 de respaldo' in m for m in errors()), (s['trade']['last_monitored_at'], errors()))

    gap2 = gap_mins | {datetime(2026, 3, 2, 11, 10, tzinfo=UTC)}        # dos huecos, en dos velas distintas
    s = store(minutes(t0 + timedelta(minutes=1), late - timedelta(minutes=1), skip=gap2),
              candles=[hour(datetime(2026, 3, 2, 10, 0)), hour(datetime(2026, 3, 2, 11, 0), low=98.7)])
    await monitor(s, late)
    check('dos huecos: el segundo todavía no cumple 26 h -> se cubre el primero y espera antes del segundo',
          s['trade']['status'] == 'open' and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 11, 9)
          and any('evaluados hasta 2026-03-02 11:09' in m for m in errors()), (s['trade']['last_monitored_at'], errors()))
    await monitor(s, late + timedelta(hours=1))
    check('dos huecos permanentes: el segundo (vela 11:00) también se cubre y cierra por SL',
          s['trade']['status'] == 'closed' and s['trade'].get('exit_time') == datetime(2026, 3, 2, 11, 0),
          (s['trade']['status'], s['trade'].get('exit_time')))

    # 5. Sin hueco: el caso normal no cambia (no consulta respaldo, no deja ERROR)
    s = store(minutes(t0 + timedelta(minutes=1), now - timedelta(minutes=1)))
    await monitor(s, now)
    check('sin hueco: punto de control en el último minuto cerrado, sin ERROR ni consultas extra',
          s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 11, 58) and not errors() and s['backup_queries'] == 0,
          (s['trade']['last_monitored_at'], errors(), s['backup_queries']))

    # 6. El plazo viene de la configuración (.env)
    wait = getattr(pt, 'MINUTE_GAP_WAIT', None)
    check('plazo por defecto 26 h (PAPER_MINUTE_GAP_WAIT_HOURS)', wait == timedelta(hours=26), wait)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

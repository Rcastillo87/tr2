"""
C-04: ninguna vela inválida llega a ohlcv_data. Barrera única en OhlcvCollector.save_bars (el único punto de escritura de
la descarga automática, la carga inicial, la reparación, la auditoría y la importación) y la misma regla en el backfill.
Sin base de datos: pool simulado que registra lo que se escribiría.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_ingest_test.py
"""
import asyncio
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import cli.backfill_bybit as bf  # noqa: E402
import collectors.ohlcv_collector as oc  # noqa: E402

fails = 0
T = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Conn:
    def __init__(self, store):
        self.store = store

    async def execute(self, sql, times, broker, symbol, interval, o, h, lo, c, v):
        self.store.extend(zip(times, o, h, lo, c, v))
        return f'INSERT 0 {len(times)}'


class Pool:
    def __init__(self):
        self.written = []

    def acquire(self):
        store = self.written

        class _C:
            async def __aenter__(self):
                return Conn(store)

            async def __aexit__(self, *e):
                return False
        return _C()


def bar(t=T, interval='60', **kw):
    b = dict(time=t, symbol='BTCUSDT', interval=interval, open=100.0, high=101.0, low=99.0, close=100.5, volume=5.0)
    b.update(kw)
    return b


def collector():
    c = oc.OhlcvCollector.__new__(oc.OhlcvCollector)
    c.pool = Pool()
    return c


async def main():
    bad_cases = [
        ('low > high', bar(low=102.0, high=101.0)),
        ('high por debajo del close', bar(high=100.0, close=100.5)),
        ('low por encima del open', bar(low=100.2, open=100.0)),
        ('volumen negativo', bar(volume=-1.0)),
        ('precio 0', bar(low=0.0)),
        ('precio negativo', bar(open=-5.0, low=-6.0)),
        ('NaN', bar(close=math.nan)),
        ('infinito', bar(high=math.inf)),
        ('hora fuera del horario (1h a las :30)', bar(t=T + timedelta(minutes=30))),
        ('hora sin zona horaria', bar(t=T.replace(tzinfo=None))),
        ('campo faltante', {k: v for k, v in bar().items() if k != 'volume'}),
        ('campo no numérico', bar(open='abc')),
    ]
    for label, b in bad_cases:
        c = collector()
        n = await c.save_bars([b])
        check(f'I {label}: no se guarda', n == 0 and not c.pool.written and c.last_rejected == 1, (n, oc.bar_problem(b)))

    good_cases = [
        ('vela normal', bar()),
        ('volumen 0 (sin operaciones)', bar(volume=0.0)),
        ('precio plano (o=h=l=c)', bar(open=100.0, high=100.0, low=100.0, close=100.0)),
        ('vela diaria a las 00:00 UTC', bar(t=T.replace(hour=0), interval='D')),
        ('vela de 1m a cualquier minuto en punto', bar(t=T + timedelta(minutes=7), interval='1')),
        ('vela de 4h a las 08:00', bar(t=T.replace(hour=8), interval='240')),
    ]
    for label, b in good_cases:
        c = collector()
        n = await c.save_bars([b])
        check(f'V {label}: se guarda', n == 1 and len(c.pool.written) == 1 and c.last_rejected == 0, (n, oc.bar_problem(b)))

    c = collector()
    mixed = [bar(t=T - timedelta(hours=2)), bar(t=T - timedelta(hours=1), low=500.0), bar(t=T)]
    n = await c.save_bars(mixed)
    check('M1 tanda mezclada: guarda solo las válidas y cuenta las rechazadas',
          n == 2 and c.last_rejected == 1 and [w[0] for w in c.pool.written] == [T - timedelta(hours=2), T], (n, c.last_rejected))
    check('M2 4h a las 09:00 (fuera de horario): rechazada', oc.bar_problem(bar(interval='240')) is not None)

    # Caminos que escriben: la descarga automática pasa por la barrera
    c = collector()

    async def fake_fetch(*a, **k):
        return [bar(t=T - timedelta(hours=1)), bar(t=T, volume=-3.0)]

    async def fake_last(*a, **k):
        return T - timedelta(hours=3)
    c.fetch_from_bybit, c.get_last_timestamp = fake_fetch, fake_last
    try:
        saved = await c.update('BTCUSDT', '60', 'bybit')
        check('P1 descarga automática (update): la vela inválida no llega a la base',
              len(c.pool.written) == 1 and c.pool.written[0][0] == T - timedelta(hours=1), (saved, c.pool.written))
    except Exception as e:  # noqa: BLE001
        check('P1 descarga automática (update): la vela inválida no llega a la base', False, repr(e))

    check('P2 el backfill usa la misma regla (no una copia propia)', bf.valid_bar is oc.valid_bar)
    check('P3 la regla del backfill ahora rechaza NaN y fuera de horario (antes no)',
          not bf.valid_bar(bar(close=math.nan)) and not bf.valid_bar(bar(t=T + timedelta(minutes=30))))

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

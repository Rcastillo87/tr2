"""
N-11 (decisión del dueño 10-nov): el collector solo borra velas en la recarga y en la invalidación explícitas, por
una sola puerta (collectors/deletion_log.delete_bars), en UNA transacción con su registro en ohlcv_deletions (con las
velas borradas hasta 50.000). Una cancelación a mitad del borrado no deja nada borrado ni un mensaje falso.
Sin base ni red: la base en memoria de collector_reload_test (con rollback real) y Bybit simulado.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_deletion_test.py
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import collector_reload_test as cr  # noqa: E402  (base en memoria + Bybit simulado)
import api.v1.collector as api  # noqa: E402

fails = 0
ROOT = Path(__file__).resolve().parents[2]


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def add_extras(w, n):
    """n velas que Bybit no tiene (a los 30 min de cada hora): sobrantes confirmados en la recarga."""
    times = sorted(w.truth)[100:100 + n]
    extras = [t + timedelta(minutes=30) for t in times]
    for t in extras:
        w.local[t] = dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=3.0)
    w.min_len = len(w.local)
    return extras


async def main():
    # D1. Recarga con 3 sobrantes: se borran y queda UN registro con las 3 velas
    w = cr.World()
    extras = add_extras(w, 3)
    r = await cr.reverify(w)
    check('D1: recarga completa borra los 3 sobrantes', r['complete'] and r['extra_deleted'] == 3
          and not any(t in w.local for t in extras), (r['complete'], r['extra_deleted']))
    rec = w.deletions[0] if w.deletions else None
    check("D1: un registro en ohlcv_deletions con origen 'reload' y cantidad 3",
          len(w.deletions) == 1 and rec[3] == 'reload' and rec[5] == 3, rec[:6] if rec else None)
    bars = json.loads(rec[8]) if rec and rec[8] else []
    check('D1: el registro guarda las 3 velas borradas (para restaurarlas) y su rango',
          rec is not None and rec[9] is True and [b['t'] for b in bars] == [t.isoformat() for t in extras]
          and bars[0]['h'] == '2.0' and rec[6] == extras[0] and rec[7] == extras[-1], (bars[:1], rec[6:8] if rec else None))

    # D2. Corte a mitad del borrado (1.500 sobrantes = 2 lotes; se corta en el 2.º): nada queda borrado ni registrado
    w = cr.World()
    extras = add_extras(w, 1500)
    w.fail_delete_after = 1200
    cancelled = False
    try:
        await cr.reverify(w)
    except asyncio.CancelledError:
        cancelled = True
    left = sum(1 for t in extras if t in w.local)
    check('D2: cancelación en el 2.º lote -> se revierte TODO (los 1.500 sobrantes siguen; antes quedaban 1.000 borrados)',
          cancelled and left == 1500, (cancelled, left))
    check('D2: sin registro de un borrado que no ocurrió', w.deletions == [], len(w.deletions))

    # D3. Mensaje de la recarga cortada: dice lo que de verdad pasó
    st = {'progress': {'extra_deleted': 0}}
    check("D3: cortada antes de borrar -> «no se eliminó nada»", api._reload_deleted_note(st) == 'no se eliminó nada'
          if hasattr(api, '_reload_deleted_note') else False)
    st = {'progress': {'extra_deleted': 3}}
    note = api._reload_deleted_note(st) if hasattr(api, '_reload_deleted_note') else ''
    check('D3: cortada después de borrar -> informa los 3 eliminados y dónde quedaron', '3' in note and 'ohlcv_deletions' in note, note)

    # D4. Invalidación por rango: transacción, conteo, DELETE … RETURNING y registro 'invalidate'
    from collectors import deletion_log as dl

    class Rec:
        def __init__(self, count):
            self.sql, self.count, self.tx = [], count, 0

        def transaction(self):
            me = self

            class _T:
                async def __aenter__(self_):
                    me.tx += 1

                async def __aexit__(self_, *e):
                    return False
            return _T()

        async def fetchval(self, sql, *a):
            self.sql.append(('fetchval', sql, a))
            return self.count

        async def fetch(self, sql, *a):
            self.sql.append(('fetch', sql, a))
            t = datetime(2026, 3, 1, 5, tzinfo=timezone.utc)
            return [dict(time=t, open=1, high=2, low=0.5, close=1.5, volume=3)]

        async def fetchrow(self, sql, *a):
            self.sql.append(('fetchrow', sql, a))
            return dict(lo=datetime(2026, 3, 1, tzinfo=timezone.utc), hi=datetime(2026, 3, 9, tzinfo=timezone.utc))

        async def execute(self, sql, *a):
            self.sql.append(('execute', sql, a))
            return f'DELETE {self.count}' if sql.lstrip().startswith('DELETE') else 'INSERT 0 1'

    lo, hi = datetime(2026, 3, 1, 5, tzinfo=timezone.utc), datetime(2026, 3, 9, tzinfo=timezone.utc)
    c = Rec(1)
    n = await dl.delete_bars(c, broker='bybit', symbol='BTCUSDT', interval='60', source='invalidate',
                             reason='prueba', start=lo, end=hi)
    kinds = [k for k, _, _ in c.sql]
    dele = [s for k, s, _ in c.sql if s.lstrip().startswith('DELETE')]
    ins = [a for k, s, a in c.sql if 'INSERT INTO ohlcv_deletions' in s]
    check('D4: invalidación en una transacción: cuenta, lee las velas, DELETE simple (sin RETURNING) y registra',
          c.tx == 1 and kinds == ['fetchval', 'fetch', 'execute', 'execute'] and n == 1 and dele
          and 'RETURNING' not in dele[0] and 'time >= $4' in dele[0] and 'time <= $5' in dele[0], (c.tx, kinds, n))
    check("D4: registro con origen 'invalidate', motivo y las velas", bool(ins) and ins[0][3] == 'invalidate'
          and ins[0][4] == 'prueba' and ins[0][9] is True and json.loads(ins[0][8])[0]['h'] == '2', ins[0][3:6] if ins else None)

    # D5. Más de 50.000 velas: se borra igual pero el registro guarda solo el resumen
    c = Rec(60_000)
    n = await dl.delete_bars(c, broker='bybit', symbol='BTCUSDT', interval='1', source='invalidate', reason='grande')
    ins = [a for k, s, a in c.sql if 'INSERT INTO ohlcv_deletions' in s]
    check('D5: 60.000 velas -> borrado con resumen (min/max), sin guardar las velas',
          n == 60_000 and not any(k == 'fetch' for k, _, _ in c.sql) and ins and ins[0][8] is None and ins[0][9] is False
          and ins[0][6] == datetime(2026, 3, 1, tzinfo=timezone.utc), (n, ins[0][5:10] if ins else None))

    # D6. Solo los orígenes permitidos; lista vacía no toca la base
    try:
        await dl.delete_bars(Rec(0), broker='bybit', symbol='X', interval='1', source='limpieza', reason='x', times=[])
        bad = False
    except ValueError:
        bad = True
    check("D6: origen distinto de reload/invalidate -> ValueError", bad)
    c = Rec(0)
    check('D6: sin tiempos -> 0 y sin consultas', await dl.delete_bars(c, broker='bybit', symbol='X', interval='1',
                                                                       source='reload', reason='x', times=[]) == 0
          and c.sql == [])

    # D7. Una sola puerta: ningún otro módulo del motor borra velas
    others = []
    for f in (ROOT / 'python-engine').rglob('*.py'):
        if 'venv' in f.parts or f.name == 'deletion_log.py':
            continue
        if re.search(r'DELETE\s+FROM\s+ohlcv_data', f.read_text(encoding='utf-8', errors='ignore')):
            others.append(str(f.relative_to(ROOT)))
    check('D7: ningún otro archivo del motor tiene «DELETE FROM ohlcv_data»', others == [], others)
    up = ROOT / 'database' / 'sql-migrations' / '2026_11_10_01_ohlcv_deletions.up.sql'
    check('D7: migración de ohlcv_deletions (idempotente, con CHECK de origen) y su .down',
          up.exists() and 'IF NOT EXISTS' in up.read_text() and "source IN ('reload', 'invalidate')" in up.read_text()
          and up.with_name('2026_11_10_01_ohlcv_deletions.down.sql').exists())

    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return fails


if __name__ == '__main__':
    sys.exit(1 if asyncio.run(main()) else 0)

"""
R-22 (19-nov): el monitor de Paper evaluaba el minuto de 1m recién cerrado aunque el collector todavía no le hubiera
guardado sus valores finales (lo guarda en formación y lo completa en la pasada siguiente, junto con el minuto nuevo).
El punto de control lo dejaba atrás: el toque de los segundos que faltaban no se veía nunca. Servidor, 05→18-nov: 7 de
16 cierres por SL/TP fijos salieron 1–27 min tarde y un TP 118 min tarde hizo perder una operación (SOL 10-nov).
Regla nueva (la de D-39 en el 1m): un minuto se evalúa cuando la base ya tiene el siguiente.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/minute_final_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minute_gap_test as mg  # noqa: E402  (base y motor simulados; sus casos no corren al importarlo)
import trading.paper_trader as pt  # noqa: E402

UTC = timezone.utc
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def at(h, m, s=0):
    return datetime(2026, 3, 2, h, m, s, tzinfo=UTC)


def naive(h, m):
    return datetime(2026, 3, 2, h, m)


def feed(until, low=None):
    """Minutos 10:01..until (inclusive) sin toque; `low` = {minuto: low} para tocar el SL (99.0, long)."""
    return mg.minutes(at(10, 1), until + timedelta(minutes=1), touch=low or {})


async def main():
    # 0. Regla pura
    has = hasattr(pt, 'final_minutes')
    fm = pt.final_minutes if has else (lambda bars, now: bars)
    check('final_minutes existe', has, '' if has else 'no existe (código anterior)')
    bars = feed(at(10, 5))
    check('el último minuto (sin siguiente) queda para el próximo ciclo', [b['time'] for b in fm(bars, at(10, 6, 10))]
          == [b['time'] for b in bars[:-1]], len(fm(bars, at(10, 6, 10))))
    check('sin minutos: nada', fm([], at(10, 6)) == [])
    old = feed(at(10, 5))
    check('serie detenida más de 26 h: el último ya es final (N-02 sin cambios)',
          len(fm(old, at(10, 5) + pt.MINUTE_GAP_WAIT)) == len(old))

    # 1. El caso del servidor: el minuto del toque llega incompleto y nunca se vuelve a mirar
    #    11:00:10 → la base tiene 10:59 a medias (sin el toque) y nada más; 11:01:10 → 10:59 final (toca) y 11:00 en formación
    s = mg.store(feed(at(10, 59)))
    await mg.monitor(s, at(11, 0, 10))
    chk1 = s['trade']['last_monitored_at']
    check('11:00:10: el 10:59 sin siguiente no se evalúa (punto de control 10:58)', chk1 == naive(10, 58), chk1)
    s['minutes'] = feed(at(11, 0), low={at(10, 59): 98.9})
    await mg.monitor(s, at(11, 1, 10))
    tr = s['trade']
    check('11:01:10: con 10:59 final se ve el toque -> stop_loss con hora 10:59 (antes quedaba abierta)',
          tr['status'] == 'closed' and tr.get('exit_reason') == 'stop_loss' and tr.get('exit_time') == naive(10, 59),
          (tr['status'], tr.get('exit_reason'), tr.get('exit_time')))

    # 2. El síntoma «+1 min»: el toque sigue en el minuto siguiente; antes salía a las 11:00, ahora a las 10:59
    s = mg.store(feed(at(10, 59)))
    await mg.monitor(s, at(11, 0, 10))
    s['minutes'] = feed(at(11, 1), low={at(10, 59): 98.9, at(11, 0): 98.8})
    await mg.monitor(s, at(11, 2, 10))
    tr = s['trade']
    check('toque en 10:59 y 11:00: la hora de salida es la del primer toque (10:59), no un minuto después',
          tr['status'] == 'closed' and tr.get('exit_time') == naive(10, 59), (tr['status'], tr.get('exit_time')))

    # 3. Collector atrasado: no avanza el punto de control sobre minutos sin siguiente; al ponerse al día, todo se evalúa
    s = mg.store(feed(at(10, 30)))
    await mg.monitor(s, at(11, 0, 10))
    check('collector atrasado (último 10:30): punto de control 10:29, sin ERROR', s['trade']['last_monitored_at']
          == naive(10, 29) and not mg.errors(), (s['trade']['last_monitored_at'], mg.errors()))
    s['minutes'] = feed(at(11, 1), low={at(10, 30): 98.9})
    await mg.monitor(s, at(11, 1, 10))
    check('al ponerse al día: el 10:30 (ya final) cierra con su hora', s['trade'].get('exit_time') == naive(10, 30),
          s['trade'].get('exit_time'))

    # 4. Caso normal: la base tiene el minuto en formación; se evalúa todo hasta el minuto cerrado
    s = mg.store(feed(at(11, 0)))
    await mg.monitor(s, at(11, 0, 10))
    check('caso normal (11:00 en formación): punto de control 10:59, sin consultas extra',
          s['trade']['last_monitored_at'] == naive(10, 59) and s.get('tail_queries', 0) == 0 and s['backup_queries'] == 0,
          (s['trade']['last_monitored_at'], s.get('tail_queries', 0), s['backup_queries']))


mg.CLOCK[0] = at(11, 0)
asyncio.run(main())
print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

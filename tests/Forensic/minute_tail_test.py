"""
N-02: final sin velas de 1m en Paper. Si la serie de 1m de la fuente lleva más de PAPER_MINUTE_GAP_WAIT_HOURS (26 h)
detenida, el tramo final se evalúa con las velas CERRADAS del intervalo operado y SL primero (la regla de BP-03 para
huecos internos y del backtest sin 1m), y sigue haciéndolo vela a vela sin volver a esperar 26 h. Si las velas solo
vienen con retraso, se espera en silencio. Sin base de datos: reutiliza los dobles de minute_gap_test.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/minute_tail_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import minute_gap_test as mg  # noqa: E402  (dobles: pool en memoria, reloj, logs)

UTC = timezone.utc
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def at(d, h, m=0):
    return datetime(2026, 3, d, h, m, tzinfo=UTC)


def hours(start, end, touch=None):
    """Velas H1 cerradas o no de [start, end); `touch` = {inicio: low}."""
    out, t = [], start
    while t < end:
        out.append(mg.hour(t.replace(tzinfo=None), low=(touch or {}).get(t, 99.5)))
        t += timedelta(hours=1)
    return out


def tail_errors():
    return [m for m in mg.errors() if 'detenida' in m]


async def main():
    t0 = at(2, 10)
    feed = mg.minutes(t0 + timedelta(minutes=1), at(2, 10, 38))          # el 1m se detiene en 10:37
    dead = at(3, 13, 7)                                                  # 26 h 30 min después

    # T1. Serie de 1m detenida > 26 h y la vela H1 de las 11:00 toca el SL: se cierra por SL (antes: nunca)
    s = mg.store(feed, candles=hours(t0, at(3, 13), touch={at(2, 11): 98.5}))
    await mg.monitor(s, dead)
    tr = s['trade']
    check('T1: serie detenida, vela 11:00 toca el SL -> stop_loss a 99.0',
          tr['status'] == 'closed' and tr.get('exit_reason') == 'stop_loss' and abs((tr.get('exit_price') or 0) - 99.0) < 1e-9,
          (tr['status'], tr.get('exit_reason'), tr.get('exit_price')))
    check('T1: exit_time = inicio de la vela que tocó (11:00), como el backtest sin 1m',
          tr.get('exit_time') == datetime(2026, 3, 2, 11, 0), tr.get('exit_time'))
    check('T1: ERROR que explica que la serie de 1m está detenida', len(tail_errors()) == 1, mg.errors())

    # T2. Serie detenida y ninguna vela toca: el punto de control avanza hasta la última vela H1 cerrada
    s = mg.store(feed, candles=hours(t0, at(3, 13)))
    await mg.monitor(s, dead)
    chk = s['trade']['last_monitored_at']
    check('T2: sin toque -> sigue abierto con el punto de control en el último minuto de la vela 12:00 del día 3',
          s['trade']['status'] == 'open' and chk == datetime(2026, 3, 3, 12, 59), (s['trade']['status'], chk))

    # T3. Ticks siguientes: sin vela nueva cerrada no hace nada (ni ERROR); con la vela 13:00 cerrada la evalúa
    #     enseguida, sin volver a esperar 26 h (el plazo se mide en la serie, no en el punto de control)
    await mg.monitor(s, at(3, 13, 40))
    check('T3: sin vela nueva cerrada -> punto de control igual y sin ERROR',
          s['trade']['last_monitored_at'] == datetime(2026, 3, 3, 12, 59) and not mg.errors(),
          (s['trade']['last_monitored_at'], mg.errors()))
    s['candles'] += hours(at(3, 13), at(3, 14), touch={at(3, 13): 98.9})
    await mg.monitor(s, at(3, 14, 1))
    check('T3: vela 13:00 cerrada y toca el SL -> cierra en el tick siguiente (sin otra espera de 26 h)',
          s['trade']['status'] == 'closed' and s['trade'].get('exit_time') == datetime(2026, 3, 3, 13, 0),
          (s['trade']['status'], s['trade'].get('exit_time')))

    # T4. Las velas de 1m solo vienen con retraso (< 26 h): espera en silencio, no usa las velas H1
    s = mg.store(feed, candles=hours(t0, at(2, 12), touch={at(2, 11): 98.5}))
    await mg.monitor(s, at(2, 12, 30))
    check('T4: 1m con retraso de 2 h -> no cierra, punto de control en 10:37, sin ERROR ni velas de respaldo',
          s['trade']['status'] == 'open' and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 10, 37)
          and not mg.errors() and s['backup_queries'] == 0,
          (s['trade']['status'], s['trade']['last_monitored_at'], mg.errors(), s['backup_queries']))

    # T5. Caso normal (1m al día): no consulta la última vela de la serie ni el respaldo
    s = mg.store(mg.minutes(t0 + timedelta(minutes=1), at(2, 11, 59)))
    await mg.monitor(s, at(2, 12))
    check('T5: 1m al día -> sin consultas extra y punto de control en 11:58',
          s.get('tail_queries', 0) == 0 and s['backup_queries'] == 0
          and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 11, 58),
          (s.get('tail_queries', 0), s['backup_queries'], s['trade']['last_monitored_at']))

    # T6. Sin ninguna vela de 1m desde la entrada (serie vacía) y > 26 h: también se cubre con H1
    s = mg.store([], candles=hours(t0, at(3, 13), touch={at(2, 15): 98.0}))
    await mg.monitor(s, dead)
    check('T6: serie de 1m vacía -> se evalúa con H1 y cierra en la vela 15:00',
          s['trade']['status'] == 'closed' and s['trade'].get('exit_time') == datetime(2026, 3, 2, 15, 0),
          (s['trade']['status'], s['trade'].get('exit_time')))

    # T7. Serie detenida, pero la próxima vela H1 aún no cierra: no hay respaldo posible y no hay ERROR
    s = mg.store(feed, candles=hours(t0, at(3, 13)))
    s['trade']['last_monitored_at'] = datetime(2026, 3, 3, 12, 59)
    await mg.monitor(s, at(3, 13, 30))
    check('T7: serie detenida sin vela nueva cerrada -> nada cambia, sin ERROR',
          s['trade']['last_monitored_at'] == datetime(2026, 3, 3, 12, 59) and not mg.errors(), mg.errors())

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

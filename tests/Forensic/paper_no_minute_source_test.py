"""
Auditoría 13-nov §3.5: Paper con la fuente en vivo SIN ninguna serie de 1m del símbolo (resolve_live_broker('1') = None).
Antes: solo un WARNING y el SL/TP no se evaluaba nunca (la posición quedaba sin gestión salvo el cierre por tiempo).
Ahora: no hay reparación que esperar, así que se evalúan las velas CERRADAS del intervalo operado con SL primero, desde
el punto de control (la regla del backtest sin 1m, de BP-03 y de N-02). Sin velas del intervalo tampoco: ERROR y nada.
Sin base de datos: reutiliza los dobles de minute_gap_test.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/paper_no_minute_source_test.py
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
SOURCES = {'1': None, '60': 'bybit'}   # fuente en vivo por intervalo (None = sin velas)


async def _broker(pool, symbol, interval, **k):
    return SOURCES.get(str(interval))

mg.pt.resolve_live_broker = _broker


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def at(d, h, m=0):
    return datetime(2026, 3, d, h, m, tzinfo=UTC)


def hours(start, end, touch=None):
    out, t = [], start
    while t < end:
        out.append(mg.hour(t.replace(tzinfo=None), low=(touch or {}).get(t, 99.5)))
        t += timedelta(hours=1)
    return out


def errs(word):
    return [m for lvl, m in mg.LOGS if lvl == 'ERROR' and word in m]


async def main():
    t0 = at(2, 10)   # entrada 10:00 (ENTRY de los dobles), SL 99.0

    # N1. Sin serie de 1m: la vela H1 de las 11:00 toca el SL -> se cierra por SL en el tick posterior a su cierre
    SOURCES.update({'1': None, '60': 'bybit'})
    s = mg.store([], candles=hours(t0, at(2, 13), touch={at(2, 11): 98.5}))
    await mg.monitor(s, at(2, 12, 1))
    tr = s['trade']
    check('N1: sin 1m, vela 11:00 toca el SL -> stop_loss a 99.0',
          tr['status'] == 'closed' and tr.get('exit_reason') == 'stop_loss' and abs((tr.get('exit_price') or 0) - 99.0) < 1e-9,
          (tr['status'], tr.get('exit_reason'), tr.get('exit_price')))
    check('N1: exit_time = inicio de la vela que tocó (11:00), como el backtest sin 1m',
          tr.get('exit_time') == datetime(2026, 3, 2, 11, 0), tr.get('exit_time'))
    check('N1: ERROR que explica que no hay serie de 1m', len(errs('sin serie de 1m')) == 1, mg.LOGS)

    # N2. Sin toque: el punto de control avanza al último minuto de la última vela cerrada; sigue abierto
    s = mg.store([], candles=hours(t0, at(2, 13)))
    await mg.monitor(s, at(2, 12, 1))
    check('N2: sin toque -> abierto, punto de control 11:59 (vela 11:00 cerrada; la 12:00 no)',
          s['trade']['status'] == 'open' and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 11, 59),
          (s['trade']['status'], s['trade']['last_monitored_at']))

    # N3. Tick siguiente sin vela nueva cerrada: nada cambia y no repite el ERROR; con la 12:00 cerrada, la evalúa
    await mg.monitor(s, at(2, 12, 30))
    check('N3: sin vela nueva cerrada -> punto de control igual, sin ERROR',
          s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 11, 59) and not errs('sin serie de 1m'),
          (s['trade']['last_monitored_at'], mg.LOGS))
    s['candles'] = hours(t0, at(2, 14), touch={at(2, 12): 98.9})
    await mg.monitor(s, at(2, 13, 1))
    check('N3: vela 12:00 cerrada y toca -> cierra con exit_time 12:00',
          s['trade']['status'] == 'closed' and s['trade'].get('exit_time') == datetime(2026, 3, 2, 12, 0),
          (s['trade']['status'], s['trade'].get('exit_time')))

    # N4. Vela de entrada: su mecha anterior a la entrada cuenta (pesimista, igual que el respaldo de N-02);
    #     exit_time no puede quedar antes de la entrada
    s = mg.store([], candles=hours(t0, at(2, 12), touch={t0: 98.0}))
    s['trade']['entry_time'] = s['trade']['last_monitored_at'] = datetime(2026, 3, 2, 10, 20)   # a mitad de la vela
    await mg.monitor(s, at(2, 11, 1))
    check('N4: la vela de entrada toca -> stop_loss con exit_time = entrada (10:20), nunca antes',
          s['trade']['status'] == 'closed' and s['trade'].get('exit_time') == datetime(2026, 3, 2, 10, 20),
          (s['trade']['status'], s['trade'].get('exit_time')))

    # N5. Sin 1m ni velas del intervalo: no rompe, sigue abierto y avisa
    SOURCES.update({'1': None, '60': None})
    s = mg.store([], candles=[])
    await mg.monitor(s, at(2, 12, 1))
    check('N5: sin 1m ni H1 -> abierto, sin cambios, ERROR explícito',
          s['trade']['status'] == 'open' and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 10, 0)
          and len(errs('ni velas')) == 1, (s['trade']['status'], s['trade']['last_monitored_at'], mg.LOGS))

    # N6. Control: con 1m disponible no se usan velas del intervalo (comportamiento de siempre)
    SOURCES.update({'1': 'bybit', '60': 'bybit'})
    s = mg.store(mg.minutes(t0 + timedelta(minutes=1), at(2, 11, 59)), candles=hours(t0, at(2, 12), touch={at(2, 11): 98.0}))
    await mg.monitor(s, at(2, 12))
    check('N6: con 1m al día -> sin consultas de respaldo, abierto, punto de control 11:58',
          s['backup_queries'] == 0 and s['trade']['status'] == 'open'
          and s['trade']['last_monitored_at'] == datetime(2026, 3, 2, 11, 58),
          (s['backup_queries'], s['trade']['status'], s['trade']['last_monitored_at']))

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

"""
19-nov (LINK): Real calcula por qué una suscripción no abre (sin señal, régimen, vela sin completar, límite…) y se lo
devuelve a Laravel, que solo registra conteos: el motivo se perdía. Ahora el motor lo escribe en engine.log con la
etiqueta [REAL-SEÑAL] SOLO cuando cambia (una línea por suscripción y vela, no una por minuto).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_signal_reason_test.py
"""
import logging
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


import api.v1.real_trading as rtapi  # noqa: E402

lines = []


class H(logging.Handler):
    def emit(self, record):
        if '[REAL-SEÑAL]' in record.getMessage():
            lines.append((record.levelname, record.getMessage()))


rtapi.logger.addHandler(H())
rtapi.logger.setLevel(logging.INFO)
log = getattr(rtapi, '_log_signal_reason', None)
check('G0 existe el registro de motivos de Real', log is not None)
if log is not None:
    seq = ['LINKUSDT: sin señal', 'LINKUSDT: sin señal', 'LINKUSDT: sin señal',
           'LINKUSDT: vela de las 12:00 UTC aún sin completar en la base (collector), se espera al minuto siguiente',
           'LINKUSDT: sin señal', 'LINKUSDT: sin señal']
    for txt in seq:
        log(11, 64, 'VWAP Tendencia — LINKUSDT H4', txt)
    check('G1 6 ticks con 3 cambios de motivo -> 3 líneas (no una por minuto)', len(lines) == 3, [m for _, m in lines])
    check('G2 cada línea dice cuenta, estrategia, suscripción y motivo (nivel INFO)',
          all(lv == 'INFO' for lv, _ in lines) and lines[0][1] ==
          '[REAL-SEÑAL] cuenta 11 · VWAP Tendencia — LINKUSDT H4 (suscripción 64): LINKUSDT: sin señal', lines[:1])
    lines.clear()
    log(11, 59, 'VWAP Tendencia — DOGEUSDT H4', 'LINKUSDT: sin señal')
    check('G3 cada suscripción lleva su propio último motivo', len(lines) == 1, lines)
    lines.clear()
    log(11, 59, 'VWAP Tendencia — DOGEUSDT H4', 'DOGEUSDT: ABIERTA short @ 0.05856')
    log(11, 59, 'VWAP Tendencia — DOGEUSDT H4', 'DOGEUSDT: ya tiene posicion abierta')
    log(11, 59, 'VWAP Tendencia — DOGEUSDT H4', 'DOGEUSDT: ya tiene posicion abierta')
    check('G4 apertura y luego «ya tiene posición» -> 2 líneas', len(lines) == 2, [m for _, m in lines])

src = open(os.path.join(os.getcwd(), 'api', 'v1', 'real_trading.py'), encoding='utf-8').read()
check('G5 el tick de Real llama al registro con el resultado de cada suscripción',
      '_log_signal_reason(account.id, sub.subscription_id, sub.strategy, result)' in src)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

"""
Validación de los parámetros de un backtest (F-03): Laravel (App\\Services\\BacktestPayload::validate, mensajes de la
pantalla) y Python (BacktestRequest, última defensa) usan las mismas reglas (backtesting/request_rules.json) y deben
aceptar y rechazar EXACTAMENTE los mismos casos. Sin base de datos (llama a `php` para la parte de Laravel).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/request_rules_test.py
Antes del parche: FALLA (se aceptaban valores imposibles: riesgo, SL, TP, comisión o saldo negativos, modos desconocidos).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())  # python-engine/

from pydantic import ValidationError  # noqa: E402

from api.v1.backtest import BacktestRequest  # noqa: E402

ROOT = Path(os.getcwd()).parent
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


try:
    from backtesting import request_rules
except ImportError:
    request_rules = None

# (caso, cambios sobre un payload válido, campo que debe fallar o None)
CASES = [
    ('payload válido', {}, None),
    ('saldo 0', {'initial_balance': 0}, 'Saldo inicial'),
    ('saldo negativo', {'initial_balance': -100}, 'Saldo inicial'),
    ('riesgo negativo', {'risk_per_trade_pct': -1}, 'Riesgo por operación'),
    ('riesgo 0', {'risk_per_trade_pct': 0}, 'Riesgo por operación'),
    ('riesgo 100 (límite)', {'risk_per_trade_pct': 100}, None),
    ('riesgo 101', {'risk_per_trade_pct': 101}, 'Riesgo por operación'),
    ('SL negativo', {'sl_pct': -1.5}, 'Stop loss'),
    ('SL 100 (precio 0)', {'sl_pct': 100}, 'Stop loss'),
    ('TP 0', {'tp_pct': 0}, 'Take profit (%)'),
    ('TP 99.9', {'tp_pct': 99.9}, None),
    ('TP2 null (opcional)', {'tp2_pct': None}, None),
    ('TP2 negativo', {'tp2_pct': -2}, 'Take profit 2'),
    ('BE 99 = sin break-even (convención de la búsqueda)', {'be_pct': 99}, None),
    ('BE 0', {'be_pct': 0}, 'Break-even'),
    ('duración 0 = sin límite', {'max_duration': 0}, None),
    ('duración negativa', {'max_duration': -1}, 'Duración máxima'),
    ('duración no entera', {'max_duration': 2.5}, 'Duración máxima'),
    ('comisión negativa', {'commission_pct': -0.01}, 'Comisión'),
    ('comisión 0', {'commission_pct': 0}, None),
    ('comisión 1.5 %', {'commission_pct': 1.5}, 'Comisión'),
    ('slippage 2 %', {'slippage_pct': 2}, 'Slippage'),
    ('ADX tendencia 120', {'regime_adx_trending': 120}, 'ADX de tendencia'),
    ('ADX lateral > tendencia', {'regime_adx_ranging': 30, 'regime_adx_trending': 25}, 'ADX lateral no puede'),
    ('ADX lateral = tendencia', {'regime_adx_ranging': 25, 'regime_adx_trending': 25}, None),
    ('régimen ambiguo desconocido', {'regime_ambiguous_as': 'LATERAL'}, 'Régimen ambiguo'),
    ('trailing stepped', {'trailing_mode': 'stepped'}, None),
    ('trailing desconocido', {'trailing_mode': 'magic'}, 'Modo de trailing'),
    ('distancia trailing 0', {'trailing_distance_pct': 0}, 'Distancia del trailing'),
    ('buffer trailing negativo', {'trailing_activation_buffer_pct': -1}, 'Buffer de activación'),
    ('ATR trailing 0', {'trailing_atr_mult': 0}, 'Multiplicador ATR del trailing'),
    ('volatilidad close', {'volatility_protection_mode': 'close'}, None),
    ('volatilidad desconocida', {'volatility_protection_mode': 'on'}, 'Protección por volatilidad'),
    ('ensanche 100', {'volatility_widen_pct': 100}, 'Ensanche por volatilidad'),
    ('período volumen 0', {'volume_filter_period': 0}, 'Período del filtro de volumen'),
    ('mult volumen negativo', {'volume_filter_mult': -1}, 'Multiplicador del filtro de volumen'),
    ('hora 24', {'hour_filter_start': 24}, 'Hora de inicio'),
    ('ventanas 0', {'n_windows': 0}, 'Ventanas walk forward'),
    ('apalancamiento 0', {'max_leverage': 0}, 'Apalancamiento máximo'),
    ('intervalo 30 (el motor no lo admite: F-02)', {'interval': '30'}, 'Intervalo'),
    ('intervalo D', {'interval': 'D'}, None),
    ('NaN', {'sl_pct': float('nan')}, 'Stop loss'),
    ('intervalo como número (60, no "60")', {'interval': 60}, 'Intervalo'),
    ('modo de trailing vacío', {'trailing_mode': ''}, 'Modo de trailing'),
]
BASE = dict(strategy='S', symbol='BTCUSDT', interval='60', initial_balance=10000.0, risk_per_trade_pct=1.0, sl_pct=1.5,
            tp_pct=3.0, be_pct=2.0, max_duration=24, commission_pct=0.055, slippage_pct=0.05, regime_adx_trending=25.0,
            regime_adx_ranging=20.0, regime_ambiguous_as='RANGING', trailing_mode=None, trailing_distance_pct=1.0,
            trailing_activation_buffer_pct=0.0, trailing_atr_mult=2.0, volume_filter_period=20, volume_filter_mult=1.2,
            n_windows=5)
# Valores reales guardados en producción (lectura 06-nov: mín y máx de configs Paper, backtests y snapshots)
STORED = [dict(be_pct=0.8, max_duration=0, regime_adx_ranging=18, regime_adx_trending=20, risk_per_trade_pct=0.5,
               sl_pct=1, tp_pct=2, trailing_activation_buffer_pct=0, trailing_atr_mult=1, trailing_distance_pct=1,
               volume_filter_mult=0.3, volume_filter_period=13, trailing_mode='atr', regime_ambiguous_as='NO_OPERAR',
               interval='120'),
          dict(be_pct=99, max_duration=96, regime_adx_ranging=25, regime_adx_trending=30, risk_per_trade_pct=1,
               sl_pct=4, tp_pct=6, trailing_activation_buffer_pct=3, trailing_atr_mult=3, trailing_distance_pct=1.5,
               volume_filter_mult=1.7, volume_filter_period=25, trailing_mode='fixed', regime_ambiguous_as='TRENDING',
               interval='240')]


def php_validate(payloads: list[dict]) -> list:
    code = ("require 'app/Services/BacktestPayload.php'; $in = json_decode(stream_get_contents(STDIN), true);"
            "echo json_encode(array_map(fn ($p) => \\App\\Services\\BacktestPayload::validate($p), $in));")
    r = subprocess.run(['php', '-r', code], cwd=ROOT, input=json.dumps(payloads, allow_nan=True).replace('NaN', '"NaN"'),
                       capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return ['ERROR PHP: ' + (r.stderr or r.stdout)[-200:]] * len(payloads)


def py_validate(p: dict):
    try:
        BacktestRequest(**p)
        return None
    except ValidationError as e:
        return '; '.join(x['msg'] for x in e.errors())


def main():
    if request_rules is None:
        check('backtesting.request_rules existe', False, 'no existe (código anterior)')
    payloads = [dict(BASE, **chg) for _, chg, _ in CASES]
    php = php_validate(payloads)
    for (name, chg, want), p, ph in zip(CASES, payloads, php):
        py = py_validate(p)
        if want is None:
            check(f'acepta: {name}', py is None and ph is None, (py, ph))
        else:
            # un entero con decimales lo rechaza Pydantic por el tipo (mensaje propio) antes que las reglas
            ok_py = py is not None and (want in py or 'valid integer' in py or 'valid string' in py)
            ok_php = isinstance(ph, str) and want in ph
            check(f'rechaza: {name}  (Python y Laravel, campo «{want}»)', ok_py and ok_php, (py, ph))
    check('mensaje en español con el rango y lo recibido',
          isinstance(php[3], str) and php[3] == 'Riesgo por operación (%): debe ser mayor que 0 y menor o igual que 100 (recibido: -1).',
          php[3])

    stored = [dict(BASE, **s) for s in STORED]
    sp = php_validate(stored)
    check('los valores guardados hoy en producción se aceptan (Python y Laravel)',
          all(py_validate(s) is None for s in stored) and sp == [None, None], ([py_validate(s) for s in stored], sp))
    inf = py_validate(dict(BASE, initial_balance=float('inf')))
    check('Python: saldo infinito rechazado (solo tiene cota inferior)', inf is not None and 'Saldo inicial' in inf, inf)
    check('los defaults de BacktestRequest son válidos', py_validate(dict(strategy='S')) is None, py_validate(dict(strategy='S')))

    ctl = (ROOT / 'app/Http/Controllers/BacktestingController.php').read_text(encoding='utf-8')
    check('controlador: valida cada payload antes de llamar a Python',
          ctl.count('BacktestPayload::validate($payload)') == 1
          and ctl.index('BacktestPayload::validate($payload)') < ctl.index("/v1/backtest/run'"))
    check('controlador: meses entero entre 1 y 60', "Meses: debe ser un número entero entre 1 y 60." in ctl)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    main()

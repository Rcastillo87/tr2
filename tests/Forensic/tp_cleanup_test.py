"""
D-31 (p71): TP2, TP3 y TP4 quitados (nunca se ejecutaban: el motor, Paper y Real cierran solo con TP1).
- Sin residuos en el código de producción (motor, trading, API, reglas, Laravel). Las columnas tp2/tp3/tp4 y
  realized_pnl_partial de la base se conservan por el historial; las dos pantallas solo esconden esas claves de
  configuraciones viejas.
- calculate_tp1 = el TP1 de antes (misma fórmula y redondeo) y None sin tp_pct.
- Un JSON o pedido viejo con tp2_pct se acepta y se ignora.
- El resultado del backtest no cambió: 190 configuraciones / 38.139 trades idénticos al motor anterior (bitácora p71).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/tp_cleanup_test.py
"""
import os
import re
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import end_of_data_test as eod  # noqa: E402  (velas sintéticas y estrategia de prueba)
from api.v1.backtest import BacktestRequest, load_strategy  # noqa: E402
from backtesting import request_rules  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.base_strategy import BaseStrategy  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


ROOT = os.path.abspath(os.path.join(os.getcwd(), '..'))
PAT = re.compile(r"tp[234]_pct|calculate_tp_levels|calculate_tp2|realized_pnl_partial|partial_pnl|\btp[234]\b|'tp[234]'|\"tp[234]\"")
SCAN = ['python-engine/backtesting', 'python-engine/trading', 'python-engine/api', 'python-engine/cli',
        'python-engine/tools', 'app']
hits = []
for base in SCAN:
    for root, dirs, files in os.walk(os.path.join(ROOT, base)):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', 'venv')]
        for f in files:
            if f.endswith(('.py', '.php', '.json')):
                p = os.path.join(root, f)
                for n, line in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
                    if PAT.search(line) and 'D-31' not in line:
                        hits.append(f'{os.path.relpath(p, ROOT)}:{n}')
check('T1 sin residuos de TP2–TP4 / PnL parcial en motor, trading, API, CLI, herramientas y Laravel', hits == [], hits[:10])
check('T2 las reglas del formulario ya no tienen tp2/3/4_pct', not any(k in request_rules.RULES for k in ('tp2_pct', 'tp3_pct', 'tp4_pct')))
check('T3 BaseStrategy sin calculate_tp_levels / calculate_tp2', not hasattr(BaseStrategy, 'calculate_tp_levels')
      and not hasattr(BaseStrategy, 'calculate_tp2'))

s = load_strategy(BacktestRequest(strategy='S', strategy_code=eod.CODE, symbol='BTCUSDT', interval='60', sl_pct=5.0,
                                  tp_pct=2.5, start_date='2026-03-02', end_date='2026-03-02',
                                  strategy_config={'tp2_pct': 4.4, 'tp3_pct': 6.0}))
cases = [(100.0, 'long', round(100.0 * (1 + 2.5 / 100), 8)), (100.0, 'short', round(100.0 * (1 - 2.5 / 100), 8)),
         (0.1234567, 'long', round(0.1234567 * (1 + 2.5 / 100), 8)), (68907.3, 'short', round(68907.3 * (1 - 2.5 / 100), 8))]
check('T4 calculate_tp1 = fórmula y redondeo del TP1 anterior (long/short, precios chicos y grandes)',
      all(s.calculate_tp1(p, side) == want for p, side, want in cases), [(p, side, s.calculate_tp1(p, side), want) for p, side, want in cases])
s.tp_pct = None
check('T5 sin tp_pct -> None', s.calculate_tp1(100.0, 'long') is None)
check('T6 un JSON viejo con tp2_pct/tp3_pct se acepta y se ignora', not hasattr(s, 'tp2_pct') and not hasattr(s, 'tp3_pct'))
check('T7 un pedido viejo con tp2_pct pasa la validación (se ignora)', request_rules.errors({'tp2_pct': -2, 'tp_pct': 2.0}) == [],
      request_rules.errors({'tp2_pct': -2, 'tp_pct': 2.0}))

s = load_strategy(BacktestRequest(strategy='S', strategy_code=eod.CODE, symbol='BTCUSDT', interval='60', sl_pct=5.0,
                                  tp_pct=10.0, start_date='2026-03-02', end_date='2026-03-02'))
r = BacktestEngine(strategy=s, df=eod.bars(sig={4: 1}), initial_balance=10000.0, risk_per_trade_pct=1.0).run()
keys = set().union(*(t.keys() for t in r['trades'])) if r['trades'] else set()
check('T8 los trades del backtest traen tp1 y ya no tp2/tp3/tp4', r['trades'] and 'tp1' in keys and not keys & {'tp2', 'tp3', 'tp4'},
      sorted(keys))

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

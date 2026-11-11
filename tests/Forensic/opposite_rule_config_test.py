"""
Salida por señal opuesta definida en el JSON de la estrategia (strategy_config): Paper y Real deben leerla igual que
el backtest. El backtest construye la estrategia con strategy_config debajo de los parámetros de operación
(loader.build_strategy); opposite_exit_rule (Paper/Real, parámetros congelados del trade) leía solo el nivel de arriba.
Caso real: la estrategia BNF pide exit_on_opposite=true en su JSON.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/opposite_rule_config_test.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from backtesting.strategies.base_strategy import opposite_exit_rule  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


CODE = "class S(BaseStrategy):\n    def generate_signals(self, df):\n        df = df.copy(); df['signal'] = 0; return df\n"


def engine_rule(params):
    """Regla que aplica el motor de backtest con la estrategia construida (engine.py)."""
    s = build_strategy(dict(params, strategy_code=CODE))
    if getattr(s, 'exit_on_opposite', False):
        return 'exit'
    return 'reverse' if getattr(s, 'close_on_opposite', False) else None


cases = [
    ('O1: exit_on_opposite solo en el JSON de la estrategia -> exit', {'strategy_config': {'exit_on_opposite': True}}, 'exit'),
    ('O2: JSON con exit y formulario con close_on_opposite=false (como envía Laravel) -> exit',
     {'close_on_opposite': False, 'strategy_config': {'exit_on_opposite': True}}, 'exit'),
    ('O3: close_on_opposite solo en el JSON -> reverse', {'strategy_config': {'close_on_opposite': True}}, 'reverse'),
    ('O4: el formulario pisa al JSON (exit_on_opposite=false arriba) -> None',
     {'exit_on_opposite': False, 'strategy_config': {'exit_on_opposite': True}}, None),
    ('O5: nivel de arriba como siempre (exit)', {'exit_on_opposite': True}, 'exit'),
    ('O6: exit manda sobre close (JSON exit, arriba close)', {'close_on_opposite': True, 'strategy_config': {'exit_on_opposite': True}}, 'exit'),
    ('O7: flags como texto (normalización)', {'strategy_config': {'exit_on_opposite': 'true'}}, 'exit'),
    ('O8: sin nada -> None', {}, None),
    ('O9: params None o strategy_config None -> None', {'strategy_config': None}, None),
]
for name, params, want in cases:
    got = opposite_exit_rule(params)
    check(name, got == want, (got, want))
check('O10: Paper/Real (opposite_exit_rule) = backtest (estrategia construida) en todos los casos',
      all(opposite_exit_rule(p) == engine_rule(p) for _, p, _ in cases), [(n[:3], opposite_exit_rule(p), engine_rule(p)) for n, p, _ in cases if opposite_exit_rule(p) != engine_rule(p)])
check('O11: None -> None', opposite_exit_rule(None) is None)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

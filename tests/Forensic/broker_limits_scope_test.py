"""
RQ-01.6: las protecciones de apertura configurables por broker (límites por cuenta: pérdida máxima del mes y trades
abiertos máximos) no son parámetros de estrategia. Viven en broker_accounts, se configuran en la cuenta y solo las lee
la ejecución Real al abrir. Esta prueba revisa que no aparezcan en ningún camino de la estrategia, de Paper, del
backtest ni de sus formularios, y que Real sí las siga aplicando. Sin base ni red.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/broker_limits_scope_test.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
fails = 0
LIMITS = re.compile(r'max_monthly_loss_pct|max_open_trades|month_start_balance')


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def hits(paths):
    out = []
    for p in paths:
        for f in ([p] if p.is_file() else sorted(p.rglob('*'))):
            if f.is_file() and f.suffix in ('.py', '.php', '.json', '.js') and LIMITS.search(f.read_text(errors='ignore')):
                out.append(str(f.relative_to(ROOT)))
    return out


E = ROOT / 'python-engine'
strategy_side = [E / 'backtesting', E / 'trading' / 'paper_trader.py', E / 'api' / 'v1' / 'backtest.py',
                 E / 'api' / 'v1' / 'paper_trading.py', E / 'cli' / 'param_search.py',
                 ROOT / 'app' / 'Services' / 'StrategyConfigSync.php', ROOT / 'app' / 'Services' / 'BacktestPayload.php',
                 ROOT / 'app' / 'Services' / 'BacktestFromSearch.php', ROOT / 'app' / 'Http' / 'Controllers' / 'BacktestingController.php',
                 ROOT / 'app' / 'Http' / 'Controllers' / 'StrategyController.php']
check('B1: ningún archivo de estrategia, backtest, búsqueda o Paper menciona los límites por cuenta', hits(strategy_side) == [],
      hits(strategy_side))
views = [ROOT / 'resources' / 'views' / d for d in ('backtesting', 'strategies', 'param-search', 'paper-trading')]
blade = [str(f.relative_to(ROOT)) for v in views for f in v.rglob('*.blade.php') if LIMITS.search(f.read_text(errors='ignore'))]
check('B2: ningún formulario de backtest, estrategia, búsqueda o Paper los ofrece', blade == [], blade)
rt = (E / 'trading' / 'real_trader.py').read_text()
check('B3: Real los sigue aplicando al abrir (lee broker_accounts y bloquea por trades abiertos)',
      'FROM broker_accounts' in rt and "max_open_trades" in rt and 'máximo de trades abiertos' in rt)
acc = (ROOT / 'app' / 'Models' / 'BrokerAccount.php').read_text()
check('B4: son atributos de la cuenta (BrokerAccount)', 'max_monthly_loss_pct' in acc and 'max_open_trades' in acc)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

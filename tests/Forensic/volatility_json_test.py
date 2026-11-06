"""
F-01 — La protección por volatilidad del JSON de la estrategia llega a la estrategia cuando el formulario no la envía,
en la pantalla (/backtest/run) y en la búsqueda de parámetros (mismo request). Sin base de datos.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/volatility_json_test.py
Antes del parche: FALLA el caso de la búsqueda (UI_FIXED forzaba la volatilidad apagada).
"""
import os
import sys

sys.path.insert(0, os.getcwd())  # python-engine/

from api.v1.backtest import BacktestRequest, load_strategy  # noqa: E402
import cli.param_search as ps  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


CODE = "class S(BaseStrategy):\n    def generate_signals(self, df):\n        df['signal'] = 0\n        return df\n"
JSON = {'volatility_protection_mode': 'widen', 'volatility_atr_multiplier': 3.0, 'volatility_widen_pct': 0.7}


def vol(s):
    return (s.volatility_protection_mode, s.volatility_atr_multiplier, s.volatility_widen_pct)


base = dict(strategy='S', strategy_code=CODE, strategy_config=JSON, symbol='BTCUSDT', interval='60')

# Pantalla: lo que llega desde Laravel
s = load_strategy(BacktestRequest(**base, sl_pct=1.5, tp_pct=3.0))
check('pantalla sin volatilidad en el request -> la del JSON', vol(s) == ('widen', 3.0, 0.7), vol(s))
s = load_strategy(BacktestRequest(**base, volatility_protection_mode=None))
check("pantalla con 'none' explícito -> apagada (el formulario manda)", vol(s)[0] is None, vol(s))
s = load_strategy(BacktestRequest(**base, volatility_protection_mode='close', volatility_atr_multiplier=2.0))
check('pantalla con modo y multiplicador -> pisan el JSON; el % sigue el JSON', vol(s) == ('close', 2.0, 0.7), vol(s))
s = load_strategy(BacktestRequest(**dict(base, strategy_config={})))
check('sin JSON ni request -> apagada (defaults de la estrategia)', vol(s) == (None, 2.5, 1.0), vol(s))

# Búsqueda: el mismo request que arma param_search (COSTS + UI_FIXED + combinación)
cfg = dict(sl_pct=1.5, tp_pct=3.0)
s = load_strategy(BacktestRequest(**base, initial_balance=ps.INITIAL, risk_per_trade_pct=ps.RISK_PCT, **ps.COSTS,
                                  **ps.UI_FIXED, **cfg))
check('búsqueda: la volatilidad del JSON se respeta (igual que la pantalla)', vol(s) == ('widen', 3.0, 0.7), vol(s))
check('búsqueda: UI_FIXED no envía volatility_*', not any(k.startswith('volatility_') for k in ps.UI_FIXED), ps.UI_FIXED)

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

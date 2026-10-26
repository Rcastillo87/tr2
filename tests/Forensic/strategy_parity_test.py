"""
Paridad de construcción: la estrategia del BACKTEST debe ser idéntica a la de PAPER y REAL para el mismo
payload que envía Laravel (y que se guarda en config_params). Sin DB.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/strategy_parity_test.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from api.v1.backtest import BacktestRequest, load_strategy  # noqa: E402
from api.v1.real_trading import SubscriptionPayload, instantiate_strategy  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402

CODE = ("class T(BaseStrategy):\n"
        "    allowed_regimes = ['RANGING']\n"
        "    def __init__(self, params):\n"
        "        super().__init__(params)\n"
        "        self.period = params.get('period', 20)\n"
        "    def generate_signals(self, df):\n"
        "        df['signal'] = 0\n"
        "        return df\n")

# Mismo payload que BacktestingController::executeAjax (valores no por defecto para detectar pérdidas)
PAYLOAD = {
    'strategy': 'T', 'strategy_code': CODE, 'strategy_config': {'period': 33, 'sl_pct': 9.9},
    'symbol': 'LINKUSDT', 'interval': '15', 'initial_balance': 5000.0, 'risk_per_trade_pct': 0.7,
    'commission_pct': 0.04, 'slippage_pct': 0.07, 'sl_pct': 1.1, 'tp_pct': 2.2, 'be_pct': 1.7,
    'max_duration': 36, 'max_duration_profit': True, 'close_on_opposite': True, 'regime_filter': True,
    'regime_adx_trending': 27.0, 'regime_adx_ranging': 18.0, 'regime_ambiguous_as': 'NO_OPERAR',
    'walk_forward': True, 'n_windows': 5, 'monthly_breakdown': True,
    'trailing_mode': 'atr', 'trailing_distance_pct': 1.5, 'trailing_activation_buffer_pct': 0.2,
    'trailing_atr_mult': 2.5, 'macro_trend_filter': True, 'volume_filter': True, 'volume_filter_period': 30,
    'volume_filter_mult': 1.4, 'volatility_protection_mode': 'widen', 'volatility_atr_multiplier': 3.0,
    'volatility_widen_pct': 0.8, 'start_date': '2025-01-01', 'end_date': '2026-09-30',
}
SKIP = {'params'}  # real añade instance.params (dict de entrada), no es un parámetro de operación
fails = 0


def state(s) -> dict:
    return {k: v for k, v in vars(s).items() if k not in SKIP}


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


bt = load_strategy(BacktestRequest(**PAYLOAD))
paper = build_strategy({**PAYLOAD})  # paper: config_params + symbol/interval de la config
real = instantiate_strategy(SubscriptionPayload(
    subscription_id=1, user_id=1, broker_account_id=1, strategy='T',
    symbol=PAYLOAD['symbol'], interval=PAYLOAD['interval'], config_params=dict(PAYLOAD)))

b, p, r = state(bt), state(paper), state(real)
diff_bp = {k: (b.get(k), p.get(k)) for k in set(b) | set(p) if b.get(k) != p.get(k)}
diff_pr = {k: (p.get(k), r.get(k)) for k in set(p) | set(r) if p.get(k) != r.get(k)}
check('backtest == paper (todos los atributos)', not diff_bp, diff_bp)
check('paper == real (todos los atributos)', not diff_pr, diff_pr)
check('parámetro propio de la estrategia llega (period=33)', getattr(bt, 'period', None) == 33, getattr(bt, 'period', None))
check('la UI manda sobre strategy_config (sl_pct 1.1, no 9.9)', bt.sl_pct == 1.1, bt.sl_pct)
check('slippage de la UI en la estrategia', bt.slippage_pct == 0.07, bt.slippage_pct)
check('allowed_regimes de la clase', bt.allowed_regimes == ['RANGING'], bt.allowed_regimes)

try:
    load_strategy(BacktestRequest(**{**PAYLOAD, 'strategy_code': ''}))
    check('sin código -> error explícito', False, 'no lanzó error')
except ValueError as e:
    check('sin código -> error explícito', 'strategy_code' in str(e), str(e))

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')

"""
Fase 2 · tramo Python. Toma el payload que Laravel envió (capturado por backtest_payload_chain_test.php)
y verifica que cada valor llega intacto a la estrategia y al motor, por el MISMO camino que /v1/backtest/run
(BacktestRequest → strategy_params → build_strategy → BacktestEngine). Además revisa la precedencia
de los parámetros escritos en el JSON de la estrategia. No toca la base de datos ni ejecuta un backtest.

Uso (desde python-engine/): venv/bin/python ../tests/Forensic/backtest_payload_chain_test.py [/tmp/tr2_bt_payload.json]
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from api.v1.backtest import BacktestRequest, load_strategy, strategy_params  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402

fails = 0


def check(name: str, ok: bool, detail: str = '') -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + detail if detail else ''}")


payload = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/tr2_bt_payload.json').read_text())
req = BacktestRequest(**payload)

# Mismo orden que run_backtest: construir la estrategia, fijar slippage, crear el motor
strategy = load_strategy(req)
strategy.slippage_pct = float(req.slippage_pct)
dummy = pd.DataFrame({'time': pd.date_range('2026-01-01', periods=3, freq='15min', tz='UTC'),
                      'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0, 'volume': 1.0})
engine = BacktestEngine(strategy=strategy, df=dummy, initial_balance=req.initial_balance,
                        risk_per_trade_pct=req.risk_per_trade_pct, trade_from=None)

# 1) Cada campo de la UI llega a la estrategia con el valor exacto del payload
ui_fields = ['symbol', 'interval', 'sl_pct', 'tp_pct', 'be_pct', 'max_duration', 'regime_filter', 'regime_adx_trending',
             'regime_adx_ranging', 'regime_ambiguous_as', 'volume_filter', 'volume_filter_period', 'volume_filter_mult',
             'macro_trend_filter', 'trailing_mode', 'trailing_distance_pct', 'trailing_atr_mult',
             'trailing_activation_buffer_pct', 'max_duration_profit', 'close_on_opposite', 'commission_pct', 'slippage_pct']
for f in ui_fields:
    got, exp = getattr(strategy, f, '<<ausente>>'), payload.get(f)
    same = (abs(float(got) - float(exp)) < 1e-12) if isinstance(exp, float) and not isinstance(exp, bool) else got == exp
    check(f"estrategia.{f}", same, '' if same else f"estrategia={got!r} payload={exp!r}")

# 2) Valores que usa el motor
check('motor.initial_balance', engine.initial_balance == payload['initial_balance'], str(engine.initial_balance))
check('motor.risk_per_trade_pct', engine.risk_per_trade_pct == payload['risk_per_trade_pct'], str(engine.risk_per_trade_pct))
check('motor.commission_rate = comisión / 100', abs(engine.commission_rate - payload['commission_pct'] / 100) < 1e-15,
      str(engine.commission_rate))
check('motor.slippage_rate = slippage / 100', abs(engine.slippage_rate - payload['slippage_pct'] / 100) < 1e-15,
      str(engine.slippage_rate))
check('motor.interval_minutes coincide con el intervalo', engine.interval_minutes == {'1': 1, '5': 5, '15': 15, '60': 60, '240': 240, 'D': 1440}.get(payload['interval']),
      str(engine.interval_minutes))

# 3) Parámetros del JSON de la estrategia: si chocan con un campo de la UI gana la UI; los propios llegan intactos
cfg = payload.get('strategy_config') or {}
merged = dict(cfg)
merged.update(strategy_params(req))  # mismo orden que loader.build_strategy
for k, v in cfg.items():
    if k in ui_fields:
        check(f"JSON '{k}'={v} lo pisa la UI ({payload[k]})", getattr(strategy, k) == payload[k], f"estrategia={getattr(strategy, k)!r}")
    elif k not in BacktestRequest.model_fields:
        check(f"JSON '{k}'={v} llega a la estrategia", merged.get(k) == v and getattr(strategy, k, v) == v,
              f"recibe {merged.get(k)!r}")

# 4) Opciones que NO están en la UI y que el usuario solo puede fijar en el JSON: ¿se respetan?
probe = dict(payload)
probe['strategy_config'] = dict(cfg, allow_short=False, hour_filter=True, hour_filter_start=9, weekend_filter=True,
                                exit_on_opposite=True, max_leverage=2.0, tp2_pct=4.4, blocked_days=[5, 6])
s2 = load_strategy(BacktestRequest(**probe))
for k, v in [('allow_short', False), ('hour_filter', True), ('hour_filter_start', 9), ('weekend_filter', True),
             ('exit_on_opposite', True), ('max_leverage', 2.0), ('tp2_pct', 4.4), ('blocked_days', [5, 6])]:
    got = getattr(s2, k, '<<ausente>>')
    check(f"JSON '{k}'={v!r} (no está en la UI) se respeta", got == v,
          '' if got == v else f"la estrategia usa {got!r}: el valor por defecto del request pisa al JSON")

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

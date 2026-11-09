"""
N-10: todos los flags booleanos de una estrategia se normalizan con as_flag. Desde un JSON pueden venir como texto
('false', '0', 'off', '') y bool('false') es True: el filtro quedaba ACTIVADO sin que nadie lo pidiera. Paper y Real
construyen la estrategia desde los params guardados (la API de backtest ya los valida con Pydantic).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/flag_normalization_test.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())   # python-engine/

from backtesting.strategies.base_strategy import BaseStrategy  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class S(BaseStrategy):
    def generate_signals(self, df):
        out = df.copy()
        out['signal'] = 1
        return out


FLAGS = {   # flag -> valor por defecto
    'regime_filter': True, 'volume_filter': False, 'macro_trend_filter': False, 'btc_trend_filter': False,
    'hour_filter': False, 'weekend_filter': False, 'max_duration_profit': False,
    'close_on_opposite': False, 'exit_on_opposite': False, 'allow_short': True,
}
FALSY = ['false', 'False', '0', 'off', 'no', '', False, 0]
TRUTHY = ['true', 'True', '1', 'on', 'yes', True, 1]

for flag, default in FLAGS.items():
    bad_f = [v for v in FALSY if getattr(S({'symbol': 'ETHUSDT', flag: v}), flag) is not False]
    bad_t = [v for v in TRUTHY if getattr(S({'symbol': 'ETHUSDT', flag: v}), flag) is not True]
    check(f'F: {flag}: textos falsos -> False', not bad_f, bad_f)
    check(f'T: {flag}: textos verdaderos -> True', not bad_t, bad_t)
    check(f'D: {flag}: ausente o null -> {default}',
          getattr(S({'symbol': 'ETHUSDT'}), flag) is default and getattr(S({'symbol': 'ETHUSDT', flag: None}), flag) is default)

# Efecto: con 'false' en texto los filtros NO actúan
sat = pd.DataFrame({'time': pd.to_datetime(['2026-11-07 03:00', '2026-11-07 12:00']),   # sábado, 03:00 y 12:00 UTC
                    'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0, 'volume': 1.0, 'signal': [1, 1]})
s = S({'symbol': 'ETHUSDT', 'weekend_filter': 'false', 'hour_filter': '0'})
out = s.apply_hour_filter(s.apply_weekend_filter(sat))
check("E1: weekend_filter='false' y hour_filter='0' -> las señales del sábado a las 03:00 siguen",
      list(out['signal']) == [1, 1], list(out['signal']))
s = S({'symbol': 'ETHUSDT', 'weekend_filter': 'true'})
check("E2: weekend_filter='true' -> las anula (el filtro sí funciona)", list(s.apply_weekend_filter(sat)['signal']) == [0, 0],
      list(s.apply_weekend_filter(sat)['signal']))
s = S({'symbol': 'ETHUSDT', 'btc_trend_filter': 'false'})
check("E3: btc_trend_filter='false' en una altcoin -> el filtro de BTC no aplica", s.btc_filter_applies() is False)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

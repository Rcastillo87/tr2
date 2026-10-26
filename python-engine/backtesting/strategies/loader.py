"""
Construcción de la instancia de estrategia a partir de un dict de parámetros.

Fuente única para paper (señales y gestión de posiciones abiertas): mismo
criterio que el backtest. Si params trae 'strategy_code', se compila la clase
dinámica (una sola vez por código, cacheada); sin código es un error explícito.
'strategy_config' (parámetros propios de la estrategia) queda por debajo de los
parámetros de operación (sl_pct, trailing, filtros...), igual que en el backtest.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from backtesting.strategies.base_strategy import BaseStrategy


@lru_cache(maxsize=64)
def _compile_strategy_class(code: str) -> type[BaseStrategy]:
    namespace = {"BaseStrategy": BaseStrategy, "pd": pd, "np": np}
    exec(code, namespace)  # noqa: S102 - código de estrategia guardado por el administrador
    for name, value in namespace.items():
        if isinstance(value, type) and name != 'BaseStrategy' and issubclass(value, BaseStrategy):
            return value
    raise ValueError("El código de la estrategia no contiene una clase que herede de BaseStrategy.")


def build_strategy(params: dict) -> BaseStrategy:
    merged = dict(params.get('strategy_config') or {})
    merged.update(params)
    code = (params.get('strategy_code') or '').strip()
    if not code:
        raise ValueError("La configuración no trae strategy_code: no hay estrategia que ejecutar.")
    cls = _compile_strategy_class(code)
    return cls(merged)

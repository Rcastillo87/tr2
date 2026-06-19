"""
Base Strategy V2
Clase base que todas las estrategias deben heredar.
"""
import pandas as pd
from abc import ABC, abstractmethod
class BaseStrategy(ABC):
    """
    Clase base para todas las estrategias de trading.
    Cada estrategia hija debe implementar:
        - generate_signals(df) -> pd.DataFrame con columna 'signal' (1=long, -1=short, 0=nada)
    Parámetros comunes configurables por estrategia:
        - symbol:       símbolo a operar (BTCUSDT, ETHUSDT, SOLUSDT)
        - interval:     timeframe (1, 5, 15, 60)
        - sl_pct:       stop loss en % (ej. 1.5)
        - tp_pct:       take profit en % (ej. 3.0) — usado como TP unico, o TP1 si tp2_pct esta definido
        - tp2_pct:      take profit secundario opcional en % (ej. 3.5). Si se define,
                        el motor evalua TP2 con prioridad sobre TP1 (igual al sistema
                        TP1/TP2 de la estrategia E-13 original en V1).
        - be_pct:       break-even se activa cuando ganancia llega a X% (ej. 0.8)
        - max_duration: máximo de velas antes de cierre por tiempo
        - regime_filter: si True, solo opera en el régimen permitido por la estrategia
    """
    name: str = "base"
    allowed_regimes: list[str] = ["TRENDING", "RANGING", "VOLATILE"]
    def __init__(self, params: dict):
        self.symbol       = params.get('symbol', 'BTCUSDT')
        self.interval     = params.get('interval', '60')
        self.sl_pct       = params.get('sl_pct', 1.5)
        self.tp_pct       = params.get('tp_pct', 3.0)
        self.tp2_pct      = params.get('tp2_pct', None)  # opcional, None = sin TP2
        self.be_pct       = params.get('be_pct', 0.8)
        self.max_duration = params.get('max_duration', 24)
        self.regime_filter = params.get('regime_filter', True)
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recibe un DataFrame con columnas OHLCV + indicadores calculados.
        Debe retornar el mismo DataFrame con una columna 'signal' agregada:
            1  -> señal de compra (long)
           -1  -> señal de venta (short)
            0  -> sin señal
        """
        pass
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara el DataFrame antes de generar señales.
        Calcula los indicadores necesarios para la estrategia.
        Sobreescribir en la estrategia hija si se necesitan indicadores adicionales.
        """
        return df
    def should_operate(self, regime: str) -> bool:
        """
        Verifica si la estrategia debe operar dado el régimen actual.
        """
        if not self.regime_filter:
            return True
        return regime in self.allowed_regimes
    def calculate_sl_tp(self, entry_price: float, side: str) -> tuple[float, float]:
        """
        Calcula Stop Loss y Take Profit (TP1) basado en el precio de entrada.
        """
        if side == 'long':
            sl = entry_price * (1 - self.sl_pct / 100)
            tp = entry_price * (1 + self.tp_pct / 100)
        else:
            sl = entry_price * (1 + self.sl_pct / 100)
            tp = entry_price * (1 - self.tp_pct / 100)
        return round(sl, 8), round(tp, 8)

    def calculate_tp2(self, entry_price: float, side: str) -> float | None:
        """
        Calcula el Take Profit secundario (TP2), si la estrategia lo define.
        Retorna None si tp2_pct no esta configurado (sin TP2, comportamiento
        identico al de una sola estrategia con un unico TP).
        """
        if self.tp2_pct is None:
            return None

        if side == 'long':
            return round(entry_price * (1 + self.tp2_pct / 100), 8)
        else:
            return round(entry_price * (1 - self.tp2_pct / 100), 8)

    def calculate_breakeven(self, entry_price: float, side: str) -> float:
        """
        Calcula el precio al que se activa el break-even.
        """
        if side == 'long':
            return entry_price * (1 + self.be_pct / 100)
        else:
            return entry_price * (1 - self.be_pct / 100)

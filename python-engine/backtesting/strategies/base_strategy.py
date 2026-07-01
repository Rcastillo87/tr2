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

    Parámetros comunes configurables:
        - symbol, interval, sl_pct, tp_pct (TP1), be_pct, max_duration, regime_filter

    Take Profit escalonado (opcional, hasta 4 niveles):
        - tp2_pct, tp3_pct, tp4_pct: niveles adicionales. El motor evalua con
          prioridad el nivel mas favorable alcanzado (TP4 > TP3 > TP2 > TP1).
          None = nivel no usado.

    Trailing Stop (opcional, mode: None | "fixed" | "stepped"):
        - trailing_mode:        None (desactivado) | "fixed" | "stepped"
        - trailing_distance_pct: distancia fija (%) para mode="fixed"
        - trailing_steps:       lista de [gain_pct, new_sl_pct] para mode="stepped"
                                 ej. [[1.0, 0.0], [2.0, 0.5], [3.0, 1.5]]
                                 significa: con +1% gan., SL a 0% (breakeven);
                                 con +2% gan., SL a +0.5%; con +3% gan., SL a +1.5%

    Proteccion por volatilidad (opcional, mode: None | "close" | "widen"):
        - volatility_protection_mode: None | "close" | "widen"
        - volatility_atr_multiplier:  umbral, ATR actual > avg * multiplier dispara la accion
        - volatility_widen_pct:       cuanto ampliar el SL (en puntos %) si mode="widen"
    """
    name: str = "base"
    allowed_regimes: list[str] = ["TRENDING", "RANGING", "VOLATILE"]

    def __init__(self, params: dict):
        self.symbol       = params.get('symbol', 'BTCUSDT')
        self.interval     = params.get('interval', '60')
        self.sl_pct       = params.get('sl_pct', 1.5)
        self.tp_pct       = params.get('tp_pct', 3.0)
        self.be_pct       = params.get('be_pct', 0.8)
        self.max_duration = params.get('max_duration', 24)
        self.regime_filter = params.get('regime_filter', True)
        # Filtro de volumen — solo opera si el volumen actual > promedio * multiplicador
        self.volume_filter          = params.get('volume_filter', False)
        self.volume_filter_period   = params.get('volume_filter_period', 20)
        self.volume_filter_mult     = params.get('volume_filter_mult', 1.2)
        # Filtro horario — solo opera en horas de alta liquidez
        self.hour_filter            = params.get('hour_filter', False)
        self.hour_filter_start      = params.get('hour_filter_start', 7)   # UTC
        self.hour_filter_end        = params.get('hour_filter_end', 21)    # UTC
        # Filtro fin de semana — bloquea sabado y domingo
        self.weekend_filter         = params.get('weekend_filter', False)
        # Bloquear horas especificas (lista de horas UTC 0-23)
        self.blocked_hours          = params.get('blocked_hours', [])
        # Bloquear dias especificos (lista: 0=Lun,1=Mar,...,6=Dom)
        self.blocked_days           = params.get('blocked_days', [])
        # Filtro fin de semana — bloquea sabado y domingo
        self.weekend_filter         = params.get('weekend_filter', False)
        # Bloquear horas especificas (lista de horas UTC 0-23)
        self.blocked_hours          = params.get('blocked_hours', [])
        # Bloquear dias especificos (lista: 0=Lun,1=Mar,...,6=Dom)
        self.blocked_days           = params.get('blocked_days', [])

        # Take profit escalonado — hasta 4 niveles, todos opcionales
        self.tp2_pct = params.get('tp2_pct', None)
        self.tp3_pct = params.get('tp3_pct', None)
        self.tp4_pct = params.get('tp4_pct', None)

        # Trailing stop
        self.trailing_mode         = params.get('trailing_mode', None)  # None | "fixed" | "stepped"
        self.trailing_distance_pct = params.get('trailing_distance_pct', 1.0)
        self.trailing_steps        = params.get('trailing_steps', [])  # [[gain_pct, new_sl_pct], ...]

        # Proteccion por volatilidad
        self.volatility_protection_mode = params.get('volatility_protection_mode', None)  # None | "close" | "widen"
        self.volatility_atr_multiplier  = params.get('volatility_atr_multiplier', 2.5)
        self.volatility_widen_pct       = params.get('volatility_widen_pct', 1.0)

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

    def apply_volume_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra señales cuando el volumen es menor al promedio * multiplicador.
        Si volume_filter=False no hace nada.
        """
        if not self.volume_filter:
            return df
        period = self.volume_filter_period
        mult   = self.volume_filter_mult
        df = df.copy()
        df['volume_ma'] = df['volume'].rolling(window=period).mean()
        # Marcar velas donde el volumen es insuficiente
        df['volume_ok'] = df['volume'] >= df['volume_ma'] * mult
        # Anular señales donde el volumen es insuficiente
        if 'signal' in df.columns:
            df.loc[~df['volume_ok'], 'signal'] = 0
        return df

    def apply_hour_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra señales fuera del horario configurado (UTC).
        Si hour_filter=False no hace nada.
        """
        if not self.hour_filter:
            return df
        df = df.copy()
        hours = pd.to_datetime(df['time']).dt.hour
        in_range = (hours >= self.hour_filter_start) & (hours < self.hour_filter_end)
        if 'signal' in df.columns:
            df.loc[~in_range, 'signal'] = 0
        return df

    def apply_weekend_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Bloquea señales en sabado (5) y domingo (6) UTC.
        Si weekend_filter=False no hace nada.
        """
        if not self.weekend_filter:
            return df
        df = df.copy()
        weekday = pd.to_datetime(df['time']).dt.dayofweek
        is_weekend = weekday >= 5
        if 'signal' in df.columns:
            df.loc[is_weekend, 'signal'] = 0
        return df

    def apply_blocked_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """Bloquea señales en horas UTC especificas."""
        if not self.blocked_hours:
            return df
        df = df.copy()
        hours = pd.to_datetime(df['time']).dt.hour
        blocked = hours.isin(self.blocked_hours)
        if 'signal' in df.columns:
            df.loc[blocked, 'signal'] = 0
        return df

    def apply_blocked_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """Bloquea señales en dias de la semana especificos (0=Lun ... 6=Dom)."""
        if not self.blocked_days:
            return df
        df = df.copy()
        weekday = pd.to_datetime(df['time']).dt.dayofweek
        blocked = weekday.isin(self.blocked_days)
        if 'signal' in df.columns:
            df.loc[blocked, 'signal'] = 0
        return df

    def should_operate(self, regime: str) -> bool:
        """Verifica si la estrategia debe operar dado el régimen actual."""
        if not self.regime_filter:
            return True
        return regime in self.allowed_regimes

    def calculate_sl_tp(self, entry_price: float, side: str) -> tuple[float, float]:
        """Calcula Stop Loss y Take Profit (TP1) basado en el precio de entrada."""
        if side == 'long':
            sl = entry_price * (1 - self.sl_pct / 100)
            tp = entry_price * (1 + self.tp_pct / 100)
        else:
            sl = entry_price * (1 + self.sl_pct / 100)
            tp = entry_price * (1 - self.tp_pct / 100)
        return round(sl, 8), round(tp, 8)

    def calculate_tp_levels(self, entry_price: float, side: str) -> dict:
        """
        Calcula todos los niveles de TP definidos (TP1 a TP4).
        Retorna dict {'tp1': float, 'tp2': float|None, 'tp3': float|None, 'tp4': float|None}
        """
        levels = {}
        pct_map = {'tp1': self.tp_pct, 'tp2': self.tp2_pct, 'tp3': self.tp3_pct, 'tp4': self.tp4_pct}

        for key, pct in pct_map.items():
            if pct is None:
                levels[key] = None
                continue
            if side == 'long':
                levels[key] = round(entry_price * (1 + pct / 100), 8)
            else:
                levels[key] = round(entry_price * (1 - pct / 100), 8)

        return levels

    def calculate_tp2(self, entry_price: float, side: str) -> float | None:
        """Retrocompatibilidad: calcula solo TP2."""
        if self.tp2_pct is None:
            return None
        if side == 'long':
            return round(entry_price * (1 + self.tp2_pct / 100), 8)
        else:
            return round(entry_price * (1 - self.tp2_pct / 100), 8)

    def calculate_breakeven(self, entry_price: float, side: str) -> float:
        """Calcula el precio al que se activa el break-even."""
        if side == 'long':
            return entry_price * (1 + self.be_pct / 100)
        else:
            return entry_price * (1 - self.be_pct / 100)

    def calculate_trailing_sl(self, entry_price: float, side: str, current_price: float,
                               current_sl: float) -> float:
        """
        Calcula el nuevo SL segun el modo de trailing configurado.
        Solo mueve el SL a favor del trade, nunca lo retrocede.
        Si trailing_mode es None, retorna current_sl sin cambios.
        """
        return calculate_trailing_sl_standalone(
            self.trailing_mode, self.trailing_distance_pct, self.trailing_steps,
            entry_price, side, current_price, current_sl,
        )

    def check_volatility_protection(self, current_sl: float, side: str,
                                     current_atr: float, avg_atr: float) -> dict:
        """
        Evalua la proteccion por volatilidad.
        Retorna dict: {'action': None|'close'|'widen', 'new_sl': float|None}
        """
        if self.volatility_protection_mode is None or avg_atr == 0:
            return {'action': None, 'new_sl': None}

        if current_atr <= avg_atr * self.volatility_atr_multiplier:
            return {'action': None, 'new_sl': None}

        if self.volatility_protection_mode == 'close':
            return {'action': 'close', 'new_sl': None}

        if self.volatility_protection_mode == 'widen':
            if side == 'long':
                new_sl = current_sl * (1 - self.volatility_widen_pct / 100)
            else:
                new_sl = current_sl * (1 + self.volatility_widen_pct / 100)
            return {'action': 'widen', 'new_sl': round(new_sl, 8)}

        return {'action': None, 'new_sl': None}


def calculate_trailing_sl_standalone(trailing_mode, trailing_distance_pct,
                                      trailing_steps, entry_price, side,
                                      current_price, current_sl):
    """
    Version standalone (sin instancia de estrategia) de calculate_trailing_sl,
    para modulos que no necesitan una instancia completa de estrategia solo
    para este calculo (ej. real_trader.py). La logica es identica a
    BaseStrategy.calculate_trailing_sl, que delega aca para no duplicarla.
    """
    if trailing_mode is None:
        return current_sl

    if side == 'long':
        gain_pct = (current_price - entry_price) / entry_price * 100
    else:
        gain_pct = (entry_price - current_price) / entry_price * 100

    if gain_pct <= 0:
        return current_sl

    new_sl = current_sl

    if trailing_mode == 'fixed':
        if side == 'long':
            candidate = current_price * (1 - trailing_distance_pct / 100)
            new_sl = max(current_sl, candidate)
        else:
            candidate = current_price * (1 + trailing_distance_pct / 100)
            new_sl = min(current_sl, candidate)

    elif trailing_mode == 'stepped':
        applicable = [s for s in (trailing_steps or []) if gain_pct >= s[0]]
        if applicable:
            best_step = max(applicable, key=lambda s: s[0])
            sl_pct_from_entry = best_step[1]

            if side == 'long':
                candidate = entry_price * (1 + sl_pct_from_entry / 100)
                new_sl = max(current_sl, candidate)
            else:
                candidate = entry_price * (1 - sl_pct_from_entry / 100)
                new_sl = min(current_sl, candidate)

    return round(new_sl, 8)

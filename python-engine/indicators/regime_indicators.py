"""
Indicadores para Market Regime Detector
ADX, ATR, Bollinger Band Width
"""

import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range"""
    high  = df['high']
    low   = df['low']
    close = df['close']

    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    return atr


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index"""
    high  = df['high']
    low   = df['low']
    close = df['close']

    prev_high  = high.shift(1)
    prev_low   = low.shift(1)
    prev_close = close.shift(1)

    plus_dm  = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    # Si plus_dm <= minus_dm, plus_dm = 0 (y viceversa)
    plus_dm  = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    plus_di  = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()

    return adx


def calculate_bb_width(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """Bollinger Band Width — distancia entre banda superior e inferior, normalizada por el precio"""
    close = df['close']

    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()

    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)

    width = (upper - lower) / sma * 100  # en porcentaje

    return width


def classify_regime(adx: float, atr: float, atr_avg: float, bb_width: float, bb_width_avg: float,
                     trending_threshold: float = 25, ranging_threshold: float = 20,
                     ambiguous_as: str = "RANGING") -> str:
    """
    Clasifica el regimen de mercado:
      - VOLATILE: ATR muy por encima del promedio historico
      - TRENDING: ADX por encima de trending_threshold (tendencia fuerte)
      - RANGING: ADX por debajo de ranging_threshold + BB estrecho (mercado lateral)
      - Zona ambigua: ningun caso anterior aplica (ej. ADX entre ambos
        umbrales, o ADX bajo pero BB ancho) - se clasifica como
        ambiguous_as ("RANGING" por defecto, preserva el comportamiento
        historico; "TRENDING" para estrategias que prefieren ser cautelosas
        ante la incertidumbre, como las de reversion a la media).

    trending_threshold / ranging_threshold / ambiguous_as son configurables
    por estrategia (ver regime_adx_trending / regime_adx_ranging /
    regime_ambiguous_as en base_strategy.py).
    """
    # Volatilidad extrema tiene prioridad sobre todo
    if atr > atr_avg * 1.8:
        return "VOLATILE"
    if adx > trending_threshold:
        return "TRENDING"
    if adx < ranging_threshold and bb_width < bb_width_avg:
        return "RANGING"
    # Zona ambigua - ni TRENDING confirmado ni RANGING confirmado
    return ambiguous_as

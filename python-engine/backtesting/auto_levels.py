"""
D-45 (p92, p93): SL, TP y break-even automáticos, opcionales y por separado. Único cálculo para backtest, Paper y Real.

Stop Loss (`sl_level_mode`):
    'fixed' (default)  el sl_pct de la config (o el SL que proponga la estrategia), como siempre
    'atr'              SL % = sl_atr_mult × ATR(14) / cierre × 100, acotado a [sl_min_pct, sl_max_pct]
Take Profit (`tp_level_mode`):
    'fixed' (default)  el tp_pct de la config
    'r'                TP % = tp_r_mult × el SL de la operación (automático, de la estrategia o fijo)
    'atr'              TP % = tp_atr_mult × ATR(14) / cierre × 100
Break-even: con SL 'atr', be_r_mult × SL (en «veces el SL»); si no, el be_pct fijo.

Todo sobre la vela de la señal (cerrada). Se escribe como `signal_sl_pct` / `signal_tp_pct` / `signal_be_pct`, el mismo
canal por el que una estrategia propone su SL; los % se aplican al precio de entrada real. Orden del SL (D-45 b):
automático → el de la estrategia → fijo. Sin ATR (calentamiento) cada nivel usa su respaldo fijo.

Vuelta atrás (D-49): modos ausentes o 'fixed' = como antes. `SLTP_AUTO_ENABLED=false` en python-engine/.env apaga los
modos en todo el sistema (las posiciones Real abiertas conservan su SL/TP en Bybit).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from indicators.regime_indicators import calculate_atr

load_dotenv(Path(__file__).resolve().parents[1] / '.env')   # el buscador corre como proceso aparte

ATR_PERIOD = 14
PCT_DECIMALS = 6   # los tres motores redondean igual: el ATR (Wilder) con 500 velas difiere en ~1e-16
LEVEL_COLS = ('signal_sl_pct', 'signal_tp_pct', 'signal_be_pct')
SL_MODES = ('fixed', 'atr')
TP_MODES = ('fixed', 'r', 'atr')
DEFAULTS = dict(sl_atr_mult=2.0, tp_r_mult=2.0, tp_atr_mult=4.0, be_r_mult=1.0, sl_min_pct=0.8, sl_max_pct=5.0)


def enabled() -> bool:
    return os.getenv('SLTP_AUTO_ENABLED', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


def modes(params: dict) -> tuple[str, str]:
    """(sl_level_mode, tp_level_mode) de unos parámetros. 'sl_tp_mode': 'atr' (p92) = SL automático + TP veces el SL."""
    sl, tp = params.get('sl_level_mode'), params.get('tp_level_mode')
    if params.get('sl_tp_mode') == 'atr':
        sl, tp = sl or 'atr', tp or 'r'
    return (sl if sl in SL_MODES else 'fixed'), (tp if tp in TP_MODES else 'fixed')


def is_auto(strategy) -> bool:
    return enabled() and (getattr(strategy, 'sl_level_mode', 'fixed') != 'fixed' or getattr(strategy, 'tp_level_mode', 'fixed') != 'fixed')


def _atr_pct(df: pd.DataFrame) -> np.ndarray:
    atr = calculate_atr(df, ATR_PERIOD).to_numpy(dtype=float)
    atr[:ATR_PERIOD] = np.nan   # sin 14 velas el ATR no existe
    with np.errstate(divide='ignore', invalid='ignore'):
        pct = atr / df['close'].to_numpy(dtype=float) * 100
    pct[~(np.isfinite(pct) & (pct > 0))] = np.nan
    return pct


def apply(df: pd.DataFrame, strategy) -> pd.DataFrame:
    """Columnas de niveles por vela. Sin modos automáticos el df no cambia (mismo objeto)."""
    if not is_auto(strategy) or df is None or len(df) == 0:
        return df
    n = len(df)
    atr_pct = _atr_pct(df)
    out = df.copy()
    base = out['signal_sl_pct'].to_numpy(dtype=float) if 'signal_sl_pct' in out.columns else np.full(n, np.nan)
    nan = np.full(n, np.nan)

    sl_auto = nan
    if strategy.sl_level_mode == 'atr':
        lo, hi = sorted((float(strategy.sl_min_pct), float(strategy.sl_max_pct)))
        sl_auto = np.round(np.clip(float(strategy.sl_atr_mult) * atr_pct, lo, hi), PCT_DECIMALS)   # NaN se conserva
    sl_signal = np.where(np.isfinite(sl_auto), sl_auto, base)
    out['signal_sl_pct'] = sl_signal

    if strategy.tp_level_mode == 'r':
        sl_used = np.where(np.isfinite(sl_signal), sl_signal, float(strategy.sl_pct))
        out['signal_tp_pct'] = np.round(sl_used * float(strategy.tp_r_mult), PCT_DECIMALS)
    elif strategy.tp_level_mode == 'atr':
        out['signal_tp_pct'] = np.round(float(strategy.tp_atr_mult) * atr_pct, PCT_DECIMALS)
    else:
        out['signal_tp_pct'] = nan
    out['signal_be_pct'] = np.round(sl_auto * float(strategy.be_r_mult), PCT_DECIMALS)   # SL fijo: sl_auto vacío = BE fijo
    return out


def row_levels(row) -> dict:
    """{'sl': %, 'tp': %, 'be': %} de una vela (None = el de la estrategia o el fijo)."""
    out = {}
    for key, col in zip(('sl', 'tp', 'be'), LEVEL_COLS):
        v = row.get(col) if hasattr(row, 'get') else None
        out[key] = float(v) if v is not None and pd.notna(v) else None
    return out

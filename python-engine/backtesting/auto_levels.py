"""
D-45 (p92): SL, TP y break-even automáticos, opcionales, por ATR. Único cálculo para backtest, Paper y Real.

Con `sl_tp_mode = 'atr'`, en la vela de la señal (cerrada):
    SL % = sl_atr_mult × ATR(14) / cierre × 100, acotado a [sl_min_pct, sl_max_pct]
    TP % = tp_r_mult × SL %          BE % = be_r_mult × SL %   (BE en «veces el SL»)
Se escriben como `signal_sl_pct` / `signal_tp_pct` / `signal_be_pct`, el mismo canal por el que una estrategia propone
su SL. Orden (D-45 b): automático → SL propuesto por la estrategia → fijo de la config. Sin ATR (calentamiento) la vela
queda con lo de la estrategia o el fijo. Los % se aplican al precio de entrada real, igual que el SL de la estrategia.

Vuelta atrás (D-49): `sl_tp_mode` ausente o 'fixed' = como antes (default). `SLTP_AUTO_ENABLED=false` en
python-engine/.env apaga el modo en todo el sistema (las posiciones Real abiertas conservan su SL/TP en Bybit).
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
DEFAULTS = dict(sl_atr_mult=2.0, tp_r_mult=2.0, be_r_mult=1.0, sl_min_pct=0.8, sl_max_pct=5.0)


def enabled() -> bool:
    return os.getenv('SLTP_AUTO_ENABLED', 'true').strip().lower() not in ('0', 'false', 'no', 'off')


def is_auto(strategy) -> bool:
    return getattr(strategy, 'sl_tp_mode', None) == 'atr' and enabled()


def apply(df: pd.DataFrame, strategy) -> pd.DataFrame:
    """Columnas de niveles por vela (sin modo automático o sin ATR, el df no cambia en esas velas)."""
    if not is_auto(strategy) or df is None or len(df) == 0:
        return df
    lo, hi = float(strategy.sl_min_pct), float(strategy.sl_max_pct)
    lo, hi = min(lo, hi), max(lo, hi)
    atr = calculate_atr(df, ATR_PERIOD).to_numpy(dtype=float)
    atr[:ATR_PERIOD] = np.nan   # sin 14 velas el ATR no existe
    close = df['close'].to_numpy(dtype=float)
    with np.errstate(divide='ignore', invalid='ignore'):
        raw = float(strategy.sl_atr_mult) * atr / close * 100
    sl = np.round(np.clip(raw, lo, hi), PCT_DECIMALS)
    valid = np.isfinite(raw) & (raw > 0)
    out = df.copy()
    base = out['signal_sl_pct'].to_numpy(dtype=float) if 'signal_sl_pct' in out.columns else np.full(len(out), np.nan)
    out['signal_sl_pct'] = np.where(valid, sl, base)
    out['signal_tp_pct'] = np.where(valid, np.round(sl * float(strategy.tp_r_mult), PCT_DECIMALS), np.nan)
    out['signal_be_pct'] = np.where(valid, np.round(sl * float(strategy.be_r_mult), PCT_DECIMALS), np.nan)
    return out


def row_levels(row) -> dict:
    """{'sl': %, 'tp': %, 'be': %} de una vela (None = usar el de la estrategia o el fijo)."""
    out = {}
    for key, col in zip(('sl', 'tp', 'be'), LEVEL_COLS):
        v = row.get(col) if hasattr(row, 'get') else None
        out[key] = float(v) if v is not None and pd.notna(v) else None
    return out

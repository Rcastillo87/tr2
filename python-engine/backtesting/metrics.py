"""
Métricas de evaluación para Backtesting y Paper Trading V2
"""

import numpy as np
import pandas as pd


def calculate_metrics(trades: list[dict], initial_balance: float = 10000.0) -> dict:
    """
    Calcula métricas de rendimiento a partir de una lista de trades cerrados.

    Cada trade debe tener al menos:
        - pnl (float)        -> ganancia/pérdida en moneda
        - pnl_pct (float)    -> ganancia/pérdida en %
        - regime (str)       -> régimen de mercado al momento de entrada
    """

    if not trades:
        return _empty_metrics()

    df = pd.DataFrame(trades)

    total_trades = len(df)
    wins   = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]

    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0.0

    gross_profit = wins['pnl'].sum()
    gross_loss   = abs(losses['pnl'].sum())

    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0

    avg_win  = wins['pnl'].mean() if len(wins) > 0 else 0.0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0.0

    # Expectancy: ganancia promedio esperada por operación
    expectancy = (df['pnl'].mean())

    # Equity curve para Sharpe y Drawdown
    equity = initial_balance + df['pnl'].cumsum()
    equity_with_start = pd.concat([pd.Series([initial_balance]), equity], ignore_index=True)

    returns = equity_with_start.pct_change().dropna()

    # Sharpe Ratio (anualizado asumiendo ~252 periodos de "trading" — aquí por trade)
    sharpe_ratio = 0.0
    returns_std = returns.std()
    if returns_std > 1e-8:  # evita división por valores casi-cero
        sharpe_ratio = (returns.mean() / returns_std) * np.sqrt(252)
        sharpe_ratio = float(np.clip(sharpe_ratio, -100, 100))  # limita outliers absurdos

    # Max Drawdown
    running_max = equity_with_start.cummax()
    drawdown = (equity_with_start - running_max) / running_max * 100
    max_drawdown = abs(drawdown.min())

    # Win rate por régimen (si está disponible)
    win_rate_by_regime = {}
    if 'regime' in df.columns:
        for regime in df['regime'].dropna().unique():
            regime_trades = df[df['regime'] == regime]
            regime_wins   = regime_trades[regime_trades['pnl'] > 0]
            win_rate_by_regime[regime] = {
                "trades":   len(regime_trades),
                "win_rate": round(len(regime_wins) / len(regime_trades) * 100, 2) if len(regime_trades) > 0 else 0.0,
                "pnl":      round(float(regime_trades['pnl'].sum()), 2),
            }

    final_balance = float(equity_with_start.iloc[-1])
    total_return_pct = (final_balance - initial_balance) / initial_balance * 100

    return {
        "total_trades":      total_trades,
        "winning_trades":    len(wins),
        "losing_trades":     len(losses),
        "win_rate":          round(win_rate, 2),
        "profit_factor":     round(profit_factor, 2) if profit_factor != float('inf') else None,
        "avg_win":           round(float(avg_win), 2),
        "avg_loss":          round(float(avg_loss), 2),
        "expectancy":        round(float(expectancy), 2),
        "sharpe_ratio":      round(float(sharpe_ratio), 2),
        "max_drawdown_pct":  round(float(max_drawdown), 2),
        "total_pnl":         round(float(df['pnl'].sum()), 2),
        "total_return_pct":  round(float(total_return_pct), 2),
        "initial_balance":   initial_balance,
        "final_balance":     round(final_balance, 2),
        "win_rate_by_regime": win_rate_by_regime,
    }


def _empty_metrics() -> dict:
    return {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "profit_factor": None,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "expectancy": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "initial_balance": 0.0,
        "final_balance": 0.0,
        "win_rate_by_regime": {},
    }

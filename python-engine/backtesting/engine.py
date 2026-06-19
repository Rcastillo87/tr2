"""
Backtesting Engine V2
Motor genérico que simula trades sobre datos históricos.
Soporta: SL/TP1/TP2, Break-even, Cierre por tiempo, Filtro de régimen.
"""

import pandas as pd
import logging
from datetime import datetime, timezone
from backtesting.metrics import calculate_metrics
from backtesting.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class BacktestEngine:

    def __init__(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        regime_data: dict | None = None,
    ):
        """
        strategy:           instancia de una estrategia hija de BaseStrategy
        df:                 DataFrame con OHLCV ordenado ascendente
        initial_balance:    capital inicial en USDT
        risk_per_trade_pct: % del capital a arriesgar por trade
        regime_data:        dict {timestamp_iso: regime_str} para filtro de régimen
        """
        self.strategy            = strategy
        self.df                  = df.copy()
        self.initial_balance     = initial_balance
        self.balance             = initial_balance
        self.risk_per_trade_pct  = risk_per_trade_pct
        self.regime_data         = regime_data or {}
        self.trades              = []

    def _get_regime_at(self, timestamp) -> str:
        """Retorna el régimen más cercano al timestamp dado."""
        if not self.regime_data:
            return "TRENDING"  # sin filtro si no hay datos de régimen
        return self.regime_data.get(str(timestamp), "TRENDING")

    def _calculate_position_size(self, entry_price: float, sl_price: float) -> float:
        """
        Position sizing basado en riesgo fijo:
        Tamaño = (capital * riesgo%) / distancia al SL
        """
        risk_amount   = self.balance * (self.risk_per_trade_pct / 100)
        sl_distance   = abs(entry_price - sl_price)

        if sl_distance == 0:
            return 0.0

        size = risk_amount / sl_distance
        return round(size, 6)

    def run(self) -> dict:
        """Ejecuta el backtest completo."""
        logger.info(f"Iniciando backtest: {self.strategy.name} | {self.strategy.symbol} | {len(self.df)} velas")

        # Preparar e indicadores
        df = self.strategy.prepare(self.df)
        df = self.strategy.generate_signals(df)

        position     = None
        equity_curve = [self.initial_balance]

        for i in range(1, len(df)):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]

            # ── Gestión de posición abierta ──────────────────────────────
            if position is not None:
                high  = float(row['high'])
                low   = float(row['low'])
                close = float(row['close'])
                bars_open = i - position['entry_bar']

                exit_price  = None
                exit_reason = None

                # Break-even: mover SL a entrada si precio llegó al nivel BE
                if not position['be_activated']:
                    be_level = position['be_level']
                    if position['side'] == 'long' and high >= be_level:
                        position['sl'] = position['entry_price']
                        position['be_activated'] = True
                    elif position['side'] == 'short' and low <= be_level:
                        position['sl'] = position['entry_price']
                        position['be_activated'] = True

                # Stop Loss
                if position['side'] == 'long' and low <= position['sl']:
                    exit_price  = position['sl']
                    exit_reason = 'stop_loss'
                elif position['side'] == 'short' and high >= position['sl']:
                    exit_price  = position['sl']
                    exit_reason = 'stop_loss'

                # Take Profit — TP2 tiene prioridad si esta definido y se alcanzo,
                # si no se evalua TP1. Replica el sistema TP1/TP2 de E-13 original.
                if exit_price is None:
                    tp2 = position.get('tp2')

                    if tp2 is not None:
                        if position['side'] == 'long' and high >= tp2:
                            exit_price, exit_reason = tp2, 'take_profit_2'
                        elif position['side'] == 'short' and low <= tp2:
                            exit_price, exit_reason = tp2, 'take_profit_2'

                    if exit_price is None:
                        if position['side'] == 'long' and high >= position['tp']:
                            exit_price, exit_reason = position['tp'], 'take_profit' if tp2 is None else 'take_profit_1'
                        elif position['side'] == 'short' and low <= position['tp']:
                            exit_price, exit_reason = position['tp'], 'take_profit' if tp2 is None else 'take_profit_1'

                # Cierre por tiempo
                if exit_price is None and bars_open >= self.strategy.max_duration:
                    exit_price  = close
                    exit_reason = 'time_exit'

                # Registrar trade cerrado
                if exit_price is not None:
                    if position['side'] == 'long':
                        pnl = (exit_price - position['entry_price']) * position['size']
                    else:
                        pnl = (position['entry_price'] - exit_price) * position['size']

                    pnl_pct = pnl / self.balance * 100
                    self.balance += pnl

                    self.trades.append({
                        "entry_time":   position['entry_time'],
                        "exit_time":    row['time'] if 'time' in df.columns else str(i),
                        "symbol":       self.strategy.symbol,
                        "side":         position['side'],
                        "entry_price":  position['entry_price'],
                        "exit_price":   exit_price,
                        "sl":           position['sl'],
                        "tp":           position['tp'],
                        "tp2":          position.get('tp2'),
                        "size":         position['size'],
                        "pnl":          round(pnl, 4),
                        "pnl_pct":      round(pnl_pct, 4),
                        "exit_reason":  exit_reason,
                        "bars_open":    bars_open,
                        "be_activated": position['be_activated'],
                        "regime":       position['regime'],
                    })

                    position = None
                    equity_curve.append(self.balance)

            # ── Nueva entrada ────────────────────────────────────────────
            if position is None and prev['signal'] != 0:
                signal = int(prev['signal'])
                side   = 'long' if signal == 1 else 'short'
                entry  = float(row['open'])  # entra en apertura de siguiente vela

                regime = self._get_regime_at(row.get('time', i))

                if not self.strategy.should_operate(regime):
                    continue

                sl, tp = self.strategy.calculate_sl_tp(entry, side)
                be     = self.strategy.calculate_breakeven(entry, side)
                size   = self._calculate_position_size(entry, sl)

                # TP2 opcional — None si la estrategia no lo define (backward compatible)
                tp2 = self.strategy.calculate_tp2(entry, side) if hasattr(self.strategy, 'calculate_tp2') else None

                if size <= 0:
                    continue

                position = {
                    'side':         side,
                    'entry_price':  entry,
                    'entry_time':   row.get('time', i),
                    'entry_bar':    i,
                    'sl':           sl,
                    'tp':           tp,
                    'tp2':          tp2,
                    'be_level':     be,
                    'be_activated': False,
                    'size':         size,
                    'regime':       regime,
                }

        # Calcular métricas finales
        metrics = calculate_metrics(self.trades, self.initial_balance)
        metrics['equity_curve'] = equity_curve

        logger.info(
            f"Backtest completo: {metrics['total_trades']} trades | "
            f"WR: {metrics['win_rate']}% | "
            f"PF: {metrics['profit_factor']} | "
            f"Sharpe: {metrics['sharpe_ratio']} | "
            f"DD: {metrics['max_drawdown_pct']}%"
        )

        return {
            "backtest_id": f"BT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self.strategy.symbol}-{self.strategy.name.replace(' ', '_').upper()}",
            "strategy":    self.strategy.name,
            "symbol":      self.strategy.symbol,
            "interval":    self.strategy.interval,
            "total_bars":  len(df),
            "metrics":     metrics,
            "trades":      self.trades,
        }

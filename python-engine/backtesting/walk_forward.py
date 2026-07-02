"""
Walk-Forward Validator V2
Valida que una estrategia funciona fuera de muestra antes de activarla.
"""

import pandas as pd
import logging
from backtesting.engine import BacktestEngine
from backtesting.strategies.base_strategy import BaseStrategy
from backtesting.metrics import calculate_metrics
from indicators.regime_indicators import calculate_atr, calculate_adx, calculate_bb_width, classify_regime

logger = logging.getLogger(__name__)

class WalkForwardValidator:

    def __init__(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        train_pct: float = 0.7,
        n_windows: int = 5,
        regime_data: dict | None = None,
    ):
        """
        strategy:           instancia de estrategia hija de BaseStrategy
        df:                 DataFrame OHLCV completo ordenado ascendente
        initial_balance:    capital inicial
        risk_per_trade_pct: % de riesgo por trade
        train_pct:          % de datos para entrenamiento en cada ventana (0.7 = 70%)
        n_windows:          número de ventanas walk-forward
        regime_data:        dict {timestamp: regime} para filtro
        """
        self.strategy            = strategy
        self.df                  = df.copy()
        self.initial_balance     = initial_balance
        self.risk_per_trade_pct  = risk_per_trade_pct
        self.train_pct           = train_pct
        self.n_windows           = n_windows
        self.regime_data         = regime_data or {}

    def _split_windows(self) -> list[dict]:
        """Divide el DataFrame en N ventanas walk-forward."""
        total_bars = len(self.df)
        window_size = total_bars // self.n_windows
        windows = []

        for i in range(self.n_windows):
            start = i * window_size
            end   = start + window_size if i < self.n_windows - 1 else total_bars

            window_df  = self.df.iloc[start:end].reset_index(drop=True)
            split_idx  = int(len(window_df) * self.train_pct)

            train_df = window_df.iloc[:split_idx].reset_index(drop=True)
            test_df  = window_df.iloc[split_idx:].reset_index(drop=True)

            windows.append({
                "window":   i + 1,
                "train_df": train_df,
                "test_df":  test_df,
                "train_bars": len(train_df),
                "test_bars":  len(test_df),
            })

        return windows

    def _build_regime_data(self, df: pd.DataFrame) -> dict:
        """Calcula el régimen histórico para cada barra del DataFrame."""
        regime_data  = {}
        atr          = calculate_atr(df)
        adx          = calculate_adx(df)
        bb_width     = calculate_bb_width(df)
        atr_avg      = atr.rolling(50).mean()
        bb_width_avg = bb_width.rolling(50).mean()

        for i in range(len(df)):
            if i < 50:
                continue
            regime = classify_regime(
                adx=float(adx.iloc[i]),
                atr=float(atr.iloc[i]),
                atr_avg=float(atr_avg.iloc[i]),
                bb_width=float(bb_width.iloc[i]),
                bb_width_avg=float(bb_width_avg.iloc[i]),
                trending_threshold=getattr(self.strategy, "regime_adx_trending", 25),
                ranging_threshold=getattr(self.strategy, "regime_adx_ranging", 20),
                ambiguous_as=getattr(self.strategy, "regime_ambiguous_as", "RANGING"),
            )
            ts = str(df.iloc[i]['time'])
            regime_data[ts] = regime

        return regime_data

    def run(self) -> dict:
        """Ejecuta la validación walk-forward completa."""
        logger.info(
            f"Walk-Forward: {self.strategy.name} | {self.strategy.symbol} | "
            f"{self.n_windows} ventanas | train={int(self.train_pct*100)}%"
        )

        windows = self._split_windows()
        window_results = []
        all_test_trades = []

        for w in windows:
            logger.info(
                f"Ventana {w['window']}/{self.n_windows}: "
                f"train={w['train_bars']} velas | test={w['test_bars']} velas"
            )

            # Correr en datos de TEST (fuera de muestra)
            if len(w['test_df']) < 50:
                logger.warning(f"Ventana {w['window']}: datos de test insuficientes, saltando")
                continue

            regime_data = self._build_regime_data(w['test_df'])
            engine = BacktestEngine(
                strategy=self.strategy,
                df=w['test_df'],
                initial_balance=self.initial_balance,
                risk_per_trade_pct=self.risk_per_trade_pct,
                regime_data=regime_data,
            )

            result = engine.run()
            metrics = result['metrics']

            window_results.append({
                "window":          w['window'],
                "train_bars":      w['train_bars'],
                "test_bars":       w['test_bars'],
                "total_trades":    metrics['total_trades'],
                "win_rate":        metrics['win_rate'],
                "profit_factor":   metrics['profit_factor'],
                "sharpe_ratio":    metrics['sharpe_ratio'],
                "max_drawdown_pct": metrics['max_drawdown_pct'],
                "total_return_pct": metrics['total_return_pct'],
                "total_pnl":       metrics['total_pnl'],
            })

            all_test_trades.extend(result['trades'])

        # Métricas agregadas sobre todos los trades fuera de muestra
        aggregate_metrics = calculate_metrics(all_test_trades, self.initial_balance)

        # Criterios de aprobación
        passed = self._evaluate(window_results, aggregate_metrics)

        return {
            "strategy":          self.strategy.name,
            "symbol":            self.strategy.symbol,
            "interval":          self.strategy.interval,
            "n_windows":         self.n_windows,
            "window_results":    window_results,
            "aggregate_metrics": aggregate_metrics,
            "passed":            passed['passed'],
            "pass_reasons":      passed['reasons'],
            "ready_for_paper":   passed['passed'],
        }

    def _evaluate(self, window_results: list, aggregate: dict) -> dict:
        """
        Evalúa si la estrategia aprueba para paper trading.
        Criterios mínimos:
            - Sharpe Ratio > 0.5
            - Win Rate > 45%
            - Max Drawdown < 15%
            - Profit Factor > 1.2
            - Mínimo 10 trades en total
        """
        reasons = []
        passed  = True

        if aggregate['total_trades'] < 10:
            passed = False
            reasons.append(f"Trades insuficientes: {aggregate['total_trades']} (mínimo 10)")

        if aggregate['sharpe_ratio'] < 0.5:
            passed = False
            reasons.append(f"Sharpe Ratio bajo: {aggregate['sharpe_ratio']} (mínimo 0.5)")

        if aggregate['win_rate'] < 45:
            passed = False
            reasons.append(f"Win Rate bajo: {aggregate['win_rate']}% (mínimo 45%)")

        if aggregate['max_drawdown_pct'] > 15:
            passed = False
            reasons.append(f"Drawdown alto: {aggregate['max_drawdown_pct']}% (máximo 15%)")

        if aggregate['profit_factor'] is not None and aggregate['profit_factor'] < 1.2:
            passed = False
            reasons.append(f"Profit Factor bajo: {aggregate['profit_factor']} (mínimo 1.2)")

        if passed:
            reasons.append("Estrategia aprobada para paper trading")

        return {"passed": passed, "reasons": reasons}

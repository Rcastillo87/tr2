"""
Estrategia: VWAP Intradía
Migración de E-13: opera rebotes y cruces desde VWAP
Solo opera en régimen TRENDING
"""

import pandas as pd
import numpy as np
from backtesting.strategies.base_strategy import BaseStrategy


class VwapIntradayStrategy(BaseStrategy):

    name            = "VWAP Intradía"
    allowed_regimes = ["TRENDING"]

    def __init__(self, params: dict):
        super().__init__(params)
        self.ema_trend_period = params.get('ema_trend_period', 50)
        self.vwap_std         = params.get('vwap_std', 1.5)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # VWAP acumulado por día
        df['date']        = pd.to_datetime(df['time']).dt.date
        df['typical']     = (df['high'] + df['low'] + df['close']) / 3
        df['tpv']         = df['typical'] * df['volume']

        df['cum_tpv']     = df.groupby('date')['tpv'].cumsum()
        df['cum_vol']     = df.groupby('date')['volume'].cumsum()
        df['vwap']        = df['cum_tpv'] / df['cum_vol']

        # Bandas VWAP (desviación estándar)
        df['vwap_std']    = df.groupby('date')['typical'].transform('std')
        df['vwap_upper']  = df['vwap'] + (self.vwap_std * df['vwap_std'])
        df['vwap_lower']  = df['vwap'] - (self.vwap_std * df['vwap_std'])

        # EMA de tendencia (filtro macro)
        df['ema_trend']   = df['close'].ewm(span=self.ema_trend_period, adjust=False).mean()

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            trend_up   = curr['close'] > curr['ema_trend']
            trend_down = curr['close'] < curr['ema_trend']

            # Long: precio cruza VWAP hacia arriba en tendencia alcista
            if (trend_up and
                    prev['close'] <= prev['vwap'] and
                    curr['close'] > curr['vwap']):
                df.at[df.index[i], 'signal'] = 1

            # Short: precio cruza VWAP hacia abajo en tendencia bajista
            elif (trend_down and
                    prev['close'] >= prev['vwap'] and
                    curr['close'] < curr['vwap']):
                df.at[df.index[i], 'signal'] = -1

        return df

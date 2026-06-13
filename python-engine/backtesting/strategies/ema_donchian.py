"""
Estrategia: Tendencia EMA/Donchian
Trend Following: cruce de EMAs + ruptura de canal Donchian
Solo opera en régimen TRENDING
"""

import pandas as pd
from backtesting.strategies.base_strategy import BaseStrategy


class EmaDonchianStrategy(BaseStrategy):

    name            = "Tendencia EMA/Donchian"
    allowed_regimes = ["TRENDING"]

    def __init__(self, params: dict):
        super().__init__(params)
        self.ema_fast        = params.get('ema_fast', 9)
        self.ema_slow        = params.get('ema_slow', 21)
        self.donchian_period = params.get('donchian_period', 20)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ema_fast']      = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow']      = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        df['donchian_high'] = df['high'].rolling(window=self.donchian_period).max()
        df['donchian_low']  = df['low'].rolling(window=self.donchian_period).min()
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            if (prev['ema_fast'] <= prev['ema_slow'] and
                    curr['ema_fast'] > curr['ema_slow'] and
                    curr['close'] >= curr['donchian_high']):
                df.at[df.index[i], 'signal'] = 1

            elif (prev['ema_fast'] >= prev['ema_slow'] and
                    curr['ema_fast'] < curr['ema_slow'] and
                    curr['close'] <= curr['donchian_low']):
                df.at[df.index[i], 'signal'] = -1

        return df

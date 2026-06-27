"""
Estrategia: Reversión a la Media
Mean Reversion: rebotes desde bandas de Bollinger extremas
Solo opera en régimen RANGING
"""

import pandas as pd
from backtesting.strategies.base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):

    name            = "Reversión a la Media"
    allowed_regimes = ["RANGING"]

    def __init__(self, params: dict):
        super().__init__(params)
        self.bb_period = params.get('bb_period', 20)
        self.bb_std    = params.get('bb_std', 2.0)
        self.rsi_period = params.get('rsi_period', 14)
        self.rsi_ob    = params.get('rsi_ob', 70)
        self.rsi_os    = params.get('rsi_os', 30)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df['bb_mid']   = df['close'].rolling(window=self.bb_period).mean()
        df['bb_std']   = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_mid'] + (self.bb_std * df['bb_std'])
        df['bb_lower'] = df['bb_mid'] - (self.bb_std * df['bb_std'])

        delta    = df['close'].diff()
        gain     = delta.clip(lower=0)
        loss     = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, float('inf'))
        df['rsi'] = 100 - (100 / (1 + rs))

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            if (prev['close'] <= prev['bb_lower'] and
                    curr['close'] > curr['bb_lower'] and
                    curr['rsi'] < self.rsi_os + 10):
                df.at[df.index[i], 'signal'] = 1

            elif (prev['close'] >= prev['bb_upper'] and
                    curr['close'] < curr['bb_upper'] and
                    curr['rsi'] > self.rsi_ob - 10):
                df.at[df.index[i], 'signal'] = -1

        df = self.apply_volume_filter(df)
        return df

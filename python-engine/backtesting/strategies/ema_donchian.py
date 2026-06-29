"""
Estrategia: Tendencia EMA/Donchian
Trend Following: ruptura Donchian abre la "ventana de tendencia",
el cruce de EMAs dentro de esa ventana dispara la entrada.
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
        self.trend_window    = params.get('trend_window', 10)  # velas que dura el "permiso de tendencia"

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()

        donchian_high = df['high'].rolling(window=self.donchian_period).max()
        donchian_low  = df['low'].rolling(window=self.donchian_period).min()

        # Breakout: el cierre rompe el canal Donchian de las N velas previas (sin contar la actual)
        df['breakout_up']   = df['close'] >= donchian_high.shift(1)
        df['breakout_down'] = df['close'] <= donchian_low.shift(1)

        # "Ventana de tendencia": True si hubo breakout en las últimas trend_window velas
        df['trend_up_active']   = df['breakout_up'].rolling(window=self.trend_window).max().astype(bool)
        df['trend_down_active'] = df['breakout_down'].rolling(window=self.trend_window).max().astype(bool)

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            cross_up   = prev['ema_fast'] <= prev['ema_slow'] and curr['ema_fast'] > curr['ema_slow']
            cross_down = prev['ema_fast'] >= prev['ema_slow'] and curr['ema_fast'] < curr['ema_slow']

            # Long: cruce EMA alcista dentro de ventana de tendencia alcista
            if cross_up and curr['trend_up_active']:
                df.at[df.index[i], 'signal'] = 1

            # Short: cruce EMA bajista dentro de ventana de tendencia bajista
            elif cross_down and curr['trend_down_active']:
                df.at[df.index[i], 'signal'] = -1

        df = self.apply_volume_filter(df)
        df = self.apply_hour_filter(df)
        df = self.apply_weekend_filter(df)
        df = self.apply_blocked_hours(df)
        df = self.apply_blocked_days(df)
        return df

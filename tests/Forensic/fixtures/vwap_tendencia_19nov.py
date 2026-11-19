# Copia de la estrategia «VWAP Tendencia» (tabla strategies, huella 979d8dec) tal como estaba el 19-nov (R-21).
"""
Estrategia: VWAP Tendencia (Robust)
"""
import pandas as pd
from backtesting.strategies.base_strategy import BaseStrategy

class VwapStrategy(BaseStrategy):
    name            = "VWAP"
    allowed_regimes = ["TRENDING", "RANGING", "VOLATILE"]

    def __init__(self, params: dict):
        super().__init__(params)
        self.mode             = params.get('mode', 'trend_follow')
        self.ema_trend_period = params.get('ema_trend_period', 50)
        self.vwap_std_filter  = params.get('vwap_std_filter', 1.5)
        self.macro_trend_filter = params.get('macro_trend_filter', False)

        if 'allowed_regimes' in params:
            self.allowed_regimes = params['allowed_regimes']

    def _calculate_vwap_base(self, df: pd.DataFrame) -> pd.DataFrame:
        df['date']    = pd.to_datetime(df['time']).dt.date
        df['typical'] = (df['high'] + df['low'] + df['close']) / 3
        df['tpv']     = df['typical'] * df['volume']
        df['cum_tpv'] = df.groupby('date')['tpv'].cumsum()
        df['cum_vol'] = df.groupby('date')['volume'].cumsum()
        df['vwap']    = df['cum_tpv'] / df['cum_vol']
        return df

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns: df[col] = df[col].astype(float)

        df = self._calculate_vwap_base(df)

        df['vwap_std_dev'] = df.groupby('date')['typical'].transform('std')
        df['vwap_upper'] = df['vwap'] + (self.vwap_std_filter * df['vwap_std_dev'])
        df['vwap_lower'] = df['vwap'] - (self.vwap_std_filter * df['vwap_std_dev'])
        df['ema_trend']  = df['close'].ewm(span=self.ema_trend_period, adjust=False).mean()

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            trend_up   = curr['close'] > curr['ema_trend']
            trend_down = curr['close'] < curr['ema_trend']

            if (trend_up and prev['close'] <= prev['vwap'] and curr['close'] > curr['vwap']):
                if curr['close'] <= curr['vwap_upper']:
                    df.at[df.index[i], 'signal'] = 1

            elif (trend_down and prev['close'] >= prev['vwap'] and curr['close'] < curr['vwap']):
                if curr['close'] >= curr['vwap_lower']:
                    df.at[df.index[i], 'signal'] = -1

        df = self.apply_volume_filter(df)
        df = self.apply_hour_filter(df)
        df = self.apply_weekend_filter(df)
        df = self.apply_blocked_hours(df)
        df = self.apply_blocked_days(df)
        return df

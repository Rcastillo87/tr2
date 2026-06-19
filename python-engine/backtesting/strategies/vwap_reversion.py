"""
Estrategia: VWAP Reversión (E-13 original)
Replica fiel de la lógica E-13 de V1: opera reversiones a la media cuando
el precio se sobre-extiende mas allá de +/-2 desviaciones estándar del VWAP
acumulado diario. A diferencia de "VWAP Intradía" (V2), esta NO sigue la
tendencia — apuesta a que el precio regrese hacia el VWAP tras el extremo.

Creada para comparar mediante backtest contra "VWAP Intradía" (V2) y decidir
si conviene migrar esta logica de regreso. No reemplaza la estrategia activa.
"""

import pandas as pd
from backtesting.strategies.base_strategy import BaseStrategy


class VwapReversionStrategy(BaseStrategy):

    name            = "VWAP Reversión (E-13)"
    allowed_regimes = ["TRENDING", "RANGING", "VOLATILE"]  # E-13 original no filtraba por régimen

    def __init__(self, params: dict):
        super().__init__(params)
        # E-13 original usaba bandas de 2 desviaciones estándar, fijo
        self.vwap_std_entry = params.get('vwap_std_entry', 2.0)
        # Evita re-disparar señales repetidas dentro del mismo tramo de 4 velas
        # (replica el "seen_zones" de la version original, basado en i // 4)
        self.zone_bars = params.get('zone_bars', 4)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df['date']    = pd.to_datetime(df['time']).dt.date
        df['typical'] = (df['high'] + df['low'] + df['close']) / 3
        df['tpv']     = df['typical'] * df['volume']

        df['cum_tpv'] = df.groupby('date')['tpv'].cumsum()
        df['cum_vol'] = df.groupby('date')['volume'].cumsum()
        df['vwap']    = df['cum_tpv'] / df['cum_vol']

        # Desviación estándar del precio tipico respecto al VWAP, ponderada por volumen,
        # acumulada desde el inicio del dia (igual que el calculo original de E-13).
        def rolling_weighted_std(group):
            typical = group['typical'].values
            volume  = group['volume'].values
            vwap_g  = group['vwap'].values
            cum_vol_g = group['cum_vol'].values

            std_dev = pd.Series(0.0, index=group.index)
            for i in range(len(group)):
                if cum_vol_g[i] > 0:
                    sq_diff = ((typical[:i + 1] - vwap_g[i]) ** 2) * volume[:i + 1]
                    std_dev.iloc[i] = (sq_diff.sum() / cum_vol_g[i]) ** 0.5
            return std_dev

        df['vwap_std_dev'] = df.groupby('date', group_keys=False).apply(rolling_weighted_std)

        df['vwap_upper_2'] = df['vwap'] + (self.vwap_std_entry * df['vwap_std_dev'])
        df['vwap_lower_2'] = df['vwap'] - (self.vwap_std_entry * df['vwap_std_dev'])

        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0

        last_zone_bar = {'LONG': -10_000, 'SHORT': -10_000}

        for i in range(20, len(df)):
            row = df.iloc[i]

            if row['vwap_std_dev'] == 0:
                continue

            price   = row['close']
            upper_2 = row['vwap_upper_2']
            lower_2 = row['vwap_lower_2']

            direction = None
            if price > upper_2:
                direction = 'SHORT'
            elif price < lower_2:
                direction = 'LONG'

            if direction is None:
                continue

            # Evitar señales repetidas dentro de la misma "zona" de N velas,
            # igual que el seen_zones (i // zone_bars) de la version original.
            zone_id = i // self.zone_bars
            last_zone_id = last_zone_bar[direction] // self.zone_bars

            if zone_id == last_zone_id:
                continue

            last_zone_bar[direction] = i
            df.at[df.index[i], 'signal'] = 1 if direction == 'LONG' else -1

        return df


class VwapReversionTrendingOnlyStrategy(VwapReversionStrategy):
    """
    Variante de prueba: misma lógica de VwapReversionStrategy (E-13), pero
    restringida a operar solo en régimen TRENDING. Usada únicamente para
    el backtest comparativo — no se usa en paper trading ni producción.
    """
    name            = "VWAP Reversión (E-13) — solo TRENDING"
    allowed_regimes = ["TRENDING"]

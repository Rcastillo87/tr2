"""
Estrategia: VWAP (unificada)
Unifica dos enfoques sobre el mismo indicador VWAP acumulado diario:

  mode="trend_follow"  — VWAP Intradía original (V2):
    Entra cuando el precio cruza el VWAP en la dirección de la tendencia
    macro (EMA de tendencia). Opera mejor en ETH H2.

  mode="reversion"     — VWAP Reversión (E-13 original):
    Entra cuando el precio se sobre-extiende mas allá de ±N desviaciones
    estándar del VWAP, apostando a que regrese al centro.
    Opera mejor en BTC/SOL H1 filtrado a régimen TRENDING.

Parámetros clave (todos configurables desde paper_strategy_configs):
  mode             : "trend_follow" | "reversion"
  vwap_std_entry   : desviaciones estándar para entrada en modo reversion (default 2.0)
  vwap_std_filter  : desviaciones estándar para filtro en modo trend_follow (default 1.5)
  ema_trend_period : periodo EMA de tendencia para modo trend_follow (default 50)
  zone_bars        : velas minimas entre señales en modo reversion (default 4)
"""

import pandas as pd
from backtesting.strategies.base_strategy import BaseStrategy


class VwapStrategy(BaseStrategy):

    name            = "VWAP"
    allowed_regimes = ["TRENDING", "RANGING", "VOLATILE"]  # se sobrescribe via config

    def __init__(self, params: dict):
        super().__init__(params)
        self.mode             = params.get('mode', 'trend_follow')
        self.ema_trend_period = params.get('ema_trend_period', 50)
        self.vwap_std_entry   = params.get('vwap_std_entry', 2.0)
        self.vwap_std_filter  = params.get('vwap_std_filter', 1.5)
        self.zone_bars        = params.get('zone_bars', 4)

        # Filtro de tendencia macro (replica E-13 original, tambien aplicable
        # a trend_follow): bloquea señales contra la tendencia mayor H4.
        # Activo por defecto en reversion; en trend_follow es opcional (False
        # por defecto) ya que normalmente trend_follow ya sigue la EMA de
        # tendencia local, pero se puede activar para filtrar pullbacks falsos.
        self.macro_trend_filter  = params.get('macro_trend_filter', self.mode == 'reversion')
        self.macro_trend_period  = params.get('macro_trend_period', 50)
        self.macro_trend_interval_hours = params.get('macro_trend_interval_hours', 4)  # H4

        # Filtro de persistencia de tendencia (solo trend_follow)
        self.trend_persistence_filter = params.get('trend_persistence_filter', False)
        self.trend_persistence_bars   = params.get('trend_persistence_bars', 4)
        self.trend_adx_threshold      = params.get('trend_adx_threshold', 25)

        # SL dinamico en zona ADX dudosa (solo trend_follow): si el ADX al
        # momento de entrar esta en la "zona gris" (entre adx_threshold y
        # adx_strong_threshold), usa un SL mas ajustado (sl_pct_weak_zone) en
        # vez del sl_pct normal, reduciendo el riesgo cuando la tendencia es
        # debil/dudosa en vez de bloquear la entrada por completo.
        self.dynamic_sl_filter      = params.get('dynamic_sl_filter', False)
        self.adx_strong_threshold   = params.get('adx_strong_threshold', 30)
        self.sl_pct_weak_zone       = params.get('sl_pct_weak_zone', 0.7)

        # allowed_regimes se puede sobreescribir desde params
        if 'allowed_regimes' in params:
            self.allowed_regimes = params['allowed_regimes']
        elif self.mode == 'trend_follow':
            self.allowed_regimes = ["TRENDING"]
        else:
            # reversion: solo TRENDING segun backtests
            self.allowed_regimes = ["TRENDING"]

    # ─────────────────────────────────────────────
    # Indicadores comunes
    # ─────────────────────────────────────────────

    def _calculate_vwap_base(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula VWAP acumulado diario y desviacion estandar ponderada por volumen."""
        df['date']    = pd.to_datetime(df['time']).dt.date
        df['typical'] = (df['high'] + df['low'] + df['close']) / 3
        df['tpv']     = df['typical'] * df['volume']

        df['cum_tpv'] = df.groupby('date')['tpv'].cumsum()
        df['cum_vol'] = df.groupby('date')['volume'].cumsum()
        df['vwap']    = df['cum_tpv'] / df['cum_vol']

        return df

    def _calculate_vwap_std_rolling(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Desviacion estandar del precio tipico respecto al VWAP, ponderada
        por volumen y acumulada desde el inicio del dia.
        Replica fielmente el calculo de E-13 original.
        """
        def rolling_weighted_std(group):
            typical   = group['typical'].values
            volume    = group['volume'].values
            vwap_g    = group['vwap'].values
            cum_vol_g = group['cum_vol'].values

            std_dev = pd.Series(0.0, index=group.index)
            for i in range(len(group)):
                if cum_vol_g[i] > 0:
                    sq_diff = ((typical[:i + 1] - vwap_g[i]) ** 2) * volume[:i + 1]
                    std_dev.iloc[i] = (sq_diff.sum() / cum_vol_g[i]) ** 0.5
            return std_dev

        df['vwap_std_dev'] = df.groupby('date', group_keys=False).apply(rolling_weighted_std)
        return df

    def _calculate_vwap_std_simple(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Desviacion estandar del precio tipico agrupado por dia.
        Mas rapido que rolling_weighted_std, suficiente para modo trend_follow.
        """
        df['vwap_std_dev'] = df.groupby('date')['typical'].transform('std')
        return df

    def _calculate_macro_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula la tendencia macro (BULLISH/BEARISH) resampleando el propio
        DataFrame (asumido H1) a un timeframe mayor (default H4) y calculando
        EMA50 sobre esas velas resampleadas. Replica el filtro de E-13 original
        (que usaba EMA50 en H4 real de Bybit) sin requerir un segundo dataset.

        El valor de tendencia de cada vela H4 se propaga (forward-fill) a todas
        las velas H1 contenidas en ese bloque de tiempo.
        """
        interval_bars = self.macro_trend_interval_hours  # asumiendo barras de 1h

        df = df.copy()
        df['time_dt'] = pd.to_datetime(df['time'])
        df = df.set_index('time_dt')

        # Resample a H4 (u otro intervalo configurado) usando el close de cada bloque
        resampled = df['close'].resample(f'{self.macro_trend_interval_hours}h').last().dropna()

        if len(resampled) < self.macro_trend_period:
            # Datos insuficientes para EMA50 en H4 — sin filtro de tendencia
            df['macro_trend'] = None
            return df.reset_index(drop=True)

        ema = resampled.ewm(span=self.macro_trend_period, adjust=False).mean()
        trend = (resampled > ema).map({True: 'BULLISH', False: 'BEARISH'})

        # Reindexar la tendencia H4 sobre el indice H1 original (forward-fill)
        trend_h1 = trend.reindex(df.index, method='ffill')
        df['macro_trend'] = trend_h1.values

        return df.reset_index(drop=True)

    def _calculate_trend_persistence(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula si el ADX ha estado por encima del umbral de forma sostenida
        durante trend_persistence_bars velas consecutivas. Marca la columna
        'trend_persistent' = True solo cuando se cumple esa condicion.
        """
        high, low, close = df['high'], df['low'], df['close']
        prev_high, prev_low, prev_close = high.shift(1), low.shift(1), close.shift(1)

        plus_dm  = (high - prev_high).clip(lower=0)
        minus_dm = (prev_low - low).clip(lower=0)
        plus_dm  = plus_dm.where(plus_dm > minus_dm, 0.0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False).mean()

        plus_di  = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/14, adjust=False).mean()

        df['_adx'] = adx
        above_threshold = adx > self.trend_adx_threshold

        # Persistente = True si las ultimas N velas (incluyendo la actual) estuvieron todas por encima
        df['trend_persistent'] = above_threshold.rolling(self.trend_persistence_bars).min().fillna(0).astype(bool)

        return df

    # ─────────────────────────────────────────────
    # Prepare
    # ─────────────────────────────────────────────

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = self._calculate_vwap_base(df)

        if self.mode == 'trend_follow':
            df = self._calculate_vwap_std_simple(df)
            df['vwap_upper'] = df['vwap'] + (self.vwap_std_filter * df['vwap_std_dev'])
            df['vwap_lower'] = df['vwap'] - (self.vwap_std_filter * df['vwap_std_dev'])
            df['ema_trend']  = df['close'].ewm(span=self.ema_trend_period, adjust=False).mean()

            if self.trend_persistence_filter or self.dynamic_sl_filter:
                df = self._calculate_trend_persistence(df)

            if self.macro_trend_filter:
                df = self._calculate_macro_trend(df)

        elif self.mode == 'reversion':
            df = self._calculate_vwap_std_rolling(df)
            df['vwap_upper_entry'] = df['vwap'] + (self.vwap_std_entry * df['vwap_std_dev'])
            df['vwap_lower_entry'] = df['vwap'] - (self.vwap_std_entry * df['vwap_std_dev'])

            if self.macro_trend_filter:
                df = self._calculate_macro_trend(df)

        return df

    # ─────────────────────────────────────────────
    # Generate signals
    # ─────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.mode == 'trend_follow':
            return self._signals_trend_follow(df)
        elif self.mode == 'reversion':
            return self._signals_reversion(df)
        return df

    def _signals_trend_follow(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Long: precio cruza VWAP hacia arriba y esta sobre la EMA de tendencia.
        Short: precio cruza VWAP hacia abajo y esta bajo la EMA de tendencia.
        """
        df = df.copy()
        df['signal'] = 0
        df['signal_sl_pct'] = self.sl_pct  # default: sl_pct normal, sobreescrito si dynamic_sl_filter activo

        for i in range(1, len(df)):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            trend_up   = curr['close'] > curr['ema_trend']
            trend_down = curr['close'] < curr['ema_trend']

            # Filtro de persistencia: si esta activo, exige que la tendencia
            # (ADX > umbral) se haya mantenido N velas consecutivas
            if self.trend_persistence_filter and 'trend_persistent' in df.columns:
                if not curr.get('trend_persistent', False):
                    continue

            # Filtro de tendencia macro H4: bloquea SHORT si la macro es BULLISH,
            # bloquea LONG si la macro es BEARISH (evita pullbacks falsos)
            macro_trend = curr.get('macro_trend') if self.macro_trend_filter and 'macro_trend' in df.columns else None

            if (trend_up and
                    prev['close'] <= prev['vwap'] and
                    curr['close'] > curr['vwap']):
                if macro_trend == 'BEARISH':
                    continue
                df.at[df.index[i], 'signal'] = 1
                if self.dynamic_sl_filter:
                    df.at[df.index[i], 'signal_sl_pct'] = self._sl_for_adx_zone(curr.get('_adx'))

            elif (trend_down and
                    prev['close'] >= prev['vwap'] and
                    curr['close'] < curr['vwap']):
                if macro_trend == 'BULLISH':
                    continue
                df.at[df.index[i], 'signal'] = -1
                if self.dynamic_sl_filter:
                    df.at[df.index[i], 'signal_sl_pct'] = self._sl_for_adx_zone(curr.get('_adx'))

        return df

    def _sl_for_adx_zone(self, adx_value) -> float:
        """
        Determina el SL a usar segun la fuerza del ADX al momento de la entrada.
        Zona debil (adx_threshold <= ADX < adx_strong_threshold): usa sl_pct_weak_zone (mas ajustado).
        Zona fuerte (ADX >= adx_strong_threshold): usa el sl_pct normal.
        Si ADX no disponible, usa el sl_pct normal por seguridad.
        """
        if adx_value is None or pd.isna(adx_value):
            return self.sl_pct

        if self.trend_adx_threshold <= adx_value < self.adx_strong_threshold:
            return self.sl_pct_weak_zone

        return self.sl_pct

    def _signals_reversion(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Long: precio rompe la banda inferior (-N*std) — se espera rebote al alza.
        Short: precio rompe la banda superior (+N*std) — se espera rebote a la baja.
        Evita señales repetidas dentro de la misma zona (zone_bars velas).
        """
        df = df.copy()
        df['signal'] = 0

        last_zone_bar = {'LONG': -10_000, 'SHORT': -10_000}

        for i in range(20, len(df)):
            row = df.iloc[i]

            if row['vwap_std_dev'] == 0:
                continue

            price   = row['close']
            upper   = row['vwap_upper_entry']
            lower   = row['vwap_lower_entry']

            direction = None
            if price > upper:
                direction = 'SHORT'
            elif price < lower:
                direction = 'LONG'

            if direction is None:
                continue

            # Filtro de tendencia macro (replica E-13 original):
            # LONG se omite si la tendencia H4 es BAJISTA (ir contra la macro-tendencia).
            # SHORT se omite si la tendencia H4 es ALCISTA.
            if self.macro_trend_filter and 'macro_trend' in df.columns:
                trend = row.get('macro_trend')
                if trend is not None:
                    if direction == 'LONG' and trend == 'BEARISH':
                        continue
                    if direction == 'SHORT' and trend == 'BULLISH':
                        continue

            zone_id      = i // self.zone_bars
            last_zone_id = last_zone_bar[direction] // self.zone_bars

            if zone_id == last_zone_id:
                continue

            last_zone_bar[direction] = i
            df.at[df.index[i], 'signal'] = 1 if direction == 'LONG' else -1

        return df

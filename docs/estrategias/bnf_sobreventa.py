"""
BNF — Sobreventa extrema contra la media de 25 días (Takashi Kotegawa), adaptada a cripto.

Idea: comprar el pánico (precio muy por debajo de su media de 25 días tras una caída rápida) y vender en el rebote
hacia la media. Solo largos.

Señales (vela cerrada, sin mirar al futuro):
  +1  ENTRADA: desviación respecto a la media <= -entry_dev_pct  Y  caída de las últimas drop_bars velas >= drop_pct.
      Solo en la PRIMERA vela que cumple (flanco): no recompra en cada vela de la misma caída.
  -1  SALIDA: el precio recuperó exit_reversion del camino hacia la media desde la desviación de la entrada
      (entró a -16 %, exit_reversion 0.5 -> sale al volver a -8 %), si la entrada fue en las últimas exit_window velas. Se ejecuta con exit_on_opposite=true y allow_short=false
      (cierra el largo, nunca abre un corto).

La media es una SMA de ma_days días expresada en velas del intervalo (25 días = 150 velas de 4h). SMA y no EMA: con
ventana finita, backtest, Paper (500 velas) y Real calculan exactamente lo mismo.

Intervalos válidos: 2h, 4h y 1D. En 15m y 1h la media de 25 días necesita más de 500 velas, las que carga Paper:
la estrategia no da señales ahí (para que el backtest no muestre algo que Paper no puede repetir).

Configuración recomendada de operación (formulario de backtest / config Paper):
  allow_short queda forzado a false en el código; exit_on_opposite=true va en el JSON de la estrategia;
  close_on_opposite=false,
  macro_trend_filter=false, btc_trend_filter=false, volume_filter=false  (bloquearían la señal de salida -1),
  regime_filter=false (el pánico suele clasificarse VOLATILE),
  sl_pct de protección (p. ej. 6–10 %), tp_pct amplio (la salida principal es la reversión), max_duration como tope.
"""


class BNFSobreventa(BaseStrategy):
    name = 'bnf_sobreventa'
    allowed_regimes = ['TRENDING', 'RANGING', 'VOLATILE']

    BARS_PER_DAY = {'15': 96, '60': 24, '120': 12, '240': 6, 'D': 1, '1440': 1}
    MAX_WINDOW = 450          # velas de historia que la estrategia puede pedir (Paper carga 500)

    def __init__(self, params: dict):
        super().__init__(params)
        self.allow_short = False   # solo largos, sin importar la configuración: la señal -1 es SALIDA, nunca un corto
        self.ma_days = int(params.get('ma_days', 25))
        self.entry_dev_pct = float(params.get('entry_dev_pct', 6.0))
        self.drop_bars = int(params.get('drop_bars', 6))
        self.drop_pct = float(params.get('drop_pct', 4.0))
        self.exit_reversion = float(params.get('exit_reversion', 0.5))
        self.exit_window = int(params.get('exit_window', 30))
        if not (self.ma_days >= 2 and self.entry_dev_pct > 0 and self.drop_bars >= 1 and self.drop_pct > 0
                and 0 < self.exit_reversion <= 1 and self.exit_window >= 1):
            raise ValueError('BNF: parámetros fuera de rango (ma_days>=2, entry_dev_pct>0, drop_bars>=1, '
                             'drop_pct>0, 0<exit_reversion<=1, exit_window>=1)')

    def ma_bars(self) -> int | None:
        per_day = self.BARS_PER_DAY.get(str(self.interval))
        if per_day is None:
            return None
        n = self.ma_days * per_day
        return n if n + self.drop_bars <= self.MAX_WINDOW else None

    def prepare(self, df):
        df = df.copy()
        n = self.ma_bars()
        close = df['close'].astype(float)
        if n is None:
            df['bnf_ma'] = np.nan
            df['bnf_dev_pct'] = np.nan
            df['bnf_drop_pct'] = np.nan
            return df
        df['bnf_ma'] = close.rolling(n, min_periods=n).mean()
        df['bnf_dev_pct'] = (close / df['bnf_ma'] - 1.0) * 100.0
        df['bnf_drop_pct'] = (close / close.shift(self.drop_bars) - 1.0) * 100.0
        return df

    def generate_signals(self, df):
        df = df.copy()
        dev = df['bnf_dev_pct']
        panic = (dev <= -self.entry_dev_pct) & (df['bnf_drop_pct'] <= -self.drop_pct)
        entry = panic & ~panic.shift(1, fill_value=False)
        # salida: recuperar exit_reversion del camino desde la desviación REAL de la última entrada (de las últimas
        # exit_window velas) hasta la media. Ej.: entró a -16 % y exit_reversion 0.5 -> sale al volver a -8 %.
        entry_dev = dev.where(entry).ffill(limit=self.exit_window - 1) if self.exit_window > 1 else dev.where(entry)
        exit_ = entry_dev.notna() & (dev >= entry_dev * (1.0 - self.exit_reversion)) & ~entry
        df['signal'] = np.where(entry, 1, np.where(exit_, -1, 0)).astype(int)
        return df

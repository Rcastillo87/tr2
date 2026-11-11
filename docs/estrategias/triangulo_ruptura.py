"""
Ruptura de triángulos (ascendente, descendente y simétrico) con SL/TP fijos en %.

Detección en cada vela cerrada t, sin mirar al futuro:
  1. Pivotes: un máximo (mínimo) local en la vela i es el mayor (menor) de las pivot_bars velas a cada lado. Solo se
     conoce en la vela i + pivot_bars: hasta entonces no existe para la estrategia (sin sesgo de futuro).
  2. Figura: con los últimos max_pivots pivotes confirmados de cada lado dentro de las últimas window velas (al
     menos min_touches por lado) se ajusta una recta arriba y otra abajo (mínimos cuadrados). Cada pivote debe quedar
     a menos de touch_tol_pct de su recta; ningún cierre entre el primer pivote y la vela anterior puede haber
     salido de la figura (estructura intacta).
  3. Tipo: ascendente (techo plano, piso que sube), descendente (techo que baja, piso plano) o simétrico (techo que
     baja y piso que sube). «Plano» = pendiente total en la figura menor que flat_tol_pct. Las rectas deben converger:
     el ancho en t es como mucho (1 - min_contraction) del ancho al inicio. Ancho inicial >= min_height_pct del precio.
  4. Volumen (opcional, vol_contraction > 0): volumen medio de la 2.ª mitad <= vol_contraction × el de la 1.ª mitad.
  5. Ruptura: cierre por encima del techo (+break_pct) -> largo; por debajo del piso (-break_pct) -> corto.
     Con breakout_vol_mult > 0 el volumen de la vela de ruptura debe ser >= breakout_vol_mult × el medio de la figura.
     bias=true opera solo a favor del sesgo (ascendente: largos; descendente: cortos; simétrico: ambos).

Entrada (entry_mode):
  aggressive: señal en la vela de ruptura.
  retest:     tras la ruptura, en las retest_bars velas siguientes el precio vuelve a la recta rota (a menos de
              touch_tol_pct) y cierra a favor (vela de rechazo: cierre > apertura en largos, < en cortos, y del
              lado correcto de la recta). Si en ese lapso cierra de nuevo dentro de la figura, se cancela.

Stop Loss (sl_mode):
  fixed: el sl_pct de la configuración.
  swing: el de la ficha. Largo: debajo del último mínimo relativo de la figura (en retest, del mínimo del pullback);
         corto: encima del último máximo. Margen sl_buffer_pct y límites [min_sl_pct, max_sl_pct]. Va en la columna
         signal_sl_pct, que el motor ya respeta igual en backtest, Paper y Real.
Take Profit: el tp_pct fijo de la configuración (el motor no admite un TP propio por señal; la proyección de la
altura del triángulo no se usa).

Ventana: window + pivot_bars <= 450 velas, para que Paper (500 velas) vea exactamente lo mismo que el backtest.
"""


class TrianguloRuptura(BaseStrategy):
    name = 'triangulo_ruptura'
    allowed_regimes = ['TRENDING', 'VOLATILE']
    MAX_WINDOW = 450

    def __init__(self, params: dict):
        super().__init__(params)
        self.pivot_bars = int(params.get('pivot_bars', 3))
        self.window = int(params.get('window', 80))
        self.min_touches = int(params.get('min_touches', 2))
        self.max_pivots = int(params.get('max_pivots', 4))
        self.touch_tol_pct = float(params.get('touch_tol_pct', 0.6))
        self.flat_tol_pct = float(params.get('flat_tol_pct', 0.8))
        self.min_contraction = float(params.get('min_contraction', 0.3))
        self.min_height_pct = float(params.get('min_height_pct', 2.0))
        self.vol_contraction = float(params.get('vol_contraction', 0.9))
        self.break_pct = float(params.get('break_pct', 0.2))
        self.breakout_vol_mult = float(params.get('breakout_vol_mult', 1.3))
        self.entry_mode = str(params.get('entry_mode', 'aggressive'))
        self.retest_bars = int(params.get('retest_bars', 8))
        self.bias = bool(params.get('bias', False)) if not isinstance(params.get('bias'), str) \
            else params.get('bias').strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')
        self.sl_mode = str(params.get('sl_mode', 'swing'))
        self.sl_buffer_pct = float(params.get('sl_buffer_pct', 0.2))
        self.min_sl_pct = float(params.get('min_sl_pct', 0.8))
        self.max_sl_pct = float(params.get('max_sl_pct', 6.0))
        self.types = [t for t in (params.get('types') or ['asc', 'desc', 'sym']) if t in ('asc', 'desc', 'sym')]
        if not (1 <= self.pivot_bars <= 10 and 2 <= self.min_touches <= self.max_pivots <= 8
                and 20 <= self.window and self.window + self.pivot_bars <= self.MAX_WINDOW
                and 0 < self.touch_tol_pct and 0 <= self.flat_tol_pct and 0 < self.min_contraction < 1
                and self.entry_mode in ('aggressive', 'retest') and self.retest_bars >= 1 and self.types
                and self.sl_mode in ('fixed', 'swing') and 0 < self.min_sl_pct <= self.max_sl_pct):
            raise ValueError('Triángulo: parámetros fuera de rango (revisa pivot_bars, min_touches<=max_pivots, '
                             f'window+pivot_bars<={self.MAX_WINDOW}, min_contraction entre 0 y 1, entry_mode, types, '
                             'sl_mode fixed|swing, 0<min_sl_pct<=max_sl_pct)')

    def _swing_sl(self, side: int, ref: float, close: float) -> float:
        """SL en % desde el cierre de la señal hasta más allá del swing de referencia, dentro de los límites."""
        buf = self.sl_buffer_pct / 100.0
        level = ref * (1 - buf) if side == 1 else ref * (1 + buf)
        pct = (close - level) / close * 100.0 if side == 1 else (level - close) / close * 100.0
        return float(min(max(pct, self.min_sl_pct), self.max_sl_pct))

    # ── pivotes confirmados ─────────────────────────────────────────────────────────────────────────────────
    def _pivots(self, values: np.ndarray, is_high: bool) -> np.ndarray:
        """Índices i de máximos (mínimos) locales estrictos en ±pivot_bars. Se usan desde la vela i + pivot_bars."""
        k, n = self.pivot_bars, len(values)
        if n < 2 * k + 1:
            return np.array([], dtype=int)
        win = np.lib.stride_tricks.sliding_window_view(values, 2 * k + 1)
        # el centro es el extremo de la ventana y su PRIMERA aparición: en una meseta (máximos iguales, frecuente con
        # el tick de monedas baratas) cuenta un solo pivote, el primero, en vez de ninguno o varios
        pos = win.argmax(axis=1) if is_high else win.argmin(axis=1)
        return np.nonzero(pos == k)[0] + k

    @staticmethod
    def _line(x: np.ndarray, y: np.ndarray):
        slope, intercept = np.polyfit(x.astype(float), y.astype(float), 1)
        return float(slope), float(intercept)

    def _figure(self, t, hi_idx, lo_idx, high, low, close, volume):
        """Triángulo vigente en la vela t (usa solo velas <= t; pivotes confirmados <= t - pivot_bars) o None."""
        k = self.pivot_bars
        start = t - self.window
        h = hi_idx[(hi_idx >= start) & (hi_idx <= t - k)][-self.max_pivots:]
        l = lo_idx[(lo_idx >= start) & (lo_idx <= t - k)][-self.max_pivots:]
        if len(h) < self.min_touches or len(l) < self.min_touches:
            return None
        su, iu = self._line(h, high[h])
        sl, il = self._line(l, low[l])
        upper = lambda i: su * i + iu   # noqa: E731
        lower = lambda i: sl * i + il   # noqa: E731
        tol = self.touch_tol_pct / 100.0
        if np.any(np.abs(high[h] - upper(h)) > tol * upper(h)) or np.any(np.abs(low[l] - lower(l)) > tol * lower(l)):
            return None
        first = int(min(h[0], l[0]))
        span = t - first
        if span < 2 * k + 2:
            return None
        w0, wt = upper(first) - lower(first), upper(t) - lower(t)
        if w0 <= 0 or wt <= 0 or w0 < self.min_height_pct / 100.0 * close[first] or wt > (1 - self.min_contraction) * w0:
            return None
        # estructura intacta: ningún cierre fuera de la figura antes de t
        rng = np.arange(first, t)
        if np.any(close[rng] > upper(rng) * (1 + tol)) or np.any(close[rng] < lower(rng) * (1 - tol)):
            return None
        mid = close[t]
        up_move = (upper(t) - upper(first)) / mid * 100.0
        lo_move = (lower(t) - lower(first)) / mid * 100.0
        flat = self.flat_tol_pct
        if abs(up_move) <= flat and lo_move > flat:
            kind = 'asc'
        elif up_move < -flat and abs(lo_move) <= flat:
            kind = 'desc'
        elif up_move < -flat and lo_move > flat:
            kind = 'sym'
        else:
            return None
        if kind not in self.types:
            return None
        if self.vol_contraction > 0:
            half = first + span // 2
            v1, v2 = volume[first:half].mean(), volume[half:t].mean()
            if not (v1 > 0 and v2 <= self.vol_contraction * v1):
                return None
        return {'kind': kind, 'first': first, 'su': su, 'iu': iu, 'sl': sl, 'il': il,
                'vol': float(volume[first:t].mean())}

    def generate_signals(self, df):
        df = df.copy()
        n = len(df)
        sig = np.zeros(n, dtype=int)
        kinds = np.full(n, '', dtype=object)
        slp = np.full(n, np.nan)
        if n < self.window + self.pivot_bars + 2:
            df['signal'] = sig
            df['tri_kind'] = kinds
            df['signal_sl_pct'] = slp
            return df
        high = df['high'].to_numpy(float)
        low = df['low'].to_numpy(float)
        close = df['close'].to_numpy(float)
        open_ = df['open'].to_numpy(float)
        volume = df['volume'].to_numpy(float)
        hi_idx = self._pivots(high, True)
        lo_idx = self._pivots(low, False)
        brk = self.break_pct / 100.0
        tol = self.touch_tol_pct / 100.0
        pending = None   # ruptura esperando retesteo: {'side', 'line_s', 'line_i', 'until', 'kind'}

        for t in range(self.window + self.pivot_bars, n):
            if pending is not None:
                if t > pending['until']:
                    pending = None
                else:
                    line = pending['line_s'] * t + pending['line_i']
                    if pending['side'] == 1:
                        if close[t] < line * (1 - tol):
                            pending = None          # volvió a cerrar dentro: ruptura fallida
                        elif low[t] <= line * (1 + tol) and close[t] > line and close[t] > open_[t]:
                            ref = low[pending['from']:t + 1].min()   # mínimo del pullback
                            slp[t] = self._swing_sl(1, ref, close[t])
                            sig[t], kinds[t], pending = 1, pending['kind'], None
                    else:
                        if close[t] > line * (1 + tol):
                            pending = None
                        elif high[t] >= line * (1 - tol) and close[t] < line and close[t] < open_[t]:
                            ref = high[pending['from']:t + 1].max()   # máximo del pullback
                            slp[t] = self._swing_sl(-1, ref, close[t])
                            sig[t], kinds[t], pending = -1, pending['kind'], None
                    if sig[t] != 0 or pending is not None:
                        continue

            # la figura se evalúa con datos hasta t-1 y la ruptura es el cierre de t
            fig = self._figure(t - 1, hi_idx, lo_idx, high, low, close, volume)
            if fig is None:
                continue
            up = fig['su'] * t + fig['iu']
            lo = fig['sl'] * t + fig['il']
            prev_up, prev_lo = up - fig['su'], lo - fig['sl']
            if close[t - 1] > prev_up * (1 + brk) or close[t - 1] < prev_lo * (1 - brk):
                continue    # la ruptura ya ocurrió en la vela anterior: una sola señal por ruptura
            vol_ok = self.breakout_vol_mult <= 0 or volume[t] >= self.breakout_vol_mult * fig['vol']
            side = 0
            if close[t] > up * (1 + brk) and vol_ok:
                side = 1
            elif close[t] < lo * (1 - brk) and vol_ok:
                side = -1
            if side == 0:
                continue
            if self.bias and ((fig['kind'] == 'asc' and side == -1) or (fig['kind'] == 'desc' and side == 1)):
                continue
            if self.entry_mode == 'aggressive':
                sig[t], kinds[t] = side, fig['kind']
                # último mínimo (máximo) relativo DE LA FIGURA: pivote confirmado hasta t-1-pivot_bars
                piv = (lo_idx if side == 1 else hi_idx)
                piv = piv[(piv >= fig['first']) & (piv <= t - 1 - self.pivot_bars)]
                since = int(piv[-1]) if len(piv) else t
                # desde ese pivote hasta t: incluye mínimos posteriores aún sin confirmar como pivote (ya ocurrieron)
                ref = low[since:t + 1].min() if side == 1 else high[since:t + 1].max()
                slp[t] = self._swing_sl(side, ref, close[t])
            else:
                s, i = (fig['su'], fig['iu']) if side == 1 else (fig['sl'], fig['il'])
                pending = {'side': side, 'line_s': s, 'line_i': i, 'until': t + self.retest_bars, 'kind': fig['kind'],
                           'from': t + 1}

        df['signal'] = sig
        df['tri_kind'] = kinds
        # sl_mode=fixed: sin columna de SL por señal -> el motor usa sl_pct
        df['signal_sl_pct'] = slp if self.sl_mode == 'swing' else np.nan
        return df

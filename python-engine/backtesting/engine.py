"""
Backtesting Engine V3 — simulación continua y pesimista.

Orden de eventos en cada vela i (todo con información disponible en ese momento):
  1. Open de la vela i: cierre por señal opuesta (señal de la vela i-1, ya cerrada).
  2. Open de la vela i: entrada si la vela i-1 dio señal y el régimen de la vela i-1
     (cerrada) lo permite. Solo desde trade_from (las velas previas calientan indicadores).
  3. Gestión de la posición DURANTE la vela i, incluida la vela de entrada:
       por cada sub-vela (1m si hay datos que cubren el rango; si no, la vela completa):
         SL vigente -> TP1 -> break-even -> trailing   (lo adverso primero)
       al cierre: protección por volatilidad y cierre por duración (en velas).
Costos: comisión en entrada y salida + slippage por lado en TODAS las ejecuciones
(entradas y salidas a mercado: SL, TP, tiempo, volatilidad, señal opuesta)
+ funding de Bybit en cada liquidación con la posición abierta (pesimista en los bordes:
  el funding que se paga cuenta si la entrada o la salida coinciden con la liquidación; el que
  se cobra solo si la posición estuvo abierta antes y después).
Rendimiento (mismos resultados, bit a bit, que la referencia tests/Forensic/reference/engine_v3_ref.py):
velas sin posición ni señal sin trabajo, índices de 1m precalculados, _scan salta en bloque (numpy) los minutos
donde no puede pasar nada y aplica la regla de _step minuto a minuto desde cada evento.
"""

import logging
import weakref
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from backtesting.metrics import calculate_metrics
from backtesting.strategies.base_strategy import NATIVE_TRAILING_MIN_BUFFER_PCT, BaseStrategy
from indicators.regime_indicators import calculate_adx, calculate_atr, calculate_bb_width

logger = logging.getLogger(__name__)

_MINUTE_ARRAYS: dict = {}   # id(DataFrame de 1m) -> (weakref, arrays, filas)


def _minute_arrays(minute_df: pd.DataFrame) -> tuple:
    """(time UTC sin tz, high, low, close) ordenados por tiempo, de solo lectura. Se preparan una vez por DataFrame
    (mientras exista) en lugar de ordenar y convertir el millón de velas de 1m en cada backtest."""
    key = id(minute_df)
    hit = _MINUTE_ARRAYS.get(key)
    if hit is not None and hit[0]() is minute_df and hit[2] == len(minute_df):
        return hit[1]
    m = minute_df.sort_values('time')
    arrays = (pd.to_datetime(m['time'], utc=True).dt.tz_convert(None).to_numpy(),   # UTC naive
              m['high'].to_numpy(dtype=float), m['low'].to_numpy(dtype=float), m['close'].to_numpy(dtype=float))
    for a in arrays:
        a.flags.writeable = False
    for k in [k for k, v in _MINUTE_ARRAYS.items() if v[0]() is None]:   # DataFrames ya liberados
        del _MINUTE_ARRAYS[k]
    _MINUTE_ARRAYS[key] = (weakref.ref(minute_df), arrays, len(minute_df))
    return arrays


BLOCK_MIN = 8   # _scan: tramos de más sub-velas se recorren con saltos en bloque (numpy); los cortos, minuto a minuto

INTERVAL_MINUTES = {'1': 1, '5': 5, '15': 15, '60': 60, '120': 120, '240': 240, 'D': 1440}


def compute_regimes(df: pd.DataFrame, trending: float, ranging: float, ambiguous_as: str) -> np.ndarray:
    """Régimen por vela, vectorizado. Misma lógica que indicators.regime_indicators.classify_regime."""
    atr = calculate_atr(df)
    adx = calculate_adx(df)
    bbw = calculate_bb_width(df)
    atr_avg = atr.rolling(50).mean()
    bbw_avg = bbw.rolling(50).mean()
    conditions = [
        (atr > atr_avg * 1.8).to_numpy(),
        (adx > trending).to_numpy(),
        ((adx < ranging) & (bbw < bbw_avg)).to_numpy(),
    ]
    return np.select(conditions, ["VOLATILE", "TRENDING", "RANGING"], default=ambiguous_as)


class BacktestEngine:

    INTERVAL_MINUTES = INTERVAL_MINUTES

    def __init__(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        regime_data: dict | None = None,
        minute_df: pd.DataFrame | None = None,
        trade_from=None,
        funding=None,
    ):
        self.strategy           = strategy
        self.df                 = df.reset_index(drop=True).copy()
        self.initial_balance    = initial_balance
        self.balance            = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_leverage       = float(getattr(strategy, 'max_leverage', 1.0) or 1.0)
        self.commission_rate    = float(getattr(strategy, 'commission_pct', 0.0) or 0.0) / 100
        self.slippage_rate      = float(getattr(strategy, 'slippage_pct', 0.0) or 0.0) / 100
        self.regime_data        = regime_data or {}
        self.trade_from         = pd.Timestamp(trade_from) if trade_from is not None else None
        self.trades: list[dict] = []
        self.interval_minutes   = INTERVAL_MINUTES.get(str(getattr(strategy, 'interval', '60')), 60)

        # Funding (collectors.funding_collector.FundingData): liquidaciones UTC sin tz + tasas
        self._f_time = self._f_rate = None
        if funding is not None and len(funding.times):
            self._f_time = np.asarray(funding.times, dtype='datetime64[ns]')
            self._f_rate = np.asarray(funding.rates, dtype=float)
        self._bar_t = self._bar_open = None   # velas principales (las fija run) para el precio de liquidación

        # Trailing en línea (_scan): mismo cálculo que BaseStrategy.calculate_trailing_sl. Si la estrategia lo
        # redefine, o el modo no es uno de los conocidos, se usa su método minuto a minuto (_step).
        self._trail_mode = getattr(strategy, 'trailing_mode', None) or None
        self._fast_trailing = (type(strategy).calculate_trailing_sl is BaseStrategy.calculate_trailing_sl
                               and self._trail_mode in (None, 'fixed', 'stepped', 'atr'))
        buf = getattr(strategy, 'trailing_activation_buffer_pct', 0.0)
        if self._trail_mode == 'fixed' and not (buf and buf > 0):
            buf = NATIVE_TRAILING_MIN_BUFFER_PCT   # igual que calculate_trailing_sl_standalone
        self._trail_buf = buf

        # Velas de 1m como arrays (búsqueda binaria, sin iterrows)
        self._m_time = self._m_high = self._m_low = self._m_close = None
        if minute_df is not None and not minute_df.empty and self.interval_minutes > 1:
            self._m_time, self._m_high, self._m_low, self._m_close = _minute_arrays(minute_df)

    # ─────────────────────────────── helpers ───────────────────────────────

    def _fill(self, price: float, side: str, is_entry: bool) -> float:
        """Precio ejecutado con slippage en contra (compra más cara, venta más barata)."""
        buying = (side == 'long') == is_entry
        return price * (1 + self.slippage_rate) if buying else price * (1 - self.slippage_rate)

    def _position_size(self, entry: float, sl: float) -> float:
        distance = abs(entry - sl)
        if distance <= 0:
            return 0.0
        raw  = self.balance * (self.risk_per_trade_pct / 100) / distance
        capd = self.balance * self.max_leverage / entry  # tope de nocional (sin apalancamiento implícito)
        return round(min(raw, capd), 6)

    @staticmethod
    def _np_time(t) -> np.datetime64:
        """Instante como datetime64[ns] UTC sin tz (igual que las velas de 1m y el funding)."""
        ts = pd.Timestamp(t)
        if ts.tzinfo is not None:
            ts = ts.tz_convert('UTC').tz_localize(None)
        return ts.to_datetime64().astype('datetime64[ns]')

    def _price_at(self, ft: np.datetime64) -> float:
        """Precio al momento de la liquidación: cierre del último minuto previo; sin 1m, open de la vela que la contiene."""
        if self._m_time is not None:
            k = int(np.searchsorted(self._m_time, ft, side='left')) - 1
            if k >= 0 and ft - self._m_time[k] <= np.timedelta64(1, 'm'):
                return float(self._m_close[k])
        k = max(0, int(np.searchsorted(self._bar_t, ft, side='right')) - 1)
        return float(self._bar_open[k])

    def _funding(self, pos: dict, exit_lo, exit_hi) -> float:
        """
        Funding neto del trade (positivo = costo). La salida ocurrió en algún momento de [exit_lo, exit_hi]:
        lo que se PAGA cuenta en [entrada, exit_hi]; lo que se COBRA solo en (entrada, exit_lo).
        """
        if self._f_time is None:
            return 0.0
        t0, lo, hi = self._np_time(pos['entry_time']), self._np_time(exit_lo), self._np_time(exit_hi)
        a = int(np.searchsorted(self._f_time, t0, side='left'))
        b = int(np.searchsorted(self._f_time, hi, side='right'))
        sign = 1.0 if pos['side'] == 'long' else -1.0
        total = 0.0
        for k in range(a, b):
            ft = self._f_time[k]
            cost = sign * self._f_rate[k] * pos['size'] * self._price_at(ft)
            if cost > 0 or (t0 < ft < lo):
                total += cost
        return total

    def _step(self, pos: dict, high: float, low: float, atr: float | None) -> tuple[float | None, str | None]:
        """Una sub-vela: SL vigente -> TP1 -> break-even -> trailing. Devuelve (nivel, motivo) o (None, None)."""
        long = pos['side'] == 'long'
        if (long and low <= pos['sl']) or (not long and high >= pos['sl']):
            return pos['sl'], ('trailing_stop' if pos['trailing_applied'] else 'stop_loss')
        tp = pos['tp1']
        if tp is not None and ((long and high >= tp) or (not long and low <= tp)):
            return tp, 'take_profit_1'
        if not pos['be_activated'] and ((long and high >= pos['be_level']) or (not long and low <= pos['be_level'])):
            pos['sl'] = max(pos['sl'], pos['entry_price']) if long else min(pos['sl'], pos['entry_price'])
            pos['be_activated'] = True
        if getattr(self.strategy, 'trailing_mode', None):
            new_sl = self.strategy.calculate_trailing_sl(
                pos['entry_price'], pos['side'], high if long else low, pos['sl'], current_atr=atr)
            if new_sl != pos['sl']:
                pos['sl'] = new_sl
                pos['trailing_applied'] = True
        return None, None

    def _scan(self, pos: dict, highs: np.ndarray, lows: np.ndarray, atr: float | None, raw: bool = False) -> tuple:
        """
        Las sub-velas de una vela, en orden, con EXACTAMENTE la regla de _step (SL vigente -> TP1 -> break-even ->
        trailing). Los tramos donde no puede ocurrir nada (sin SL, TP, break-even ni activación del trailing) se saltan
        en bloque con numpy; desde el primer evento, minuto a minuto. Devuelve (índice, nivel, motivo) o (None, None, None).
        raw=True: vela completa (sin 1m): los precios pasan como numpy.float64, igual que a _step en ese caso (el
        redondeo de numpy y el de Python pueden diferir en el último decimal: se conserva el mismo tipo).
        """
        n = len(highs)
        if not self._fast_trailing:   # trailing propio de la estrategia: la regla original, minuto a minuto
            for k in range(n):
                level, reason = (self._step(pos, highs[k], lows[k], atr) if raw
                                 else self._step(pos, float(highs[k]), float(lows[k]), atr))
                if level is not None:
                    return k, level, reason
            return None, None, None

        s = self.strategy
        long = pos['side'] == 'long'
        entry, tp, be_level = pos['entry_price'], pos['tp1'], pos['be_level']
        mode = self._trail_mode
        buf = self._trail_buf
        block = n > BLOCK_MIN   # tramos cortos: más rápido minuto a minuto que preparar numpy
        k = 0
        while k < n:
            if not block:
                j = 0
            else:
                j = self._next_event(pos, highs[k:], lows[k:], long, entry, tp, be_level, mode, buf, atr)
                if j is None:
                    return None, None, None
            k += j
            # 2. Desde ahí, la regla de _step minuto a minuto (trailing en línea, igual que calculate_trailing_sl)
            while k < n:
                high, low = (highs[k], lows[k]) if raw else (float(highs[k]), float(lows[k]))
                sl = pos['sl']
                if (long and low <= sl) or (not long and high >= sl):
                    return k, sl, ('trailing_stop' if pos['trailing_applied'] else 'stop_loss')
                if tp is not None and ((long and high >= tp) or (not long and low <= tp)):
                    return k, tp, 'take_profit_1'
                if not pos['be_activated'] and ((long and high >= be_level) or (not long and low <= be_level)):
                    pos['sl'] = sl = max(sl, entry) if long else min(sl, entry)
                    pos['be_activated'] = True
                if mode is None:
                    k += 1
                    break          # sin trailing: vuelve al salto en bloque
                price = high if long else low
                gain_pct = (price - entry) / entry * 100 if long else (entry - price) / entry * 100
                if gain_pct <= buf:
                    k += 1
                    break          # sin trailing en este minuto: vuelve al salto en bloque
                new_sl = sl
                if mode == 'fixed':
                    distance = entry * s.trailing_distance_pct / 100
                    new_sl = max(sl, price - distance) if long else min(sl, price + distance)
                elif mode == 'stepped':
                    applicable = [st for st in (s.trailing_steps or []) if gain_pct >= st[0]]
                    if applicable:
                        step_pct = max(applicable, key=lambda st: st[0])[1]
                        new_sl = max(sl, entry * (1 + step_pct / 100)) if long else min(sl, entry * (1 - step_pct / 100))
                elif mode == 'atr' and atr and atr > 0:
                    new_sl = max(sl, price - atr * s.trailing_atr_mult) if long else min(sl, price + atr * s.trailing_atr_mult)
                new_sl = round(new_sl, 8)
                if new_sl != sl:
                    pos['sl'] = new_sl
                    pos['trailing_applied'] = True
                k += 1
                break              # vuelve al salto en bloque con el SL actualizado
        return None, None, None

    def _next_event(self, pos: dict, hs: np.ndarray, ls: np.ndarray, long: bool, entry: float, tp, be_level: float,
                    mode, buf: float, atr: float | None) -> int | None:
        """Primer minuto del tramo donde puede pasar algo (SL, TP, break-even o un movimiento del trailing). None = ninguno."""
        sl = pos['sl']
        ev = (ls <= sl) if long else (hs >= sl)
        if tp is not None:
            ev = ev | ((hs >= tp) if long else (ls <= tp))
        if not pos['be_activated']:
            ev = ev | ((hs >= be_level) if long else (ls <= be_level))
        if mode is not None:
            # Trailing activo (ganancia > colchón): solo es evento si puede mover el SL — el candidato lo supera,
            # o el SL vigente aún no está redondeado (calculate_trailing_sl redondea a 8 decimales).
            gain = ((hs - entry) / entry * 100) if long else ((entry - ls) / entry * 100)
            active = gain > buf
            if round(sl, 8) != sl:
                ev = ev | active
            else:
                cand = self._trail_candidates(long, entry, hs if long else ls, gain, atr)
                if cand is not None:
                    ev = ev | (active & ((cand > sl) if long else (cand < sl)))
        j = int(ev.argmax())
        return j if ev[j] else None

    def _trail_candidates(self, long: bool, entry: float, prices: np.ndarray, gain: np.ndarray,
                          atr: float | None) -> np.ndarray | None:
        """SL candidato del trailing en cada sub-vela (mismo cálculo que calculate_trailing_sl, sin redondear).
        None = el trailing no propone nada (solo redondea el SL vigente)."""
        s, mode = self.strategy, self._trail_mode
        if mode == 'fixed':
            d = entry * s.trailing_distance_pct / 100
            return prices - d if long else prices + d
        if mode == 'atr':
            if not (atr and atr > 0):
                return None
            return prices - atr * s.trailing_atr_mult if long else prices + atr * s.trailing_atr_mult
        if mode == 'stepped':
            steps = s.trailing_steps or []
            if not steps:
                return None
            cand = np.full(len(prices), -np.inf if long else np.inf)
            best = np.full(len(prices), -np.inf)
            for st in steps:   # el escalón aplicable de mayor umbral (empates: el primero, como max())
                take = (gain >= st[0]) & (st[0] > best)
                best = np.where(take, st[0], best)
                cand = np.where(take, entry * (1 + st[1] / 100) if long else entry * (1 - st[1] / 100), cand)
            return cand
        return None

    def _close(self, pos: dict, level: float, reason: str, exit_time, bars_held: int, exit_span=None) -> None:
        exit_price = self._fill(level, pos['side'], is_entry=False)
        size = pos['size']
        gross = (exit_price - pos['entry_price']) * size if pos['side'] == 'long' else (pos['entry_price'] - exit_price) * size
        commission = (pos['entry_price'] + exit_price) * size * self.commission_rate
        funding = self._funding(pos, *(exit_span or (exit_time, exit_time)))
        pnl = gross - commission - funding
        pnl_pct = pnl / self.balance * 100
        self.balance += pnl
        self.trades.append({
            "entry_time":   pos['entry_time'],
            "exit_time":    exit_time,
            "symbol":       self.strategy.symbol,
            "side":         pos['side'],
            "entry_price":  pos['entry_price'],
            "exit_price":   exit_price,
            "exit_level":   level,
            "sl":           pos['sl'],
            "tp1":          pos['tp1'],
            "tp2":          pos['tp2'],
            "tp3":          pos['tp3'],
            "tp4":          pos['tp4'],
            "size":         size,
            "gross_pnl":    round(gross, 4),
            "commission":   round(commission, 4),
            "funding":      round(funding, 4),
            "pnl":          round(pnl, 4),
            "pnl_pct":      round(pnl_pct, 4),
            "exit_reason":  reason,
            "bars_open":    bars_held,
            "be_activated": pos['be_activated'],
            "trailing_applied": pos['trailing_applied'],
            "regime":       pos['regime'],
        })

    # ─────────────────────────────── simulación ───────────────────────────────

    def run(self) -> dict:
        s = self.strategy
        logger.info(f"Iniciando backtest: {s.name} | {s.symbol} | {len(self.df)} velas")

        df = s.compute_signals(self.df)
        n = len(df)
        times  = pd.to_datetime(df['time'])
        opens  = df['open'].to_numpy(dtype=float)
        highs  = df['high'].to_numpy(dtype=float)
        lows   = df['low'].to_numpy(dtype=float)
        closes = df['close'].to_numpy(dtype=float)
        self._bar_t = pd.to_datetime(df['time'], utc=True).dt.tz_convert(None).to_numpy(dtype='datetime64[ns]')
        self._bar_open = opens
        bar_times = list(times)   # Timestamps (lo mismo que times.iloc[i], sin el costo de pandas por vela)
        m_lo = m_hi = None        # velas de 1m de cada vela grande: [m_lo[i], m_hi[i]) en _m_time
        if self._m_time is not None:
            m_lo = np.searchsorted(self._m_time, self._bar_t, side='left')
            m_hi = np.searchsorted(self._m_time, self._bar_t + np.timedelta64(int(self.interval_minutes), 'm'), side='left')
        signals = df['signal'].fillna(0).astype(int).to_numpy()
        signal_sl = df['signal_sl_pct'].to_numpy(dtype=float) if 'signal_sl_pct' in df.columns else None

        if self.regime_data:
            regimes = np.array([self.regime_data.get(str(t), "TRENDING") for t in df['time']])
        else:
            regimes = compute_regimes(df, getattr(s, 'regime_adx_trending', 25),
                                      getattr(s, 'regime_adx_ranging', 20),
                                      getattr(s, 'regime_ambiguous_as', 'RANGING'))

        needs_atr = getattr(s, 'volatility_protection_mode', None) is not None or getattr(s, 'trailing_mode', None) == 'atr'
        atr = calculate_atr(df).to_numpy() if needs_atr else None
        atr_avg = pd.Series(atr).rolling(50).mean().to_numpy() if needs_atr else None

        first_trade_idx = 1
        if self.trade_from is not None:  # velas previas: solo calentamiento de indicadores
            tf = self.trade_from
            if times.dt.tz is not None and tf.tzinfo is None:
                tf = tf.tz_localize('UTC')
            elif times.dt.tz is None and tf.tzinfo is not None:
                tf = tf.tz_convert('UTC').tz_localize(None)
            first_trade_idx = max(1, int((times < tf).sum()))
        step = timedelta(minutes=self.interval_minutes)
        exit_on_opposite = bool(getattr(s, 'close_on_opposite', False) or getattr(s, 'exit_on_opposite', False))
        reverse_on_opposite = not bool(getattr(s, 'exit_on_opposite', False))
        allow_short = bool(getattr(s, 'allow_short', True))
        max_duration = int(getattr(s, 'max_duration', 0) or 0)
        equity_curve = [self.initial_balance]
        pos = None
        one_ns, one_min = pd.Timedelta(1, 'ns'), pd.Timedelta(minutes=1)

        for i in range(max(1, first_trade_idx), n):
            prev_signal = signals[i - 1]
            if pos is None and prev_signal == 0:   # sin posición ni señal: la vela no cambia nada
                continue
            bar_time = bar_times[i]

            # 1. Señal opuesta (vela i-1 cerrada) -> salida al open de la vela i
            if pos is not None and exit_on_opposite and prev_signal != 0:
                if (pos['side'] == 'long' and prev_signal == -1) or (pos['side'] == 'short' and prev_signal == 1):
                    self._close(pos, opens[i], 'opposite_signal', bar_time, i - pos['entry_bar'])
                    pos = None
                    equity_curve.append(self.balance)
                    if not reverse_on_opposite:
                        continue

            # 2. Entrada al open de la vela i con señal y régimen de la vela i-1 (ambos ya conocidos)
            if pos is None and prev_signal != 0:
                side = 'long' if prev_signal == 1 else 'short'
                regime = str(regimes[i - 1])
                if (side == 'long' or allow_short) and s.should_operate(regime):
                    entry = self._fill(opens[i], side, is_entry=True)
                    sl_pct = signal_sl[i - 1] if signal_sl is not None and not np.isnan(signal_sl[i - 1]) else s.sl_pct
                    sl = round(entry * (1 - sl_pct / 100) if side == 'long' else entry * (1 + sl_pct / 100), 8)
                    levels = s.calculate_tp_levels(entry, side)
                    size = self._position_size(entry, sl)
                    if size > 0:
                        pos = {
                            'side': side, 'entry_price': entry, 'entry_time': bar_time, 'entry_bar': i,
                            'sl': sl, 'tp1': levels['tp1'], 'tp2': levels.get('tp2'), 'tp3': levels.get('tp3'),
                            'tp4': levels.get('tp4'), 'be_level': s.calculate_breakeven(entry, side),
                            'be_activated': False, 'trailing_applied': False, 'size': size, 'regime': regime,
                            'vol_widened': False,
                        }

            if pos is None:
                continue

            # 3. Gestión DURANTE la vela i (incluida la vela de entrada)
            # Trailing durante la vela i: ATR de la vela i-1 (cerrada). El de i incluye su high/low.
            trail_atr = float(atr[i - 1]) if needs_atr and not np.isnan(atr[i - 1]) else None
            bar_atr = float(atr[i]) if needs_atr and not np.isnan(atr[i]) else None  # al cierre de i
            level = reason = exit_span = None
            a, b = (int(m_lo[i]), int(m_hi[i])) if m_lo is not None else (0, 0)
            if a < b:
                k, level, reason = self._scan(pos, self._m_high[a:b], self._m_low[a:b], trail_atr)
                if level is not None:
                    m0 = pd.Timestamp(self._m_time[a + k])
                    exit_span = (m0, m0 + one_min - one_ns)
            else:
                _, level, reason = self._scan(pos, highs[i:i + 1], lows[i:i + 1], trail_atr, raw=True)

            bars_held = i - pos['entry_bar'] + 1
            if level is None and needs_atr and getattr(s, 'volatility_protection_mode', None):
                vol = s.check_volatility_protection(pos['sl'], pos['side'], bar_atr or 0.0,
                                                    float(atr_avg[i]) if not np.isnan(atr_avg[i]) else 0.0)
                if vol['action'] == 'close':
                    level, reason = closes[i], 'volatility_protection'
                elif vol['action'] == 'widen' and vol['new_sl'] is not None and not pos['vol_widened']:
                    pos['sl'] = vol['new_sl']   # una sola vez por trade (igual que paper y real)
                    pos['vol_widened'] = True

            if level is None and max_duration > 0 and bars_held >= max_duration:
                in_profit = closes[i] > pos['entry_price'] if pos['side'] == 'long' else closes[i] < pos['entry_price']
                if not getattr(s, 'max_duration_profit', False):
                    level, reason = closes[i], 'time_exit'
                elif in_profit:
                    level, reason = closes[i], 'time_exit_profit'

            if level is not None:
                at_close = reason in ('volatility_protection', 'time_exit', 'time_exit_profit')
                if at_close:
                    exit_span = (bar_time + step, bar_time + step)
                elif exit_span is None:   # salida dentro de la vela sin 1m: momento exacto desconocido
                    exit_span = (bar_time, bar_time + step - one_ns)
                self._close(pos, level, reason, bar_time + step if at_close else bar_time, bars_held, exit_span)
                pos = None
                equity_curve.append(self.balance)

        metrics = calculate_metrics(self.trades, self.initial_balance)
        metrics['equity_curve'] = equity_curve
        logger.info(f"Backtest completo: {metrics['total_trades']} trades | WR: {metrics['win_rate']}% | "
                    f"PF: {metrics['profit_factor']} | Sharpe: {metrics['sharpe_ratio']} | DD: {metrics['max_drawdown_pct']}%")
        return {
            "backtest_id": f"BT-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{s.symbol}-{s.name.replace(' ', '_').upper()}",
            "strategy":    s.name,
            "symbol":      s.symbol,
            "interval":    s.interval,
            "total_bars":  n,
            "metrics":     metrics,
            "trades":      self.trades,
        }

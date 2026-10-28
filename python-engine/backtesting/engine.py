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
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from backtesting.metrics import calculate_metrics
from backtesting.strategies.base_strategy import BaseStrategy
from indicators.regime_indicators import calculate_adx, calculate_atr, calculate_bb_width

logger = logging.getLogger(__name__)

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

        # Velas de 1m como arrays (búsqueda binaria, sin iterrows)
        self._m_time = self._m_high = self._m_low = self._m_close = None
        if minute_df is not None and not minute_df.empty and self.interval_minutes > 1:
            m = minute_df.sort_values('time')
            self._m_time  = pd.to_datetime(m['time'], utc=True).dt.tz_convert(None).to_numpy()  # UTC naive
            self._m_high  = m['high'].to_numpy(dtype=float)
            self._m_low   = m['low'].to_numpy(dtype=float)
            self._m_close = m['close'].to_numpy(dtype=float)

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

    def _sub_bars(self, start, end):
        """(times, highs, lows) de las velas de 1m en [start, end). None si no hay datos de 1m."""
        if self._m_time is None:
            return None
        a = np.searchsorted(self._m_time, self._np_time(start), side='left')
        b = np.searchsorted(self._m_time, self._np_time(end), side='left')
        if a >= b:
            return None
        return self._m_time[a:b], self._m_high[a:b], self._m_low[a:b]

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
        if self._f_time is not None:
            self._bar_t = pd.to_datetime(df['time'], utc=True).dt.tz_convert(None).to_numpy(dtype='datetime64[ns]')
            self._bar_open = opens
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

        for i in range(max(1, first_trade_idx), n):
            bar_time = times.iloc[i]
            prev_signal = signals[i - 1]

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
            sub = self._sub_bars(bar_time, bar_time + step)
            level = reason = None
            one_ns = pd.Timedelta(1, 'ns')
            exit_span = (bar_time, bar_time + step - one_ns)   # salida dentro de la vela: momento exacto desconocido
            if sub is not None:
                for mt, h, l in zip(*sub):
                    level, reason = self._step(pos, float(h), float(l), trail_atr)
                    if level is not None:
                        m0 = pd.Timestamp(mt)
                        exit_span = (m0, m0 + pd.Timedelta(minutes=1) - one_ns)
                        break
            else:
                level, reason = self._step(pos, highs[i], lows[i], trail_atr)

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

"""
Backtesting Engine V2 — Extendido
Motor genérico que simula trades sobre datos históricos.
Soporta: SL, hasta 4 niveles de TP, Break-even, Trailing Stop,
Proteccion por volatilidad, Cierre por tiempo, Filtro de régimen.
"""

import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
from backtesting.metrics import calculate_metrics
from backtesting.strategies.base_strategy import BaseStrategy
from indicators.regime_indicators import calculate_atr

logger = logging.getLogger(__name__)


class BacktestEngine:

    # Duracion en minutos de cada intervalo soportado - usado para decidir
    # si aplica la simulacion de salida granular (1 min) y para acotar el
    # rango de velas de 1 min que corresponden a cada vela de la estrategia.
    INTERVAL_MINUTES = {'1': 1, '5': 5, '15': 15, '60': 60, '120': 120, '240': 240, 'D': 1440}

    def __init__(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        regime_data: dict | None = None,
        minute_df: pd.DataFrame | None = None,
    ):
        self.strategy            = strategy
        self.df                  = df.copy()
        self.initial_balance     = initial_balance
        self.balance             = initial_balance
        self.risk_per_trade_pct  = risk_per_trade_pct
        self.regime_data         = regime_data or {}
        self.trades              = []

        # Simulacion de salida granular (2026-07-09): para intervalos >= H1
        # con trailing activo, el SL/BE/trailing/TP se evalua vela a vela de
        # 1 minuto dentro de cada vela de la estrategia, en vez de una sola
        # vez con el high/low agregado de toda la vela grande. Sin esto, el
        # backtest le da al trailing hasta 1 vela COMPLETA de retraso (ver
        # comentario historico mas abajo) - mucho mas permisivo que Paper
        # (que ya monitorea a 1 min) y que el trailing nativo de Bybit en
        # real (reacciona tick a tick). Resultado: backtest sistematicamente
        # mas optimista que produccion para estrategias con trailing en H1+.
        self.minute_df = None
        if minute_df is not None and not minute_df.empty:
            # Indexado por tiempo (DatetimeIndex ordenado) en vez de solo
            # ordenar + reset_index - permite busqueda binaria (searchsorted,
            # O(log n)) en vez de escanear el dataset completo con una
            # mascara booleana en cada vela con posicion abierta (era el
            # cuello de botella real: O(n) por vela, ~1M filas en 2 años).
            self.minute_df = minute_df.sort_values('time').set_index('time')

        interval_minutes = self.INTERVAL_MINUTES.get(getattr(strategy, 'interval', None), 0)
        self.use_minute_exit = (
            self.minute_df is not None
            and getattr(strategy, 'trailing_mode', None) is not None
            and interval_minutes >= 60
        )

    def _get_regime_at(self, timestamp) -> str:
        if not self.regime_data:
            return "TRENDING"
        return self.regime_data.get(str(timestamp), "TRENDING")

    def _calculate_position_size(self, entry_price: float, sl_price: float) -> float:
        risk_amount = self.balance * (self.risk_per_trade_pct / 100)
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            return 0.0
        return round(risk_amount / sl_distance, 6)

    def _simulate_exit_minute_bars(self, position: dict, row_time, interval_minutes: int) -> tuple[float | None, str | None, bool]:
        """
        Recorre las velas de 1 minuto correspondientes a la vela de la
        estrategia (row_time, row_time + interval_minutes) evaluando BE, SL,
        trailing y TP en orden cronologico real - mismo criterio y orden que
        paper_trader.py's monitor_open_trades(). Actualiza position in-place
        (sl, be_activated, trailing_applied). Devuelve (exit_price, exit_reason)
        o (None, None) si no se cerro dentro de esta vela.

        NOTA: si no hay velas de 1 min en el rango (hueco de datos), no hace
        nada aca - el caller cae de vuelta al chequeo con el high/low de la
        vela grande como fallback.
        """
        window_end = row_time + timedelta(minutes=interval_minutes)
        start_idx = self.minute_df.index.searchsorted(row_time, side='left')
        end_idx   = self.minute_df.index.searchsorted(window_end, side='left')
        minute_bars = self.minute_df.iloc[start_idx:end_idx]
        if minute_bars.empty:
            return None, None, False

        for _, mbar in minute_bars.iterrows():
            high = float(mbar['high'])
            low  = float(mbar['low'])

            if not position['be_activated']:
                be_level = position['be_level']
                if position['side'] == 'long' and high >= be_level:
                    position['sl'] = position['entry_price']
                    position['be_activated'] = True
                elif position['side'] == 'short' and low <= be_level:
                    position['sl'] = position['entry_price']
                    position['be_activated'] = True

            # SL - etiqueta segun si el trailing ya estaba activo ANTES de
            # este chequeo (mismo criterio que el fix de 2026-07-09 en
            # paper_trader.py/real_trader.py: distinguir stop_loss original
            # de trailing_stop, no ambos como 'stop_loss' generico).
            sl_label = 'trailing_stop' if position.get('trailing_applied') else 'stop_loss'
            if position['side'] == 'long' and low <= position['sl']:
                return position['sl'], sl_label, True
            elif position['side'] == 'short' and high >= position['sl']:
                return position['sl'], sl_label, True

            if hasattr(self.strategy, 'calculate_trailing_sl') and self.strategy.trailing_mode:
                ref_price = high if position['side'] == 'long' else low
                new_sl = self.strategy.calculate_trailing_sl(
                    position['entry_price'], position['side'], ref_price, position['sl']
                )
                if new_sl != position['sl']:
                    position['sl'] = new_sl
                    position['trailing_applied'] = True

            for key, label in [('tp4', 'take_profit_4'), ('tp3', 'take_profit_3'),
                                ('tp2', 'take_profit_2'), ('tp1', 'take_profit_1')]:
                level = position.get(key)
                if level is None:
                    continue
                if position['side'] == 'long' and high >= level:
                    return level, label, True
                elif position['side'] == 'short' and low <= level:
                    return level, label, True

        return None, None, True

    def _get_active_tp(self, position: dict) -> tuple[float | None, str | None]:
        """
        Devuelve el nivel de TP activo con mayor prioridad (TP4 > TP3 > TP2 > TP1)
        entre los definidos para esta posicion.
        """
        for key, label in [('tp4', 'take_profit_4'), ('tp3', 'take_profit_3'),
                            ('tp2', 'take_profit_2'), ('tp1', 'take_profit_1')]:
            if position.get(key) is not None:
                return position[key], label
        return None, None

    def run(self) -> dict:
        logger.info(f"Iniciando backtest: {self.strategy.name} | {self.strategy.symbol} | {len(self.df)} velas")

        df = self.strategy.prepare(self.df)
        df = self.strategy.generate_signals(df)

        # Precalcular ATR para proteccion por volatilidad, si esta activada
        needs_atr = getattr(self.strategy, 'volatility_protection_mode', None) is not None
        if needs_atr:
            df['_atr']     = calculate_atr(df)
            df['_atr_avg'] = df['_atr'].rolling(50).mean()

        position     = None
        equity_curve = [self.initial_balance]

        for i in range(1, len(df)):
            row  = df.iloc[i]
            prev = df.iloc[i - 1]

            # ── Gestión de posición abierta ──────────────────────────────
            if position is not None:
                high  = float(row['high'])
                low   = float(row['low'])
                close = float(row['close'])
                bars_open = i - position['entry_bar']

                exit_price  = None
                exit_reason = None

                # Simulacion granular (1 min) para BE/SL/trailing, cuando
                # aplica (interval >= H1, trailing activo, hay minute_df
                # disponible). Reemplaza el chequeo con el high/low de la
                # vela grande - actualiza position['sl']/be_activated/
                # trailing_applied in-place y puede devolver un cierre ya
                # resuelto (incluye su propio chequeo de TP internamente).
                used_minute_bars = False
                if self.use_minute_exit:
                    row_time = row.get('time', None)
                    if row_time is not None:
                        interval_minutes = self.INTERVAL_MINUTES.get(self.strategy.interval, 60)
                        exit_price, exit_reason, used_minute_bars = self._simulate_exit_minute_bars(
                            position, row_time, interval_minutes
                        )

                if not used_minute_bars:
                    # Fallback al comportamiento original: sin minute_df para
                    # esta vela (hueco de datos), sin trailing, o interval < H1.
                    # Break-even: mover SL a entrada si precio llegó al nivel BE
                    if not position['be_activated']:
                        be_level = position['be_level']
                        if position['side'] == 'long' and high >= be_level:
                            position['sl'] = position['entry_price']
                            position['be_activated'] = True
                        elif position['side'] == 'short' and low <= be_level:
                            position['sl'] = position['entry_price']
                            position['be_activated'] = True

                    # Stop Loss — se evalúa con el SL vigente ANTES de aplicar el
                    # trailing de esta vela. Evita look-ahead bias: no podemos
                    # asumir que el high (usado para mover el trailing) ocurrió
                    # antes que el low (usado para disparar el SL) dentro de la
                    # misma vela OHLC.
                    if position['side'] == 'long' and low <= position['sl']:
                        exit_price  = position['sl']
                        exit_reason = 'stop_loss'
                    elif position['side'] == 'short' and high >= position['sl']:
                        exit_price  = position['sl']
                        exit_reason = 'stop_loss'

                    # Trailing Stop (independiente del break-even, puede moverlo mas)
                    # Solo se aplica si la posición no se cerró por SL en esta vela;
                    # su efecto rige recién desde la vela siguiente.
                    if exit_price is None and hasattr(self.strategy, 'calculate_trailing_sl') and self.strategy.trailing_mode:
                        ref_price = high if position['side'] == 'long' else low
                        new_sl = self.strategy.calculate_trailing_sl(
                            position['entry_price'], position['side'], ref_price, position['sl']
                        )
                        if new_sl != position['sl']:
                            position['sl'] = new_sl
                            position['trailing_applied'] = True

                # Proteccion por volatilidad
                if exit_price is None and needs_atr and hasattr(self.strategy, 'check_volatility_protection'):
                    current_atr = float(row['_atr']) if pd.notna(row['_atr']) else 0
                    avg_atr     = float(row['_atr_avg']) if pd.notna(row['_atr_avg']) else 0

                    vol_check = self.strategy.check_volatility_protection(
                        position['sl'], position['side'], current_atr, avg_atr
                    )

                    if vol_check['action'] == 'close':
                        exit_price  = close
                        exit_reason = 'volatility_protection'
                    elif vol_check['action'] == 'widen' and vol_check['new_sl'] is not None:
                        position['sl'] = vol_check['new_sl']

                # Take Profit — evaluar niveles de mayor a menor prioridad
                if exit_price is None:
                    for key, label in [('tp4', 'take_profit_4'), ('tp3', 'take_profit_3'),
                                        ('tp2', 'take_profit_2'), ('tp1', 'take_profit_1')]:
                        level = position.get(key)
                        if level is None:
                            continue
                        if position['side'] == 'long' and high >= level:
                            exit_price, exit_reason = level, label
                            break
                        elif position['side'] == 'short' and low <= level:
                            exit_price, exit_reason = level, label
                            break

                # Cierre por tiempo
                if exit_price is None and bars_open >= self.strategy.max_duration:
                    exit_price  = close
                    exit_reason = 'time_exit'

                # Registrar trade cerrado
                if exit_price is not None:
                    if position['side'] == 'long':
                        gross_pnl = (exit_price - position['entry_price']) * position['size']
                    else:
                        gross_pnl = (position['entry_price'] - exit_price) * position['size']

                    # Comision sobre el valor nocional, entrada + salida (mismo
                    # criterio que BYBIT_TAKER_FEE en real_trader.py). Antes de
                    # 2026-07-09 el backtest no descontaba ningun costo aca.
                    commission_pct = getattr(self.strategy, 'commission_pct', 0.0) / 100
                    entry_notional = position['entry_price'] * position['size']
                    exit_notional  = exit_price * position['size']
                    commission = (entry_notional + exit_notional) * commission_pct
                    pnl = gross_pnl - commission

                    pnl_pct = pnl / self.balance * 100
                    self.balance += pnl

                    self.trades.append({
                        "entry_time":   position['entry_time'],
                        "exit_time":    row['time'] if 'time' in df.columns else str(i),
                        "symbol":       self.strategy.symbol,
                        "side":         position['side'],
                        "entry_price":  position['entry_price'],
                        "exit_price":   exit_price,
                        "sl":           position['sl'],
                        "tp1":          position.get('tp1'),
                        "tp2":          position.get('tp2'),
                        "tp3":          position.get('tp3'),
                        "tp4":          position.get('tp4'),
                        "size":         position['size'],
                        "gross_pnl":    round(gross_pnl, 4),
                        "commission":   round(commission, 4),
                        "pnl":          round(pnl, 4),
                        "pnl_pct":      round(pnl_pct, 4),
                        "exit_reason":  exit_reason,
                        "bars_open":    bars_open,
                        "be_activated": position['be_activated'],
                        "trailing_applied": position.get('trailing_applied', False),
                        "regime":       position['regime'],
                    })

                    position = None
                    equity_curve.append(self.balance)

            # ── Nueva entrada ────────────────────────────────────────────
            if position is None and prev['signal'] != 0:
                signal = int(prev['signal'])
                side   = 'long' if signal == 1 else 'short'
                entry  = float(row['open'])

                regime = self._get_regime_at(row.get('time', i))

                if not self.strategy.should_operate(regime):
                    continue

                # SL dinamico: si la estrategia marco un sl_pct especifico para esta
                # señal (ej. zona ADX debil), se usa temporalmente en vez del sl_pct fijo
                effective_sl_pct = prev['signal_sl_pct'] if 'signal_sl_pct' in df.columns else self.strategy.sl_pct

                if side == 'long':
                    sl = entry * (1 - effective_sl_pct / 100)
                else:
                    sl = entry * (1 + effective_sl_pct / 100)
                sl = round(sl, 8)

                tp1 = self.strategy.calculate_sl_tp(entry, side)[1]
                be  = self.strategy.calculate_breakeven(entry, side)
                size = self._calculate_position_size(entry, sl)

                # Niveles TP2-TP4 opcionales
                if hasattr(self.strategy, 'calculate_tp_levels'):
                    tp_levels = self.strategy.calculate_tp_levels(entry, side)
                    tp2, tp3, tp4 = tp_levels.get('tp2'), tp_levels.get('tp3'), tp_levels.get('tp4')
                else:
                    tp2 = self.strategy.calculate_tp2(entry, side) if hasattr(self.strategy, 'calculate_tp2') else None
                    tp3 = None
                    tp4 = None

                if size <= 0:
                    continue

                position = {
                    'side':         side,
                    'entry_price':  entry,
                    'entry_time':   row.get('time', i),
                    'entry_bar':    i,
                    'sl':           sl,
                    'tp1':          tp1,
                    'tp2':          tp2,
                    'tp3':          tp3,
                    'tp4':          tp4,
                    'be_level':     be,
                    'be_activated': False,
                    'trailing_applied': False,
                    'size':         size,
                    'regime':       regime,
                }

        metrics = calculate_metrics(self.trades, self.initial_balance)
        metrics['equity_curve'] = equity_curve

        logger.info(
            f"Backtest completo: {metrics['total_trades']} trades | "
            f"WR: {metrics['win_rate']}% | PF: {metrics['profit_factor']} | "
            f"Sharpe: {metrics['sharpe_ratio']} | DD: {metrics['max_drawdown_pct']}%"
        )

        return {
            "backtest_id": f"BT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self.strategy.symbol}-{self.strategy.name.replace(' ', '_').upper()}",
            "strategy":    self.strategy.name,
            "symbol":      self.strategy.symbol,
            "interval":    self.strategy.interval,
            "total_bars":  len(df),
            "metrics":     metrics,
            "trades":      self.trades,
        }

"""
Paper Trader V2 — Refactorizado
Abre y gestiona posiciones simuladas usando precios en vivo de Bybit.
Los parametros de cada estrategia/simbolo se leen desde config_map
(cargado desde paper_strategy_configs en DB), no hardcodeados.
"""

import asyncpg
import pandas as pd
import logging
import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from trading.bybit_client import get_current_price
from indicators.regime_indicators import calculate_atr, calculate_adx, calculate_bb_width, classify_regime
from trading.risk_manager import RiskManager
from collectors.broker_resolver import closed_bars, interval_delta, resolve_live_broker
from backtesting.strategies.loader import build_strategy

load_dotenv()

logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

VIRTUAL_BALANCE = 10000.0


class PaperTrader:

    def __init__(self, pool: asyncpg.Pool, default_params: dict, config_map: dict | None = None):
        """
        pool:           asyncpg connection pool
        default_params: parámetros base de respaldo (los de cada config los sobrescriben)
        config_map:     {paper_strategy_config_id: config} de las configs ACTIVAS
        """
        self.pool           = pool
        self.default_params = default_params
        self.config_map     = config_map or {}
        self.risk_manager   = RiskManager(pool)

    # ─────────────────────────────────────────────
    # Helpers de params
    # ─────────────────────────────────────────────

    @staticmethod
    def _label(cfg: dict) -> str:
        return f"{cfg['display_name']} [#{cfg['id']}]"

    def _get_params_for(self, config_id: int) -> dict:
        """Parámetros VIVOS de una config activa (para entradas nuevas)."""
        cfg = self.config_map[config_id]
        params = dict(self.default_params)
        cfg_params = cfg['params'] if isinstance(cfg['params'], dict) else json.loads(cfg['params'])
        params.update(cfg_params)
        params['symbol']   = cfg['symbol']
        params['interval'] = cfg['interval']
        return params

    def _trade_params(self, trade: dict) -> dict | None:
        """
        Parámetros CONGELADOS con los que se abrió el trade (config_snapshot).
        Un cambio de config (Auto-Sync) solo afecta a entradas nuevas.
        """
        snapshot = trade.get('config_snapshot')
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        if snapshot:
            return snapshot
        config_id = trade.get('paper_strategy_config_id')
        if config_id in self.config_map:
            logger.warning(f"[PAPER] Trade #{trade['id']} sin config_snapshot (anterior al snapshot): "
                           f"se usa la config viva #{config_id}")
            return self._get_params_for(config_id)
        logger.error(f"[PAPER] Trade #{trade['id']} sin snapshot ni config activa (#{config_id}): no se gestiona")
        return None

    @staticmethod
    def _fill(price: float, side: str, is_entry: bool, params: dict | None) -> float:
        """Precio ejecutado con el slippage de la config, siempre en contra (igual que el backtest)."""
        rate = float((params or {}).get('slippage_pct') or 0.0) / 100
        buying = (side == 'long') == is_entry
        return price * (1 + rate) if buying else price * (1 - rate)

    @staticmethod
    def _closed_bars(df: pd.DataFrame, interval: str, now: datetime) -> pd.DataFrame:
        """Solo velas cerradas (time + intervalo <= ahora), guarde o no el collector la vela en formación."""
        return closed_bars(df, interval, now)

    def _strategy_for_open_trade(self, trade: dict):
        params = self._trade_params(trade)
        if params is None:
            return None
        try:
            return build_strategy(params)
        except Exception as e:
            logger.error(f"[PAPER] Trade #{trade['id']}: la estrategia del snapshot no se puede construir: {e}")
            return None

    # ─────────────────────────────────────────────
    # Datos
    # ─────────────────────────────────────────────

    async def get_bars(self, symbol: str, interval: str, broker: str | None = None) -> pd.DataFrame:
        if broker is None:
            broker = await resolve_live_broker(self.pool, symbol, interval)
            if broker is None:  # sin datos o desactualizados: no operar
                return pd.DataFrame()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE broker = $1 AND symbol = $2 AND interval = $3
                ORDER BY time DESC
                LIMIT 500
                """,
                broker, symbol, interval
            )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df = df.iloc[::-1].reset_index(drop=True)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    async def get_current_regime(self, df: pd.DataFrame, trending_threshold: float = 25,
                                  ranging_threshold: float = 20, ambiguous_as: str = "RANGING") -> str:
        if len(df) < 64:
            return "RANGING"

        atr      = calculate_atr(df)
        adx      = calculate_adx(df)
        bb_width = calculate_bb_width(df)
        atr_avg      = atr.rolling(50).mean()
        bb_width_avg = bb_width.rolling(50).mean()

        last = len(df) - 1
        return classify_regime(
            adx=float(adx.iloc[last]),
            atr=float(atr.iloc[last]),
            atr_avg=float(atr_avg.iloc[last]),
            bb_width=float(bb_width.iloc[last]),
            bb_width_avg=float(bb_width_avg.iloc[last]),
            trending_threshold=trending_threshold,
            ranging_threshold=ranging_threshold,
            ambiguous_as=ambiguous_as,
        )

    # ─────────────────────────────────────────────
    # Posiciones abiertas en DB
    # ─────────────────────────────────────────────

    async def get_open_trades(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, strategy, paper_strategy_config_id, config_snapshot, symbol, interval, side,
                       entry_price, sl, tp, tp2, tp3, tp4, be_level, be_activated, trailing_applied, vol_widened,
                       size, entry_time, regime, max_profit_pct, max_loss_pct, last_monitored_at
                FROM paper_trades
                WHERE status = 'open'
                """
            )
        return [dict(r) for r in rows]

    async def has_open_trade(self, config_id: int) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM paper_trades WHERE paper_strategy_config_id = $1 AND status = 'open'",
                config_id
            )
        return row is not None

    # ─────────────────────────────────────────────
    # Calculo de PnL flotante
    # ─────────────────────────────────────────────

    @staticmethod
    def calculate_floating_pnl_pct(entry_price: float, current_price: float,
                                    side: str, size: float) -> float:
        if side == 'long':
            pnl = (current_price - entry_price) * size
        else:
            pnl = (entry_price - current_price) * size
        return (pnl / VIRTUAL_BALANCE) * 100

    # ─────────────────────────────────────────────
    # Abrir nueva posicion
    # ─────────────────────────────────────────────

    async def open_trade(self, config_id: int, strategy_instance, side: str, entry_price: float, regime: str,
                         signal_sl_pct: float | None = None):
        cfg          = self.config_map[config_id]
        cfg_params   = self._get_params_for(config_id)  # los mismos con los que se construyó strategy_instance
        display_name = cfg['display_name']
        symbol       = cfg['symbol']
        interval     = cfg['interval']
        entry_price  = self._fill(entry_price, side, True, cfg_params)

        if signal_sl_pct is not None:  # SL propuesto por la señal (mismo criterio que el backtest)
            sl = round(entry_price * (1 - signal_sl_pct / 100) if side == 'long'
                       else entry_price * (1 + signal_sl_pct / 100), 8)
        else:
            sl, _ = strategy_instance.calculate_sl_tp(entry_price, side)
        be     = strategy_instance.calculate_breakeven(entry_price, side)
        tp_levels = strategy_instance.calculate_tp_levels(entry_price, side)
        tp, tp2, tp3, tp4 = tp_levels['tp1'], tp_levels['tp2'], tp_levels['tp3'], tp_levels['tp4']
        risk_pct = cfg_params.get('risk_per_trade_pct',
                   self.default_params.get('risk_per_trade_pct', 1.0))
        risk_amount = VIRTUAL_BALANCE * (risk_pct / 100)
        sl_distance = abs(entry_price - sl)
        raw_size    = (risk_amount / sl_distance) if sl_distance > 0 else 0.0
        max_leverage = float(cfg_params.get('max_leverage', 1.0))
        max_size    = (VIRTUAL_BALANCE * max_leverage) / entry_price
        size        = round(min(raw_size, max_size), 6)

        if size <= 0:
            return

        # config_snapshot: parámetros congelados de ESTE trade. La gestión de la
        # posición y la comisión de cierre se calculan con ellos, no con la config viva.
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO paper_trades
                        (strategy, paper_strategy_config_id, symbol, interval, side, entry_price, sl, tp, tp2, tp3, tp4,
                         be_level, be_activated, size, regime, entry_time, status,
                         max_profit_pct, max_loss_pct, config_snapshot, created_at, updated_at)
                    VALUES
                        ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, false, $13, $14, $15, 'open', 0, 0, $16::jsonb, now(), now())
                    """,
                    display_name, config_id, symbol, interval, side, entry_price, sl, tp, tp2, tp3, tp4, be,
                    size, regime, datetime.now(timezone.utc).replace(tzinfo=None),
                    json.dumps(cfg_params)
                )
        except asyncpg.UniqueViolationError:
            logger.warning(f"[PAPER] {self._label(cfg)}: ya existe una posición abierta (tick concurrente); no se duplica")
            return

        logger.info(
            f"[PAPER] OPEN {self._label(cfg)} {symbol} {side.upper()} @ {entry_price} "
            f"SL={sl} TP1={tp} TP2={tp2} TP3={tp3} TP4={tp4} BE={be} regime={regime} interval={interval}"
        )

    # ─────────────────────────────────────────────
    # Cerrar posicion
    # ─────────────────────────────────────────────

    async def close_trade(self, trade: dict, exit_price: float, exit_reason: str):
        entry_price  = float(trade['entry_price'])
        size         = float(trade['size'])
        side         = trade['side']
        trade_params = self._trade_params(trade) or {}
        exit_price   = self._fill(exit_price, side, False, trade_params)

        if side == 'long':
            gross_pnl = (exit_price - entry_price) * size
        else:
            gross_pnl = (entry_price - exit_price) * size

        # Comision configurable por estrategia (misma logica que el motor de
        # backtest: % del valor nocional, entrada + salida). Real NO necesita
        # esto - ya descuenta la comision real de Bybit via BYBIT_TAKER_FEE.
        # Paper si la necesita para reflejar el costo real de operar, igual
        # que backtest - sin esto, Paper subestimaba resultados igual que
        # el backtest lo hacia antes del fix de 2026-07-09.
        cfg_params = trade_params  # comisión con la que se abrió el trade
        # Config sin commission_pct (anterior a 2026-07-09): taker de Bybit, único broker operado
        commission_pct = float(cfg_params.get('commission_pct', 0.055)) / 100
        commission = (entry_price * size + exit_price * size) * commission_pct
        pnl = gross_pnl - commission

        pnl_pct = pnl / VIRTUAL_BALANCE * 100

        max_profit_pct = max(float(trade.get('max_profit_pct', 0)), pnl_pct)
        max_loss_pct   = min(float(trade.get('max_loss_pct', 0)), pnl_pct)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE paper_trades
                SET exit_price = $1, pnl = $2, pnl_pct = $3, exit_reason = $4,
                    exit_time = $5, status = 'closed',
                    max_profit_pct = $6, max_loss_pct = $7, commission = $8,
                    updated_at = now()
                WHERE id = $9
                """,
                exit_price, round(pnl, 4), round(pnl_pct, 4), exit_reason,
                datetime.now(timezone.utc).replace(tzinfo=None),
                round(max_profit_pct, 4), round(max_loss_pct, 4), round(commission, 4),
                trade['id']
            )

        logger.info(
            f"[PAPER] CLOSE #{trade['id']} {trade['strategy']} {trade['symbol']} "
            f"{side.upper()} @ {exit_price} reason={exit_reason} pnl={round(pnl, 2)}"
        )

    # ─────────────────────────────────────────────
    # Monitor: revisar posiciones abiertas
    # ─────────────────────────────────────────────

    async def monitor_open_trades(self) -> dict:
        """
        Evalua cada trade abierto recorriendo, vela a vela, las velas de 1min
        acumuladas desde el ultimo chequeo (no solo el precio actual). Esto
        replica la logica del motor de backtest (BE, luego SL con el SL
        previo a esta vela, luego trailing, luego volatilidad, luego TP, en
        ese orden por vela) en vez de mirar una sola foto de precio cada 5
        minutos. Sin esto, una mecha que toca SL/trailing y se recupera antes
        del proximo ciclo de paper queda invisible para paper pero SI la
        detecta el trailing nativo de Bybit en real, sesgando a paper hacia
        mejores resultados de forma sistematica, no solo por ruido.
        """
        open_trades = await self.get_open_trades()
        results     = {"checked": 0, "closed": 0, "be_activated": 0}

        now = datetime.now(timezone.utc)

        for trade in open_trades:
            results["checked"] += 1
            symbol = trade['symbol']
            side   = trade['side']
            strategy_instance = self._strategy_for_open_trade(trade)  # parámetros congelados del trade
            if strategy_instance is None:
                logger.error(f"[PAPER] Trade #{trade['id']}: no se pudo determinar la estrategia, saltando este ciclo")
                continue
            sl       = float(trade['sl'])
            tp       = float(trade['tp'])
            be_level = float(trade['be_level'])
            be_activated = bool(trade['be_activated'])
            vol_widened  = bool(trade.get('vol_widened', False))
            trailing_applied = bool(trade.get('trailing_applied', False))
            entry    = float(trade['entry_price'])
            size     = float(trade['size'])
            max_profit_pct = float(trade.get('max_profit_pct', 0) or 0)
            max_loss_pct   = float(trade.get('max_loss_pct', 0) or 0)

            last_checkpoint = trade.get('last_monitored_at') or trade['entry_time']
            if last_checkpoint.tzinfo is None:
                last_checkpoint = last_checkpoint.replace(tzinfo=timezone.utc)

            # Velas 1m de UNA sola fuente: si dos fuentes se solapan, sin este
            # filtro cada minuto se evaluaría dos veces (y con precios distintos).
            minute_broker = await resolve_live_broker(self.pool, symbol, '1', require_fresh=False)
            async with self.pool.acquire() as conn:
                bars = await conn.fetch(
                    """
                    SELECT time, open, high, low, close
                    FROM ohlcv_data
                    WHERE broker = $4 AND symbol = $1 AND interval = '1' AND time > $2 AND time <= $3
                    ORDER BY time ASC
                    """,
                    symbol, last_checkpoint, now - timedelta(minutes=1), minute_broker  # solo 1m cerradas
                ) if minute_broker else []
            if minute_broker is None:
                logger.warning(f"[PAPER] Trade #{trade['id']} {symbol}: sin velas de 1m; SL/TP no evaluados este ciclo")

            exit_price    = None
            exit_reason   = None
            last_bar_time = last_checkpoint

            # ATR de la última vela CERRADA del intervalo (trailing ATR y protección por volatilidad)
            needs_atr = (getattr(strategy_instance, 'volatility_protection_mode', None) is not None
                         or getattr(strategy_instance, 'trailing_mode', None) == 'atr')
            closed_atr = closed_atr_avg = None
            if needs_atr:
                vbars = self._closed_bars(await self.get_bars(symbol, trade['interval']), trade['interval'], now)
                if len(vbars) >= 51:
                    atr_series = calculate_atr(vbars)
                    closed_atr = float(atr_series.iloc[-1])
                    closed_atr_avg = float(atr_series.rolling(50).mean().iloc[-1])

            for bar in bars:
                high  = float(bar['high'])
                low   = float(bar['low'])
                last_bar_time = bar['time']

                # Mismo orden que el motor V3: SL vigente -> TP1 -> break-even -> trailing
                sl_label = 'trailing_stop' if trailing_applied else 'stop_loss'
                if (side == 'long' and low <= sl) or (side == 'short' and high >= sl):
                    exit_price, exit_reason = sl, sl_label
                elif (side == 'long' and high >= tp) or (side == 'short' and low <= tp):
                    exit_price, exit_reason = tp, 'take_profit_1'
                else:
                    if not be_activated and ((side == 'long' and high >= be_level) or (side == 'short' and low <= be_level)):
                        sl = max(sl, entry) if side == 'long' else min(sl, entry)
                        be_activated = True
                        results["be_activated"] += 1
                    if getattr(strategy_instance, 'trailing_mode', None) is not None:
                        new_sl = strategy_instance.calculate_trailing_sl(
                            entry, side, high if side == 'long' else low, sl, current_atr=closed_atr)
                        if new_sl != sl:
                            sl = new_sl
                            trailing_applied = True

                fav_price = high if side == 'long' else low
                adv_price = low if side == 'long' else high
                fav_pct = self.calculate_floating_pnl_pct(entry, fav_price, side, size)
                adv_pct = self.calculate_floating_pnl_pct(entry, adv_price, side, size)
                if fav_pct > max_profit_pct:
                    max_profit_pct = fav_pct
                if adv_pct < max_loss_pct:
                    max_loss_pct = adv_pct

                if exit_price is not None:
                    break

            # Protección por volatilidad: una vez por ciclo, con la última vela cerrada del intervalo
            if exit_price is None and bars and closed_atr is not None and closed_atr_avg is not None \
                    and getattr(strategy_instance, 'volatility_protection_mode', None) is not None:
                vol_check = strategy_instance.check_volatility_protection(sl, side, closed_atr, closed_atr_avg)
                if vol_check['action'] == 'close':
                    exit_price, exit_reason = float(bars[-1]['close']), 'volatility_protection'
                elif vol_check['action'] == 'widen' and vol_check['new_sl'] is not None and not vol_widened:
                    sl = vol_check['new_sl']   # una sola vez por trade
                    vol_widened = True

            if exit_price is not None:
                await self.close_trade(trade, exit_price, exit_reason)
                results["closed"] += 1
                continue

            checkpoint_to_store = last_bar_time.replace(tzinfo=None) if last_bar_time.tzinfo else last_bar_time
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE paper_trades
                    SET sl = $1, be_activated = $2, trailing_applied = $3,
                        max_profit_pct = $4, max_loss_pct = $5,
                        last_monitored_at = $6, vol_widened = $8, updated_at = now()
                    WHERE id = $7
                    """,
                    sl, be_activated, trailing_applied,
                    round(max_profit_pct, 4), round(max_loss_pct, 4),
                    checkpoint_to_store, trade['id'], vol_widened
                )

            entry_time = trade['entry_time']
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            max_bars = int(getattr(strategy_instance, 'max_duration', 0) or 0)
            if max_bars > 0 and now - entry_time >= interval_delta(trade['interval']) * max_bars:
                last_price = float(bars[-1]['close']) if bars else await get_current_price(symbol)
                if last_price is None:
                    logger.warning(f"[PAPER] Trade #{trade['id']}: duración máxima cumplida pero sin precio; reintento próximo ciclo")
                    continue
                in_profit = last_price > entry if side == 'long' else last_price < entry
                if not getattr(strategy_instance, 'max_duration_profit', False):
                    await self.close_trade(trade, last_price, 'time_exit')
                    results["closed"] += 1
                elif in_profit:
                    await self.close_trade(trade, last_price, 'time_exit_profit')
                    results["closed"] += 1

        return results

    # ─────────────────────────────────────────────
    # Posiciones abiertas con precio actual
    # ─────────────────────────────────────────────

    async def get_open_trades_with_live_price(self) -> list[dict]:
        open_trades = await self.get_open_trades()
        price_cache: dict[str, float] = {}
        enriched = []

        for trade in open_trades:
            symbol = trade['symbol']

            if symbol not in price_cache:
                price = await get_current_price(symbol)
                price_cache[symbol] = price

            current_price = price_cache[symbol]
            trade = dict(trade)
            trade['current_price'] = current_price

            if current_price is not None:
                entry = float(trade['entry_price'])
                size  = float(trade['size'])
                side  = trade['side']

                floating_pnl_pct = self.calculate_floating_pnl_pct(entry, current_price, side, size)
                trade['floating_pnl_pct'] = round(floating_pnl_pct, 4)
                trade['floating_pnl']     = round(floating_pnl_pct / 100 * VIRTUAL_BALANCE, 4)
            else:
                trade['floating_pnl_pct'] = None
                trade['floating_pnl']     = None

            enriched.append(trade)

        return enriched

    # ─────────────────────────────────────────────
    # Buscar nuevas senales
    # ─────────────────────────────────────────────

    async def check_new_signals(self) -> dict:
        results = {}

        if await self.risk_manager.is_kill_switch_active():
            for cfg in self.config_map.values():
                results[self._label(cfg)] = "KILL SWITCH activo — sin nuevas entradas"
            return results

        # Solo el kill switch manual (igual que real); sin pausas automáticas (no las simula el backtest).

        for config_id, cfg in self.config_map.items():
            label    = self._label(cfg)
            symbol   = cfg['symbol']
            interval = cfg['interval']

            if await self.has_open_trade(config_id):
                results[label] = f"{symbol}: ya tiene posicion abierta"
                continue

            now = datetime.now(timezone.utc)
            df = self._closed_bars(await self.get_bars(symbol, interval), interval, now)
            if len(df) < 64:
                results[label] = f"{symbol}: datos insuficientes o desactualizados"
                continue
            if pd.to_datetime(df['time'].iloc[-1], utc=True) + 2 * interval_delta(interval) <= now:
                results[label] = f"{symbol}: falta la última vela cerrada (collector atrasado), no se opera"
                continue

            try:
                strategy = build_strategy(self._get_params_for(config_id))
            except Exception as e:
                results[label] = f"Error construyendo la estrategia: {e}"
                continue

            regime = await self.get_current_regime(
                df, trending_threshold=strategy.regime_adx_trending,
                ranging_threshold=strategy.regime_adx_ranging,
                ambiguous_as=strategy.regime_ambiguous_as
            )
            if not strategy.should_operate(regime):
                results[label] = f"{symbol}: regimen no permitido ({regime})"
                continue

            df = strategy.prepare(df)
            df = strategy.generate_signals(df)

            last_closed = df.iloc[-1]  # df ya solo contiene velas cerradas
            signal = int(last_closed['signal'])
            if signal == 0:
                results[label] = f"{symbol}: sin senal"
                continue

            candle_time = last_closed['time']
            if hasattr(candle_time, 'tzinfo') and candle_time.tzinfo is not None:
                candle_time = candle_time.tz_convert('UTC').tz_localize(None)
            async with self.pool.acquire() as conn:
                already_traded = await conn.fetchrow(
                    """SELECT id FROM paper_trades
                       WHERE paper_strategy_config_id = $1 AND entry_time >= $2
                       ORDER BY entry_time DESC LIMIT 1""",
                    config_id, candle_time
                )
            if already_traded:
                results[label] = f"{symbol}: senal ya operada en esta vela (trade #{already_traded['id']})"
                continue

            side        = 'long' if signal == 1 else 'short'
            entry_price = await get_current_price(symbol)
            if entry_price is None:
                results[label] = f"{symbol}: error obteniendo precio"
                continue

            raw_sl = last_closed.get('signal_sl_pct') if 'signal_sl_pct' in df.columns else None
            signal_sl_pct = float(raw_sl) if raw_sl is not None and pd.notna(raw_sl) else None
            await self.open_trade(config_id, strategy, side, entry_price, regime, signal_sl_pct)
            results[label] = f"{symbol}: ABIERTA {side} @ {entry_price} (regime={regime})"

        return results

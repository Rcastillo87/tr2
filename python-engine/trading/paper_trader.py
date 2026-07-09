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
from datetime import datetime, timezone
from dotenv import load_dotenv

from trading.bybit_client import get_current_price
from indicators.regime_indicators import calculate_atr, calculate_adx, calculate_bb_width, classify_regime
from trading.risk_manager import RiskManager

load_dotenv()

logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

VIRTUAL_BALANCE = 10000.0


class PaperTrader:

    def __init__(self, pool: asyncpg.Pool, strategies: dict, default_params: dict,
                 config_map: dict | None = None):
        """
        pool:           asyncpg connection pool
        strategies:     dict {display_name: StrategyClass}
        default_params: parametros base de respaldo
        config_map:     dict {display_name: config_dict} con params especificos por config
        """
        self.pool          = pool
        self.strategies    = strategies
        self.default_params = default_params
        self.config_map    = config_map or {}
        self.risk_manager  = RiskManager(pool)

    # ─────────────────────────────────────────────
    # Helpers de params
    # ─────────────────────────────────────────────

    def _get_params_for(self, display_name: str, symbol: str) -> dict:
        """
        Devuelve los parametros combinados para una config especifica.
        Los params de config_map sobreescriben los default_params.
        """
        params = dict(self.default_params)

        if display_name in self.config_map:
            cfg         = self.config_map[display_name]
            cfg_params  = cfg['params'] if isinstance(cfg['params'], dict) else json.loads(cfg['params'])
            params.update(cfg_params)
            params['symbol']   = cfg['symbol']
            params['interval'] = cfg['interval']
        else:
            params['symbol'] = symbol

        return params

    # ─────────────────────────────────────────────
    # Datos
    # ─────────────────────────────────────────────

    async def get_bars(self, symbol: str, interval: str) -> pd.DataFrame:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                ORDER BY time DESC
                LIMIT 200
                """,
                symbol, interval
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
                SELECT id, strategy, symbol, interval, side, entry_price, sl, tp, tp2, tp3, tp4,
                       be_level, be_activated, trailing_applied, size, entry_time, regime,
                       max_profit_pct, max_loss_pct, last_monitored_at
                FROM paper_trades
                WHERE status = 'open'
                """
            )
        return [dict(r) for r in rows]

    async def has_open_trade(self, display_name: str, symbol: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM paper_trades
                WHERE strategy = $1 AND symbol = $2 AND status = 'open'
                """,
                display_name, symbol
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

    async def open_trade(self, display_name: str, strategy_instance, symbol: str,
                          side: str, entry_price: float, regime: str, interval: str):
        # Leer params especificos de la config (paper_strategy_configs)
        cfg_params = self._get_params_for(display_name, symbol)

        # Actualizar instancia con params correctos de la config
        for attr in ['sl_pct', 'tp_pct', 'tp2_pct', 'tp3_pct', 'tp4_pct', 'be_pct', 'max_duration',
                     'trailing_mode', 'trailing_distance_pct', 'trailing_steps']:
            if attr in cfg_params:
                setattr(strategy_instance, attr, cfg_params[attr])

        sl, _  = strategy_instance.calculate_sl_tp(entry_price, side)
        be     = strategy_instance.calculate_breakeven(entry_price, side)
        tp_levels = strategy_instance.calculate_tp_levels(entry_price, side)
        tp, tp2, tp3, tp4 = tp_levels['tp1'], tp_levels['tp2'], tp_levels['tp3'], tp_levels['tp4']
        risk_pct = cfg_params.get('risk_per_trade_pct',
                   self.default_params.get('risk_per_trade_pct', 1.0))
        risk_amount = VIRTUAL_BALANCE * (risk_pct / 100)
        sl_distance = abs(entry_price - sl)
        size        = round(risk_amount / sl_distance, 6) if sl_distance > 0 else 0.0

        if size <= 0:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO paper_trades
                    (strategy, symbol, interval, side, entry_price, sl, tp, tp2, tp3, tp4, be_level,
                     be_activated, size, regime, entry_time, status,
                     max_profit_pct, max_loss_pct, created_at, updated_at)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, false, $12, $13, $14, 'open', 0, 0, now(), now())
                """,
                display_name, symbol, interval, side, entry_price, sl, tp, tp2, tp3, tp4, be,
                size, regime, datetime.now(timezone.utc).replace(tzinfo=None)
            )

        logger.info(
            f"[PAPER] OPEN {display_name} {symbol} {side.upper()} @ {entry_price} "
            f"SL={sl} TP1={tp} TP2={tp2} TP3={tp3} TP4={tp4} BE={be} regime={regime} interval={interval}"
        )

    # ─────────────────────────────────────────────
    # Cerrar posicion
    # ─────────────────────────────────────────────

    async def close_trade(self, trade: dict, exit_price: float, exit_reason: str):
        entry_price = float(trade['entry_price'])
        size        = float(trade['size'])
        side        = trade['side']

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
        cfg_params = self._get_params_for(trade['strategy'], trade['symbol'])
        if 'commission_pct' in cfg_params:
            commission_pct = cfg_params['commission_pct'] / 100
        else:
            # Config sin commission_pct guardado (creada antes de 2026-07-09,
            # o manualmente sin pasar por un backtest reciente). Detectar
            # broker por symbol en vez de asumir 0.055% (Bybit) a ciegas -
            # evita cobrar comision de Bybit a un trade de IG.
            async with self.pool.acquire() as conn:
                broker_row = await conn.fetchrow(
                    "SELECT broker FROM collector_configs WHERE symbol = $1 LIMIT 1",
                    trade['symbol']
                )
            broker = broker_row['broker'] if broker_row else 'bybit'
            commission_pct = (0.055 / 100) if broker == 'bybit' else 0.0
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

    async def update_breakeven(self, trade_id: int, new_sl: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE paper_trades SET sl = $1, be_activated = true, updated_at = now() WHERE id = $2",
                new_sl, trade_id
            )

    async def update_trailing_sl(self, trade_id: int, new_sl: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE paper_trades SET sl = $1, trailing_applied = true, updated_at = now() WHERE id = $2",
                new_sl, trade_id
            )

    async def update_volatility_widen(self, trade_id: int, new_sl: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE paper_trades SET sl = $1, updated_at = now() WHERE id = $2",
                new_sl, trade_id
            )

    async def update_max_excursion(self, trade_id: int, floating_pnl_pct: float,
                                    current_max_profit: float, current_max_loss: float):
        new_max_profit = max(current_max_profit, floating_pnl_pct)
        new_max_loss   = min(current_max_loss, floating_pnl_pct)

        if new_max_profit == current_max_profit and new_max_loss == current_max_loss:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE paper_trades
                SET max_profit_pct = $1, max_loss_pct = $2, updated_at = now()
                WHERE id = $3
                """,
                round(new_max_profit, 4), round(new_max_loss, 4), trade_id
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
        strategy_instances = {}
        for display_name, cls in self.strategies.items():
            params = self._get_params_for(display_name, '')
            strategy_instances[display_name] = cls(params)

        now = datetime.now(timezone.utc)

        for trade in open_trades:
            results["checked"] += 1
            symbol = trade['symbol']
            side   = trade['side']
            strategy_instance = strategy_instances.get(trade['strategy'],
                                list(strategy_instances.values())[0])
            sl       = float(trade['sl'])
            tp       = float(trade['tp'])
            tp2      = float(trade['tp2']) if trade.get('tp2') is not None else None
            tp3      = float(trade['tp3']) if trade.get('tp3') is not None else None
            tp4      = float(trade['tp4']) if trade.get('tp4') is not None else None
            be_level = float(trade['be_level'])
            be_activated = bool(trade['be_activated'])
            trailing_applied = bool(trade.get('trailing_applied', False))
            entry    = float(trade['entry_price'])
            size     = float(trade['size'])
            max_profit_pct = float(trade.get('max_profit_pct', 0) or 0)
            max_loss_pct   = float(trade.get('max_loss_pct', 0) or 0)

            last_checkpoint = trade.get('last_monitored_at') or trade['entry_time']
            if last_checkpoint.tzinfo is None:
                last_checkpoint = last_checkpoint.replace(tzinfo=timezone.utc)

            async with self.pool.acquire() as conn:
                bars = await conn.fetch(
                    """
                    SELECT time, open, high, low, close
                    FROM ohlcv_data
                    WHERE symbol = $1 AND interval = '1' AND time > $2 AND time <= $3
                    ORDER BY time ASC
                    """,
                    symbol, last_checkpoint, now
                )

            exit_price    = None
            exit_reason   = None
            last_bar_time = last_checkpoint

            for bar in bars:
                high  = float(bar['high'])
                low   = float(bar['low'])
                last_bar_time = bar['time']

                if not be_activated:
                    if side == 'long' and high >= be_level:
                        sl = entry
                        be_activated = True
                        results["be_activated"] += 1
                    elif side == 'short' and low <= be_level:
                        sl = entry
                        be_activated = True
                        results["be_activated"] += 1

                # NOTA (2026-07-09): distinguir si el SL que disparo el cierre
                # es el original o uno ya movido por el trailing (mismo fix
                # aplicado en real_trader.py) - trailing_applied refleja si
                # el trailing ya actuo en una vela anterior de este mismo loop.
                sl_label = 'trailing_stop' if trailing_applied else 'stop_loss'
                if side == 'long' and low <= sl:
                    exit_price, exit_reason = sl, sl_label
                elif side == 'short' and high >= sl:
                    exit_price, exit_reason = sl, sl_label

                if exit_price is None and getattr(strategy_instance, 'trailing_mode', None) is not None:
                    ref_price = high if side == 'long' else low
                    new_sl = strategy_instance.calculate_trailing_sl(entry, side, ref_price, sl)
                    if new_sl != sl:
                        sl = new_sl
                        trailing_applied = True

                if exit_price is None and getattr(strategy_instance, 'volatility_protection_mode', None) is not None:
                    vbars = await self.get_bars(symbol, trade['interval'])
                    if not vbars.empty and len(vbars) >= 51:
                        atr_series = calculate_atr(vbars)
                        current_atr = float(atr_series.iloc[-1])
                        avg_atr = float(atr_series.rolling(50).mean().iloc[-1])
                        vol_check = strategy_instance.check_volatility_protection(sl, side, current_atr, avg_atr)
                        if vol_check['action'] == 'close':
                            exit_price, exit_reason = float(bar['close']), 'volatility_protection'
                        elif vol_check['action'] == 'widen' and vol_check['new_sl'] is not None:
                            sl = vol_check['new_sl']

                if exit_price is None:
                    for level, label in [(tp4, 'take_profit_4'), (tp3, 'take_profit_3'), (tp2, 'take_profit_2')]:
                        if level is None:
                            continue
                        if side == 'long' and high >= level:
                            exit_price, exit_reason = level, label
                            break
                        elif side == 'short' and low <= level:
                            exit_price, exit_reason = level, label
                            break
                    if exit_price is None:
                        if side == 'long' and high >= tp:
                            exit_price, exit_reason = tp, 'take_profit' if tp2 is None else 'take_profit_1'
                        elif side == 'short' and low <= tp:
                            exit_price, exit_reason = tp, 'take_profit' if tp2 is None else 'take_profit_1'

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
                        last_monitored_at = $6, updated_at = now()
                    WHERE id = $7
                    """,
                    sl, be_activated, trailing_applied,
                    round(max_profit_pct, 4), round(max_loss_pct, 4),
                    checkpoint_to_store, trade['id']
                )

            entry_time = trade['entry_time']
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            hours_open = (now - entry_time).total_seconds() / 3600
            if hours_open >= strategy_instance.max_duration:
                if bars:
                    last_price = float(bars[-1]['close'])
                else:
                    last_price = await get_current_price(symbol)
                    if last_price is None:
                        last_price = sl
                await self.close_trade(trade, last_price, 'time_exit')
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
            for display_name in self.strategies:
                results[display_name] = "KILL SWITCH activo — sin nuevas entradas"
            return results

        for display_name, strategy_cls in self.strategies.items():
            cfg = self.config_map.get(display_name, {})
            cfg_params = cfg.get('params', {})
            if isinstance(cfg_params, str):
                cfg_params = json.loads(cfg_params)

            symbol   = cfg.get('symbol', 'BTCUSDT')
            interval = cfg.get('interval', '60')

            if await self.has_open_trade(display_name, symbol):
                results[display_name] = f"{symbol}: ya tiene posicion abierta"
                continue

            # NOTA (2026-07-09): se quito el chequeo de is_paused() (pausas
            # automaticas por volatilidad extrema, tabla risk_controls). Real
            # Trading no tiene ningun filtro equivalente, y Paper existe para
            # aproximar el comportamiento de Real lo mas fiel posible - un
            # filtro exclusivo de Paper generaba divergencia silenciosa (una
            # pausa automatica del 2026-07-06 bloqueo BTCUSDT en TODAS las
            # estrategias de Paper durante 3 dias mientras Real seguia
            # operando normal, sin que nadie lo supiera hasta revisar). El
            # kill switch manual (is_kill_switch_active) SI se mantiene -
            # es control explicito del usuario, no se dispara solo.

            df = await self.get_bars(symbol, interval)
            if len(df) < 64:
                results[display_name] = f"{symbol}: datos insuficientes"
                continue

            params = self._get_params_for(display_name, symbol)
            strategy = strategy_cls(params)
            regime   = await self.get_current_regime(
                df, trending_threshold=strategy.regime_adx_trending,
                ranging_threshold=strategy.regime_adx_ranging,
                ambiguous_as=strategy.regime_ambiguous_as
            )

            if not strategy.should_operate(regime):
                results[display_name] = f"{symbol}: regimen no permitido ({regime})"
                continue

            df = strategy.prepare(df)
            df = strategy.generate_signals(df)

            last_closed = df.iloc[-2]
            signal = int(last_closed['signal'])

            if signal == 0:
                results[display_name] = f"{symbol}: sin senal"
                continue

            candle_time = last_closed['time']
            if hasattr(candle_time, 'tzinfo') and candle_time.tzinfo is not None:
                candle_time = candle_time.tz_localize(None)
            async with self.pool.acquire() as conn:
                already_traded = await conn.fetchrow(
                    """SELECT id FROM paper_trades
                       WHERE strategy = $1 AND symbol = $2
                         AND entry_time >= $3
                       ORDER BY entry_time DESC LIMIT 1""",
                    display_name, symbol, candle_time
                )
            if already_traded:
                results[display_name] = f"{symbol}: senal ya operada en esta vela (trade #{already_traded['id']})"
                continue

            side        = 'long' if signal == 1 else 'short'
            entry_price = await get_current_price(symbol)

            if entry_price is None:
                results[display_name] = f"{symbol}: error obteniendo precio"
                continue

            await self.open_trade(display_name, strategy, symbol, side,
                                   entry_price, regime, interval)
            results[display_name] = f"{symbol}: ABIERTA {side} @ {entry_price} (regime={regime})"

        return results

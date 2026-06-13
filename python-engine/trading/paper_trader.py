"""
Paper Trader V2
Abre y gestiona posiciones simuladas usando precios en vivo de Bybit.
"""

import asyncpg
import pandas as pd
import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from trading.bybit_client import get_current_price
from indicators.regime_indicators import calculate_atr, calculate_adx, calculate_bb_width, classify_regime

load_dotenv()

logger = logging.getLogger(__name__)

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

SYMBOLS  = os.getenv('SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT').split(',')
INTERVAL = '60'  # todas las estrategias V2 operan en H1
LOOKBACK_BARS = 100


class PaperTrader:

    def __init__(self, pool: asyncpg.Pool, strategies: dict, default_params: dict):
        """
        pool:           asyncpg connection pool
        strategies:     dict {name: StrategyClass}
        default_params: parámetros comunes (sl_pct, tp_pct, be_pct, max_duration, risk_per_trade_pct)
        """
        self.pool = pool
        self.strategies = strategies
        self.default_params = default_params

    # ─────────────────────────────────────────────
    # Datos
    # ─────────────────────────────────────────────

    async def get_bars(self, symbol: str) -> pd.DataFrame:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = $2
                ORDER BY time DESC
                LIMIT $3
                """,
                symbol, INTERVAL, LOOKBACK_BARS
            )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df = df.iloc[::-1].reset_index(drop=True)

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    async def get_current_regime(self, df: pd.DataFrame) -> str:
        """Calcula el régimen actual a partir de las velas H1."""
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
        )

    # ─────────────────────────────────────────────
    # Posiciones abiertas en DB
    # ─────────────────────────────────────────────

    async def get_open_trades(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, strategy, symbol, interval, side, entry_price, sl, tp,
                       be_level, be_activated, size, entry_time, regime
                FROM paper_trades
                WHERE status = 'open'
                """
            )
        return [dict(r) for r in rows]

    async def has_open_trade(self, strategy: str, symbol: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM paper_trades
                WHERE strategy = $1 AND symbol = $2 AND status = 'open'
                """,
                strategy, symbol
            )
        return row is not None

    # ─────────────────────────────────────────────
    # Abrir nueva posición
    # ─────────────────────────────────────────────

    async def open_trade(self, strategy_name: str, strategy_instance, symbol: str, side: str,
                          entry_price: float, regime: str):
        sl, tp = strategy_instance.calculate_sl_tp(entry_price, side)
        be     = strategy_instance.calculate_breakeven(entry_price, side)

        # Position sizing: 1% de riesgo fijo sobre balance virtual de 10,000
        balance = 10000.0
        risk_pct = self.default_params.get('risk_per_trade_pct', 1.0)
        risk_amount = balance * (risk_pct / 100)
        sl_distance = abs(entry_price - sl)
        size = round(risk_amount / sl_distance, 6) if sl_distance > 0 else 0.0

        if size <= 0:
            return

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO paper_trades
                    (strategy, symbol, interval, side, entry_price, sl, tp, be_level,
                     be_activated, size, regime, entry_time, status, created_at, updated_at)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7, $8, false, $9, $10, $11, 'open', now(), now())
                """,
                strategy_name, symbol, INTERVAL, side, entry_price, sl, tp, be,
                size, regime, datetime.now(timezone.utc)
            )

        logger.info(
            f"[PAPER] OPEN {strategy_name} {symbol} {side.upper()} @ {entry_price} "
            f"SL={sl} TP={tp} BE={be} regime={regime}"
        )

    # ─────────────────────────────────────────────
    # Cerrar posición
    # ─────────────────────────────────────────────

    async def close_trade(self, trade: dict, exit_price: float, exit_reason: str):
        entry_price = float(trade['entry_price'])
        size        = float(trade['size'])
        side        = trade['side']

        if side == 'long':
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        pnl_pct = pnl / 10000.0 * 100  # sobre balance virtual de referencia

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE paper_trades
                SET exit_price = $1, pnl = $2, pnl_pct = $3, exit_reason = $4,
                    exit_time = $5, status = 'closed', updated_at = now()
                WHERE id = $6
                """,
                exit_price, round(pnl, 4), round(pnl_pct, 4), exit_reason,
                datetime.now(timezone.utc), trade['id']
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

    # ─────────────────────────────────────────────
    # Monitor: revisar posiciones abiertas
    # ─────────────────────────────────────────────

    async def monitor_open_trades(self) -> dict:
        """Revisa cada posición abierta contra el precio actual y la cierra si aplica."""
        open_trades = await self.get_open_trades()
        results = {"checked": 0, "closed": 0, "be_activated": 0}

        # Cache de precios para no pedir el mismo símbolo varias veces
        price_cache: dict[str, float] = {}

        # Cache de max_duration por estrategia
        strategy_params = {}
        for name, cls in self.strategies.items():
            strategy_params[name] = cls(self.default_params)

        for trade in open_trades:
            results["checked"] += 1
            symbol = trade['symbol']

            if symbol not in price_cache:
                price = await get_current_price(symbol)
                if price is None:
                    continue
                price_cache[symbol] = price

            current_price = price_cache[symbol]
            side = trade['side']
            sl   = float(trade['sl'])
            tp   = float(trade['tp'])
            be_level = float(trade['be_level'])
            entry    = float(trade['entry_price'])

            exit_price  = None
            exit_reason = None

            # Break-even
            if not trade['be_activated']:
                if side == 'long' and current_price >= be_level:
                    await self.update_breakeven(trade['id'], entry)
                    results["be_activated"] += 1
                elif side == 'short' and current_price <= be_level:
                    await self.update_breakeven(trade['id'], entry)
                    results["be_activated"] += 1

            # Stop Loss
            if side == 'long' and current_price <= sl:
                exit_price, exit_reason = sl, 'stop_loss'
            elif side == 'short' and current_price >= sl:
                exit_price, exit_reason = sl, 'stop_loss'

            # Take Profit
            if exit_price is None:
                if side == 'long' and current_price >= tp:
                    exit_price, exit_reason = tp, 'take_profit'
                elif side == 'short' and current_price <= tp:
                    exit_price, exit_reason = tp, 'take_profit'

            # Cierre por tiempo
            if exit_price is None:
                entry_time = trade['entry_time']
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                hours_open = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
                max_duration = strategy_params.get(trade['strategy'], strategy_params[list(strategy_params.keys())[0]]).max_duration

                if hours_open >= max_duration:
                    exit_price, exit_reason = current_price, 'time_exit'

            if exit_price is not None:
                await self.close_trade(trade, exit_price, exit_reason)
                results["closed"] += 1

        return results

    # ─────────────────────────────────────────────
    # Buscar nuevas señales
    # ─────────────────────────────────────────────

    async def check_new_signals(self) -> dict:
        """Para cada estrategia/símbolo, revisa si la última vela cerrada generó señal."""
        results = {}

        for strategy_name, strategy_cls in self.strategies.items():
            for symbol in SYMBOLS:
                key = f"{strategy_name}/{symbol}"

                if await self.has_open_trade(strategy_name, symbol):
                    results[key] = "ya tiene posición abierta"
                    continue

                df = await self.get_bars(symbol)
                if len(df) < 64:
                    results[key] = "datos insuficientes"
                    continue

                params = dict(self.default_params)
                params['symbol'] = symbol

                strategy = strategy_cls(params)
                regime   = await self.get_current_regime(df)

                if not strategy.should_operate(regime):
                    results[key] = f"régimen no permitido ({regime})"
                    continue

                df = strategy.prepare(df)
                df = strategy.generate_signals(df)

                # Señal de la última vela cerrada (la anterior a la actual en formación)
                last_closed = df.iloc[-2]
                signal = int(last_closed['signal'])

                if signal == 0:
                    results[key] = "sin señal"
                    continue

                side = 'long' if signal == 1 else 'short'
                entry_price = await get_current_price(symbol)

                if entry_price is None:
                    results[key] = "error obteniendo precio"
                    continue

                await self.open_trade(strategy_name, strategy, symbol, side, entry_price, regime)
                results[key] = f"ABIERTA {side} @ {entry_price} (regime={regime})"

        return results

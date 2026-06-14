"""
Risk Manager V2
Evalúa drawdown diario, drawdown total y volatilidad extrema por estrategia/símbolo.
Aplica/levanta pausas en la tabla risk_controls.
"""

import asyncpg
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta
from indicators.regime_indicators import calculate_atr

logger = logging.getLogger(__name__)

INITIAL_BALANCE = 10000.0

DAILY_DRAWDOWN_PCT = 3.0
TOTAL_DRAWDOWN_PCT = 10.0
VOLATILITY_MULTIPLIER = 2.0


class RiskManager:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ─────────────────────────────────────────────
    # Kill Switch global
    # ─────────────────────────────────────────────

    async def is_kill_switch_active(self) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM risk_controls
                WHERE reason = 'kill_switch_manual' AND active = true
                  AND strategy IS NULL AND symbol IS NULL
                LIMIT 1
                """
            )
        return row is not None

    # ─────────────────────────────────────────────
    # Verificar si una estrategia/símbolo está pausado
    # ─────────────────────────────────────────────

    async def is_paused(self, strategy: str, symbol: str) -> bool:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id FROM risk_controls
                WHERE active = true
                  AND (
                        (strategy = $1 AND symbol IS NULL)
                     OR (strategy = $1 AND symbol = $2)
                  )
                LIMIT 1
                """,
                strategy, symbol
            )
        return row is not None

    # ─────────────────────────────────────────────
    # Calcular PnL por estrategia (hoy y total)
    # ─────────────────────────────────────────────

    async def get_pnl(self, strategy: str) -> dict:
        async with self.pool.acquire() as conn:
            total_pnl = await conn.fetchval(
                """
                SELECT COALESCE(SUM(pnl), 0)
                FROM paper_trades
                WHERE strategy = $1 AND status = 'closed'
                """,
                strategy
            )

            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
            daily_pnl = await conn.fetchval(
                """
                SELECT COALESCE(SUM(pnl), 0)
                FROM paper_trades
                WHERE strategy = $1 AND status = 'closed' AND exit_time >= $2
                """,
                strategy, today_start
            )

        return {
            "total_pnl": float(total_pnl),
            "daily_pnl": float(daily_pnl),
        }

    # ─────────────────────────────────────────────
    # Crear pausa
    # ─────────────────────────────────────────────

    async def create_pause(self, strategy: str | None, symbol: str | None, reason: str,
                            value: float, threshold: float, auto_resume_at: datetime | None = None):
        # Evitar duplicados: si ya existe una pausa activa igual, no crear otra
        async with self.pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id FROM risk_controls
                WHERE active = true AND reason = $1
                  AND (strategy = $2 OR ($2 IS NULL AND strategy IS NULL))
                  AND (symbol = $3 OR ($3 IS NULL AND symbol IS NULL))
                """,
                reason, strategy, symbol
            )

            if existing:
                return False

            await conn.execute(
                """
                INSERT INTO risk_controls
                    (strategy, symbol, reason, value, threshold, active, paused_at, auto_resume_at, created_at, updated_at)
                VALUES
                    ($1, $2, $3, $4, $5, true, $6, $7, now(), now())
                """,
                strategy, symbol, reason, value, threshold,
                datetime.now(timezone.utc).replace(tzinfo=None),
                auto_resume_at.replace(tzinfo=None) if auto_resume_at else None
            )

        logger.warning(
            f"[RISK] PAUSA creada — strategy={strategy} symbol={symbol} "
            f"reason={reason} value={value} threshold={threshold}"
        )
        return True

    # ─────────────────────────────────────────────
    # Levantar pausas vencidas (drawdown diario al día siguiente)
    # ─────────────────────────────────────────────

    async def resume_expired_pauses(self) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE risk_controls
                SET active = false, resumed_at = $1, updated_at = now()
                WHERE active = true AND auto_resume_at IS NOT NULL AND auto_resume_at <= $1
                """,
                now
            )
        # asyncpg retorna algo como "UPDATE N"
        try:
            count = int(result.split()[-1])
        except (ValueError, IndexError):
            count = 0

        if count > 0:
            logger.info(f"[RISK] {count} pausa(s) reactivada(s) automáticamente")

        return count

    # ─────────────────────────────────────────────
    # Volatilidad extrema por símbolo
    # ─────────────────────────────────────────────

    async def check_volatility(self, symbol: str) -> dict | None:
        """Retorna info si ATR actual > 2x ATR promedio (volatilidad extrema)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND interval = '60'
                ORDER BY time DESC
                LIMIT 100
                """,
                symbol
            )

        if len(rows) < 60:
            return None

        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df = df.iloc[::-1].reset_index(drop=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        atr = calculate_atr(df)
        atr_current = float(atr.iloc[-1])
        atr_avg = float(atr.tail(50).mean())

        if atr_avg <= 0:
            return None

        ratio = atr_current / atr_avg

        if ratio > VOLATILITY_MULTIPLIER:
            return {
                "atr_current": round(atr_current, 4),
                "atr_avg": round(atr_avg, 4),
                "ratio": round(ratio, 2),
            }

        return None

    # ─────────────────────────────────────────────
    # Evaluación completa — corre antes de cada paper tick
    # ─────────────────────────────────────────────

    async def evaluate(self, strategies: list[str], symbols: list[str]) -> dict:
        results = {"new_pauses": [], "resumed": 0, "kill_switch": False}

        results["resumed"] = await self.resume_expired_pauses()
        results["kill_switch"] = await self.is_kill_switch_active()

        if results["kill_switch"]:
            return results

        # Drawdown por estrategia
        for strategy in strategies:
            pnl = await self.get_pnl(strategy)

            daily_dd_pct = (pnl['daily_pnl'] / INITIAL_BALANCE) * 100
            total_dd_pct = (pnl['total_pnl'] / INITIAL_BALANCE) * 100

            if daily_dd_pct <= -DAILY_DRAWDOWN_PCT:
                tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=None
                )
                created = await self.create_pause(
                    strategy=strategy, symbol=None, reason='daily_drawdown',
                    value=daily_dd_pct, threshold=-DAILY_DRAWDOWN_PCT,
                    auto_resume_at=tomorrow,
                )
                if created:
                    results["new_pauses"].append(f"{strategy}: daily_drawdown ({daily_dd_pct:.2f}%)")

            if total_dd_pct <= -TOTAL_DRAWDOWN_PCT:
                created = await self.create_pause(
                    strategy=strategy, symbol=None, reason='total_drawdown',
                    value=total_dd_pct, threshold=-TOTAL_DRAWDOWN_PCT,
                    auto_resume_at=None,  # requiere reactivación manual
                )
                if created:
                    results["new_pauses"].append(f"{strategy}: total_drawdown ({total_dd_pct:.2f}%)")

        # Volatilidad extrema por símbolo (afecta a todas las estrategias en ese símbolo)
        for symbol in symbols:
            vol = await self.check_volatility(symbol)
            if vol:
                for strategy in strategies:
                    created = await self.create_pause(
                        strategy=strategy, symbol=symbol, reason='volatility_extreme',
                        value=vol['ratio'], threshold=VOLATILITY_MULTIPLIER,
                        auto_resume_at=None,
                    )
                    if created:
                        results["new_pauses"].append(f"{strategy}/{symbol}: volatility_extreme (ratio={vol['ratio']})")

        return results

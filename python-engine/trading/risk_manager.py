"""
Risk Manager: kill switch manual global (tabla risk_controls, reason='kill_switch_manual').

Activo -> paper y real NO abren posiciones nuevas; las abiertas se siguen gestionando.
Activar:    INSERT INTO risk_controls (reason, active, paused_at, created_at, updated_at)
            VALUES ('kill_switch_manual', true, now(), now(), now());
Desactivar: UPDATE risk_controls SET active = false, resumed_at = now(), updated_at = now()
            WHERE reason = 'kill_switch_manual' AND active;

Las pausas automáticas por drawdown/volatilidad se eliminaron (2026-10-26): ningún componente las
aplicaba y el backtest no las simula. Si se necesitan, deben aplicarse igual en backtest, paper y real.
"""
import asyncpg


class RiskManager:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

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

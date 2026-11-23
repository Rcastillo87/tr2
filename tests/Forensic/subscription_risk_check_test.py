"""
C5-20 (p98): la base solo acepta un riesgo propio de suscripción Real (risk_override_pct) NULL o con 0 < r ≤ 100.
A. Estático: la migración agrega el CHECK (idempotente) y la de bajada lo quita.
B. Con PostgreSQL (DB_* en el entorno; si no, SKIP), en una transacción que se revierte: aplicada dos veces sin error;
   acepta NULL, 0,01, 1 y 100; rechaza 0, −1 y 100,01; la de bajada lo quita.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/subscription_risk_check_test.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tests/Forensic/ (C5-04: barrera de base)
from test_db import require_test_db, test_dsn  # noqa: E402
ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


MIG = ROOT / 'database' / 'sql-migrations'
UP = MIG / '2026_11_23_02_subscription_risk_check.up.sql'
DOWN = MIG / '2026_11_23_02_subscription_risk_check.down.sql'
up = UP.read_text(encoding='utf-8') if UP.exists() else ''
down = DOWN.read_text(encoding='utf-8') if DOWN.exists() else ''
NAME = 'real_strategy_subscriptions_risk_override_check'
check('A1: la migración agrega el CHECK 0 < r ≤ 100 (NULL permitido)',
      NAME in up and 'risk_override_pct IS NULL OR (risk_override_pct > 0 AND risk_override_pct <= 100)' in up)
check('A2: idempotente (duplicate_object) y espera corta por el bloqueo',
      'duplicate_object' in up and 'lock_timeout' in up)
check('A3: la de bajada lo quita', f'DROP CONSTRAINT IF EXISTS {NAME}' in down)

if not require_test_db('B'):   # C5-04: nunca la base de producción
    pass
else:
    import asyncpg
    DB_DSN = test_dsn()

    async def main():
        c = await asyncpg.connect(DB_DSN)
        tr = c.transaction()
        await tr.start()
        try:
            await c.execute(up)
            await c.execute(up)
            n = await c.fetchval("SELECT count(*) FROM pg_constraint WHERE conname = $1", NAME)
            check('B1: aplicada dos veces sin error, un solo CHECK', n == 1, n)
            # usuario y cuenta propios de la prueba (se revierten con la transacción)
            usr = await c.fetchval("""INSERT INTO users (name, email, password) VALUES ('c5-20', 'c5-20@test.invalid', 'x')
                                      RETURNING id""")
            acc = await c.fetchval("""INSERT INTO broker_accounts (user_id, account_type, label) VALUES ($1, 'demo', 'c5-20')
                                      RETURNING id""", usr)

            async def accepts(v):
                sp = c.transaction()
                await sp.start()
                try:
                    await c.execute("""INSERT INTO real_strategy_subscriptions (user_id, strategy, symbol, status,
                        broker_account_id, risk_override_pct) VALUES ($1, 'T', 'RISKUSDT', 'paused', $2, $3)""", usr, acc, v)
                    return True
                except asyncpg.CheckViolationError:
                    return False
                finally:
                    await sp.rollback()
            for v in (None, 0.01, 1, 100):
                check(f'B2: acepta {v}', await accepts(v))
            for v in (0, -1, 100.01):
                check(f'B3: rechaza {v}', not await accepts(v))
            await c.execute(down)
            n = await c.fetchval("SELECT count(*) FROM pg_constraint WHERE conname = $1", NAME)
            check('B4: la de bajada lo quita', n == 0, n)
        finally:
            await tr.rollback()
            await c.close()

    asyncio.run(main())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

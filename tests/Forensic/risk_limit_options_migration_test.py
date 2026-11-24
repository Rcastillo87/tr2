"""
D-66 (p111): columnas de las opciones de los límites de riesgo por cuenta Real (broker_accounts).
A. Estático: la migración agrega las 6 columnas con valores que dejan la cuenta como hoy (límites activos, sin pausa) y el
   CHECK de 1–30 días; idempotente; la de bajada lo quita todo.
B. Con PostgreSQL de pruebas (C5-04; si no, SKIP), en una transacción que se revierte: aplicada dos veces sin error; una
   cuenta existente queda con los límites activos y sin pausa; acepta NULL, 1 y 30 días; rechaza 0 y 31; la de bajada
   quita columnas y CHECK.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/risk_limit_options_migration_test.py
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
UP = MIG / '2026_11_24_01_risk_limit_options.up.sql'
DOWN = MIG / '2026_11_24_01_risk_limit_options.down.sql'
up = UP.read_text(encoding='utf-8') if UP.exists() else ''
down = DOWN.read_text(encoding='utf-8') if DOWN.exists() else ''
COLS = {'monthly_loss_enabled': 'boolean       NOT NULL DEFAULT true', 'open_trades_limit_enabled': 'boolean       NOT NULL DEFAULT true',
        'loss_pause_days': 'smallint      NULL', 'loss_paused_until': 'timestamp     NULL',
        'loss_period_start': 'timestamp     NULL', 'loss_period_balance': 'numeric(20,8) NULL'}
NAME = 'broker_accounts_loss_pause_days_check'
check('A1: las 6 columnas, con los límites activos por defecto y lo demás vacío',
      all(f'ADD COLUMN IF NOT EXISTS {k:<25} {v}' in up for k, v in COLS.items()))
check('A2: CHECK de 1 a 30 días (NULL = hasta fin de mes)', NAME in up and 'loss_pause_days IS NULL OR loss_pause_days BETWEEN 1 AND 30' in up)
check('A3: idempotente y espera corta por el bloqueo', 'duplicate_object' in up and 'lock_timeout' in up)
check('A4: la de bajada quita el CHECK y las 6 columnas',
      f'DROP CONSTRAINT IF EXISTS {NAME}' in down and all(f'DROP COLUMN IF EXISTS {k}' in down for k in COLS))

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
            usr = await c.fetchval("""INSERT INTO users (name, email, password) VALUES ('d-66', 'd-66@test.invalid', 'x')
                                      RETURNING id""")
            acc = await c.fetchval("""INSERT INTO broker_accounts (user_id, account_type, label) VALUES ($1, 'demo', 'd-66')
                                      RETURNING id""", usr)
            await c.execute(up)
            await c.execute(up)
            n = await c.fetchval("""SELECT count(*) FROM information_schema.columns WHERE table_name = 'broker_accounts'
                                    AND column_name = ANY($1::text[])""", list(COLS))
            k = await c.fetchval("SELECT count(*) FROM pg_constraint WHERE conname = $1", NAME)
            check('B1: aplicada dos veces sin error: 6 columnas y un solo CHECK', n == 6 and k == 1, (n, k))
            row = await c.fetchrow("SELECT * FROM broker_accounts WHERE id = $1", acc)
            check('B2: una cuenta que ya existía queda como hoy (límites activos, sin pausa ni período)',
                  row['monthly_loss_enabled'] is True and row['open_trades_limit_enabled'] is True
                  and all(row[x] is None for x in ('loss_pause_days', 'loss_paused_until', 'loss_period_start', 'loss_period_balance')),
                  dict(row))

            async def accepts(v):
                sp = c.transaction()
                await sp.start()
                try:
                    await c.execute("UPDATE broker_accounts SET loss_pause_days = $1 WHERE id = $2", v, acc)
                    return True
                except asyncpg.CheckViolationError:
                    return False
                finally:
                    await sp.rollback()
            for v in (None, 1, 30):
                check(f'B3: acepta {v} días', await accepts(v))
            for v in (0, 31):
                check(f'B4: rechaza {v} días', not await accepts(v))
            await c.execute(down)
            n = await c.fetchval("""SELECT count(*) FROM information_schema.columns WHERE table_name = 'broker_accounts'
                                    AND column_name = ANY($1::text[])""", list(COLS))
            k = await c.fetchval("SELECT count(*) FROM pg_constraint WHERE conname = $1", NAME)
            check('B5: la de bajada quita columnas y CHECK', n == 0 and k == 0, (n, k))
        finally:
            await tr.rollback()
            await c.close()

    asyncio.run(main())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(1 if fails else 0)

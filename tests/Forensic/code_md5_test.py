"""
MEJ-002 (p86): cada operación de Paper y Real tiene la huella (md5) del código de la estrategia con que se abrió:
columna generada `strategy_code_md5` desde `config_snapshot->>'strategy_code'` (también para las históricas).
A. Estático: la migración crea la columna generada en las dos tablas y la de bajada la quita; ningún INSERT del motor
   la escribe (una columna generada no admite valores); el comparador usa la misma huella.
B. Con PostgreSQL (DB_* en el entorno; si no, SKIP), en una transacción que se revierte: la huella de la base es la
   misma que la de Python, se recalcula al cambiar el snapshot, NULL sin código, no se puede escribir, y la migración es
   idempotente y reversible.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/code_md5_test.py
"""
import asyncio
import hashlib
import json
import os
import re
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


UP = ROOT / 'database' / 'sql-migrations' / '2026_11_20_01_trade_code_md5.up.sql'
DOWN = ROOT / 'database' / 'sql-migrations' / '2026_11_20_01_trade_code_md5.down.sql'
up = UP.read_text(encoding='utf-8') if UP.exists() else ''
down = DOWN.read_text(encoding='utf-8') if DOWN.exists() else ''
gen = r"ADD COLUMN IF NOT EXISTS strategy_code_md5 char\(32\)\s+GENERATED ALWAYS AS \(md5\(config_snapshot->>'strategy_code'\)\) STORED"
check('A1: la migración crea la huella generada en paper_trades y real_trades',
      bool(re.search(r'ALTER TABLE paper_trades ' + gen, up)) and bool(re.search(r'ALTER TABLE real_trades ' + gen, up)))
check('A2: la de bajada la quita en las dos', 'paper_trades DROP COLUMN IF EXISTS strategy_code_md5' in down
      and 'real_trades DROP COLUMN IF EXISTS strategy_code_md5' in down)
check('A3: espera corta por el bloqueo (no frena los ticks si una tabla está ocupada)', "SET lock_timeout" in up)
for f in ('trading/paper_trader.py', 'trading/real_trader.py'):
    src = (ROOT / 'python-engine' / f).read_text(encoding='utf-8')
    ins = re.findall(r'INSERT INTO (?:paper|real)_trades\s*\((.*?)\)', src, re.S)
    check(f'A4: {f}: sus INSERT no escriben la columna generada', ins and all('strategy_code_md5' not in i for i in ins), len(ins))
import tools.analysis.compare_paper_vs_backtest as cmp  # noqa: E402
CODE = (ROOT / 'tests' / 'Forensic' / 'fixtures' / 'vwap_tendencia_19nov.py').read_text(encoding='utf-8') + "# ñ é\n"
check('A5: el comparador usa la misma huella (md5 del texto en UTF-8)',
      cmp.code_version({'strategy_code': CODE}) == hashlib.md5(CODE.encode('utf-8')).hexdigest()
      and cmp.code_version({}) is None)

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
            await c.execute(up)   # idempotente
            info = await c.fetch("""SELECT table_name, is_generated FROM information_schema.columns
                                    WHERE column_name = 'strategy_code_md5' AND table_name IN ('paper_trades', 'real_trades')
                                    ORDER BY table_name""")
            check('B1: columna generada en las dos tablas (aplicada dos veces sin error)',
                  [(r['table_name'], r['is_generated']) for r in info] == [('paper_trades', 'ALWAYS'), ('real_trades', 'ALWAYS')],
                  [dict(r) for r in info])
            snap = json.dumps({'strategy_code': CODE, 'sl_pct': 1.0})
            tid = await c.fetchval("""INSERT INTO paper_trades (strategy, symbol, interval, side, entry_price, sl, tp, be_level,
                size, entry_time, status, config_snapshot) VALUES ('t', 'MD5USDT', '60', 'long', 1, 0.99, 1.02, 1.01, 1, now(),
                'open', $1::jsonb) RETURNING id""", snap)
            got = await c.fetchval("SELECT strategy_code_md5 FROM paper_trades WHERE id = $1", tid)
            check('B2: la huella de la base = md5 de Python del mismo código (con acentos)',
                  got == hashlib.md5(CODE.encode('utf-8')).hexdigest(), got)
            await c.execute("UPDATE paper_trades SET config_snapshot = jsonb_set(config_snapshot, '{strategy_code}', '\"x = 1\"')"
                            " WHERE id = $1", tid)
            got = await c.fetchval("SELECT strategy_code_md5 FROM paper_trades WHERE id = $1", tid)
            check('B3: al cambiar el snapshot se recalcula', got == hashlib.md5(b'x = 1').hexdigest(), got)
            await c.execute("UPDATE paper_trades SET config_snapshot = NULL WHERE id = $1", tid)
            check('B4: sin snapshot: NULL', await c.fetchval("SELECT strategy_code_md5 FROM paper_trades WHERE id = $1", tid) is None)
            sp = c.transaction()
            await sp.start()
            try:
                await c.execute("UPDATE paper_trades SET strategy_code_md5 = 'x' WHERE id = $1", tid)
                wrote = True
            except asyncpg.PostgresError:
                wrote = False
            await sp.rollback()
            check('B5: nadie puede escribirla a mano', not wrote)
            await c.execute(down)
            left = await c.fetchval("SELECT count(*) FROM information_schema.columns WHERE column_name = 'strategy_code_md5'"
                                   " AND table_name IN ('paper_trades', 'real_trades')")
            check('B6: la de bajada la quita', left == 0, left)
        finally:
            await tr.rollback()
            await c.close()

    asyncio.run(main())

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

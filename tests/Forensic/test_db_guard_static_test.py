"""
C5-04 (p102, D-56): ninguna prueba toca una base cuyo nombre no termine en «test».
A. La barrera (`test_db.py`): con la base de producción configurada se salta y no arma conexión; con la de pruebas sí.
B. Vigilancia de todas las pruebas Python de tests/Forensic: ninguna arma su propia conexión (sin «postgresql://»,
   sin `from db import DB_DSN`, sin leer DB_HOST por su cuenta) y toda la que llama a asyncpg.connect / create_pool
   importa la barrera. Así una prueba nueva no puede olvidarla.
Las pruebas PHP que arrancan Laravel (role_matrix_test, real_reconcile_selector_test, …) no están en la regresión: se
corren a mano en el servidor y siempre dentro de una transacción que se revierte (fuera de esta regla, D-56).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/test_db_guard_static_test.py
"""
import io
import os
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


try:
    import test_db
except ImportError as e:
    check('existe tests/Forensic/test_db.py', False, str(e))
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)

# ── A. La barrera ──
KEYS = ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')
saved = {k: os.environ.get(k) for k in KEYS}


def env(**kw):
    for k in KEYS:
        os.environ.pop(k, None)
    os.environ.update(kw)


try:
    base = dict(DB_HOST='127.0.0.1', DB_PORT='5432', DB_USER='u', DB_PASSWORD='secreto-xyz')
    env(**base, DB_NAME='trading2')
    out = io.StringIO()
    with redirect_stdout(out):
        ok = test_db.require_test_db('B')
    check('A1: base de producción («trading2»): se salta con aviso', ok is False and 'no es de pruebas' in out.getvalue(),
          out.getvalue().strip())
    check('A2: el aviso no muestra el nombre de la base ni la contraseña',
          'trading2' not in out.getvalue() and 'secreto' not in out.getvalue(), out.getvalue().strip())
    try:
        test_db.test_dsn()
        raised = False
    except test_db.NotATestDatabase:
        raised = True
    check('A3: test_dsn() con la base de producción: lanza, nunca arma la conexión', raised)
    for name in ('testing2', 'test_trading', 'trading2_test_bak', ''):
        env(**base, DB_NAME=name)
        with redirect_stdout(io.StringIO()):
            r = test_db.require_test_db('x')
        check(f'A4: «{name}» no es de pruebas (debe TERMINAR en «test»)', r is False)
    env(DB_NAME='tr2test')
    with redirect_stdout(io.StringIO()):
        r = test_db.require_test_db('x')
    check('A5: sin DB_HOST: se salta', r is False)
    env(**base, DB_NAME='tr2test')
    with redirect_stdout(io.StringIO()):
        r = test_db.require_test_db('x')
    check('A6: base de pruebas («tr2test»): se usa y el DSN apunta a ella',
          r is True and test_db.test_dsn() == 'postgresql://u:secreto-xyz@127.0.0.1:5432/tr2test', r)
finally:
    env(**{k: v for k, v in saved.items() if v is not None})

# ── B. Vigilancia de las pruebas ──
OWN_DSN = re.compile(r"postgresql://|from db import DB_DSN|getenv\(\s*['\"]DB_HOST['\"]\s*\)")
CONNECT = re.compile(r"asyncpg\.(connect|create_pool)\(")
files = sorted(p for p in HERE.glob('*.py') if p.name not in ('test_db.py', Path(__file__).name))
own = [p.name for p in files if OWN_DSN.search(p.read_text(encoding='utf-8'))]
check('B1: ninguna prueba arma su propia conexión (postgresql://, from db import DB_DSN, getenv DB_HOST)', own == [], own)
unguarded = [p.name for p in files if CONNECT.search(p.read_text(encoding='utf-8'))
             and 'from test_db import' not in p.read_text(encoding='utf-8')]
check('B2: toda prueba que se conecta a la base importa la barrera', unguarded == [], unguarded)
connecting = [p.name for p in files if CONNECT.search(p.read_text(encoding='utf-8'))]
check('B3: la vigilancia ve las pruebas que usan base (≥ 14)', len(connecting) >= 14, len(connecting))
for name in ('code_md5_test.py', 'subscription_risk_check_test.py', 'vwap_metrics_fix_test.py', 'execution_ledger_test.py',
             'broker_events_test.py', 'bars_order_test.py'):
    s = (HERE / name).read_text(encoding='utf-8')
    check(f'B4: {name}: la sección con base pasa por require_test_db y usa test_dsn()',
          'require_test_db(' in s and 'test_dsn()' in s, name)

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

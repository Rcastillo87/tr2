"""
C5-04 (p102, D-56): barrera única para las pruebas que usan PostgreSQL.

Ninguna prueba toca una base cuyo nombre no termine en «test». El motor carga python-engine/.env al importarse
(auto_levels, p92), así que en el servidor una prueba ve la base de PRODUCCIÓN: ahí estas partes se saltan con un aviso
y la regresión del instalador nunca escribe (ni lee) en ella. Aquí corren contra la base de pruebas (tr2test).

Uso en una prueba:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I no agrega la carpeta de la prueba
    from test_db import require_test_db, test_dsn
    if require_test_db('B'):            # imprime «SKIP B: …» y devuelve False si la base no es de pruebas
        conn = await asyncpg.connect(test_dsn())

`test_dsn()` vuelve a comprobar la barrera (lanza si la base no es de pruebas): nunca se arma una conexión sin ella.
`test_db_guard_static_test.py` vigila que toda prueba que se conecta a la base use esta barrera.
"""
from __future__ import annotations

import os

SUFFIX = 'test'


class NotATestDatabase(RuntimeError):
    """La base configurada no es de pruebas: la prueba no debe conectarse."""


def db_name() -> str:
    return (os.getenv('DB_NAME') or '').strip()


def is_test_db() -> bool:
    """Hay base configurada y su nombre termina en «test»."""
    return bool(os.getenv('DB_HOST')) and db_name().endswith(SUFFIX)


def require_test_db(section: str) -> bool:
    """True si la sección puede usar la base; si no, imprime por qué se salta (sin mostrar el nombre ni credenciales)."""
    if not os.getenv('DB_HOST'):
        print(f'SKIP {section}: sin DB_* en el entorno')
        return False
    if not db_name().endswith(SUFFIX):
        print(f'SKIP {section}: la base configurada no es de pruebas (su nombre no termina en «{SUFFIX}»): no se toca')
        return False
    return True


def test_dsn() -> str:
    """DSN de la base de pruebas. Lanza NotATestDatabase si la barrera no se cumple."""
    if not is_test_db():
        raise NotATestDatabase('la base configurada no es de pruebas: la prueba no se conecta')
    return (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
            f"{os.getenv('DB_PORT')}/{db_name()}")

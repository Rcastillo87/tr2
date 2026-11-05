"""
Ejecuta el SQL REAL de un SELECT sobre filas en memoria con SQLite, para que las pruebas midan la consulta que
corre en producción y no una reimplementación que se queda vieja cuando cambia el SQL.
Alcance: SELECT simples (parámetros $N, comparaciones, AND/OR, ORDER BY, LIMIT). Casts '::tipo' se ignoran.
Fechas: UTC sin zona, en texto de ancho fijo (el orden lexicográfico es el cronológico).
"""
import json
import re
import sqlite3
from datetime import datetime, timezone


def _val(v):
    if isinstance(v, datetime):   # incluye pandas.Timestamp
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        return v.strftime('%Y-%m-%d %H:%M:%S.%f')
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def fetchrow(rows: list[dict], table: str, sql: str, args, columns=()) -> dict | None:
    cols = sorted({k for r in rows for k in r} | set(columns) | {'id'})
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute(f'CREATE TABLE {table} ({", ".join(cols)})')
    for r in rows:
        db.execute(f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})',
                   [_val(r.get(c)) for c in cols])
    query = re.sub(r'::\w+', '', re.sub(r'\$(\d+)', r'?\1', sql))
    row = db.execute(query, [_val(a) for a in args]).fetchone()
    db.close()
    return dict(row) if row else None

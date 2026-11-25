"""
C6-06: el esquema guardado (database/schema/pgsql-schema.sql) contiene todo lo que crean las migraciones SQL
(database/sql-migrations/*.up.sql): tablas, columnas, índices y restricciones con nombre, descontando lo que una
migración posterior borra. Así un esquema viejo (como el de D-66, sin las 6 columnas de broker_accounts) no pasa la
regresión.
Sin base: lee los dos archivos. S1–S6 prueban el lector con ejemplos; R1 el esquema real del repositorio.
El esquema se regenera en el servidor con ops/schema_dump.sh (solo lectura).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/schema_sync_test.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(os.getenv('TR2_SCHEMA_FILE') or ROOT / 'database' / 'schema' / 'pgsql-schema.sql')
MIGRATIONS = ROOT / 'database' / 'sql-migrations'
fails = 0

IDENT = r'(?:"[^"]+"|[a-z_][a-z0-9_$]*)'
NAME = rf'(?:{IDENT}\.)?({IDENT})'   # con o sin esquema (public.)


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def unq(x: str) -> str:
    return x.strip('"')


def strip_sql(sql: str) -> str:
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)
    sql = re.sub(r'--[^\n]*', ' ', sql)
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)   # textos (defaults, comentarios) fuera
    return re.sub(r'\s+', ' ', sql).strip().lower()


def split_top(s: str, sep: str = ',') -> list[str]:
    out, depth, cur = [], 0, []
    for ch in s:
        depth += ch == '('
        depth -= ch == ')'
        if ch == sep and depth == 0:
            out.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if ''.join(cur).strip():
        out.append(''.join(cur).strip())
    return out


def paren_body(s: str, start: int) -> str:
    depth = 0
    for i in range(start, len(s)):
        depth += s[i] == '('
        depth -= s[i] == ')'
        if depth == 0:
            return s[start + 1:i]
    return s[start + 1:]


class Objects:
    """Lo que deja definido una secuencia de sentencias SQL (de una migración o de un volcado de pg_dump)."""

    def __init__(self):
        self.tables: dict[str, set[str]] = {}
        self.indexes: set[str] = set()
        self.constraints: set[str] = set()

    def apply(self, sql: str) -> 'Objects':
        for st in strip_sql(sql).split(';'):
            st = st.strip()
            st = re.sub(r'^(?:do \$\$ begin |begin |exception .*$)', '', st).strip()
            if not st:
                continue
            m = re.match(rf'create (?:unlogged )?table (?:if not exists )?{NAME} ?\(', st)
            if m:
                t = unq(m.group(1))
                cols = self.tables.setdefault(t, set())
                for item in split_top(paren_body(st, m.end() - 1)):
                    c = re.match(rf'constraint ({IDENT})', item)
                    if c:
                        self.constraints.add(unq(c.group(1)))
                    elif not re.match(r'(primary key|unique|check|foreign key|exclude|like) ', item):
                        cols.add(unq(item.split(' ')[0]))
                continue
            m = re.match(rf'alter table (?:if exists )?(?:only )?{NAME} (.*)$', st)
            if m:
                t = unq(m.group(1))
                for act in split_top(m.group(2)):
                    if a := re.match(rf'add (?:column )?(?:if not exists )?({IDENT}) ', act + ' '):
                        if a.group(1) not in ('constraint', 'primary', 'unique', 'check', 'foreign'):
                            self.tables.setdefault(t, set()).add(unq(a.group(1)))
                            continue
                    if a := re.match(rf'add constraint ({IDENT})', act):
                        self.constraints.add(unq(a.group(1)))
                    elif a := re.match(rf'drop (?:column )?(?:if exists )?({IDENT})', act):
                        if a.group(1) != 'constraint':
                            self.tables.get(t, set()).discard(unq(a.group(1)))
                    if a := re.match(rf'drop constraint (?:if exists )?({IDENT})', act):
                        self.constraints.discard(unq(a.group(1)))
                    elif a := re.match(rf'rename column ({IDENT}) to ({IDENT})', act):
                        self.tables.get(t, set()).discard(unq(a.group(1)))
                        self.tables.setdefault(t, set()).add(unq(a.group(2)))
                    elif a := re.match(rf'rename constraint ({IDENT}) to ({IDENT})', act):
                        self.constraints.discard(unq(a.group(1)))
                        self.constraints.add(unq(a.group(2)))
                continue
            m = re.match(rf'create (?:unique )?index (?:concurrently )?(?:if not exists )?({IDENT}) on ', st)
            if m:
                self.indexes.add(unq(m.group(1)))
                continue
            m = re.match(rf'drop index (?:concurrently )?(?:if exists )?{NAME}', st)
            if m:
                self.indexes.discard(unq(m.group(1)))
                continue
            m = re.match(rf'drop table (?:if exists )?{NAME}', st)
            if m:
                self.tables.pop(unq(m.group(1)), None)
                continue
            m = re.match(rf'alter index (?:if exists )?{NAME} rename to ({IDENT})', st)
            if m:
                self.indexes.discard(unq(m.group(1)))
                self.indexes.add(unq(m.group(2)))
        return self


def missing(required: Objects, have: Objects) -> list[str]:
    out = []
    for t, cols in sorted(required.tables.items()):
        if t not in have.tables:
            out.append(f'tabla {t}')
            continue
        out += [f'columna {t}.{c}' for c in sorted(cols - have.tables[t])]
    out += [f'índice {i}' for i in sorted(required.indexes - have.indexes)]
    out += [f'restricción {c}' for c in sorted(required.constraints - have.constraints)]
    return out


# ── S: el lector ──
s = Objects().apply("""
CREATE TABLE IF NOT EXISTS foo (id bigserial PRIMARY KEY, name varchar(20) NOT NULL DEFAULT 'a,b', amount numeric(20, 8),
  CONSTRAINT foo_name_chk CHECK (name <> ''));
ALTER TABLE foo ADD COLUMN IF NOT EXISTS extra boolean NOT NULL DEFAULT true, ADD COLUMN old_col int;
DO $$ BEGIN
    ALTER TABLE foo ADD CONSTRAINT foo_extra_check CHECK (extra IS NOT NULL);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE UNIQUE INDEX IF NOT EXISTS foo_name_uq ON foo (name);
CREATE INDEX foo_tmp_idx ON foo (amount);
ALTER TABLE foo DROP COLUMN IF EXISTS old_col;
DROP INDEX IF EXISTS foo_tmp_idx;
-- ALTER TABLE foo ADD COLUMN comentada int;
""")
check('S1: tabla y columnas (comas dentro de paréntesis y de textos no cortan)',
      s.tables.get('foo') == {'id', 'name', 'amount', 'extra'}, s.tables)
check('S2: restricciones con nombre, también dentro de DO $$', s.constraints == {'foo_name_chk', 'foo_extra_check'}, s.constraints)
check('S3: índices; lo que una migración posterior borra no se exige', s.indexes == {'foo_name_uq'}, s.indexes)
d = Objects().apply("""
CREATE TABLE public.foo (
    id bigint NOT NULL,
    name character varying(20) DEFAULT 'a'::character varying NOT NULL,
    amount numeric(20,8),
    extra boolean DEFAULT true NOT NULL,
    CONSTRAINT foo_name_chk CHECK (((name)::text <> ''::text))
);
ALTER TABLE ONLY public.foo
    ADD CONSTRAINT foo_extra_check CHECK ((extra IS NOT NULL));
CREATE UNIQUE INDEX foo_name_uq ON public.foo USING btree (name);
""")
check('S4: el mismo resultado leyendo un volcado de pg_dump (public., ONLY, USING btree)', missing(s, d) == [], missing(s, d))
d2 = Objects().apply('CREATE TABLE public.foo (id bigint, name text, amount numeric);')
check('S5: un volcado viejo: faltan la columna nueva, el índice y las restricciones', missing(s, d2) == [
    'columna foo.extra', 'índice foo_name_uq', 'restricción foo_extra_check', 'restricción foo_name_chk'], missing(s, d2))
check('S6: una tabla que falta entera', missing(Objects().apply('CREATE TABLE bar (x int);'), d) == ['tabla bar'])

# ── R: el esquema del repositorio contra las migraciones ──
ups = sorted(MIGRATIONS.glob('*.up.sql'))
req = Objects()
for f in ups:
    req.apply(f.read_text(encoding='utf-8'))
have = Objects().apply(SCHEMA.read_text(encoding='utf-8')) if SCHEMA.is_file() else Objects()
n_cols = sum(len(c) for c in req.tables.values())
check(f'R0: migraciones leídas ({len(ups)} archivos: {len(req.tables)} tablas, {n_cols} columnas, {len(req.indexes)} índices, '
      f'{len(req.constraints)} restricciones)', len(ups) >= 24 and 'broker_accounts' in req.tables
      and 'loss_period_balance' in req.tables['broker_accounts'])
miss = missing(req, have)
check(f'R1: el esquema guardado tiene todo lo de las migraciones ({SCHEMA.name})', miss == [],
      f'{len(miss)} faltan: ' + ', '.join(miss[:20]) + (' …' if len(miss) > 20 else ''))

print('TODO OK' if fails == 0 else f'{fails} FALLOS')
sys.exit(1 if fails else 0)

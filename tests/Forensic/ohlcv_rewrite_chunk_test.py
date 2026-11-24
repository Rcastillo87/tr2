"""
C6-05 (parte 2): la reparación de un fragmento con lotes solapados (database/sql/ohlcv_rewrite_chunk.sql, la que corre
ops/ohlcv_rewrite_chunk.sh) solo se confirma si las velas quedan idénticas; si no, se deshace sola.
Contra PostgreSQL de pruebas (C5-04; si no, SKIP) con psql y el archivo tal cual, en un esquema propio que se borra al
final. decompress_chunk / compress_chunk son imitaciones (aquí no hay TimescaleDB) que registran la llamada y, según el
caso, no cambian nada, reescriben las mismas filas, pierden una vela, cambian un precio o fallan.
R1 sin cambios -> se confirma (llamó a descomprimir y comprimir)   R2 reescribe las mismas filas -> se confirma
R3 pierde una vela -> se deshace, velas intactas                    R4 cambia un precio -> se deshace, precio intacto
R5 compress_chunk falla -> se deshace                               R6 velas repetidas -> no toca (no descomprime)
R7 el fragmento cambió desde el respaldo -> no toca                 S1–S5 el script: respaldo antes, nombre válido, etc.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/ohlcv_rewrite_chunk_test.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tests/Forensic/ (C5-04: barrera de base)
from test_db import require_test_db, test_dsn  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / 'database' / 'sql' / 'ohlcv_rewrite_chunk.sql'
SQL = SQL_PATH.read_text(encoding='utf-8')
SH = (ROOT / 'ops' / 'ohlcv_rewrite_chunk.sh').read_text(encoding='utf-8')
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


body = [l for l in SH.splitlines() if not l.lstrip().startswith('#')]
code = '\n'.join(body)
i_copy, i_sql = code.find('COPY (SELECT * FROM'), code.find('< "$SQL"')
check('S1: el script respalda el fragmento ANTES de reescribirlo', 0 <= i_copy < i_sql, (i_copy, i_sql))
check('S2: valida el nombre del fragmento y que sea un fragmento comprimido de ohlcv_data',
      '^_hyper_[0-9]+_[0-9]+_chunk$' in code and "h.table_name = 'ohlcv_data'" in code and 'compressed_chunk_id IS NOT NULL' in code)
check('S3: pasa al SQL las velas del respaldo y exige ver la verificación final',
      '-v rows="$rows"' in code and 'IDENTICAS $rows velas' in code and 'gzip -t' in code)
check('S4: UNA transacción con espera de bloqueo corta', SQL.count('BEGIN;') == 1 and SQL.count('COMMIT;') == 1
      and "lock_timeout = '5s'" in SQL and 'ON_ERROR_STOP' in SQL)
check('S5: compara número de velas y md5 de todas las filas antes y después',
      'n1 <> n0 OR h1 IS DISTINCT FROM h0' in SQL and 'n0 <> expected' in SQL and 'k0 <> n0' in SQL
      and SQL.index('k0 <> n0') < SQL.index('decompress_chunk('))

SETUP = r"""
DROP SCHEMA IF EXISTS c605t CASCADE;
CREATE SCHEMA c605t;
CREATE TABLE c605t.fake (broker text, symbol text, "interval" text, "time" timestamptz, open numeric, close numeric);
CREATE TABLE c605t.calls (k text);
CREATE TABLE c605t.mode (m text);
INSERT INTO c605t.fake SELECT b, s, i, timestamptz '2026-10-08' + make_interval(mins => n), 100 + n, 101 + n
  FROM unnest(ARRAY['bybit','binance']) b, unnest(ARRAY['BTCUSDT','SOLUSDT']) s, unnest(ARRAY['1','5']) i,
       generate_series(0, 199) n;
CREATE FUNCTION c605t.decompress_chunk(c regclass, f boolean DEFAULT false) RETURNS regclass LANGUAGE plpgsql AS $f$
BEGIN INSERT INTO c605t.calls VALUES ('d'); RETURN c; END $f$;
CREATE FUNCTION c605t.compress_chunk(c regclass, f boolean DEFAULT true) RETURNS regclass LANGUAGE plpgsql AS $f$
DECLARE m text := (SELECT max(mode.m) FROM c605t.mode);
BEGIN
  INSERT INTO c605t.calls VALUES ('c');
  IF m = 'rewrite' THEN
    CREATE TEMP TABLE tmp_c605 ON COMMIT DROP AS SELECT * FROM c605t.fake ORDER BY random();
    DELETE FROM c605t.fake; INSERT INTO c605t.fake SELECT * FROM tmp_c605;
  ELSIF m = 'lose' THEN DELETE FROM c605t.fake WHERE ctid = (SELECT min(ctid) FROM c605t.fake);
  ELSIF m = 'alter' THEN UPDATE c605t.fake SET close = close + 0.01 WHERE symbol = 'SOLUSDT' AND "time" = timestamptz '2026-10-08 01:00+00' AND broker = 'bybit' AND "interval" = '1';
  ELSIF m = 'fail' THEN RAISE EXCEPTION 'falla simulada de compress_chunk';
  END IF;
  RETURN c;
END $f$;
"""
N = 2 * 2 * 2 * 200


def psql(dsn, sql=None, stdin=None, vars_=None):
    cmd = ['psql', '-X', '-q', '-tA', dsn]
    for k, v in (vars_ or {}).items():
        cmd += ['-v', f'{k}={v}']
    if sql is not None:
        cmd += ['-v', 'ON_ERROR_STOP=1', '-c', sql]
    env = dict(os.environ, PGOPTIONS='-c search_path=c605t,public')
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=env, timeout=120)


def one(dsn, q):
    return psql(dsn, q).stdout.strip()


def run_case(dsn, mode, rows=N):
    psql(dsn, 'DELETE FROM c605t.calls; DELETE FROM c605t.mode; INSERT INTO c605t.mode VALUES (%s)' % (f"'{mode}'"))
    r = psql(dsn, stdin=SQL, vars_={'chunk': 'c605t.fake', 'rows': rows})
    return r.returncode, r.stdout + r.stderr, one(dsn, 'SELECT coalesce(string_agg(k, \'\' ORDER BY k DESC), \'\') FROM c605t.calls')


def digest(dsn):
    return one(dsn, "SELECT count(*) || ':' || md5(string_agg(t::text, E'\\n' ORDER BY t::text)) FROM c605t.fake t")


if require_test_db('R'):
    dsn = test_dsn()
    s = psql(dsn, SETUP)
    check('R0: preparación del esquema de prueba', s.returncode == 0, s.stderr[-300:])
    try:
        d0 = digest(dsn)
        rc, out, calls = run_case(dsn, 'same')
        check('R1: sin cambios -> se confirma', rc == 0 and f'IDENTICAS {N} velas' in out and calls == 'dc' and digest(dsn) == d0,
              (rc, out[-200:], calls))
        rc, out, calls = run_case(dsn, 'rewrite')
        check('R2: reescribe las mismas filas en otro orden -> se confirma', rc == 0 and 'IDENTICAS' in out and digest(dsn) == d0,
              (rc, out[-200:]))
        rc, out, calls = run_case(dsn, 'lose')
        check('R3: pierde una vela -> se deshace, velas intactas',
              rc != 0 and 'se deshace' in out and calls == '' and digest(dsn) == d0, (rc, out[-200:], calls))
        rc, out, calls = run_case(dsn, 'alter')
        check('R4: cambia un precio -> se deshace, precio intacto', rc != 0 and digest(dsn) == d0, (rc, out[-200:]))
        rc, out, calls = run_case(dsn, 'fail')
        check('R5: compress_chunk falla -> se deshace', rc != 0 and calls == '' and digest(dsn) == d0, (rc, out[-200:]))
        rc, out, calls = run_case(dsn, 'same', rows=N + 1)
        check('R7: el fragmento cambió desde el respaldo -> no toca', rc != 0 and 'cambió entre el respaldo' in out and calls == '',
              (rc, out[-200:], calls))
        psql(dsn, "INSERT INTO c605t.fake SELECT * FROM c605t.fake WHERE symbol = 'BTCUSDT' AND \"time\" = timestamptz '2026-10-08 00:00+00' AND broker = 'bybit' AND \"interval\" = '1'")
        rc, out, calls = run_case(dsn, 'same', rows=N + 1)
        check('R6: velas repetidas -> no toca (no descomprime)', rc != 0 and 'repetidas' in out and calls == '', (rc, out[-200:], calls))
    finally:
        psql(dsn, 'DROP SCHEMA IF EXISTS c605t CASCADE')

print('TODO OK' if fails == 0 else f'{fails} FALLOS')
sys.exit(1 if fails else 0)

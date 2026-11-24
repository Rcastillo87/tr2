-- C6-05 (parte 2): reescribe UN fragmento de ohlcv_data con lotes comprimidos solapados (decompress_chunk +
-- compress_chunk) en UNA transacción, y la confirma solo si las velas quedan idénticas: mismo número que el respaldo
-- y el mismo md5 de todas las filas antes y después. Si algo no cuadra, se deshace y las velas quedan como estaban.
-- Lo usa ops/ohlcv_rewrite_chunk.sh (que antes respalda el fragmento):
--   psql -v ON_ERROR_STOP=1 -v chunk=_timescaledb_internal._hyper_1_123_chunk -v rows=<velas del respaldo> < este archivo
\set ON_ERROR_STOP 1
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10min';
SELECT set_config('tr2.chunk', :'chunk', true) IS NOT NULL AS chunk_ok, set_config('tr2.rows', :'rows', true) IS NOT NULL AS rows_ok;
DO $$
DECLARE
  c        regclass := current_setting('tr2.chunk')::regclass;
  expected bigint   := current_setting('tr2.rows')::bigint;
  n0 bigint; k0 bigint; h0 text; n1 bigint; h1 text;
  q text;
BEGIN
  q := format('SELECT count(*), count(DISTINCT (broker, symbol, "interval", "time")), '
              'md5(string_agg(t::text, E''\n'' ORDER BY t::text)) FROM %s t', c);
  EXECUTE q INTO n0, k0, h0;
  IF n0 <> expected THEN
    RAISE EXCEPTION 'el fragmento % tiene % velas y el respaldo %: cambió entre el respaldo y la reparación (no se tocó)', c, n0, expected;
  END IF;
  IF k0 <> n0 THEN
    RAISE EXCEPTION 'el fragmento % tiene % velas repetidas (misma serie y hora): no se toca', c, n0 - k0;
  END IF;
  PERFORM decompress_chunk(c, true);
  PERFORM compress_chunk(c, true);
  EXECUTE q INTO n1, k0, h1;
  IF n1 <> n0 OR h1 IS DISTINCT FROM h0 THEN
    RAISE EXCEPTION 'velas distintas tras reescribir % (% antes, % después): se deshace', c, n0, n1;
  END IF;
  RAISE NOTICE 'IDENTICAS % velas (md5 %)', n1, h1;
END $$;
COMMIT;

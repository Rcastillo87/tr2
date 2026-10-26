-- Compresión de ohlcv_data (TimescaleDB). Chunks de más de 14 días: el collector solo escribe la semana actual.
\set ON_ERROR_STOP 1
DO $$ BEGIN
  IF current_setting('timescaledb.license', true) IS DISTINCT FROM 'timescale' THEN
    RAISE EXCEPTION 'Licencia TimescaleDB % no incluye compresión: nada aplicado', current_setting('timescaledb.license', true);
  END IF;
END $$;
ALTER TABLE ohlcv_data SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'broker, symbol, interval',
  timescaledb.compress_orderby   = 'time DESC'
);
SELECT add_compression_policy('ohlcv_data', INTERVAL '14 days', if_not_exists => true);

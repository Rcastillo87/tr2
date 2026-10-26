-- Revertir: descomprime todo y quita la política (requiere espacio en disco ~ tamaño sin comprimir).
\set ON_ERROR_STOP 1
SELECT remove_compression_policy('ohlcv_data', if_exists => true);
SELECT decompress_chunk(c, true) FROM show_chunks('ohlcv_data') c;
ALTER TABLE ohlcv_data SET (timescaledb.compress = false);

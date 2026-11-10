-- N-11 (decisión del dueño 10-nov): el collector solo borra velas en la recarga y en la invalidación explícitas, y cada
-- borrado deja aquí su registro con las velas borradas (hasta 50.000; más, solo el resumen) para poder restaurarlas.
CREATE TABLE IF NOT EXISTS ohlcv_deletions (
    id            bigserial    PRIMARY KEY,
    broker        varchar(32)  NOT NULL,
    symbol        varchar(20)  NOT NULL,
    "interval"    varchar(5)   NOT NULL,
    source        varchar(16)  NOT NULL,
    reason        text         NOT NULL,
    deleted_count integer      NOT NULL,
    first_time    timestamptz,
    last_time     timestamptz,
    bars          jsonb,
    bars_saved    boolean      NOT NULL DEFAULT false,
    created_at    timestamptz  NOT NULL DEFAULT now()
);
DO $$ BEGIN
    ALTER TABLE ohlcv_deletions ADD CONSTRAINT ohlcv_deletions_source_chk CHECK (source IN ('reload', 'invalidate'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS ohlcv_deletions_series_idx ON ohlcv_deletions (broker, symbol, "interval", created_at DESC);

-- p89 (MEJ-004): libro de ejecuciones (fills) de Bybit por operación Real, y el estado de su registro.
-- Las operaciones que ya existen quedan 'historical': las registra el comando real:executions-backfill (con vista
-- previa); las nuevas las registra el tick (python-engine/trading/execution_ledger.py). Idempotente.
SET lock_timeout = '10s';
CREATE TABLE IF NOT EXISTS real_trade_executions (
    id              bigserial PRIMARY KEY,
    real_trade_id   bigint      NOT NULL REFERENCES real_trades(id) ON DELETE CASCADE,
    leg             varchar(5)  NOT NULL CHECK (leg IN ('open', 'close')),
    exec_id         varchar(64) NOT NULL UNIQUE,
    order_id        varchar(64) NOT NULL,
    symbol          varchar(32) NOT NULL,
    side            varchar(4)  NOT NULL,
    exec_price      numeric     NOT NULL,
    exec_qty        numeric     NOT NULL,
    exec_value      numeric,
    exec_fee        numeric,
    fee_rate        numeric,
    is_maker        boolean,
    exec_type       varchar(24),
    stop_order_type varchar(32),
    exec_time       timestamp   NOT NULL,
    created_at      timestamp   NOT NULL DEFAULT timezone('UTC', now())
);
CREATE INDEX IF NOT EXISTS real_trade_executions_trade_idx ON real_trade_executions (real_trade_id);
COMMENT ON TABLE real_trade_executions IS 'MEJ-004: partes (fills) de Bybit de la apertura y el cierre de cada operación Real';
-- La columna y la marca 'historical' van juntas y solo la primera vez: repetir la migración no toca operaciones nuevas.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name = 'real_trades' AND column_name = 'executions_status') THEN
    ALTER TABLE real_trades ADD COLUMN executions_status varchar(12);
    UPDATE real_trades SET executions_status = 'historical';
  END IF;
END $$;
COMMENT ON COLUMN real_trades.executions_status IS 'MEJ-004: NULL pendiente · open_ok · ok · missing · historical';

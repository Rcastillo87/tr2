-- orderLinkId de la orden de apertura, guardado ANTES de enviarla a Bybit: si el motor se cae a mitad de una
-- apertura, la conciliación pregunta por ESA orden y adopta o descarta el 'pending_open' sin adivinar.
ALTER TABLE real_trades ADD COLUMN IF NOT EXISTS order_link_id varchar(40) NULL;
CREATE INDEX IF NOT EXISTS real_trades_pending_open_idx ON real_trades (broker_account_id) WHERE status = 'pending_open';

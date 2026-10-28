-- Límites de riesgo por cuenta de broker (los edita el usuario que conectó la cuenta).
--   max_monthly_loss_pct: pérdida neta máxima del mes (trades cerrados) en % del saldo inicial del mes.
--   max_open_trades: posiciones abiertas a la vez en la cuenta (todas las estrategias).
--   month_start_balance / month_start_at: patrimonio al empezar el mes (o al conectar la cuenta), en hora de Bogotá.
-- Valores por defecto = config/trading.php (risk_limits).
ALTER TABLE broker_accounts
    ADD COLUMN IF NOT EXISTS max_monthly_loss_pct numeric(5,2) NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS max_open_trades      smallint     NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS month_start_balance  numeric(20,8) NULL,
    ADD COLUMN IF NOT EXISTS month_start_at       date          NULL;
DO $$ BEGIN
    ALTER TABLE broker_accounts ADD CONSTRAINT broker_accounts_max_monthly_loss_chk CHECK (max_monthly_loss_pct BETWEEN 1 AND 30);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE broker_accounts ADD CONSTRAINT broker_accounts_max_open_trades_chk CHECK (max_open_trades BETWEEN 1 AND 20);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
-- suma del PnL del mes por cuenta
CREATE INDEX IF NOT EXISTS real_trades_closed_month_idx ON real_trades (broker_account_id, exit_time) WHERE status = 'closed';

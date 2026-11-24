-- D-66 (p111): opciones de los límites de riesgo por cuenta Real. Todo nuevo y con valores que dejan la cuenta como hoy:
--   monthly_loss_enabled / open_trades_limit_enabled: false = «sin límite» (el número se conserva para reactivarlo);
--   loss_pause_days: al llegar a la pérdida máxima, días sin entradas (1–30); NULL = hasta fin de mes (como hoy);
--   loss_paused_until: hasta cuándo dura la pausa en curso (UTC, como exit_time); NULL = sin pausa;
--   loss_period_start / loss_period_balance: al reanudar, desde cuándo y sobre qué patrimonio se cuenta de cero.
-- Idempotente; espera corta por el bloqueo.
SET lock_timeout = '10s';
ALTER TABLE broker_accounts
    ADD COLUMN IF NOT EXISTS monthly_loss_enabled      boolean       NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS open_trades_limit_enabled boolean       NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS loss_pause_days           smallint      NULL,
    ADD COLUMN IF NOT EXISTS loss_paused_until         timestamp     NULL,
    ADD COLUMN IF NOT EXISTS loss_period_start         timestamp     NULL,
    ADD COLUMN IF NOT EXISTS loss_period_balance       numeric(20,8) NULL;
DO $$ BEGIN
    ALTER TABLE broker_accounts ADD CONSTRAINT broker_accounts_loss_pause_days_check
        CHECK (loss_pause_days IS NULL OR loss_pause_days BETWEEN 1 AND 30);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

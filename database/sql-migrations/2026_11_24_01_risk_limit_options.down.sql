-- Bajada de 2026_11_24_01 (D-66): quita las opciones de los límites; las cuentas vuelven a «límites activos, sin pausa».
SET lock_timeout = '10s';
ALTER TABLE broker_accounts DROP CONSTRAINT IF EXISTS broker_accounts_loss_pause_days_check;
ALTER TABLE broker_accounts
    DROP COLUMN IF EXISTS loss_period_balance,
    DROP COLUMN IF EXISTS loss_period_start,
    DROP COLUMN IF EXISTS loss_paused_until,
    DROP COLUMN IF EXISTS loss_pause_days,
    DROP COLUMN IF EXISTS open_trades_limit_enabled,
    DROP COLUMN IF EXISTS monthly_loss_enabled;

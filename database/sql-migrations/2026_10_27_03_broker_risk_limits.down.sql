-- Revierte 2026_10_27_03_broker_risk_limits
DROP INDEX IF EXISTS real_trades_closed_month_idx;
ALTER TABLE broker_accounts
    DROP CONSTRAINT IF EXISTS broker_accounts_max_open_trades_chk,
    DROP CONSTRAINT IF EXISTS broker_accounts_max_monthly_loss_chk,
    DROP COLUMN IF EXISTS month_start_at,
    DROP COLUMN IF EXISTS month_start_balance,
    DROP COLUMN IF EXISTS max_open_trades,
    DROP COLUMN IF EXISTS max_monthly_loss_pct;

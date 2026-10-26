-- Volatilidad 'widen' una sola vez por trade (paper y real), igual que el backtest.
BEGIN;
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS vol_widened boolean NOT NULL DEFAULT false;
ALTER TABLE real_trades  ADD COLUMN IF NOT EXISTS vol_widened boolean NOT NULL DEFAULT false;
COMMIT;

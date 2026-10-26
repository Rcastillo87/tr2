BEGIN;
ALTER TABLE paper_trades DROP COLUMN IF EXISTS vol_widened;
ALTER TABLE real_trades  DROP COLUMN IF EXISTS vol_widened;
COMMIT;

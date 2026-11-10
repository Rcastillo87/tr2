ALTER TABLE backtests DROP CONSTRAINT IF EXISTS backtests_origin_check;
ALTER TABLE backtests DROP COLUMN IF EXISTS origin_meta;
ALTER TABLE backtests DROP COLUMN IF EXISTS origin;

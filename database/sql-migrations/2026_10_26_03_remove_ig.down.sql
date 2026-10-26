-- Revertir: vuelve la columna; los datos se restauran con los CSV del respaldo:
--   \copy broker_accounts FROM '/root/backups/ig_<fecha>/broker_accounts.csv' CSV HEADER
--   \copy collector_configs FROM '/root/backups/ig_<fecha>/collector_configs.csv' CSV HEADER
--   \copy ohlcv_data FROM '/root/backups/ig_<fecha>/ohlcv_data.csv' CSV HEADER
BEGIN;
ALTER TABLE collector_configs ADD COLUMN IF NOT EXISTS epic varchar(40);
COMMIT;

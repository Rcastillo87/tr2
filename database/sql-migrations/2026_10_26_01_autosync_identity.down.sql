-- Revierte 2026_10_26_01_autosync_identity.up.sql
DROP TABLE IF EXISTS strategy_config_changes;
DROP INDEX IF EXISTS real_trades_paper_strategy_config_id_index;
ALTER TABLE real_trades DROP COLUMN IF EXISTS config_snapshot;
DROP INDEX IF EXISTS paper_trades_one_open_per_config;
DROP INDEX IF EXISTS paper_trades_config_status_index;
ALTER TABLE paper_trades DROP CONSTRAINT IF EXISTS paper_trades_paper_strategy_config_id_foreign;
ALTER TABLE paper_trades DROP COLUMN IF EXISTS paper_strategy_config_id;
ALTER TABLE paper_strategy_configs DROP CONSTRAINT IF EXISTS paper_strategy_configs_backtest_symbol_unique;
ALTER TABLE paper_strategy_configs DROP CONSTRAINT IF EXISTS paper_strategy_configs_backtest_id_foreign;
ALTER TABLE paper_strategy_configs ALTER COLUMN backtest_id DROP NOT NULL;
ALTER TABLE paper_strategy_configs
  ADD CONSTRAINT paper_strategy_configs_backtest_id_foreign
  FOREIGN KEY (backtest_id) REFERENCES backtests(id) ON DELETE SET NULL;
CREATE INDEX idx_paper_configs_backtest_active ON paper_strategy_configs (backtest_id, active);
CREATE UNIQUE INDEX paper_strategy_configs_unique ON paper_strategy_configs (strategy_class, symbol, "interval", (params ->> 'mode'));

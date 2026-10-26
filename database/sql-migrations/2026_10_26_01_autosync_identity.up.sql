-- Auto-Sync fase 0: identidad config <-> backtest <-> trades.
-- Ejecutar SIEMPRE dentro de una transacción con ON_ERROR_STOP.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM paper_trades WHERE status = 'open') THEN
    RAISE EXCEPTION 'ABORTADO: hay paper trades abiertos';
  END IF;
  IF EXISTS (SELECT 1 FROM real_trades WHERE status IN ('open','pending_open','pending_close')) THEN
    RAISE EXCEPTION 'ABORTADO: hay real trades abiertos';
  END IF;
  IF EXISTS (SELECT 1 FROM paper_strategy_configs WHERE backtest_id IS NULL) THEN
    RAISE EXCEPTION 'ABORTADO: existen configs sin backtest_id';
  END IF;
END $$;

-- 1. paper_strategy_configs: 1 config por (backtest, moneda)
DROP INDEX IF EXISTS paper_strategy_configs_unique;
DROP INDEX IF EXISTS idx_paper_configs_backtest_active;
ALTER TABLE paper_strategy_configs DROP CONSTRAINT paper_strategy_configs_backtest_id_foreign;
ALTER TABLE paper_strategy_configs ALTER COLUMN backtest_id SET NOT NULL;
ALTER TABLE paper_strategy_configs
  ADD CONSTRAINT paper_strategy_configs_backtest_id_foreign
  FOREIGN KEY (backtest_id) REFERENCES backtests(id) ON DELETE RESTRICT;
ALTER TABLE paper_strategy_configs
  ADD CONSTRAINT paper_strategy_configs_backtest_symbol_unique UNIQUE (backtest_id, symbol);

-- 2. paper_trades: identidad por id (no por display_name)
ALTER TABLE paper_trades ADD COLUMN paper_strategy_config_id bigint;
UPDATE paper_trades pt SET paper_strategy_config_id = c.id
  FROM paper_strategy_configs c WHERE c.display_name = pt.strategy;
ALTER TABLE paper_trades
  ADD CONSTRAINT paper_trades_paper_strategy_config_id_foreign
  FOREIGN KEY (paper_strategy_config_id) REFERENCES paper_strategy_configs(id) ON DELETE SET NULL;
CREATE INDEX paper_trades_config_status_index ON paper_trades (paper_strategy_config_id, status);
CREATE UNIQUE INDEX paper_trades_one_open_per_config ON paper_trades (paper_strategy_config_id) WHERE status = 'open';

-- 3. real_trades: parámetros congelados al abrir
ALTER TABLE real_trades ADD COLUMN config_snapshot jsonb;
CREATE INDEX real_trades_paper_strategy_config_id_index ON real_trades (paper_strategy_config_id);

-- 4. Auditoría de cambios de configuración
CREATE TABLE strategy_config_changes (
  id                       bigserial PRIMARY KEY,
  paper_strategy_config_id bigint REFERENCES paper_strategy_configs(id) ON DELETE SET NULL,
  backtest_id              bigint REFERENCES backtests(id) ON DELETE SET NULL,
  symbol                   varchar(32) NOT NULL,
  action                   varchar(16) NOT NULL CHECK (action IN ('created','updated','deactivated','deleted')),
  old_params               jsonb,
  new_params               jsonb,
  changed_keys             text[] NOT NULL DEFAULT '{}',
  source                   varchar(32) NOT NULL,
  user_id                  bigint REFERENCES users(id) ON DELETE SET NULL,
  created_at               timestamp(0) NOT NULL DEFAULT timezone('UTC', now())
);
CREATE INDEX strategy_config_changes_config_created ON strategy_config_changes (paper_strategy_config_id, created_at DESC);

-- Verificación
DO $$
DECLARE n_unlinked int; n_dup int;
BEGIN
  SELECT count(*) INTO n_unlinked FROM paper_trades WHERE paper_strategy_config_id IS NULL;
  SELECT count(*) INTO n_dup FROM (SELECT backtest_id, symbol FROM paper_strategy_configs GROUP BY 1,2 HAVING count(*) > 1) d;
  RAISE NOTICE 'VERIFICACION: paper_trades_sin_config=% duplicados=%', n_unlinked, n_dup;
  IF n_unlinked > 0 OR n_dup > 0 THEN
    RAISE EXCEPTION 'ABORTADO: verificación post-migración fallida';
  END IF;
END $$;

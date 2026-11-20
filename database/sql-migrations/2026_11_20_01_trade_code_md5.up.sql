-- p86 (MEJ-002 de la auditoría): versión del código de la estrategia con que se abrió cada operación de Paper y Real.
-- El snapshot de cada trade ya guarda el código completo; esta columna es su huella (md5) para agrupar y consultar sin
-- comparar textos (p. ej. qué trades se abrieron con el VWAP Tendencia viejo, 979d8dec…, y cuáles con el corregido).
-- Columna generada: la calcula PostgreSQL desde config_snapshot (también para las operaciones históricas) y no la
-- escribe nadie. NULL = trade sin snapshot o sin código en el snapshot. Idempotente.
SET lock_timeout = '10s';
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS strategy_code_md5 char(32)
    GENERATED ALWAYS AS (md5(config_snapshot->>'strategy_code')) STORED;
ALTER TABLE real_trades ADD COLUMN IF NOT EXISTS strategy_code_md5 char(32)
    GENERATED ALWAYS AS (md5(config_snapshot->>'strategy_code')) STORED;
COMMENT ON COLUMN paper_trades.strategy_code_md5 IS 'MEJ-002: md5 del código de la estrategia del snapshot (generada)';
COMMENT ON COLUMN real_trades.strategy_code_md5 IS 'MEJ-002: md5 del código de la estrategia del snapshot (generada)';

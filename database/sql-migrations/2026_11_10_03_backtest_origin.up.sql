-- RQ-01.3: origen de cada backtest (manual | search), fijado al crearlo. NULL = anterior a p50 sin rastro.
-- origin_meta: foto de la búsqueda (run_id, row_id, focus, mode, symbols_mode, search_at, created_at); sin FK.
ALTER TABLE backtests ADD COLUMN IF NOT EXISTS origin varchar(16);
ALTER TABLE backtests ADD COLUMN IF NOT EXISTS origin_meta jsonb;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'backtests_origin_check') THEN
    ALTER TABLE backtests ADD CONSTRAINT backtests_origin_check CHECK (origin IS NULL OR origin IN ('manual', 'search'));
  END IF;
END $$;
COMMENT ON COLUMN backtests.origin IS 'RQ-01.3: manual | search; NULL = origen no registrado (anterior a p50)';
COMMENT ON COLUMN backtests.origin_meta IS 'RQ-01.3: foto de la busqueda que lo creo (sin FK)';

-- Recuperación: los backtests que «Crear en historial» dejó registrados en results.created de su búsqueda.
-- Si un backtest figura en varias búsquedas, gana la creación más antigua. Idempotente (solo origin IS NULL).
UPDATE backtests b
   SET origin = 'search',
       origin_meta = jsonb_build_object('run_id', s.run_id, 'row_id', s.row_id, 'focus', s.focus, 'mode', s.mode,
                                        'symbols_mode', NULL, 'search_at', s.search_at, 'created_at', s.created_at,
                                        'recovered', true)
  FROM (SELECT DISTINCT ON ((c.value->>'backtest_id')::bigint)
               (c.value->>'backtest_id')::bigint AS backtest_id, r.id AS run_id, c.key AS row_id, r.focus, r.mode,
               to_char(r.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') AS search_at,
               c.value->>'at' AS created_at
          FROM param_search_runs r
          CROSS JOIN LATERAL jsonb_each(CASE WHEN jsonb_typeof(r.results::jsonb->'created') = 'object'
                                             THEN r.results::jsonb->'created' ELSE '{}'::jsonb END) c
         WHERE jsonb_typeof(c.value) = 'object'
           AND c.value->>'status' = 'done'
           AND (c.value->>'backtest_id') ~ '^[0-9]{1,18}$'
         ORDER BY (c.value->>'backtest_id')::bigint, c.value->>'at', r.id) s
 WHERE b.id = s.backtest_id
   AND b.origin IS NULL;

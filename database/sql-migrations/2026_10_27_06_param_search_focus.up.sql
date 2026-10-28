-- Búsqueda v3: enfoque (qué se busca) y modo (cómo) de cada búsqueda. Las anteriores quedan como 'gain' · 'interval'.
ALTER TABLE param_search_runs
    ADD COLUMN IF NOT EXISTS focus varchar(8) NOT NULL DEFAULT 'gain',
    ADD COLUMN IF NOT EXISTS mode  varchar(8) NOT NULL DEFAULT 'interval';
DO $$ BEGIN
    ALTER TABLE param_search_runs ADD CONSTRAINT param_search_runs_focus_chk CHECK (focus IN ('gain', 'wr', 'cons'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE param_search_runs ADD CONSTRAINT param_search_runs_mode_chk CHECK (mode IN ('interval', 'symbol'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

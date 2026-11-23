-- D-45 (p93): qué SL/TP prueba cada búsqueda. fixed = como siempre (las anteriores) · auto = automáticos · both = los dos.
ALTER TABLE param_search_runs ADD COLUMN IF NOT EXISTS sltp varchar(8) NOT NULL DEFAULT 'fixed';
DO $$ BEGIN
    ALTER TABLE param_search_runs ADD CONSTRAINT param_search_runs_sltp_chk CHECK (sltp IN ('fixed', 'auto', 'both'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

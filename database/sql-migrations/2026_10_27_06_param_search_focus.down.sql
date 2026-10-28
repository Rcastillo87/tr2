ALTER TABLE param_search_runs DROP CONSTRAINT IF EXISTS param_search_runs_mode_chk;
ALTER TABLE param_search_runs DROP CONSTRAINT IF EXISTS param_search_runs_focus_chk;
ALTER TABLE param_search_runs DROP COLUMN IF EXISTS mode, DROP COLUMN IF EXISTS focus;

ALTER TABLE param_search_runs DROP CONSTRAINT IF EXISTS param_search_runs_sltp_chk;
ALTER TABLE param_search_runs DROP COLUMN IF EXISTS sltp;

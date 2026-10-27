-- Falla si hay más de una búsqueda en cola/corriendo: cancelarlas antes.
DROP INDEX IF EXISTS param_search_runs_one_running;
DROP INDEX IF EXISTS param_search_runs_one_active_per_strategy;
CREATE UNIQUE INDEX param_search_runs_one_active ON param_search_runs ((true)) WHERE status IN ('queued', 'running');

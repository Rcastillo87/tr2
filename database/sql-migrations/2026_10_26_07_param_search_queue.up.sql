-- Búsquedas en cola: varias pueden esperar (una por estrategia) y la cola research las corre de a una.
-- Antes: una sola activa (en cola o corriendo) en todo el sistema.
DROP INDEX IF EXISTS param_search_runs_one_active;
CREATE UNIQUE INDEX param_search_runs_one_running ON param_search_runs ((true)) WHERE status = 'running';
CREATE UNIQUE INDEX param_search_runs_one_active_per_strategy ON param_search_runs (strategy_id) WHERE status IN ('queued', 'running');

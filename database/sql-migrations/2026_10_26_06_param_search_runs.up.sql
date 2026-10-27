-- Búsqueda de configuraciones (módulo Estrategias → "Buscar"): una fila por búsqueda.
-- Ejecutar dentro de una transacción con ON_ERROR_STOP.
CREATE TABLE param_search_runs (
    id                 bigserial PRIMARY KEY,
    strategy_id        bigint      NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    user_id            bigint      REFERENCES users(id) ON DELETE SET NULL,
    status             varchar(16) NOT NULL DEFAULT 'queued'
                       CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled')),
    intervals          jsonb       NOT NULL,                 -- ["240"] · ["60","120"]
    search_symbols     jsonb       NOT NULL,                 -- elige SOLO con estas
    validation_symbols jsonb       NOT NULL DEFAULT '[]',    -- monedas que la búsqueda no ve
    months             smallint    NOT NULL DEFAULT 24 CHECK (months BETWEEN 6 AND 36),
    samples            smallint    NOT NULL DEFAULT 40 CHECK (samples BETWEEN 1 AND 200),
    seed               integer     NOT NULL DEFAULT 7,
    strategy_code_md5  char(32),                             -- código evaluado (detecta "código desactualizado")
    period_start       date,
    split_date         date,
    period_end         date,                                 -- exclusivo
    phase              varchar(32),
    progress_done      integer     NOT NULL DEFAULT 0,
    progress_total     integer     NOT NULL DEFAULT 0,
    progress_note      text,
    heartbeat_at       timestamptz,
    pid                integer,
    cancel_requested   boolean     NOT NULL DEFAULT false,
    results            jsonb,
    error              text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    started_at         timestamptz,
    finished_at        timestamptz,
    updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX param_search_runs_strategy_created_index ON param_search_runs (strategy_id, created_at DESC);
-- Una sola búsqueda activa en TODO el sistema (protege CPU/RAM de paper y real): la base lo garantiza.
CREATE UNIQUE INDEX param_search_runs_one_active ON param_search_runs ((true)) WHERE status IN ('queued', 'running');

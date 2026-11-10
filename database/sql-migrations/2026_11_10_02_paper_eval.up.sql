-- RQ-01.5: diagnóstico de Paper. Qué decidió cada config en cada evaluación y por qué (sin cambiar la lógica).
-- paper_eval_state: una fila por config con la última decisión (se reemplaza en cada tick).
-- paper_eval_log: historial agrupado por (config, vela, motivo) con la cantidad de evaluaciones; retención 30 días
-- (PAPER_EVAL_RETENTION_DAYS). Horas en UTC sin zona, como paper_trades. Sin FK a paper_strategy_configs: el
-- historial sobrevive al borrado de una config (igual que strategy_config_changes).
CREATE TABLE IF NOT EXISTS paper_eval_state (
    paper_strategy_config_id bigint      PRIMARY KEY,
    evaluated_at             timestamp   NOT NULL,
    code                     varchar(32) NOT NULL,
    detail                   text        NOT NULL,
    regime                   varchar(16),
    signal                   smallint,
    filters                  jsonb,
    candle_time              timestamp,
    last_bar_time            timestamp,
    bars                     integer
);
CREATE TABLE IF NOT EXISTS paper_eval_log (
    id                       bigserial   PRIMARY KEY,
    paper_strategy_config_id bigint      NOT NULL,
    bucket_time              timestamp   NOT NULL,
    code                     varchar(32) NOT NULL,
    detail                   text        NOT NULL,
    regime                   varchar(16),
    signal                   smallint,
    filters                  jsonb,
    first_at                 timestamp   NOT NULL,
    last_at                  timestamp   NOT NULL,
    evaluations              integer     NOT NULL DEFAULT 1,
    CONSTRAINT paper_eval_log_key UNIQUE (paper_strategy_config_id, bucket_time, code)
);
CREATE INDEX IF NOT EXISTS paper_eval_log_recent_idx ON paper_eval_log (paper_strategy_config_id, last_at DESC);
CREATE INDEX IF NOT EXISTS paper_eval_log_last_at_idx ON paper_eval_log (last_at);

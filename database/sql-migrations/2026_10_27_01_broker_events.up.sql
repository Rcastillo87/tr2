-- Bandeja de salida de eventos de broker: el motor (Python) registra; Laravel (broker:events, cada minuto)
-- los convierte en avisos para el dueño de la cuenta. Sin FK: registrar un evento nunca debe fallar.
-- Retención 90 días (rastro forense; los avisos de la campana duran 30).
CREATE TABLE IF NOT EXISTS broker_events (
    id                bigserial    PRIMARY KEY,
    broker_account_id bigint       NOT NULL,
    trade_id          bigint       NULL,
    event             varchar(40)  NOT NULL,
    data              jsonb        NOT NULL DEFAULT '{}'::jsonb,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    processed_at      timestamptz  NULL
);
-- drenado: solo los pendientes, en orden
CREATE INDEX IF NOT EXISTS broker_events_pending_idx ON broker_events (id) WHERE processed_at IS NULL;
CREATE INDEX IF NOT EXISTS broker_events_account_idx ON broker_events (broker_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS broker_events_created_at_idx ON broker_events (created_at);

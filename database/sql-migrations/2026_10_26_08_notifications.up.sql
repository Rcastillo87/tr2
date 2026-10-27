-- Avisos en la plataforma (Laravel database notifications). Retención 30 días (SystemAlerts::prune, diario).
CREATE TABLE IF NOT EXISTS notifications (
    id              uuid PRIMARY KEY,
    type            varchar(255) NOT NULL,
    notifiable_type varchar(255) NOT NULL,
    notifiable_id   bigint       NOT NULL,
    data            text         NOT NULL,
    read_at         timestamp(0) without time zone NULL,
    created_at      timestamp(0) without time zone NULL,
    updated_at      timestamp(0) without time zone NULL
);
CREATE INDEX IF NOT EXISTS notifications_notifiable_type_notifiable_id_index ON notifications (notifiable_type, notifiable_id);
-- campana: no leídos por usuario, más nuevos primero
CREATE INDEX IF NOT EXISTS notifications_unread_idx ON notifications (notifiable_id, created_at DESC) WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS notifications_created_at_idx ON notifications (created_at);

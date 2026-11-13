-- p62 (decisión del dueño 13-nov): suscripción marcada para eliminarse cuando su última operación viva termine.
-- La pone UserDeactivation al inactivar un usuario (las que tienen operaciones vivas); purgeFinished la elimina al
-- cerrar, aunque el usuario ya esté reactivado. Idempotente.
ALTER TABLE real_strategy_subscriptions ADD COLUMN IF NOT EXISTS retire_on_close boolean NOT NULL DEFAULT false;

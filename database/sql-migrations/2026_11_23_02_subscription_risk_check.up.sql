-- C5-20 (p98): el riesgo propio de una suscripción Real, si se fija, debe ser > 0 y ≤ 100 % (la misma regla F-03 del
-- riesgo de la configuración). NULL = usa el de la configuración. Idempotente; espera corta por el bloqueo.
SET lock_timeout = '10s';
DO $$ BEGIN
    ALTER TABLE real_strategy_subscriptions ADD CONSTRAINT real_strategy_subscriptions_risk_override_check
        CHECK (risk_override_pct IS NULL OR (risk_override_pct > 0 AND risk_override_pct <= 100));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

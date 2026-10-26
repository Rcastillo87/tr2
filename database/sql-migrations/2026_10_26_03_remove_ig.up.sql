-- Elimina IG (respaldo previo en /root/backups/ig_*). Reactiva H4 y D de Bybit.
BEGIN;
DELETE FROM ohlcv_data WHERE broker = 'ig';
DELETE FROM collector_configs WHERE broker = 'ig';
DELETE FROM broker_accounts WHERE broker = 'ig'
  AND NOT EXISTS (SELECT 1 FROM real_trades rt WHERE rt.broker_account_id = broker_accounts.id)
  AND NOT EXISTS (SELECT 1 FROM real_strategy_subscriptions r WHERE r.broker_account_id = broker_accounts.id);
DELETE FROM python_engine_state WHERE key = 'ig_quota_blocked_until';
ALTER TABLE collector_configs DROP COLUMN IF EXISTS epic;
UPDATE collector_configs SET active = true, updated_at = now()
 WHERE broker = 'bybit' AND interval IN ('240', 'D') AND active = false;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM broker_accounts WHERE broker = 'ig') THEN
    RAISE EXCEPTION 'Quedó una cuenta IG con trades o suscripciones: revisar antes de continuar';
  END IF;
END $$;
COMMIT;

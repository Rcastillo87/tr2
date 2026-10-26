-- credentials_extra solo la usaba IG (eliminado el 2026-10-26). Aborta si alguna cuenta tiene datos.
BEGIN;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM broker_accounts WHERE credentials_extra IS NOT NULL) THEN
    RAISE EXCEPTION 'ABORTADO: hay cuentas con credentials_extra';
  END IF;
END $$;
ALTER TABLE broker_accounts DROP COLUMN IF EXISTS credentials_extra;
COMMIT;

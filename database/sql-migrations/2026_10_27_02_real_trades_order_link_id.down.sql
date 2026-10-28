-- Revierte 2026_10_27_02_real_trades_order_link_id
DROP INDEX IF EXISTS real_trades_pending_open_idx;
ALTER TABLE real_trades DROP COLUMN IF EXISTS order_link_id;

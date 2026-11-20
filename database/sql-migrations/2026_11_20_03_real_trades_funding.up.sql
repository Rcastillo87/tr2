-- R-24 (p90): funding de Bybit de cada operación Real, separado de la comisión, como en Paper (positivo = pagado).
-- net_pnl = pnl − commission − funding. NULL = todavía no separado (lo hace el libro de ejecuciones, MEJ-004).
ALTER TABLE real_trades ADD COLUMN IF NOT EXISTS funding numeric(20,8) NULL;

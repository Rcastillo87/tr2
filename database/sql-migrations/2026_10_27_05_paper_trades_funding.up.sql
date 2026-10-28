-- Funding de Bybit de cada trade de paper (positivo = pagado). Ya está descontado en pnl (mismo criterio que el backtest).
-- NULL = trade cerrado antes de que paper descontara funding.
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS funding numeric(20,8) NULL;

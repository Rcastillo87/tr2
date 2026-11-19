-- D-40 (p79), decisión del dueño 19-nov: las operaciones YA cerradas como stop_loss cuyo stop estaba en la entrada (o
-- mejor) por el break-even, sin trailing, pasan a break_even. Misma regla que backtesting/exit_reasons.stop_exit_reason.
-- Al instalar p78 cumplían la regla: Paper #342 y #379, Real #100 (ETH). Idempotente (solo filas stop_loss que cumplen
-- la regla). Real: deja exit_reason_corrected en su historial (audit_log). Paper no tiene historial: el valor anterior
-- queda en este archivo, en la salida del instalador y en docs/BITACORA.md. Precio, PnL y saldo no cambian.
UPDATE real_trades t
   SET exit_reason = 'break_even',
       audit_log = COALESCE(t.audit_log::jsonb, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
           'action', 'exit_reason_corrected',
           'timestamp', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
           'data', jsonb_build_object('from', 'stop_loss', 'to', 'break_even',
                                      'by', 'p79 D-40, decisión del dueño 19-nov', 'sl', t.sl, 'entry_price', t.entry_price)))
 WHERE t.status = 'closed' AND t.exit_reason = 'stop_loss' AND t.be_activated AND NOT COALESCE(t.trailing_applied, false)
   AND ((t.side = 'long' AND t.sl >= t.entry_price) OR (t.side = 'short' AND t.sl <= t.entry_price))
RETURNING 'real' AS tabla, t.id, t.symbol, t.side, t.entry_price, t.sl, t.exit_price, 'stop_loss -> break_even' AS cambio;

UPDATE paper_trades t
   SET exit_reason = 'break_even'
 WHERE t.status = 'closed' AND t.exit_reason = 'stop_loss' AND t.be_activated AND NOT COALESCE(t.trailing_applied, false)
   AND ((t.side = 'long' AND t.sl >= t.entry_price) OR (t.side = 'short' AND t.sl <= t.entry_price))
RETURNING 'paper' AS tabla, t.id, t.symbol, t.side, t.entry_price, t.sl, t.exit_price, 'stop_loss -> break_even' AS cambio;

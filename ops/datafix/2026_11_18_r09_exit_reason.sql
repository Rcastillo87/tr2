-- R-09 (p69), decisión del dueño 18-nov (D-15): corrige el motivo de salida de los cierres de Bybit recuperados por la
-- conciliación con la etiqueta fija reconciled_sl_tp_bybit. Misma regla que el monitor (settle_exchange_close): precio de
-- salida contra SL/TP; trailing_stop si el SL era de trailing. Idempotente (solo filas con la etiqueta vieja); deja
-- exit_reason_corrected en el historial con el valor anterior. PnL y saldo no cambian.
WITH n AS (
  SELECT id,
         CASE WHEN side = 'long'
              THEN CASE WHEN exit_price <= sl THEN CASE WHEN trailing_applied THEN 'trailing_stop' ELSE 'stop_loss' END
                        WHEN exit_price >= tp THEN 'take_profit_1' ELSE 'closed_other' END
              ELSE CASE WHEN exit_price >= sl THEN CASE WHEN trailing_applied THEN 'trailing_stop' ELSE 'stop_loss' END
                        WHEN exit_price <= tp THEN 'take_profit_1' ELSE 'closed_other' END
         END AS new_reason
  FROM real_trades
  WHERE status = 'closed' AND exit_reason = 'reconciled_sl_tp_bybit' AND exit_price IS NOT NULL AND sl IS NOT NULL AND tp IS NOT NULL
)
UPDATE real_trades t
   SET exit_reason = n.new_reason,
       audit_log = COALESCE(t.audit_log::jsonb, '[]'::jsonb) || jsonb_build_array(jsonb_build_object(
           'action', 'exit_reason_corrected',
           'timestamp', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
           'data', jsonb_build_object('from', 'reconciled_sl_tp_bybit', 'to', n.new_reason,
                                      'by', 'p69 R-09, decisión del dueño 18-nov', 'exit_price', t.exit_price, 'sl', t.sl, 'tp', t.tp)))
  FROM n
 WHERE t.id = n.id AND t.exit_reason = 'reconciled_sl_tp_bybit'
RETURNING t.id, t.symbol, t.side, t.exit_price, t.sl, t.tp, t.trailing_applied, n.new_reason;

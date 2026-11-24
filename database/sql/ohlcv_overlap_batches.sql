-- C6-05: lotes comprimidos solapados en UN fragmento comprimido de ohlcv_data (solo lectura).
-- {comp} = esquema.tabla del fragmento comprimido (del catálogo de TimescaleDB, con format('%I.%I')).
-- Cada serie (broker, symbol, interval: el segmentby de la compresión) debe tener sus lotes sin pisarse en el tiempo:
-- un lote cuyo mínimo no supera el máximo de los anteriores de la misma serie está solapado.
SELECT broker, symbol, "interval", count(*) AS lotes, min(mn) AS desde
FROM (
    SELECT broker, symbol, "interval", _ts_meta_min_1 AS mn,
           max(_ts_meta_max_1) OVER (PARTITION BY broker, symbol, "interval" ORDER BY _ts_meta_min_1, _ts_meta_max_1
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_max
    FROM {comp}
) q
WHERE prev_max >= mn
GROUP BY broker, symbol, "interval"
ORDER BY broker, symbol, "interval"

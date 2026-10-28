# Bitácora de cambios — TR2

> Registro cronológico de lo que cambió, por qué y cómo se verificó. Lo más reciente arriba.
> Incluye los cambios que **no viven en git** (configuración de la base, datos, servidor): sin esta bitácora se perderían.
> Horas en UTC salvo que se indique. Commits en `main` de `github.com/Rcastillo87/tr2`.

---

## 2026-10-27 (Bogotá) — Integridad de velas, filtros v2, búsqueda v3, funding y riesgo en real

### Resumen para el dueño
- **Las velas llegaban desordenadas desde la base** en algunos casos (TimescaleDB). Quedó corregido en tres capas: configuración de la base, datos reescritos y un escudo en el código que ordena y avisa. Los resultados de backtest, búsqueda, paper y real son confiables.
- **Funding de Bybit** incluido en backtest y paper (pesimista en los bordes).
- **Motor 4–5× más rápido** con resultados idénticos.
- **Búsqueda de estrategias v3**: enfoque (ganancia / win rate / consistencia), "gana" = gana en los primeros 2/3 **y** en el último 1/3, modo por moneda hasta 5 monedas, historial con monedas y eliminar.
- **Auditoría de filtros** con datos reales: casi ningún filtro distingue ganadoras de perdedoras; el régimen con los 3 regímenes no hacía nada. **Filtros de apertura v2**: regímenes permitidos elegibles + tendencia de BTC para altcoins.
- **Real**: órdenes idempotentes (`orderLinkId`), avisos de broker, límites de riesgo por cuenta.
- Universo de **12 monedas**; BNB fuera del collector.

### Commits (orden cronológico)

| Commit | Qué | Verificación |
|---|---|---|
| `f59a091` | Real: 110072 devuelve la orden original, 110017 sin reintento; un cierre sin `Filled` se decide por la posición real (nunca por precio de mercado); `pending_close` liquidable | `bybit_order_idempotency_test.py`, `bybit_order_idempotency_demo.py` (solo demo) |
| `98e795b` | Real: avisos de broker (`broker_events` → campana del dueño), vigilancia del tick real, cuentas pausadas siguen gestionando sus posiciones | `broker_events_test.py`, `broker_events_drain_test.php`, `broker_event_messages_test.php` |
| `d2d463e` | Real: `pending_open` recuperable (`orderLinkId` guardado antes de enviar; la conciliación pregunta por SU orden), chequeo de liquidación al abrir, apalancamiento real | `real_recovery_test.py`, `real_liq_demo.py` (solo demo) |
| `d4cd1c4` | Real: límites de riesgo por cuenta (pérdida máxima del mes y trades abiertos), panel en `/trading/accounts` editable por el dueño | `risk_limits_test.py`, `risk_limits_laravel_test.php` |
| `e7f881b` | Backtest: funding de Bybit por trade. Paga si la liquidación cae en [entrada, salida]; cobra solo en (entrada, salida) abierto; precio = cierre del minuto anterior. Caché `funding_rates` / `funding_coverage` | `funding_test.py` |
| `58aa311` | Paper: funding al cerrar con el mismo criterio; columna `paper_trades.funding` | `paper_parity_test.py` |
| `51db17c` | Motor 4–5× más rápido sin cambiar resultados: salta velas ociosas, índices de 1m precalculados, `_scan` en bloques numpy; la búsqueda carga el 1m una vez por moneda | `engine_speed_parity_test.py` (contra `reference/engine_v3_ref.py`), `param_search_cache_test.py` |
| `477fae8` | Búsqueda v3 (entrega B, diseño aprobado "TR2 — Búsqueda de estrategias v3") | `param_search_v3_test.py`, `param_search_v3_laravel_test.php` |
| `bf7c837` | Velas siempre en orden: `collectors/bars.py` (`bars_frame`, `sorted_records`) en backtest, paper, real y régimen; ordena, quita horas repetidas y **avisa** `[BARS]` en el log | `bars_order_test.py` |
| `8c3cd6d` | La prueba de velas cubre 1m de 2 años y `plan_cache_mode`; herramienta `tools/analysis/filter_audit.py` | `bars_order_test.py --db` |
| `e98d2e9` | Limpieza: documentos viejos a `docs/archive/` | — |
| `e81a79b` | Búsqueda: prueba 4 niveles de volumen (0,8 / 1,0 / 1,2 / 1,5); no prueba régimen en estrategias con los 3 regímenes; la caché de señales distingue el nivel de volumen (antes habría mezclado resultados) | `param_search_v3_test.py` |
| `1ebcb56` | Filtros de apertura v2 (diseño aprobado "TR2 — Filtros de apertura v2"): `allowed_regimes` elegibles con aviso "no bloquea nada"; `btc_trend_filter` (EMA 50 H4 de BTC) en backtest, paper y real | `filters_v2_test.py`, `backtest_payload_chain_test.{php,py}`, `backtest_form_payload_test.php` |
| `6f35019` | Búsqueda: prueba la tendencia de BTC en los enfoques; el backtest creado desde la búsqueda lleva el filtro | SOL H4 real: 274 ops PF 1,41 → con BTC 227 ops PF 1,50 |
| `ecf6c6e` | La prueba de velas falla si la **base** entrega desordenado (antes medía después del escudo y no lo veía) | `bars_order_test.py --db`: TODO OK |

### Cambios fuera de git (base de datos y servidor)

| Cambio | Detalle | Cómo deshacer |
|---|---|---|
| `ALTER DATABASE trading2 SET timescaledb.enable_ordered_append = off` | Como `postgres`. El ordered append sobre fragmentos parciales desordenaba | `ALTER DATABASE trading2 RESET timescaledb.enable_ordered_append` |
| `ALTER DATABASE trading2 SET plan_cache_mode = force_custom_plan` | El plan genérico de asyncpg (desde la 6.ª ejecución) desordenaba aun sin ordered append | `ALTER DATABASE trading2 RESET plan_cache_mode` |
| Recompresión de 123 fragmentos parciales | `/root/patches/recompress/recompress.sh`, terminó 03:36 con 0 parciales. **Dejó lotes solapados** (ver abajo) | — |
| 50 fragmentos reescritos (`decompress_chunk` + `compress_chunk`) | Lotes comprimidos solapados en el tiempo: la lectura ordenada asume que no se solapan → 30 saltos en SOL 1m de junio 2026. Detección: `/root/patches/batches/detect.sql`; log `/root/patches/batches/fix.log`. Después: 0 solapes, 0 saltos | — (los datos no cambian) |
| `ALTER SYSTEM SET maintenance_work_mem = '256MB'`, `autovacuum_work_mem = '128MB'` | Antes ~1 GB por tarea con `autovacuum_max_workers = 10` (picos de hasta ~10 GB en un VPS de 7,8 GB) | `ALTER SYSTEM RESET …; SELECT pg_reload_conf()` |
| Universo de 12 monedas | BTC, ETH, SOL, XRP, ZEC, HYPE, ENA, DOGE, SUI, NEAR, 1000PEPE, LINK × 1m, 5m, 15m, 1h, 2h, 4h, 1D. Historia desde 2024-06-01 para ENA, DOGE y 1000PEPE; 1D para HYPE, LINK, NEAR, SUI, ZEC; funding precargado. BNB desactivado en el collector (sus velas se conservan). Script `/root/patches/universe/universe_20261027b.py` | reactivar en `collector_configs` |
| Búsquedas anteriores borradas | 44 (43 terminadas, 1 fallida). Respaldo `/root/patches/cleanup/20261028_0355/param_search_runs.csv` | — |
| `.env`: `QUEUE_CONNECTION` repetido | Quedó `redis` (era el valor efectivo); se quitó `database`. Respaldo `env.bak` en la misma carpeta | restaurar `env.bak` |
| 178 respaldos `.bak*` borrados del proyecto | Archivados en `/root/patches/cleanup/20261028_0355/baks.tgz` (504 KB) | `tar -xzf` |
| Migraciones SQL aplicadas | `2026_10_27_01` a `2026_10_27_06` (broker events, `order_link_id`, límites de riesgo, funding, `paper_trades.funding`, búsqueda focus/mode) | `.down.sql` de cada una |

### Hallazgos de la auditoría de filtros (`tools/analysis/filter_audit.py`)
- Criterio: un filtro **sirve** si sube el PF y no baja la ganancia total (en R) en los primeros 16 meses **y** en los últimos 8. "Mejora calidad" = sube el PF pero se gana menos.
- **Régimen con ambiguo = lateral**: sin efecto en 48/48 combinaciones de VWAP Tendencia, VWAP Reversión, Cruce de Medias y FSupertrend (permiten los 3 regímenes). Motivó los filtros v2.
- En general los filtros quitan ganadoras y perdedoras en la misma proporción (recorte casi al azar). Ninguno convierte una estrategia perdedora en ganadora.
- **Tendencia de BTC**: el único filtro nuevo con alcance (sube PF en 5 de 6 estrategias en ambos tramos), pero empeora VWAP Tendencia en SUI y ZEC → opcional, apagado por defecto.
- **Paper (VWAP Tendencia H4, volumen ×0,8)**: SUI → ×1,0 "sirve" (PF 1,32→1,53 y 1,11→1,20); SOL ×1,2 mejora calidad; ZEC mejor en ×0,8. El dueño decidió rehacer las búsquedas desde cero.

### Revalidación de paper (funding + velas ordenadas, mismo rango 2024-10..2026-09)

| Config | Operaciones | Win rate | Retorno | PF | Drawdown | Funding pagado |
|---|---|---|---|---|---|---|
| #54 SUI H4 | 281 | 42,0 % | +50,8 % | 1,24 | 17,9 % | 39,8 USDT |
| #55 ZEC H4 | 317 | 41,0 % | +65,9 % | 1,24 | 14,1 % | 84,2 USDT |
| #56 SOL H4 | 259 | 44,4 % | +68,5 % | 1,36 | 10,8 % | 90,9 USDT |

Mismas operaciones que el backtest #86; parámetros de paper = backtest (sin diferencias).

### Lecciones del día
- Un escudo en el código que corrige en silencio **oculta** el problema a las pruebas: la prueba debe medir la fuente (sin avisos `[BARS]`), no el resultado ya corregido.
- La recompresión de fragmentos parciales de TimescaleDB 2.27 puede dejar lotes solapados; arreglo definitivo: `decompress_chunk` + `compress_chunk`.
- `postgres` no lee archivos en `/root/`: pasar el SQL por la entrada estándar (`psql < archivo`).
- Scripts pegados en la terminal: envolver en `( … )`. Un `set -e` o un `exit` pegados directo cierran la sesión SSH.

### Pendientes que dejó el día
1. Revisión automática 2 veces al día de lotes solapados tras la compresión de TimescaleDB (job `policy_compression` cada 12 h, `compress_after` 14 días).
2. Reconciliación paper vs backtest con trades reales (cuando paper lleve 1–2 semanas).
3. Funding en pantalla (diseño "TR2 — Funding en pantalla" listo, pospuesto).
4. Documentos `docs/01_GENERAL.md`, `02_TECHNICAL.md`, `03_AI_CONTEXT.md`: reescritura completa (hoy solo se actualizaron las secciones afectadas).

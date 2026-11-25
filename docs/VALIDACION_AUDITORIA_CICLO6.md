# Validación del informe de mejoras — Ciclo 6 (TR2)

> Validación punto por punto del «Informe de mejoras y trabajos pendientes — Ciclo 6» (24-nov, versión auditada
> `542b6f4`). **Método (PROMPT_MAESTRO §6.0):** validar contra el código y el servidor (lectura de solo lectura);
> clasificar como **defecto** (contradice una decisión, dato equivocado o riesgo de dinero/datos → arreglo
> recomendado), **sugerencia** (cambia algo que funciona como el dueño decidió → decide el dueño) o **refutado**;
> proponer en español simple; prueba que falla con el código anterior, mutaciones y regresión completa; registrar aquí,
> en `docs/BITACORA.md` y, si hay decisión, en `docs/DECISIONES_DUENO.md`. Orden del informe (§3); resueltos aparte.
> Se mantienen D-48, D-58, D-63, D-64, D-67 y D-45/D-49 (informe §4).

## Pendientes del ciclo

| Orden | ID | Prioridad | Punto | Estado |
|---|---|---|---|---|
| 5 | C6-07 | P2 | Comparación SL/TP fijo vs automático | Corrida 25-nov; decisión: automático solo en LINK #64, PEPE #69, SUI #79 (el dueño lo cambia desde el backtest) |

## Validados

### C6-04 · Fechas reales de cada tramo de la búsqueda (P3) — **Sugerencia (pantalla)** · Instalado en p122 (`4f53e69`)
- **Código:** la barra mostraba «Elegir · meses 1–14 / Validar · 15–19 / Prueba final · 20–24» (meses redondeados de
  los cortes guardados) y el encabezado «24 meses (2024-11-01 → 2026-11-01)», con el fin exclusivo del rango (el último
  día que cuenta es el 31-oct). Los cortes reales salen de `segment_cuts` (60/20/20 del tiempo, no de meses enteros):
  p. ej. 13-ene y 8-jun-2026.
- **Fix (boceto aprobado 25-nov, «si»):** `App\Support\SearchPeriodLabels` arma, desde `results.period` de cada
  búsqueda, el total («1 nov 2024 → 31 oct 2026») y las fechas de cada tramo («1 nov 2024 – 12 ene 2026», «13 ene –
  7 jun 2026», «8 jun – 31 oct 2026»); el controlador las entrega (`period_labels`) y la vista las pone debajo de cada
  tramo (escapadas) y en el encabezado. Búsquedas de dos tramos: total corregido, sin tramos; datos raros: como antes.
  D-58 sin cambios (la barra sigue diciendo que el total ordena y filtra y que la prueba final solo se muestra).
- **Prueba:** `search_period_labels_test.php` (nueva; código anterior 4 FALLOS); `search_three_segments_static_test`
  sigue en TODO OK; mutaciones 7/7; regresión 85 Python + 38 PHP en TODO OK.
- **Instalado p122 (`4f53e69`, 25-nov 02:1x UTC):** búsqueda #205: «1 nov 2024 → 31 oct 2026 · 1 nov 2024 – 12 ene 2026 |
  13 ene – 7 jun 2026 | 8 jun – 31 oct 2026»; el dueño lo vio en pantalla.

### C6-06 · Esquema PostgreSQL del repositorio (P3) — **Defecto (documentación técnica)** · Instalado en p121 (`7f9c636`)
- **Código:** p111 aplicó la migración de D-66 (`2026_11_24_01_risk_limit_options`: 6 columnas y
  `broker_accounts_loss_pause_days_check`) sin regenerar `database/schema/pgsql-schema.sql`; la última regeneración fue
  p108. Ninguna prueba comparaba las migraciones con el volcado. Confirmado: el informe tiene razón.
- **Fix (opción B del dueño, 24-nov: sin acceso al repositorio desde aquí):** `schema_sync_test.py` (nueva): lee todas
  las migraciones `*.up.sql` (tablas, columnas, índices y restricciones con nombre, también dentro de `DO $$`, descontando
  lo que una migración posterior borra) y exige que estén en el volcado. p121 regenera el volcado en el servidor con
  `ops/schema_dump.sh` (solo lectura) **antes** de la regresión, comprueba que tenga las mismas tablas que la base y las
  6 columnas con su tipo y default, y lo incluye en el commit. Regla nueva en PROMPT_MAESTRO §6.5: todo instalador con
  migración regenera el volcado antes de la regresión.
- **Prueba:** S1–S6 el lector (columnas con comas en tipos y textos, `DO $$`, borrados posteriores, formato de
  `pg_dump`, volcado viejo, tabla que falta); R1 el volcado real. Contra un `pg_dump` local de PostgreSQL de pruebas con
  todas las migraciones: 0 faltantes; quitando 1 columna y 1 restricción: las 2 detectadas. La copia local del volcado
  está vieja (no se puede traer del servidor): ahí R1 falla, como debe; en el servidor corre con el regenerado.
  Mutaciones 6/6; regresión 85 Python + 37 PHP.
- **Instalado p121 (`7f9c636`, 25-nov 01:36 UTC):** volcado regenerado, 30 tablas (igual que la base), 1.851 → 1.858
  líneas; las 6 columnas con su tipo y default; `schema_sync_test` en TODO OK en el servidor.

### C6-07 · Comparación controlada SL/TP fijo vs automático (P2) — **Sugerencia (validación, no defecto)** · Herramienta en p119
- **Servidor (lectura 24-nov 23:57 UTC):** nadie usó todavía el modo automático: 72 búsquedas `fixed`, 14 configs de
  Paper/Real con SL y TP fijos, 15 backtests guardados fijos; el interruptor general `SLTP_AUTO_ENABLED` encendido.
- **Código:** la búsqueda «Los dos y comparar» (`sample_configs`, `sltp='both'`) sortea una config fija y otra
  automática **distintas** (cambian también filtros, trailing, duración): es una competencia, como dice su ayuda («gana
  el que mejor rinda»), no una comparación controlada (informe: mismas reglas de entrada y filtros). No es defecto: es
  lo aprobado en D-45.
- **Decisión (24-nov, ejemplo de una config probada dos veces):** «Comparar mis 14 configs». Sin cambios de pantallas.
- **Herramienta (p119):** `tools/analysis/compare_levels.py`: por cada config de `paper_strategy_configs` (todas, o
  `--configs`), un backtest con la config tal cual (SL/TP fijo explícito) y otro idéntico con SL = k × ATR(14)
  [mín, máx], TP = m × el SL y break-even en veces el SL (los de D-45; otros con `--sl-atr-mult`, `--tp-r-mult`, …).
  Mismo periodo que la pantalla (D-58: 24 meses completos), las velas se cargan **una vez** por config con el mismo
  camino que `/backtest/run` y cada variante corre con el mismo `_simulate` sobre su copia. Métricas del informe por
  config y variante: retorno neto, profit factor, caída máxima, operaciones, % ganadas, ganancia media (USDT y %), meses
  positivos / peor / mejor mes, duración media y motivos de salida; resumen de quién gana por métrica y por moneda;
  `--json-out` con todo (huella de parámetros). Solo lee la base (transacción de solo lectura), corre en un proceso
  aparte con prioridad mínima (`low_priority`, como la búsqueda) y de a una config; con el interruptor apagado no compara.
- **Prueba:** `compare_levels_test.py` (nueva: P1 las dos pruebas solo difieren en el SL/TP, aunque la config ya tuviera
  niveles; P2 multiplicadores; P3 métricas; P4–P5 quién gana y resumen; P6 una config que falla no frena las demás,
  periodo D-58, interruptor; P7 backtest real sobre velas sintéticas: «fijo» = el backtest de la config tal cual, «auto»
  SL por ATR dentro de los topes, velas sin pisarse; S solo lectura y baja prioridad); mutaciones 9/10 (la décima, «sin
  copia de las velas», es equivalente hoy: `_simulate` no modifica las velas; la copia se deja por seguridad);
  regresión 84 Python + 36 PHP en TODO OK.
- **Resultado (servidor, 25-nov; 15 configs, 2024-11-01 → 2026-10-31; automático SL 2×ATR [0,8–5 %], TP 2× el SL, BE
  1× el SL):** retorno: gana el fijo en 12, el automático en 3; profit factor: fijo 11, automático 4; caída máxima:
  automático 9, fijo 6. Por moneda, el fijo gana en 10 de 11 (solo PEPE al revés). Con automático dos configs pasan a
  perder (ENA #67 +21,7 → −7,0 %; SUI #72 +6,1 → −10,4 %). El automático gana en las tres métricas en LINK #64
  (0,1 → 4,2 %), PEPE #69 (7,9 → 16,6 %) y SUI #79 (20,4 → 26,9 %). Sesgo a favor del fijo: las configs salieron de
  búsquedas con SL/TP fijo y el automático va con los valores por defecto; una comparación pareja es una búsqueda
  «Automáticos».
- **Decisión (25-nov):** «Automático en PEPE, SUI y LINK»: solo esas 3; el resto sigue fijo. Se cambia con el camino de
  siempre (editar el backtest de la config: SL «Automático», TP «veces el SL», Guardar → StrategyConfigSync), sin
  datafix; la config es la misma para Paper y Real (#64 y #69 están activas en la cuenta 11, demo). Vuelta atrás: volver
  a «Fijo» en el backtest (D-49 nivel 1).

### C6-05 · Lotes comprimidos solapados en TimescaleDB (P2) — **Defecto confirmado (está ocurriendo)** · Instalado en p117 (`c3946eb`) y p118 (`373c3ef`)
- **Antecedente:** el 28-oct una recompresión dejó lotes solapados (50 fragmentos reescritos; `detect.sql`, que crea una
  tabla temporal). El motor ordena y avisa `[BARS]` (`bars_frame`). Faltaba la revisión automática (BITACORA 28-oct).
- **Servidor (lecturas 24-nov 20:38–20:45 UTC, solo lectura):** compresión `segmentby` broker, symbol, interval;
  `orderby` time DESC; 127 fragmentos comprimidos; revisión completa en 0,53 s. Agrupando solo por moneda y
  temporalidad salían 4.341 falsos solapes (en la base hay velas viejas de otro broker); por la serie completa, **12
  series reales** en 2 fragmentos comprimidos **después** del arreglo de octubre: `_hyper_1_123_chunk` (8-oct: BNB, BTC,
  ETH, SOL 1m, 8–10 lotes) y `_hyper_1_124_chunk` (15-oct: los mismos en 1m y 5m). `engine.log`: **64 `[BARS]` desde hoy
  14:47 UTC** (SOL/1 y BNB/1, 1.008.000 velas: lecturas de 2 años de 1m) — el motor las ordenó; en la lectura de C5-13
  (mañana del 24-nov) eran 0.
- **Decisión (24-nov):** parte 1, revisión automática solo lectura («Procede»); parte 2, reparar los 2 fragmentos en un
  parche aparte con respaldo y verificación («Sí, en un parche aparte»).
- **Parte 1 (p117):** `database/sql/ohlcv_overlap_batches.sql` (por serie completa, `max` de los lotes anteriores ≥
  mínimo del lote) y `ohlcv:overlap-check` (transacción de solo lectura; aviso `ohlcv-overlap` con fragmento, moneda,
  temporalidad y lotes; se cierra solo al quedar en 0; si falla, no toca el aviso; nunca repara), cada 3 h a los :10 UTC
  (tras la compresión de 05:38 / 17:38).
- **Prueba:** `ohlcv_overlap_check_test.py` (nueva: la consulta real contra PostgreSQL de pruebas sobre una tabla que
  imita un fragmento comprimido: sin solapes, parcial, otro broker y otra temporalidad sin falsos positivos, contenido,
  tras reparar un hueco, varios, borde exacto) y `ohlcv_overlap_command_test.php` (nueva); mutaciones 10/10 (K5 se
  reforzó: un aviso comentado pasaba); regresión 82 Python + 36 PHP en TODO OK.
- **Instalado p117 (`c3946eb`, 24-nov 23:20 UTC):** la primera revisión encontró exactamente las 12 series de la lectura
  (`_hyper_1_123_chunk`: BNB 10, BTC 8, ETH 9, SOL 10 lotes en 1m; `_hyper_1_124_chunk`: BNB 8, BTC 9, ETH 9, SOL 10 en 1m
  y 1 en 5m) y abrió el aviso.
- **Parte 2 (p118):** `ops/ohlcv_rewrite_chunk.sh <fragmento>` (reutilizable cuando vuelva a pasar): 1) comprueba que es un
  fragmento comprimido de `ohlcv_data`; 2) respalda todas sus velas (`/root/patches/ohlcv_rewrite/…csv.gz`, verificado);
  3) `database/sql/ohlcv_rewrite_chunk.sql`: en UNA transacción (`lock_timeout` 5 s), antes de tocar exige el mismo número
  de velas que el respaldo y ninguna repetida; `decompress_chunk` + `compress_chunk`; confirma solo si el número y el md5 de
  todas las filas son iguales antes y después; si no, se deshace sola. El instalador solo repara los fragmentos aprobados
  que sigan avisados, sin búsquedas en curso, sin la compresión corriendo y lejos de 05:38 / 17:38 UTC; al final vuelve a
  correr la revisión (el aviso debe cerrarse). Mismo método que el arreglo del 28-oct (50 fragmentos), ahora con respaldo
  y verificación.
- **Prueba p118:** `ohlcv_rewrite_chunk_test.py` (nueva: el SQL tal cual con psql contra PostgreSQL de pruebas, con
  `decompress_chunk`/`compress_chunk` imitados: sin cambios y filas reescritas → se confirma; vela perdida, precio
  cambiado, falla de la compresión → se deshace con las velas intactas; repetidas o cambio desde el respaldo → no toca);
  mutaciones 7/8 (la octava, «md5 sin `ORDER BY`», es equivalente en PostgreSQL 16: el plan ya ordena la entrada por el
  `count(DISTINCT …)`; se deja el `ORDER BY` para no depender del plan); regresión 83 Python + 36 PHP en TODO OK.
- **Instalado p118 (`373c3ef`, 24-nov 23:49 UTC):** `_hyper_1_123_chunk` 169.897 velas, reescrito en 10 s;
  `_hyper_1_124_chunk` 169.897 velas, 7 s; idénticas antes y después (número y md5); respaldos en
  `/root/patches/ohlcv_rewrite/`; la revisión dio «Sin lotes comprimidos solapados» y cerró el aviso.

### C6-02 · Estado del panel de riesgo coherente con el motor (P2) — **Defecto (pantalla)** · Instalado en p116 (`f9bcfe6`)
- **Código:** `RiskLimits::evaluate` devolvía `ok` («Opera normal») con una nota cuando faltaba el saldo base del mes,
  aunque el motor no abre (D-51). **Hallazgo propio, mismo tipo:** con una operación en estado dudoso el motor tampoco
  abre (D-50) y el panel también decía «Opera normal».
- **Fix («sí», 24-nov, tras un ejemplo; boceto mostrado):** estados `waiting_baseline` («Esperando saldo base · sin
  entradas nuevas») y `unresolved` («Operación sin confirmar · sin entradas nuevas», con su número y moneda), con estilo
  de advertencia y explicación (las abiertas se siguen gestionando; el motor reintenta cada minuto). Mismo orden que el
  motor: pausa → saldo base → operación dudosa → pérdida máxima → trades abiertos. Con la pérdida «sin límite» no se
  exige el saldo base (como el motor). La consulta de dudosas usa la regla del motor (3 min). Vuelve a «Opera normal»
  sola al resolverse. El motor no cambia.
- **Prueba:** `risk_limit_options_test.php` A13 (antes esperaba la nota bajo «ok»: cambia por la decisión), A13b–c,
  A16–A20b, B4b; código anterior 6 FALLOS; mutaciones 6/6 (una séptima, «no pasa la dudosa», sobrevivía: A20b);
  `execution_ledger_fairness_test` B1 ahora aplica las migraciones del libro dentro de su transacción (no depende del
  estado de la base local); regresión 81 Python + 35 PHP en TODO OK.

### C6-01 · Equidad de la cola del libro de ejecuciones (P2) — **Defecto pequeño (latente)** · Instalado en p115 (`0cd5811`)
- **Código:** `execution_ledger.process_pending` tomaba las 20 pendientes más antiguas (`LIMIT limit * 10`, por id) y
  descartaba DESPUÉS las que esperaban su reintento (`RETRY_EVERY`, 10 min): con 20 o más esperando, una operación nueva
  no entraba nunca a la selección. El retraso tenía tope: a las 24 h del cierre una operación que no cuadra pasa a
  `mismatch` y sale de la cola (C5-01); mientras tanto, las nuevas sin comisiones ni funding separados. La gestión de
  posiciones nunca se frenaba (las excepciones del libro se capturan).
- **Servidor (lectura 24-nov 19:24 UTC):** 16 cerradas `ok`, 2 abiertas `open_ok`; 0 en cola. **Nunca ocurrió.**
- **Fix («Procede» 24-nov):** las que esperan se excluyen EN la consulta (`AND NOT (id = ANY($3::bigint[]))`,
  `LIMIT limit`); mismo ritmo (2 por ciclo, espera de 10 min), mismo orden por antigüedad entre las listas y la misma
  protección contra duplicados (`exec_id`); la memoria de esperas olvida lo vencido hace más de 2 días.
- **Prueba:** `execution_ledger_fairness_test.py` (nueva: F1 25 antiguas esperando + 1 nueva; F2 ritmo y orden; F3
  error y recuperación alternados; F4 excepción; F5 limpieza; B1 la consulta real en PostgreSQL de pruebas); código
  anterior 4 FALLOS; mutaciones 6/6 (una séptima, «no sale de la espera al recuperarse», sobrevivía: se reforzó F3);
  regresión 81 Python + 35 PHP en TODO OK.

### C6-03 · Circuit breaker ante operaciones dudosas (P1) — **Defecto pequeño (latente)** · Instalado en p114 (`7d5956e`, D-68)
- **Código:** `CircuitBreakerMaxLossJob` elegía las cuentas con `open` / `pending_close` y
  `check_max_loss_circuit_breaker` solo revisaba `open`: una operación `pending_open` vieja u `orphaned` viva en Bybit
  quedaba fuera de la segunda red mientras no se adoptara. La protegían el SL provisional de la orden (2 %, D-13), el
  bloqueo de entradas (D-50), la conciliación adelantada cada minuto y el aviso a los 15 min. Hallazgo aparte: si Bybit
  no da el precio al abrir, la orden sale sin SL provisional.
- **Servidor (lectura 24-nov 18:38 UTC):** 16 cerradas, 2 abiertas; 0 operaciones dudosas en la historia (0 adoptadas,
  0 huérfanas, 0 cierres recuperados); 0 errores del circuit breaker y de la conciliación en `engine.log`; los 3
  `protection_failed` son del caso R-17 (19-nov). **Nunca ocurrió.**
- **Fix (D-68, «Vigilar y cerrar si es segura» 24-nov):** el job elige también las cuentas con dudosas (misma regla de
  3 min de D-50); `RealTrader._circuit_breaker_unresolved`: por cada dudosa, la posición de Bybit; si es con certeza la
  suya (`identify_unresolved_position`: lado igual, tamaño ≤ pedido, sin otra operación viva en la moneda, no huérfana
  de cierre), la misma regla que las abiertas con la entrada de Bybit y su SL (o 2 % desde la entrada si no lo tiene):
  si pasa el tope (1,2 ×), cierre reduce-only del tamaño de Bybit, historial `circuit_breaker_unresolved_close` y aviso
  `max_loss_close` («operación sin confirmar»); la conciliación anota el cierre (C5-14). Sin certeza: nunca cierra;
  aviso `unresolved_unprotected` una vez. Error de Bybit = «no sé». Corre con el turno exclusivo de la cuenta.
- **Prueba:** `circuit_breaker_unresolved_test.py` (nueva, U1–U13b); código anterior 15 FALLOS; mutaciones 11/11 (una
  duodécima, «ignora el SL de Bybit», sobrevivía porque el SL de la prueba era el 2 %: se agregó U2c); regresión 80
  Python + 35 PHP en TODO OK.

## Resueltos del ciclo (instalados y verificados)

| ID | Fix | Instalado | Verificación |
|---|---|---|---|
| C6-04 | Fechas reales de cada tramo y período hasta el último día que cuenta | p122 `4f53e69` | búsqueda #205 con sus 3 fechas |
| C6-06 | Volcado del esquema al día + `schema_sync_test` (migraciones ⊆ volcado) | p121 `7f9c636` | 30 tablas; 6 columnas de D-66 presentes |
| C6-05 | Revisión automática cada 3 h de lotes solapados + reparación con respaldo de los 2 fragmentos de octubre | p117 `c3946eb`, p118 `373c3ef` | 339.794 velas idénticas; 0 solapes; aviso cerrado |
| C6-02 | El panel de riesgo dice «Esperando saldo base» / «Operación sin confirmar» como el motor | p116 `f9bcfe6` | 120 vistas compiladas y revisadas |
| C6-01 | La cola del libro de ejecuciones descarta en la consulta las que esperan reintento | p115 `0cd5811` | 16 cerradas `ok`, 2 abiertas `open_ok`; motor y tick sin errores |
| C6-03 | El circuit breaker también cubre las operaciones dudosas vivas; cierra solo con certeza, si no aviso máximo (D-68) | p114 `7d5956e` | 2 abiertas, 0 dudosas; tick Real y motor sin errores tras el reinicio |

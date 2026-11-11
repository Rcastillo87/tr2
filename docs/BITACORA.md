# Bitácora de cambios — TR2

> Registro cronológico de lo que cambió, por qué y cómo se verificó. Lo más reciente arriba.
> Incluye los cambios que **no viven en git** (configuración de la base, datos, servidor): sin esta bitácora se perderían.
> Horas en UTC salvo que se indique. Commits en `main` de `github.com/Rcastillo87/tr2`.

---

## ▶ Próxima sesión (empezar aquí)
**Lista vigente: `docs/PENDIENTES_AUDITORIA.md`.** Las tres rondas de auditoría están resueltas en código (estado de los 70 hallazgos en `docs/CERTIFICACION_AUDITORIA.md`).
1. **Respaldo de la base** fuera del VPS: confirmar que existe y que se puede restaurar.
2. **Paridad con datos reales:** `cd python-engine && venv/bin/python tools/analysis/compare_paper_vs_backtest.py --config <id>` sobre cada config activa de Paper con trades; registrar aquí (los trades anteriores al 05-nov tienen la hora de salida vieja).
3. **Fase 12:** el dueño elige opciones en `docs/FASE12_ESTADISTICA.md` (recomendado: drawdown flotante → tres tramos → costos en el tamaño → cartera → renombrar el walk forward).
4. **Infraestructura:** `trading2-horizon` como `User=tr2` (revisar qué de `storage/` y `bootstrap/cache` quedó con dueño root); revisión automática de lotes solapados tras `policy_compression` (`/root/patches/batches/detect.sql`); regenerar `database/schema/pgsql-schema.sql` (desactualizado).
5. **Pantallas (maqueta primero):** `cross` en la búsqueda (N-03), separación maestra/config/suscripción (CFG-06/07/09), funding en pantalla, «código desactualizado» en Paper; decidir si borrar una estrategia debe bloquearse como un backtest (cascada).
6. **Limpieza:** TP2–TP4 (REAL-05); reescribir `docs/01–03`; slippage de altcoins en demo.
7. **Seguridad:** sin cambios (los `.env` 664 dentro de `/home/tr2` 770; no poner 600).
- **Tarea manual del dueño:** reemplazar las instrucciones del proyecto "Ruben Castillo" en claude.ai por `docs/PROMPT_MAESTRO.md` (**V7.3**, 10-nov). No se puede hacer por script.

---

## 2026-11-10 (Bogotá) — RQ-01: gestión de configuraciones y diagnóstico de Paper

### Validación del requerimiento contra el código (`a0fa1a3`)
- **RQ-01.1** (configs Paper bajo cada estrategia): parcial. Hay fila desplegable con métricas, por backtest y solo activas. Falta Trades/mes (`avg_monthly_trades` existe pero ningún código la llena), el enlace al backtest exacto y los conteos Paper.
- **RQ-01.2** (estado «migrada» en la búsqueda): parcial. `results.created.<fila>` + «✓ Creado #id» + índice único `backtests.hash`. Falta el enlace, reconciliar al borrar el backtest (hoy queda «Creado» y bloqueada) y la guarda en el servidor.
- **RQ-01.3** (origen del backtest): no existe.
- **RQ-01.4** (listado global): no existe (`backtesting/index.blade.php` es una vista sin uso).
- **RQ-01.5** (diagnóstico de Paper): el motivo por config ya se calculaba en cada tick, pero solo llegaba como texto a `laravel.log`.
- **RQ-01.6** (protecciones por broker fuera de Paper/Real): **cumple**. Los límites por cuenta viven en `broker_accounts` y solo los lee Real al abrir (`broker_limits_scope_test.py`).
- **RQ-01.7** (ciclo de vida): **cumple** (CFG-01 a 05, p34, p40b); las referencias de búsqueda al borrar entran con RQ-01.2.
- Supuestos (sin respuesta pendiente): RQ-01.6 = límites por cuenta; RQ-01.4 = una fila por backtest guardado con su estado en Paper.

### RQ-01.5 — Diagnóstico de Paper persistido (p48)
- Cada config termina el tick con un motivo normalizado (14 códigos, ver `02_TECHNICAL` §11) y el mismo texto de siempre para Laravel. La única excepción: «sin senal» ahora dice qué filtro la anuló (`filter_blocked`).
- `compute_signals` anota, solo si se le pide, la señal de la última vela tras la estrategia y cada filtro, sin cambiar el resultado. Una estrategia con `compute_signals` propio deja la traza vacía y no se rompe.
- Tablas `paper_eval_state` (última decisión por config) y `paper_eval_log` (agrupado por config, vela y motivo, con la cantidad de evaluaciones; 30 días). En H4 son unas pocas filas por config al día, no una por minuto. Un fallo del registro solo deja un aviso.
- **Prueba:** `paper_eval_test.py` (22 casos): cada motivo, el filtro que bloquea, la agrupación, el fallo del registro, `compute_signals` idéntico con y sin traza, y **los mismos 16 trades con y sin registro** en 150 velas × 3 ticks. Con el código anterior se corta (no hay registro). Mutaciones: no registrar (corta), fallo del registro que corta el tick (corta), una fila por tick (2 fallos). La mutación «culpar al primer filtro en 0» resultó equivalente y se simplificó `blocking_filter`.
- Falta la pantalla (con maqueta).
- Instalación de p47 el 10-nov (informe de resultados del 3.er ciclo, solo documentación): `main` = `21b8a66`.
- Instalación de p48 el 10-nov: `main` = `06f1212`. A las 22:28 UTC `paper_eval_state` ya tenía las 11 configs activas: 9 `no_signal`, 2 `regime_blocked` (#61 BTC, #69 PEPE).

### RQ-01.1 — Trades/mes de cada config Paper (p49)
- **Antes:** `avg_monthly_trades` existía, pero ningún código la llenaba: la columna estaba vacía en todas las configs.
- **Cambio:** el backtest guarda por moneda los trades que cerró la estrategia (`metrics.trades_by_symbol`) y cuántos cerró el final del rango (`closed_at_end`). `saveBacktest` los descarta si no cuadran con `total_trades` firmado (`consistentTradeCounts`). Al crear o llenar la config, `tradesPerMonth()` divide los trades de **esa moneda** por el rango real (`end_date − start_date`, días / 30,4375; si faltan fechas, `audited_months`). Con menos de medio mes o datos inválidos queda NULL (N/D), nunca 0 inventado.
- **Por qué por moneda:** en un backtest de 3 monedas, el total ÷ meses daría a cada config el triple de su frecuencia real.
- **Datos existentes:** el instalador llena las configs cuyo backtest es de **una** moneda (total − cierre forzado, si se conoce, ÷ meses del rango). Las multimoneda guardadas antes de p49 quedan N/D hasta que se vuelva a guardar su backtest: no hay forma honesta de repartir el total.
- **Prueba:** `trades_per_month_test.php` (15 casos). Con el código anterior: 11 fallos. Mutaciones (todas detectadas): total del backtest con cualquier cantidad de monedas, sin descontar el cierre forzado, meses pedidos en vez del rango real, aceptar conteos que no suman el total.
- Falta en pantalla: la columna Trades/mes en la fila de configs, con maqueta.
- Instalación de p49 el 10-nov: `main` = `10f4f61`. Trades/mes con valor: 0/15 → **15/15** (todas las configs vienen de backtests de una moneda).

### RQ-01.3 — Origen de cada backtest (p50)
- **Antes:** nada distinguía un backtest guardado a mano de uno creado desde una búsqueda; el único rastro era `results.created` dentro de la búsqueda, y se pierde si la búsqueda se borra.
- **Cambio:** `backtests.origin` (`manual` | `search`, CHECK en la base) y `origin_meta` (foto de la búsqueda: id, fila, foco, modo, monedas elegidas, fecha de la búsqueda y de la creación; sin FK). Se fija **solo al crear**; un re-test no lo cambia. El origen «search» llega por un atributo interno de la petición que pone `BacktestFromSearch`, no por un campo del formulario: el navegador no puede declararlo. `App\Support\BacktestOrigin` es la única fuente (validación de la foto y texto de pantalla).
- **Datos existentes:** la migración recupera como `search` (marcados `recovered`) los backtests que «Crear en historial» dejó en `results.created` con estado `done`; si uno figura en varias búsquedas gana la creación más antigua. El resto queda NULL = «Origen no registrado»: no se inventa «manual».
- **Orden de instalación:** la migración corre **antes** de aplicar el código (columnas nulas: el código anterior las ignora), para que ningún guardado falle entre la aplicación y el final del instalador. Se agregó la clave `pre` al generador de instaladores.
- **Prueba:** `backtest_origin_test.php` (14 casos; 5 fallos con el código anterior; mutaciones detectadas: run_id como texto, foto sin filtrar claves, origen reescrito en cada guardado, origen leído del formulario) y `backtest_origin_save_test.php` (integración por el `saveBacktest` real, transacción revertida: manual, intento del navegador, búsqueda, re-test en ambos sentidos, CHECK de la base, recuperados que coinciden con su búsqueda). Migración probada en PostgreSQL 16 local: dos corridas (idempotente), recuperación con duplicados y datos basura, `down`.
- Falta en pantalla la línea de origen, con maqueta.
- Instalación de p50 el 11-nov: `main` = `5ca81c7`. De 28 backtests, **27 recuperados** como creados desde búsquedas (coinciden con `results.created`); 1 queda «Origen no registrado». Integración: 7 PASS.

### RQ-01.2 — «Crear en historial» sin estados falsos ni duplicados (p51)
- **Antes:** `results.created` se leía tal cual. Si se borraba el backtest, la fila seguía en «✓ Creado #id» y no se podía volver a crear; si el job moría, la fila quedaba en «Creando…» para siempre. El servidor no revisaba si la fila ya estaba creada o en curso: un doble clic, otra pestaña o una llamada directa encolaba otra creación.
- **Cambio:** la lectura se concilia con la base (`createdStates()`): backtest borrado → `deleted` (disponible); en curso por más de 5 h → `error` (disponible). `create()` bloquea la búsqueda, rechaza con 409 lo ya creado o en curso, y reserva las filas con un token antes de encolar; el job solo crea las filas reservadas con su token (o sin reserva, para los jobs encolados antes de p51) y libera las suyas si muere. Un solo lugar escribe `results.created` (`markCreated`). `token` es una propiedad no promovida con valor por defecto: un job serializado antes de p51 se lee con `token = null`.
- **Pantalla:** sin cambios de Blade. «deleted» no muestra insignia y la fila se puede elegir; la reserva se ve como «Creando…» y mantiene el refresco; un rechazo llega como mensaje de error. La insignia «backtest borrado» queda para la maqueta.
- **Prueba:** `search_create_rules_test.php` (16 casos; 7 fallos con el código anterior; mutaciones detectadas: no mirar si el backtest existe, en curso sin límite de tiempo, sin bloqueo de la búsqueda, job que no salta filas ajenas, done que no bloquea) y `search_create_guard_test.php` (integración por `results()`, `create()` y el job reales, cola falsa y creador doble, transacción revertida).
- Instalación de p51 el 11-nov: `main` = `5c5ab53`. Integración 9 PASS. 1 fila «creada» cuyo backtest ya no existía volvió a quedar disponible.
- Maquetas de pantalla RQ-01 (Trades/mes, origen, insignias de búsqueda, backtests guardados, diagnóstico de Paper) presentadas al dueño el 11-nov y aprobadas («procede, no cambies mucho el diseño»). Se implementan en 3 parches, sin tocar el estilo existente: p52 (pantallas existentes), p53 (backtests guardados), p54 (diagnóstico de Paper).

### Pantallas RQ-01, parte 1: pantallas existentes (p52)
- **Estrategias** (fila desplegada de cada backtest en Paper): se agregan al final de la misma línea Trades/mes (por moneda si el backtest tiene varias; N/D con explicación al pasar el cursor), abiertos · cerrados de Paper y el enlace «Backtest #id ↗» a `history#bt-<id>`. Los conteos salen de UNA consulta agregada (`count(*) FILTER`, índice `paper_trades_config_status_index`).
- **Historial:** cada tarjeta lleva `id="bt-<id>"` (la tarjeta enlazada se resalta con `:target`), el número de backtest, una línea «Origen» (`BacktestOrigin::describe`; enlace a la búsqueda solo si existe y el usuario puede verla) y Trades/mes como 6.ª columna de parámetros, calculado con `StrategyConfigSync::tradesPerMonth` (la misma regla que las configs).
- **Búsqueda:** una sola función de insignia para las dos vistas de resultados: «✓ Creado #id ↗» enlaza al historial; «Backtest #id borrado · disponible» (ámbar); «En cola…» para la reserva; «✗ No se creó · reintentar».
- **Prueba:** `rq01_screens_static_test.php` (7 casos, 7 fallos con el código anterior; regresión) y `rq01_screens_test.php` (integración: renderiza las 3 vistas con la base real y backtests de prueba de cada origen, transacción revertida; la primera corrida de p52 se revirtió porque la prueba no compartía `$errors` con las vistas como hace el middleware web: era la prueba, no la pantalla; la segunda, porque la prueba cortaba cada tarjeta en su propio atributo `class` y la dejaba vacía: también de la prueba). El JS de la búsqueda se verificó con `node --check` y la insignia con 9 casos en node.

## 2026-11-09 (Bogotá) — Auditoría del 07-nov: validación y fixes (3.er ciclo)

### Resumen para el dueño
- **Informe:** `TR2_Actualizacion_Auditoria_Con_Hallazgos_Originales_2026-11-07` + matriz CSV. Recupera los textos de REAL-05 y CFG-01, 02, 06–09 y agrega N-01 a N-16.
- **Validación contra el código (`1e867d5`):** todos los hallazgos son reales, con estas precisiones: **N-04** no habilita ni bloquea nada (`passed` solo llega a la celda «Aprobado» del Excel), así que baja a P3; **N-13** se cierra por análisis (el SL/TP se recalcula con el precio de ejecución: el riesgo real = riesgo × precio real ÷ precio estimado, un desvío del tamaño del slippage); **N-09** es más grave de lo que dice el informe: `display_name` = estrategia + símbolo + intervalo, y dos backtests de la misma combinación comparten nombre.
- **Diagnóstico en producción (solo lectura, 09-nov 14:19 UTC):** 0 cierres Real sin PnL; 0 `pending_open`; 2 trades Real (1 abierto, 1 cerrado); 1 cuenta (11, demo, activa); **nombre repetido: «VWAP Tendencia — ETHUSDT H4» = #68 (activa) y #62**; 0 trades Paper sin config; flags siempre booleanos (15 configs); 0 trades Paper abiertos; servidor, base y motor en UTC; `INTERNAL_API_KEY` con valor en `python-engine/.env`.

### N-05 — Cierre Real sin liquidación (p33)
- **Antes:** si `close_trade()` encontraba la posición ya cerrada en Bybit (SL/TP nativo, liquidación o cierre manual entre el monitor y la orden), marcaba `closed` con `exit_reason='reconciled'`, sin precio, PnL ni comisión, con la hora del proceso y sin exigir el estado abierto. El límite mensual toma ese PnL nulo como 0.
- **Ahora:** se liquida con el closed-pnl de Bybit desde la apertura (`settle_exchange_close`: precio, PnL neto, comisión = bruto − neto, hora de Bybit; motivo deducido del precio). Si Bybit todavía no lo indexó, **no se cierra sin cifras**: devuelve `False`, queda en la auditoría (`close_unconfirmed` / `pnl_pending`) y el próximo ciclo o la reconciliación lo liquidan. Todos los llamadores ya tratan `False` como «reintentar» (la señal opuesta no abre la reversa).
- `epoch_ms()` compartido entre `real_trader` y `/real/reconcile` (antes había una copia local).
- **Prueba:** `real_close_settle_test.py` (18 casos). Con el código anterior: **12 FALLOS**. Mutaciones: motivo del llamador (2 fallos), «sin closed-pnl devuelve True» (1 fallo).

### N-01 — `pending_open` fuera de la reconciliación (p34)
- **Antes:** `RealTradingReconcileJob` enviaba al motor las cuentas activas con suscripciones activas y, de las demás, solo las que tenían trades `open`/`pending_close`/`orphaned`. Una cuenta pausada (a mano o por el circuit breaker) o sin suscripciones, cuyo único trade quedara en `pending_open` por un reinicio a mitad de la apertura, nunca se reconciliaba. Si la orden se había llenado en Bybit, la posición quedaba solo con el SL/TP provisional y sin gestión.
- **Ahora:** una sola lista, `RealTrade::RECONCILE_STATUSES` (`pending_open`, `open`, `pending_close`, `orphaned`), que usa el selector. Al adoptarse, el trade pasa a `open` y el tick de la cuenta lo gestiona aunque la cuenta esté pausada.
- **Pruebas:** `real_reconcile_statuses_test.php` (PHP puro, en la regresión: 12 casos; **8 FALLOS** con el código anterior). `real_reconcile_selector_test.php` (Laravel + base real, en una transacción revertida, con `Http::fake`): corre en la instalación; incluye el control con el selector anterior.
- Instalación de p33 el 09-nov: regresión 44 en TODO OK; motor reiniciado, tick de Paper 200, 0 errores; `main` = `01fc216`.

### N-02 — Final sin velas de 1m en Paper (p35)
- **Antes:** el monitor solo trataba como hueco un minuto faltante **entre** velas presentes (BP-03). Si la serie de 1m se detenía, no había velas nuevas: `_minute_path` ni se llamaba (`if bars else []`) y el SL/TP del trade abierto no se evaluaba nunca, aunque las velas del intervalo sí siguieran llegando.
- **Ahora:** `_stale_minute_tail()`: cuando ya pudo cerrar una vela completa del intervalo después del último minuto evaluado, se consulta la última vela de 1m de la fuente. Si tiene más de `PAPER_MINUTE_GAP_WAIT_HOURS` (26 h), el final [primer minuto sin evaluar, ahora) se cubre con las velas **cerradas** del intervalo y SL primero (la regla de BP-03 y del backtest sin 1m). El plazo se mide en la serie, no en el punto de control: una vez detenida, cada vela nueva se evalúa al cerrar, sin otra espera de 26 h. Con 1m solo atrasado (< 26 h) se espera en silencio; en el caso normal no hay consultas extra.
- **Prueba:** `minute_tail_test.py` (10 casos; **7 FALLOS** con el código anterior). Mutaciones: sin comprobar que la serie está detenida (1 fallo), plazo desde el punto de control (2), la cola también espera 26 h desde su inicio (1), consulta en cada tick (1). `minute_gap_test.py` (BP-03) sigue en TODO OK; su doble de base agrega `fetchval`.
- Instalación de p34 el 09-nov: regresión 45 en TODO OK; Horizon reiniciado (6 procesos); integración contra la base real: S1–S5 PASS (el selector anterior no enviaba la cuenta: reproduce N-01); `main` = `9adecbb`.

### N-07 — Tick, circuit breaker y reconciliación sobre la misma cuenta (p36)
- **Antes:** solo el tick tomaba el candado de la cuenta. El circuit breaker (cada minuto) y la reconciliación (cada 5 min) podían correr a la vez que el tick sobre los mismos trades: dos procesos enviando el cierre del mismo trade (el segundo, rechazado por Bybit al ser `reduceOnly`), o la reconciliación marcando `orphaned` un trade que el tick acababa de cerrar (sus UPDATE de estado eran `WHERE id = $1`, sin exigir el estado). Además, `close_trade` pasaba a `pending_close` sin comprobar que siguiera `open`.
- **Ahora:**
  - `_exclusive(account_id, espera, trabajo)`: un turno por cuenta para los tres. El tick se omite si la cuenta está ocupada (como antes); el circuit breaker espera hasta 15 s y la reconciliación hasta 20 s, por debajo de los timeouts HTTP de sus jobs (25 s y 90 s). Si se agota, la cuenta queda para el próximo ciclo, con aviso en el log. Cuentas distintas no se esperan entre sí.
  - El cierre se **reclama**: `open` → `pending_close` solo `AND status = 'open'`; si otro ya lo reclamó, no se envía orden. El registro final exige `pending_close`; los pasos a `orphaned` (monitor y reconciliación) exigen `open`/`pending_close` y el paso a `failed` de un huérfano exige `orphaned`.
  - Como un `pending_close` ya no se puede volver a reclamar, el monitor (que corre con el turno de la cuenta) devuelve a `open` un `pending_close` sin confirmar cuya posición sigue viva; así los reintentos siguen como antes.
- El candado es de memoria: vale porque el motor corre como **un solo proceso** (el instalador lo verifica en `ExecStart` y revierte si hay `--workers` > 1).
- **Prueba:** `real_concurrency_test.py` (16 casos, con tiempos reales; **12 FALLOS** con el código anterior). Mutaciones: circuit breaker sin turno (3 fallos), reclamo sin exigir `open` (1), monitor sin devolver a `open` (1), ignorar el reclamo fallido (1), tick que espera en vez de omitirse (1).
- Instalación de p35 el 09-nov: regresión 46 en TODO OK; motor reiniciado, tick de Paper 200, 0 errores; `main` = `1734f98`.

### N-06 + N-16 — Contabilidad y hora del cierre Real normal (p37)
- **Antes:** tras el Filled de la orden de cierre, la comisión se estimaba con la tasa taker (0,055 % de entrada y salida), el funding no se descontaba, `exit_time` era la hora del proceso y `pnl_pct` era el PnL **bruto** sobre el saldo previo (la pantalla mostraba el USDT neto al lado de un % bruto; Paper usa el neto).
- **Ahora:** se consulta el closed-pnl de esa orden (3 intentos, 2 s entre ellos): neto = `closedPnl` de Bybit (ya descuenta comisiones y funding), `commission` = bruto − neto, `exit_time` = hora del cierre en Bybit. Si no aparece: comisión estimada y `exit_time` = ejecución de la orden (`updatedTime`). `pnl_pct` = neto / saldo previo, también en el camino de posición ya cerrada. Las cifras salen de una sola función (`close_figures`); la auditoría `closed` dice de dónde salieron (`figures`) y, si Bybit informa `openFee`/`closeFee`, separa `fees` y `funding`.
- **Datos:** el único trade Real cerrado recalcula su `pnl_pct` con el neto (la instalación imprime antes y después).
- **Prueba:** `real_close_accounting_test.py` (13 casos; **11 FALLOS** con el código anterior). Mutaciones: `pnl_pct` bruto (3), hora del proceso (2), sin hora de la orden (1), un solo intento (2), funding sin separar (1).
- Instalación de p36 el 09-nov (modo reanudación: una corrida anterior se cortó): regresión 47 en TODO OK; motor en un solo proceso; reiniciado, tick de Paper 200, 0 errores; `main` = `bf4fce0`.

### N-09 — Identidad de configs por id, no por etiqueta (p38)
- **Antes:** la etiqueta «estrategia — símbolo intervalo» se usaba como identidad en tres lugares:
  - `StrategyConfigSync::renameReferences`, al renombrar una config, reasignaba los trades Paper abiertos `WHERE config = X OR strategy = etiqueta_vieja`. Con dos configs de la misma etiqueta (**hay una en producción: «VWAP Tendencia — ETHUSDT H4», #68 y #62**), el trade abierto de una pasaba a la otra; la primera quedaba «sin trade» y podía abrir otro.
  - `StrategyController::destroy` buscaba configs activas con `LIKE 'Nombre%'`: «VWAP» quedaba bloqueada por una variante activa de «VWAP Tendencia», y `%`/`_` del nombre eran comodines.
  - Los filtros de Paper usaban `LIKE 'Nombre%'` (sin separador): «VWAP» mostraba los trades de «VWAP Tendencia». Real ya usaba `' —%'`.
- **Ahora:** `renameReferences` reasigna por nombre solo trades de legado **sin** `paper_strategy_config_id`. `Strategy::hasActivePaper()` compara por el `strategy_id` del backtest (por la etiqueta exacta solo configs de legado sin backtest). `App\Support\StrategyLabel` arma la etiqueta (`compose`) y el patrón de filtro (`likePrefix`: nombre exacto + separador, con `% _ \` escapados), usado por los filtros de Paper y Real y por el borrado.
- El motor Paper ya indexaba sus configs por id (`config_map[cfg['id']]`); la documentación decía `display_name` y se corrigió.
- **Pruebas:** `strategy_label_test.php` (PHP puro, en la regresión: 16 casos; **10 FALLOS** con el código anterior). `strategy_identity_test.php` (Laravel + base real, transacción revertida): dos configs con la misma etiqueta y un trade de cada tipo, con el control del criterio anterior; y una estrategia cuyo nombre es prefijo de otra con config activa.
- Instalación de p37 el 09-nov: regresión 48 en TODO OK; motor reiniciado, tick de Paper 200, 0 errores; `pnl_pct` neto en los 2 trades Real cerrados (#85: −0,9956 → −1,0540; #86: −0,3285 → −0,4020); `main` = `7abfa89`.

### N-10 — Flags booleanos normalizados (p39)
- **Antes:** solo `allow_short`, `close_on_opposite` y `exit_on_opposite` pasaban por `as_flag`. `regime_filter`, `volume_filter`, `macro_trend_filter`, `hour_filter`, `weekend_filter` y `max_duration_profit` tomaban el valor crudo, y `btc_trend_filter` usaba `bool()`. Un `"false"` o `"0"` guardado como texto en los params activaba el filtro en Paper y Real (el backtest no, porque Pydantic convierte). El diagnóstico del 09-nov mostró que hoy todos están guardados como booleanos: es defensa.
- **Ahora:** los 7 flags pasan por `as_flag(valor, default)` en `BaseStrategy.__init__`. `tools/analysis/filter_audit.py` también (usaba `bool()`).
- **Prueba:** `flag_normalization_test.py` (33 casos: los 10 flags con textos falsos, verdaderos y null, más el efecto en los filtros horario, de fin de semana y de BTC; **21 FALLOS** con el código anterior). Mutaciones: un flag sin `as_flag` (4), `bool()` (2), default cambiado (1).
- Instalación de p38 el 09-nov: regresión 49 en TODO OK; Horizon reiniciado; integración contra la base real S1–S5 PASS (reproduce los dos casos con el criterio anterior); `main` = `387d646`.

### CFG-05 — Borrado seguro de un backtest (p40)
- **Antes:** `destroyBacktest` bloqueaba solo con config activa o con trades Real `open`/`pending_open`/`pending_close`, fuera de la transacción. No miraba trades Paper abiertos de configs ya detenidas (siguen gestionándose hasta cerrar) ni trades Real `orphaned` (su reconciliación necesita la config; FK `SET NULL`). No dejaba rastro del borrado.
- **Ahora:** `StrategyConfigSync::deleteBacktest()` (el controlador solo delega). Dentro de la transacción, con las configs bloqueadas, no borra si hay config activa, trade Paper abierto o trade Real en `RealTrade::RECONCILE_STATUSES` (la lista de p34, que incluye `orphaned`). Al borrar: pausa las suscripciones Real activas, deja una fila `deleted` por config en `strategy_config_changes` (fuente `backtest_delete`, parámetros en `old_params`) y borra. Las FK de esa tabla son `ON DELETE SET NULL` (consultado en producción el 09-nov): al borrar, la fila pierde `paper_strategy_config_id` y `backtest_id`; por eso la identidad de lo borrado va en `new_params.deleted` = `{config_id, backtest_id, display_name}`. Las 18 filas de historial que hoy no tienen config son borrados anteriores sin ese dato.
- **Visto de paso:** borrar una **estrategia** borra sus backtests en cascada (FK `ON DELETE CASCADE`) sin pasar por estas reglas; sus configs sobreviven con `backtest_id` nulo y sus trades siguen gestionándose. Queda documentado. La tabla de rutas de `02_TECHNICAL` y `03_AI_CONTEXT` lista un `PaperStrategyConfigController` que ya no existe: se corrige en el parche de documentación.
- **Pruebas:** `backtest_delete_rules_test.php` (PHP puro, en la regresión: 12 casos; **12 FALLOS** con el código anterior). `backtest_delete_test.php` (Laravel + base real, transacción revertida): trade Paper abierto, Real `orphaned` y config activa bloquean (con el control del criterio anterior); sin nada vivo borra, pausa suscripciones y audita.
- **Primer intento (p40) revertido por su propia prueba de integración:** la prueba buscaba la fila `deleted` por `paper_strategy_config_id`, que la FK `SET NULL` deja nulo al borrar. El instalador revirtió todo (`main` siguió en `bd904e9`). Corregido en **p40b** (lápida en `new_params`).
- Instalación de p39 el 09-nov: regresión 50 en TODO OK; motor reiniciado, tick de Paper 200, 0 errores; `main` = `bd904e9`.

### N-12, N-14, N-15 — Endurecimiento del motor (p41)
- **N-12 (antes):** el middleware de `main.py` comparaba `request.headers.get(...) != os.getenv('INTERNAL_API_KEY')`. Sin la variable y sin la cabecera daba `None == None` y el pedido pasaba. La exposición es baja (el motor solo escucha en 127.0.0.1), pero el criterio fallaba abierto. **Ahora:** `api/internal_auth.py` (`key_ok`, `hmac.compare_digest`); sin clave configurada, todo salvo `/health` recibe 503 y queda un CRITICAL al arrancar; con clave, cabecera ausente, vacía o distinta → 401. En producción la clave está definida (diagnóstico del 09-nov), así que no cambia nada en operación.
- **N-14 (antes):** `/collector/add-symbol` aceptaba cualquier texto como intervalo o símbolo y contaba `INSERT 0 0` (ya existía) como insertado. **Ahora:** intervalos de `request_rules.json` (la misma lista que el backtest y Laravel), sin repetir; símbolo normalizado a mayúsculas y `^[A-Z0-9]{2,20}$`; `inserted` = filas nuevas. Los errores son 400 con texto, que Laravel muestra tal cual.
- **N-15 (antes):** `/collector/backfill` e `/collector/invalidate` leían una fecha sin zona con la zona del proceso. El servidor está en UTC (diagnóstico del 09-nov), así que no había error en producción. **Ahora:** `utc_datetime()`: sin zona = UTC; con zona, convertida.
- **Visto de paso:** `/collector/invalidate` borra un rango de `ohlcv_data` (con `confirm=True`). Junto con la recarga, es la otra excepción a «el collector nunca borra»; entra en la decisión de N-11.
- **Entorno local:** se instaló `fastapi==0.115.0`, la versión del servidor (había 0.162 y la app no arrancaba con `add_event_handler`).
- **Prueba:** `engine_hardening_test.py` (18 casos, con la app completa vía `TestClient` y la zona del proceso en Bogotá; con el código anterior, 8 FALLOS y luego se corta porque `utc_datetime` no existe). Mutaciones: sin el 503 (2), vacío == vacío pasa (1), contar `INSERT 0 0` (1), fecha sin zona en la zona del proceso (2).
- Instalación de p40b el 10-nov: regresión 51 en TODO OK; Horizon reiniciado; integración contra la base real 10/10 PASS (incluye la lápida en `new_params`); `main` = `474c162`.

### N-04 — «Lista para Paper» con compuerta de calidad (p42)
- **Antes:** `ready_for_paper` = `passed` = solo métricas. Un backtest con slippage 0, comisión menor que la real, sin funding o con huecos en las velas principales podía salir «Aprobada». El efecto práctico era acotado: `passed`/`ready_for_paper` no habilita ni bloquea nada en la aplicación; solo se ve en la celda «Aprobada» del Excel exportado.
- **Ahora:** `data_quality_issues()` lista las condiciones **optimistas**: slippage 0, comisión < 0,055 % (taker de Bybit), funding no disponible y avisos de cobertura o huecos de las velas principales (`BacktestData.data_problems`). `evaluate_for_paper(metrics, calidad)` devuelve `passed` (métricas, sin cambios), `quality_ok`, `quality_reasons` y `ready_for_paper` = las dos. Los motivos de calidad van también en `pass_reasons` («Calidad: …»). El Excel muestra «Aprobada» con `ready_for_paper` (resultados anteriores: `passed`). Las condiciones pesimistas no bloquean.
- **Prueba:** `quality_gate_test.py` (15 casos: la función y `/backtest/run` completo con datos sintéticos; **13 FALLOS** con el código anterior). Mutaciones: `ready` ignora la calidad (1), sin revisar funding (3), sin pasar los huecos (3), comisión solo si es 0 (2).
- La sección de `/backtest/run` de `02_TECHNICAL` describe todavía un `WalkForwardValidator` que ya no se usa: se marcó como histórica y se reescribe en el parche de documentación.
- Instalación de p41 el 10-nov: regresión 52 en TODO OK; motor reiniciado, tick de Paper 200 (confirma que Laravel envía la clave interna), 0 errores; `main` = `b64b4ce`.

### Decisiones del dueño (10-nov)
- **N-03: (a)** corregir ya la atribución de los tramos, aparte de Fase 12.
- **N-11: (a)** el collector puede borrar solo en la recarga y la invalidación explícitas, con re-verificación y registro de lo borrado; el Prompt rector se actualiza en consecuencia.

### N-03 — Trades que cruzan el corte en/fuera de muestra (p43)
- **Antes:** `segment_stats` asignaba cada trade por `entry_time`: uno que abría antes del corte y cerraba después contaba **entero** en el tramo de elección, aunque su resultado dependiera de precios posteriores al corte. Además, la simulación es continua: el PnL del último tramo venía en USDT con el tamaño del saldo ya ganado (o perdido) en los primeros 2/3, y su retorno se dividía por el capital inicial.
- **Ahora:** en el tramo de elección cuentan los trades que abren **y cierran** antes del corte; los que cruzan no cuentan en ninguno y se informan en `cross` (en `seg_view` y `seg_sum`, que guarda la búsqueda). En el último tramo (`last=True`) cuentan todos los que abren en él, incluido el cierre `end_of_data`. El PnL de cada trade en los tramos es `pnl_pct × INITIAL`; PF y drawdown de los tramos salen de ese PnL. Las métricas del periodo completo (estrellas, `/backtest/run`) no cambian.
- **Efecto:** las búsquedas nuevas pueden aceptar o rechazar distinto en el borde; las guardadas no se recalculan. La pantalla de resultados no muestra `cross` todavía (cambiar la vista requiere tu autorización y un mockup).
- **Prueba:** `is_oos_attribution_test.py` (11 casos, incluidos los bordes «cierra justo en el corte» y «abre justo en el corte»; con el código anterior, **8 FALLOS** y se corta). Mutaciones: sin llevar al capital inicial (2), el último tramo también corta (4), el que cruza suma igual (3). `param_search_v3_test` sigue en TODO OK.
- Instalación de p42 el 10-nov: la salida recibida fue la de una segunda corrida («YA APLICADO»); verificado después: `main` = `origin/main` = `c193ee3`.

### N-11 — Cuándo y cómo borra el collector (p44, opción a)
- **Antes:** el Prompt rector decía «el collector nunca borra», pero había dos caminos que borraban velas: la recarga (sobrantes que Bybit ya no tiene, tras re-verificar) y `/collector/invalidate` (un rango, con `confirm=True`). La recarga borraba en lotes de 1.000 **confirmados uno por uno**: una cancelación a mitad dejaba la mitad borrada y el mensaje decía «no se eliminó nada». Ninguno dejaba registro de lo borrado.
- **Ahora:** una sola puerta, `collectors/deletion_log.delete_bars()`, con orígenes `reload` e `invalidate` únicamente. Lee las velas (o, con más de 50.000, su rango) y las borra con un `DELETE` simple, todo en **una transacción** junto con su registro en `ohlcv_deletions` (origen, motivo, cantidad, rango y las velas, para restaurarlas). Una cancelación o un error revierte todo. El mensaje de la recarga cortada dice lo que de verdad pasó. `ohlcv_data` es una hypertable comprimida: el diseño evita `DELETE … RETURNING` sobre chunks comprimidos.
- `/collector/invalidate` recibe las fechas como instantes UTC con zona: `ohlcv_data.time` es `timestamptz`. Corrige el comentario de p41, que la llamaba «timestamp» y pasaba la fecha sin zona.
- **Migración:** `database/sql-migrations/2026_11_10_01_ohlcv_deletions.up.sql` (idempotente; `.down.sql` la quita). La aplica el instalador antes de reiniciar el motor.
- **Prueba:** `collector_deletion_test.py` (14 casos, con la base en memoria de `collector_reload_test`, que ahora tiene transacción con rollback real). Con el código anterior, **6 FALLOS**: un corte en el 2.º lote dejó **1.200 de 1.500** velas borradas y sin registro. Mutaciones: sin transacción (2), sin registro (5), cualquier origen (1), guardar siempre las velas (1).
- Instalación de p43 el 10-nov: regresión 54 en TODO OK; motor reiniciado, tick de Paper 200, 0 errores; `main` = `352ca33`.

### N-08 — Tipos del JSON de la estrategia (p45)
- **Antes:** el JSON editado de la estrategia (`strategy_config_override`) solo se revisaba como JSON válido y se fusionaba (F-05). Un `"20"` en texto donde la estrategia espera un número, o un `"false"` en texto donde espera un booleano, llegaba tal cual al motor. La validación F-03 cubre solo los campos del formulario.
- **Ahora:** `BacktestPayload::configOverrideError(base, override)`, antes de `mergeConfig`. Cada clave que la estrategia ya tiene en su config guardada debe conservar el tipo, en profundidad (número finito, booleano, texto, lista con el tipo de su primer elemento, objeto), y el error nombra la ruta (`rsi.levels[1]`). Las claves nuevas se siguen aceptando (F-05: el código de la estrategia puede leer parámetros que no están en su config por defecto); `null` en la base admite cualquier valor.
- La instalación lista, solo como información, las estrategias que guardan números como texto en su config (el formulario los reenviaría como número y serían rechazados).
- **Prueba:** `strategy_config_types_test.php` (PHP puro, en la regresión: 14 casos; **14 FALLOS** con el código anterior). Mutaciones: sin revisar booleanos (2), aceptar números en texto (3), no bajar a objetos anidados (2). `config_merge_test.php` (F-05) sigue en TODO OK.
- Instalación de p44 el 10-nov: regresión 55 en TODO OK; migración `ohlcv_deletions` aplicada (12 columnas); motor reiniciado, tick de Paper 200, 0 errores; `main` = `c45cd42`.

### Cierre del ciclo y documentación (p46)
- **Resultado del 3.er ciclo (09–10 nov):** 16 hallazgos nuevos validados contra el código y en la base: 15 corregidos (p33–p45, uno por parche, cada uno con prueba antes/después, mutaciones y regresión) y N-13 cerrado por análisis. Las decisiones del dueño fueron N-03 (a) y N-11 (a). Un parche (p40) lo revirtió su propia prueba de integración y salió corregido como p40b. Regresión: de 43 (p32) a **56** (45 Python + 11 PHP), más 4 pruebas de integración contra la base real.
- **Documentación:** `CERTIFICACION_AUDITORIA.md` reescrita (70 hallazgos: los 54 originales clasificados, sin «falta el texto», + N-01 a N-16 con parche, commit y prueba); `PENDIENTES_AUDITORIA.md` pasa a ser la lista vigente; `PROMPT_MAESTRO.md` → **V7.3** (fuentes únicas nuevas, motor con 1 worker obligatorio, pruebas de integración en la instalación, lecciones); `FASE12` revisado; `README` (pruebas nuevas, regresión 45 + 11, documentos de auditoría, volcado del esquema desactualizado); `02_TECHNICAL` y `03_AI_CONTEXT` sin el `PaperStrategyConfigController` retirado.
- Instalación de p45 el 10-nov: regresión 56 en TODO OK; Horizon reiniciado (6 procesos); ninguna estrategia guarda números como texto en su config; `main` = `d22b684`.
- Instalación de p46 el 10-nov: regresión 56 en TODO OK; solo documentación, sin reinicios; `main` = `a0fa1a3`. Proyecto «Ruben Castillo» en claude.ai actualizado (certificación, pendientes, Fase 12, Prompt V7.3; V7.2 retirada).
- **Resultados para el auditor (p47):** `docs/RESULTADOS_CICLO_07NOV.md` (método, diagnóstico en producción, evidencia por hallazgo: fallos antes del fix, mutaciones, integración y commit instalado; desviaciones).

## 2026-11-09 (Bogotá) — /trading caía con error 500: `[]->firstWhere()` en la vista

### Resumen para el dueño
- **Síntoma (09-nov):** `GET /trading` → «Call to a member function firstWhere() on array» en `resources/views/trading/index.blade.php:229`.
- **Causa:** en las líneas 230 (trades abiertos) y 346 (trades cerrados) la etiqueta DEMO/REAL de la cuenta usaba `[]->firstWhere('id', $trade->broker_account_id)`, un método sobre un array literal, que es un error fatal en PHP 8. Lo dejó una edición anterior: el controlador conserva cuatro líneas vacías en el arreglo de la vista. Solo se ejecuta **dentro del bucle de trades de Real**: con 0 trades nunca falló (lectura del 05-nov: 0 trades de Real); con el primer trade de la cuenta 11 la página se cayó.
- **Corrección:** las dos líneas usan `$filterOptions['accounts']`, las cuentas del usuario (`id, label, account_type, broker`) que el controlador ya entrega y la vista ya usa en el filtro. **Sin cambio visual**: la etiqueta vuelve a mostrar el tipo real de la cuenta.
- **Prevención:** `tests/Forensic/blade_static_test.php` revisa **todas** las vistas (58) buscando métodos sobre `[]` o `null` literal, que `php -l` no detecta, y entra en la regresión.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `resources/views/trading/index.blade.php` (2 líneas); `tests/Forensic/blade_static_test.php` (nuevo) | La prueba nueva da 3 PASS; con la vista anterior, **2 FALLOS** (las dos líneas). Expresión regular comprobada: marca `[]->x(` y `null->x(`, no `null?->x(`. `view:cache` en la instalación. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p32** el 09-nov: regresión 43 en TODO OK; cachés de Laravel limpiadas como `tr2`; Horizon reiniciado; motor **no** reiniciado (sin cambios de Python). `main` subido (`cea6472..1e867d5`). El dueño confirmó que `/trading` carga con los trades de la cuenta 11.

---

## 2026-11-06 (Bogotá) — Cierre de la sesión de fixes: certificación para el auditor y opciones de la fase 12

### Resumen para el dueño
- **Fixes 1 a 11 de la auditoría del 05-nov: instalados** (p19 a p29). Regresión: 36 Python + 6 PHP en TODO OK en el servidor.
- **`docs/CERTIFICACION_AUDITORIA.md`:** los 54 hallazgos (49 de la 1.ª auditoría + 5 nuevos) con estado, parche, prueba y sección de la bitácora, para que el auditor los certifique uno por uno: 35 corregidos, 8 por diseño o documentados, 2 cerrados por datos, NUEVO-04/05 en la fase 12. **Faltan 7 textos** (REAL-05, CFG-01, 02, 06–09): no están transcritos en el repositorio; con su texto se verifican como el resto.
- **`docs/FASE12_ESTADISTICA.md`:** opciones con costo y efecto para holdout (NUEVO-04), cartera (NUEVO-05), walk forward, drawdown flotante y tamaño con costos. Orden recomendado: drawdown flotante → tres tramos → costos en el tamaño (toca Real) → cartera → renombrar el walk forward. **Nada se programa sin la elección del dueño.**
- **Pendiente del dueño:** la corrida del comparador (p28) sobre las configs activas de Paper; y la propuesta de Horizon sin root (`PENDIENTES_AUDITORIA.md`).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `docs/CERTIFICACION_AUDITORIA.md`, `docs/FASE12_ESTADISTICA.md` (nuevos); bitácora y pendientes al día | Solo documentación. Números de parche verificados contra la bitácora (donde no hay número registrado dice «ver bitácora»). Totales cuadran (54). Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p30** el 06-nov (solo documentación, 4 archivos; sin reinicios): regresión 42 en TODO OK; `main` subido (`291da9b..fcea3f5`). La actualización del resto de la documentación (README, `PROMPT_MAESTRO` V7.2, 01/02/03, «Próxima sesión») va en **p31**.
- Instalado con **p31** el 06-nov (solo documentación, 6 archivos): regresión 42 en TODO OK; `main` subido (`fcea3f5..cea6472`).
- Copias en el proyecto «Ruben Castillo» de claude.ai: `claude/PROMPT_MAESTRO_V7.2.md`, `claude/CERTIFICACION_AUDITORIA.md`, `claude/FASE12_ESTADISTICA.md`, `claude/PENDIENTES_AUDITORIA.md`. Las instrucciones del proyecto se reemplazan a mano por el contenido de `PROMPT_MAESTRO` V7.2.

---

## 2026-11-06 (Bogotá) — Formulario: JSON editado se fusiona (F-05); F-02 y F-04 cerrados (stepped sin pasos se rechaza)

### Resumen para el dueño
- **F-05 (auditoría del 05-nov).** El JSON de la estrategia editado en el formulario **reemplazaba** toda la configuración: una clave omitida se perdía. **Lectura (06-nov):** 0 de 28 backtests usaron JSON editado (ni parcial ni completo), así que el defecto existía pero nunca afectó nada.
  - **Ahora (el dueño eligió fusionar):** `BacktestPayload::mergeConfig()` fusiona el JSON sobre la config de la estrategia por **clave de primer nivel**. Lo omitido se conserva; una lista u objeto escrito se reemplaza entero (predecible). Un JSON inválido sigue rechazándose antes. El backtest guarda la config completa resultante.
- **F-02 (intervalo 30m).** El selector **no usa** la lista de etiquetas: muestra `CollectorConfig::activeIntervals()`, que hoy son 1, 5, 15, 60, 120, 240 y D. **30m no aparece**: cerrado por datos. Desde p27 un 30 enviado a mano se rechaza con un error claro. La etiqueta `'30' => '30m'` queda sin efecto.
- **F-04 (trailing escalonado).** El modo `stepped` necesita `trailing_steps` y **ninguna de las 6 estrategias los tiene**: agregarlo al selector crearía un modo que no hace nada. **Cerrado por diseño (decisión del dueño)**, con una regla en `request_rules.json` que aplican Laravel y Python: `stepped` sin pasos (en el payload o en el JSON) se rechaza con «El trailing escalonado necesita pasos (trailing_steps) en el JSON de la estrategia: sin pasos no hace nada.». Si un día se quiere usar, se diseña su editor de pasos con maqueta.
- **La vista no cambia.**

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `app/Services/BacktestPayload.php` (`mergeConfig()`, regla `requires_when`); `BacktestingController.php` (fusiona); `backtesting/request_rules.json` y `.py` (regla de pasos) | `tests/Forensic/config_merge_test.php` (8 casos: parcial conserva, clave nueva, lista y objeto se reemplazan enteros, completo = igual, sin config, el controlador fusiona, JSON inválido se rechaza antes) y `request_rules_test.py` (+5 casos: stepped sin pasos, con pasos en payload o JSON, listas vacías). Antes del cambio: **3 + 2 FALLOS**. 7 mutaciones detectadas (una tras agregar el caso de pasos vacíos en el JSON). Regresión en TODO OK |

### Cambios fuera de git
- **p29, primera corrida cortada** (06-nov ~20:46 UTC): el diff se aplicó pero el pegado no llegó completo; no corrieron las pruebas, los reinicios ni el commit (HEAD seguía en `56e80bc` con 8 archivos modificados; el PHP nuevo ya respondía en la web sin regresión). Se completó con el instalador regenerado en **modo «aplicado sin terminar»**: regresión 42 en TODO OK, cachés de Laravel como `tr2`, autoload OK, Horizon reiniciado (8 procesos), motor reiniciado, tick de Paper `200`, 0 errores en `engine.log`, `main` subido (`56e80bc..291da9b`).

### Lecciones (instalación)
- Un pegado largo puede llegar incompleto. El md5 protege lo que se **escribe**, pero una corrida puede cortarse **después** de aplicar. Los instaladores detectan ahora «aplicado sin terminar» (md5 final + HEAD todavía en el commit anterior): no reaplican ni pisan los respaldos y siguen con pruebas, reinicios y commit (probado en el simulador en los dos modos).
- La salida esperada se escribe sin bloque de código: un bloque parece un comando y llegó a pegarse en la terminal (sin efecto: «command not found»).

---

## 2026-11-06 (Bogotá) — Comparador Paper vs backtest rehecho: paridad de eventos por config (BP-06)

### Resumen para el dueño
- **Auditoría del 05-nov.** `tools/analysis/compare_paper_vs_backtest.py` no servía para certificar las configs actuales:
  - fechas por defecto invertidas (16-oct → 15-oct: rango vacío);
  - solo conocía clases viejas (falla con `DynamicStrategy`, que son todas);
  - no mandaba `strategy_code`;
  - `int('D')` se caía;
  - buscaba los trades de Paper por **nombre**;
  - comparaba el **PnL absoluto**, que no es comparable (Paper dimensiona con saldo fijo y el backtest con el acumulado);
  - no conocía `end_of_data`;
  - no comparaba la hora de salida.
- **Ahora (herramienta de línea de comandos, no la usa la pantalla):** `--config <id>`.
  - Usa los **parámetros congelados** del snapshot de los trades del rango (con `strategy_code`); si la config cambió dentro del rango, avisa.
  - Fechas por defecto: del primer trade de Paper a hoy.
  - Empareja por **(lado, vela de entrada)** y compara motivo, **hora exacta de salida** (tolerancia de 5 min solo en `time_exit`, que Paper ejecuta en el tick siguiente), Δ de precios (≤ 0,3 %) y **PnL %**.
  - Paper abierta frente a `end_of_data` = «abierta», no divergencia.
  - Código de salida 0/1/2 y `--json-out`.
- **Criterio acordado** (`PENDIENTES_AUDITORIA.md` §3.5): paridad de reglas y eventos, no de PnL.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `tools/analysis/compare_paper_vs_backtest.py` (reescrito, funciones puras + E/S separada) | `tests/Forensic/compare_tool_test.py`: 25 casos en PASS (emparejamiento por lado y vela, motivo y hora distintos, tolerancia de `time_exit`, abierta vs `end_of_data`, lados distintos no se emparejan, resumen, velas `D` y 240 alineadas a 00:00 UTC, payload con `strategy_code` y `strategy_config` del snapshot, fechas por defecto, cambio de snapshot, `main()` de punta a punta con códigos 0/1/2, sin PnL absoluto; **con salidas reales de Paper simulado y del motor: 34 de 34 iguales, 0 divergencias**). Antes del cambio: FALLA. 8 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p28** el 06-nov: regresión 41 en TODO OK; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log`; `main` subido (`8c1ac16..56e80bc`). La corrida del comparador sobre las configs reales queda pendiente del dueño (comando en la sesión; resultado a registrar aquí).

---

## 2026-11-06 (Bogotá) — Validación de los parámetros del backtest, mismas reglas en Laravel y Python (F-03)

### Resumen para el dueño
- **Auditoría del 05-nov.** Se aceptaban valores imposibles: riesgo, SL, TP, comisión o saldo negativos, y modos desconocidos. El controlador solo validaba el slippage y el trailing fijo mínimo; `BacktestRequest` no tenía rangos.
- **Criterio:** se rechaza lo **imposible** (precio ≤ 0, porcentajes fuera de rango, modos o intervalos que no existen), no lo imprudente. `be_pct = 99` («sin break-even», convención de la búsqueda) sigue siendo válido.
- **Lectura real (06-nov):** todos los valores guardados (configs Paper, 28 backtests, snapshots de trades, estrategias) caen dentro de los rangos; 0 con ADX lateral > tendencia. **Nada guardado se rechaza.**
- **Ahora:**
  - **Una sola fuente de reglas:** `python-engine/backtesting/request_rules.json` (rangos, enteros, opcionales, modos, intervalos del motor y la regla cruzada ADX lateral ≤ tendencia).
  - **Laravel** (`BacktestPayload::validate`, en el controlador antes de llamar a Python, para la pantalla y el backtest desde la búsqueda) devuelve el primer error en español, p. ej. «Riesgo por operación (%): debe ser mayor que 0 y menor o igual que 100 (recibido: -1).». Meses: entero entre 1 y 60.
  - **Python** (`BacktestRequest`, `model_validator`) aplica las mismas reglas como última defensa para cualquier llamador (422).
- **Parte de motor de F-02:** el intervalo 30 (que muestra la pantalla) ahora da un error claro en vez de convertirse en 60 sin aviso. Quitarlo de la vista queda para F-02, con maqueta.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `backtesting/request_rules.json` y `request_rules.py` (nuevos); `api/v1/backtest.py` (validador); `app/Services/BacktestPayload.php` (`validate()`); `BacktestingController.php` (valida cada payload y los meses) | `tests/Forensic/request_rules_test.py`: 50 casos en PASS. La **misma tabla** pasa por Python y por Laravel (`php`), con 44 casos de aceptar o rechazar en los límites, NaN, infinito, enteros, opcionales, modos, intervalo 30 y numérico, y ADX cruzado; mensaje exacto en español; **valores guardados en producción aceptados**; defaults válidos; el controlador valida antes de llamar a Python. Antes del cambio: **47 FALLOS**. 8 mutaciones detectadas (dos casos agregados tras mutaciones no detectadas: intervalo numérico y saldo infinito). Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p27** el 06-nov: regresión 40 en TODO OK; `php -l`; cachés de Laravel como `tr2`; autoload de `App\Services\BacktestPayload` OK; Horizon reiniciado con `systemctl` (6 procesos); motor reiniciado; tick de Paper `200`; 0 errores en `engine.log`; `main` subido (`e9951b2..8c1ac16`).

---

## 2026-11-06 (Bogotá) — Funding de Bybit al día en la reparación diaria y aviso si se atrasa (C-12)

### Resumen para el dueño
- **Auditoría (03-nov y 05-nov).** El funding de Bybit solo se descargaba a demanda (backtest y cierre de Paper). Lectura del 03-nov: atraso entre 9 h y **6 d 21 h** según la moneda. El backtest avisa en pantalla si falta; Paper solo deja log; Real no depende (usa `closedPnl` de Bybit).
- **Ahora (plan de §3.7, la opción más liviana):**
  - La reparación diaria de las 04:00 (`cli/collector_repair.py`, cola research) pone al día el funding de cada moneda activa del collector **desde lo ya cubierto** (`load_funding`, ~1 consulta por moneda), **antes** de la auditoría histórica. El resultado trae `funding`: por moneda, cobertura, atraso en horas y error.
  - Un fallo de Bybit o una excepción en una moneda se informa y no frena las demás ni la reparación.
  - Una moneda con más de **30 h** sin cubrir (`FUNDING_STALE_HOURS`) abre el aviso **«Funding atrasado: N moneda(s)»** en la campana (`SystemAlerts`, incidente `funding_stale`), que se **cierra solo** al ponerse al día. La simulación (`--dry-run`) y la validación sin reparación no tocan el aviso.
  - Paper sin cambios.
- **En la instalación:** una corrida del refresco deja las monedas activas al día.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `cli/collector_repair.py` (`refresh_funding()`, paso en `run()`, línea FUNDING en la salida); `app/Services/SystemAlerts.php` (incidente `funding_stale`) | `tests/Forensic/funding_refresh_test.py` (12 casos: desde `covered_to` hasta ahora, al día sin errores, fallo y excepción no frenan, atraso 165 h, sin cobertura desde 2024-06-01 y `lag None`, dry-run, `--solo`, integrado en `run()` **antes de la auditoría**, umbral 30 h) y `tests/Forensic/funding_alert_test.php` (7 casos: abre con monedas, horas, umbral y errores; «sin datos»; se resuelve; sin sección o simulación no toca; el resto no cambia). Antes del cambio: **1 + 4 FALLOS**. 8 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p26** el 06-nov: regresión 39 en TODO OK; `php -l`; cachés de Laravel como `tr2`; **Horizon reiniciado con `systemctl`** (7 procesos); corrida inicial del funding: **12 monedas, 0 errores, ninguna atrasada**; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log`; `main` subido (`247fd27..e9951b2`).

---

## 2026-11-06 (Bogotá) — Snapshot sin strategy_code: se usa el código de la config viva (BP-07)

### Resumen para el dueño
- **Auditoría del 05-nov.** Si el `config_snapshot` de un trade abierto no traía `strategy_code`, `build_strategy` fallaba:
  - **Paper** saltaba la posición en cada ciclo: **sin SL/TP**.
  - **Real** saltaba la gestión del bot (break-even, trailing, volatilidad, duración); el SL/TP de Bybit seguía activo.
- **Lectura real (06-nov):** 0 trades de Paper o Real con snapshot sin código, 0 sin snapshot, 0 configs sin código y 0 apariciones del error en todos los logs. **Riesgo teórico hoy.** El dueño eligió la defensa barata.
- **Ahora:**
  - Si al snapshot le falta el código (o está en blanco), se toma **solo el código** de la config viva (Paper: la config activa del trade; Real: la de la suscripción, nueva columna `live_strategy_code` en las dos consultas de trades abiertos).
  - Los parámetros siguen siendo los **congelados**, y queda un `WARNING` en `engine.log`.
  - Sin config viva, el error de siempre.
  - Un snapshot con código usa el suyo.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `trading/paper_trader.py` (`_trade_params`); `trading/real_trader.py` (`_trade_strategy`, `live_strategy_code`) | `tests/Forensic/snapshot_code_test.py`: 11 casos en PASS (Paper cierra por SL con los parámetros congelados, sin el slippage de la config viva; aviso; sin config viva igual que antes; snapshot con código usa el suyo; código en blanco = faltante; Real construye la estrategia con `sl_pct` congelado; aviso; sin código vivo, `None`; las dos consultas traen la columna). Antes del cambio: **8 FALLOS**. 6 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p25** el 06-nov: regresión 37 en TODO OK; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log`; `main` subido (`c2e29ca..247fd27`).

---

## 2026-11-06 (Bogotá) — Backtest: la hora de salida es la del evento (NUEVO-02)

### Resumen para el dueño
- **Auditoría del 05-nov.** Con 1m, una salida por SL/TP/trailing se guardaba con la **apertura de la vela grande** (en H4, un SL a las 03:47 quedaba a las 00:00), aunque el motor ya conocía el minuto (`m0`, que usaba para el funding). Desde p19 Paper guarda el minuto del evento, así que backtest y Paper tenían horas distintas para la misma salida.
- **Ahora:** `exit_time = inicio de exit_span`, la misma fuente que el funding:
  - con 1m, el minuto que disparó la salida;
  - salidas al cierre (tiempo máximo, volatilidad), el cierre de la vela (sin cambios);
  - sin 1m o con la vela incompleta (NUEVO-01), la apertura de la vela, momento desconocido, igual que Paper (sin cambios).
- El minuto del 1m venía **sin zona horaria**; ahora se guarda en UTC, como `entry_time` y el resto de las salidas.
- **Ninguna métrica cambia.** Solo el Sharpe usa `exit_time` (PnL por día UTC), y el minuto cae siempre en el día de su vela. Walk forward, desglose mensual y el corte 2/3 de la búsqueda usan `entry_time`. Cambia la hora que se muestra y se exporta, y el comparador (BP-06) puede comparar horas exactas.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `backtesting/engine.py` (`exit_time = exit_span[0]`, en UTC); `engine_speed_parity_test.py` (la referencia V3 guarda la vela: se acepta el minuto solo dentro de esa vela; **11.027 salidas** pasan al minuto); `minute_coverage_test.py` (TP por 1m en su minuto); `signal_reuse_test.py` (la paridad Paper vs motor ahora exige **la misma hora exacta**) | `tests/Forensic/exit_time_test.py`: 8 casos en PASS (SL y TP con 1m en su minuto, UTC, sin 1m y respaldo = apertura, salida al cierre = cierre, **métricas idénticas** a las calculadas con la hora de la vela, minuto dentro de su vela). Antes del cambio: **2 FALLOS** (los de 1m). 3 mutaciones detectadas (una cuarta resultó equivalente y se simplificó el código). Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p24** el 06-nov: regresión 36 en TODO OK; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log`; `main` subido (`2ebbbd2..c2e29ca`).

---

## 2026-11-06 (Bogotá) — La protección por volatilidad del JSON ya no se pisa con valores por defecto (F-01)

### Resumen para el dueño
- **Auditoría del 05-nov.** El formulario de Backtesting no tiene campos de volatilidad, pero `BacktestingController` mandaba **siempre** `volatility_protection_mode = null`, `×2.5` y `1.0 %`. Python toma como «enviado» todo lo que llega (`exclude_unset`), así que esos valores **pisaban el JSON de la estrategia**. Ese payload se guarda como `config_params` y con él se implementan las configs de Paper/Real, así que el defecto se propagaba.
- **La búsqueda imitaba el defecto a propósito:** `param_search.py` (`UI_FIXED`: «lo que la pantalla envía siempre») y `BacktestFromSearch` (`'none'`).
- **Lectura real (06-nov):** 0 de 6 estrategias con volatilidad en su JSON; 0 de 28 backtests guardados con el JSON pisado; 0 configs de Paper afectadas; 0 con volatilidad activa. **El defecto nunca afectó un resultado.**
- **Ahora:**
  - `App\Services\BacktestPayload::volatility()` manda la volatilidad **solo si vino en el request**; `'none'` = apagada explícita. Si no vino, manda el JSON.
  - La búsqueda (`UI_FIXED = {}`) y `BacktestFromSearch` dejan de forzarla: la pantalla, la búsqueda y el backtest lanzado desde la búsqueda la tratan igual.
- **Sin cambios visibles hoy**, porque ninguna estrategia la define. Si una la define en su JSON, se respeta en todos lados.
- **Instalación:** cambia PHP, así que se agregan `php -l`, cachés de Laravel limpiadas **como el dueño de `storage/`** (no root), verificación del autoload de la clase nueva y `horizon:terminate` (solo sin búsquedas activas) para que los workers carguen el código nuevo.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `app/Services/BacktestPayload.php` (nuevo); `BacktestingController.php` (sin defaults de volatilidad); `BacktestFromSearch.php` (sin `'none'`); `cli/param_search.py` (`UI_FIXED = {}`) | `tests/Forensic/backtest_payload_volatility_test.php` (10 casos: sin campos no se envía nada, `'none'` = null, valores enviados viajan, vacíos = no enviados, el controlador usa el servicio sin defaults, el formulario de la búsqueda no trae volatilidad) y `tests/Forensic/volatility_json_test.py` (6 casos: pantalla sin campos → JSON, `'none'` apaga, enviado pisa, sin JSON → apagada, **la búsqueda respeta el JSON**). Antes del cambio: **4 + 2 FALLOS**. 6 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p23** el 06-nov: regresión 35 en TODO OK; `php -l`; cachés de Laravel (config/route/view) limpiadas como `tr2`; autoload de `App\Services\BacktestPayload` OK; **Horizon NO se reinició**: `trading2-horizon` corre como **root** y `horizon:terminate` lanzado como `tr2` no pudo enviarle la señal, sin mostrar error (`ActiveEnterTimestamp` seguía en 03-nov 20:19). Se reinició a mano el 06-nov **18:45:22 UTC** con `systemctl restart trading2-horizon`, sin búsquedas activas (6 procesos). Mientras tanto, el único efecto posible fue que un backtest lanzado desde la búsqueda siguiera forzando `'none'`, sin impacto: ninguna estrategia usa volatilidad. Desde p25 el instalador usa `systemctl restart` y verifica que cambie la hora de arranque; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log`; `main` subido (`eec81a5..2ebbbd2`).

---

## 2026-11-06 (Bogotá) — Backtest: la posición abierta al final del rango se cierra con end_of_data (BP-04)

### Resumen para el dueño
- **Auditoría del 05-nov.** Si al terminar el rango quedaba una posición abierta, el motor calculaba las métricas sin ella: no aparecía en trades, balance ni métricas. Si iba perdiendo, el backtest y cada combinación de la búsqueda salían mejor de lo real. Reproducido: con el código anterior el trade desaparece (9 fallos de la prueba nueva). En la batería sintética de paridad del motor ocurre en **27 resultados**.
- **Ahora (opción a, elegida por el dueño):**
  - Se cierra al **cierre de la última vela**, con motivo `end_of_data`, slippage en contra, comisión y funding hasta ese cierre, como cualquier salida.
  - Cuenta en trades, balance, curva de capital y métricas. El resultado trae `closed_at_end`.
  - La pantalla avisa: «1 posición seguía abierta al final del rango: se cerró al último cierre (motivo end_of_data…)».
- **Búsqueda de parámetros:** usa el mismo motor, así que ahora también ve ese trade. Las búsquedas ya guardadas no cambian; las nuevas pueden diferir en el último trade de cada combinación.
- **Paper/Real:** no cambian. Ahí la posición sigue viva y la cierran sus reglas. Las pruebas de paridad Paper/Real vs motor comparan sin ese último trade del motor.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `backtesting/engine.py` (cierre `end_of_data`, `closed_at_end`); `api/v1/backtest.py` (aviso); `engine_speed_parity_test.py` (la referencia V3 congelada descarta la posición: se compara sin ese único último trade, con las métricas recalculadas, y se exige que aparezca); `paper_opposite_test.py` y `real_opposite_test.py` (paridad sin el `end_of_data` del motor) | `tests/Forensic/end_of_data_test.py`: 13 casos en PASS (long y short con slippage del lado correcto, `exit_time` = cierre de la última vela, comisión de entrada y salida, `bars_open`, métricas y equity, funding del tramo abierto, sin posición al final no cambia nada, entrada en la última vela, reversa + short abierto, aviso y trade en `/backtest/run`). Antes del cambio: **9 FALLOS**. Las 3 pruebas ajustadas pasan también con el código viejo. 7 mutaciones detectadas. Regresión en TODO OK, ahora con `param_search_v3_test` |

### Cambios fuera de git
- Instalado con **p22** el 06-nov: regresión 33 en TODO OK; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log` desde el reinicio; `main` subido (`fd21778..eec81a5`).

---

## 2026-11-05 (Bogotá) — Backtest: vela con minutos de 1m faltantes = vela completa con SL primero (NUEVO-01)

### Resumen para el dueño
- **Auditoría del 05-nov.** El backtest usa el 1m si cubre al menos el **98 %** del rango (`MIN_COMPLETENESS`). Dentro de ese rango, una vela grande a la que le faltaban minutos se evaluaba **solo con los minutos presentes**: un SL tocado en los que faltan no se veía. Reproducido: con el SL en los minutos faltantes el trade no cerraba, quedaba abierto hasta el final del histórico y desaparecía del resultado (eso es BP-04).
- **Historial:** el 98 % y la regla «no mezclar» vienen de `aea032b` (26-oct, «1m solo si cubre todo el rango»). El 98 % nació como umbral para **reportar** huecos. «No mezclar» evita dos criterios cuando el 1m empieza tarde, no trata un minuto suelto que falta.
- **Lectura real (05-nov), 24 meses:** 2 horas con 1m incompleto en total. HYPE tiene 1 (faltan 55 min); BNB tiene 1 (26 min, fuera del collector); las otras 11 monedas tienen 0.
- **Ahora (opción 1, elegida por el dueño):**
  - Una vela grande a la que le falta cualquier minuto se evalúa como **vela completa con SL primero**, igual que sin 1m y que Paper ante un hueco permanente (p20): backtest y Paper homologados.
  - El resto del rango sigue con 1m. El umbral del 98 % para usar o descartar el 1m entero no cambia.
  - La pantalla avisa: «Aviso: N vela(s) de X con minutos de 1m faltantes: evaluadas con vela completa y SL primero (pesimista)». El resultado trae `minute_fallback_bars`.
- **Costo:** ninguno. El motor ya calculaba los minutos de cada vela; es una comparación vectorial.
- **Efecto:** con los datos actuales solo cambia una vela de HYPE, y solo si en esa hora había una posición abierta. La búsqueda de parámetros usa el mismo motor (mismo resultado que un backtest de la pantalla).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `backtesting/engine.py` (`m_full` por vela, `minute_fallback_bars`); `api/v1/backtest.py` (aviso) | `tests/Forensic/minute_coverage_test.py`: 10 casos en PASS (1m completo sin cambios, SL en minutos faltantes, TP en los minutos con SL en la vela gana el SL, vela incompleta sin toque sigue, conteo solo del tramo operado incluida la vela sin minutos, sin 1m, **homologación con Paper**: mismo motivo, precio y hora; aviso en `/backtest/run`). Antes del cambio: **8 FALLOS**. 5 mutaciones detectadas. `engine_speed_parity_test` (referencia del motor V3) y `param_search_v3_test` en TODO OK. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p21** el 05-nov: regresión 31 en TODO OK; motor reiniciado; tick de Paper `200`; 0 errores en `engine.log` desde el reinicio; `main` subido (`dc0a5c8..fd21778`).

---

## 2026-11-05 (Bogotá) — Paper no salta un hueco dentro del 1m (BP-03)

### Resumen para el dueño
- **Qué decía la auditoría:** sin velas de 1m, Paper no evalúa SL/TP. **Verificado en el código:** sin 1m (o con el 1m atrasado) Paper **no pierde** los minutos. No avanza su punto de control y los evalúa en orden cuando el collector se pone al día, con el precio del nivel y la hora real (p19). Usar la vela grande en ese caso empeoraría la paridad, porque el backtest del mismo tramo sí tendrá el 1m.
- **El hueco real:** si al 1m le faltaban minutos **en medio**, la consulta `time > punto de control` traía los minutos siguientes y Paper **saltaba el hueco en silencio**. Un SL dentro del hueco se perdía para siempre, aunque la reparación lo llenara después (el punto de control ya había pasado).
- **Lectura real (05-nov):** 0 días con 1m incompleto en 30 días en las 11 monedas activas de Paper; 0 avisos «sin velas de 1m» en todos los logs. **Riesgo teórico hoy.** El 1m atrasado ya lo vigila el vigilante del collector (C-06) y los huecos la validación de las 04:00 (C-03/C-04).
- **Ahora (opción 1, elegida por el dueño):**
  - Paper evalúa solo los minutos **seguidos** desde su punto de control. Ante un hueco **se detiene antes**, deja `[ERROR]` en `engine.log` con el tramo faltante y espera la reparación; cuando se llena, sigue y evalúa esos minutos.
  - Si a las **26 h** (`PAPER_MINUTE_GAP_WAIT_HOURS`; ya pasó una reparación de las 04:00) el hueco sigue, lo cubre con las velas del intervalo operado **completas y SL primero**, la misma regla por sub-vela que el motor sin 1m. La salida queda con la hora de inicio de la vela, como el backtest.
  - Sin vela de respaldo, sigue esperando (nunca salta). Una guarda impide un bucle sin fin si el respaldo no avanzara.
- **Caso normal sin cambios:** sin hueco no hay consultas extra ni avisos. El hueco se detecta con los minutos que ya trae el monitor.
- **No cambia:** Real (su SL/TP vive en Bybit), el backtest (su caso es NUEVO-01, fix 3) y la regla de entradas.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `trading/paper_trader.py`: `split_at_minute_gap()`, `_minute_path()`, `_gap_candles()`; el monitor recorre esa ruta; `MINUTE_GAP_WAIT` desde `.env`; `python-engine/.env.example`; `tests/Forensic/paper_parity_test.py` (el arnés entrega 1m completo, sin huecos, como producción) | `tests/Forensic/minute_gap_test.py`: 18 casos en PASS (regla de corte, punto de control con segundos, hueco reciente: se detiene y avisa sin consultas extra, **hueco reparado con el SL adentro: cierra en ese minuto**, hueco permanente: SL con vela completa y hora de la vela, sin toque sigue, sin doble evaluación, sin vela de respaldo espera, dos huecos con plazos distintos, caso normal sin cambios, plazo 26 h). Antes del cambio: **15 FALLOS** (con el código viejo el SL del hueco reparado se pierde). `paper_parity_test` con el arnés nuevo: TODO OK antes y después (arnés fiel). 7 mutaciones detectadas (una destapó un bucle sin fin, ahora con guarda). Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p20** el 05-nov: regresión 30 en TODO OK; motor reiniciado; tick de Paper `POST /v1/paper/tick 200` con el código nuevo; 0 errores en `engine.log` desde el reinicio (verificación nueva, probada con un `[ERROR]` simulado); `main` subido (`a373996..dc0a5c8`).

---

## 2026-11-05 (Bogotá) — Señal ya operada como el motor y hora de salida del evento (NUEVO-03, BP-08, BP-05)

### Resumen para el dueño
- **Auditoría del 05-nov.** Paper y Real decidían si una señal ya se había usado con `entry_time >= apertura de la vela de la señal`. Esa regla venía de BP-02 (`c8d1223`), que solo trataba la salida por señal opuesta; no era un diseño deliberado (bitácora, «Próxima sesión» punto 8: sondas A y B). Dos divergencias con el motor:
  - **A:** trade abierto y cerrado por SL dentro de la misma vela, y esa vela cierra con señal nueva → el motor entra en el open siguiente; Paper/Real **no entraban**.
  - **B:** señal vieja de la misma dirección ignorada (había posición) y SL a mitad de la vela siguiente → el motor no la usa; Paper/Real **reabrían con la señal vieja**, a un precio que el backtest nunca usó. En Real era dinero.
- **Ahora (Paper y Real, mismo SQL):** la señal de la vela que cierra en T abre solo si en T no había posición y nadie entró desde T: `entry_time >= T OR exit_time >= T` bloquea. Las filas `error`/`failed` de Real (sin `exit_time`) solo cuentan por `entry_time`, como antes (una entrada fallida no reintenta la misma señal).
- **La regla depende de que `exit_time` sea la hora del evento:**
  - **Paper (BP-05):** antes guardaba la hora de proceso. Ahora guarda el minuto de 1m que tocó el SL/TP/trailing, el cierre de ese minuto en la protección por volatilidad, y **T** (cierre de la vela de la señal, como el motor) en la salida por señal opuesta, también para el funding. `time_exit` sigue con la hora de proceso.
  - **Real:** el cierre nativo de Bybit (SL/TP/trailing) guardaba la hora de detección del monitor. Ahora guarda el `updatedTime` del closed-pnl (el último tramo); sin hora, `now()` como antes. Las salidas por orden propia y la conciliación no cambian.
- **Lectura real (05-nov):** 0 de 12 trades de Paper y 0 de 0 de Real con una reentrada en la misma vela de un cierre SL/TP: el defecto existía pero todavía no había ocurrido.
- **Efecto visible:** en Paper, la hora de salida puede quedar hasta ~2 min antes que con el código anterior; en Real, la hora de Bybit. Solo la usan la pantalla (orden y duración) y `RiskLimits` (pérdida del mes), que queda más exacto.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `trading/paper_trader.py` (regla de señal ya operada; `exit_time` = inicio de `exit_span`; salida por señal opuesta con T); `trading/real_trader.py` (misma regla; `bybit_close_time()`; `close_trade(exit_time=…)` con `COALESCE($9::timestamp, now())`); `tests/Forensic/sqlfake.py` (las pruebas ejecutan el SQL real sobre SQLite en memoria); `paper_opposite_test.py` y `real_opposite_test.py` usan `sqlfake` | `tests/Forensic/signal_reuse_test.py`: 20 casos en PASS (sondas A y B en Paper y Real, bordes en T, 3 ticks por vela, `exit_time` del SL y de la señal opuesta, señal consumida por `exit_on_opposite`, fila `error` de Real, hora de Bybit con 2 tramos y sin hora, **paridad completa Paper vs motor con 1m**: 31/34/33 operaciones con 9–11 entradas justo tras SL/TP, mismas operaciones y `exit_time` del evento). Antes del cambio: **16 FALLOS** (los 4 restantes son guardas que pasan igual). Las pruebas viejas con el arnés de SQL real pasan con el código viejo (arnés fiel). 9 mutaciones detectadas. Regresión en TODO OK |

### Lecciones
- Las bases simuladas que reconocen una consulta por su texto se quedan viejas cuando cambia el SQL: ahora se ejecuta el SQL real (`sqlfake.py`).
- Una regla que compara contra `exit_time` exige que `exit_time` sea la hora del evento, no la del proceso.

### Lecciones (instalación)
- El motor **no escribe en el journal**: escribe en `python-engine/logs/engine.log` (systemd `StandardOutput=append`, rotado por logrotate). La línea «errores del motor desde el reinicio: 0» del instalador p19 usaba `journalctl` y no verificaba nada; se rehízo a mano sobre `engine.log` (sin errores). Desde p20 los instaladores leen `engine.log`.
- Las líneas de acceso de uvicorn (`INFO: 127.0.0.1 … POST /v1/paper/tick`) no llevan hora: para filtrar por hora usar solo las líneas del logger de la app.

### Cambios fuera de git
- Instalado con **p19** el 05-nov: regresión 29 en TODO OK; `trading2-engine` reiniciado **20:52:28 UTC**; tick de Paper con el código nuevo (trade abierto actualizado); `engine.log` sin `Traceback` ni `[ERROR]`; `/v1/paper/tick` respondiendo 200; `main` subido (`bb78810..a373996`).

---

## 2026-11-03 (Bogotá) — En vivo, la fuente de velas es solo Bybit (C-11)

### Resumen para el dueño
- `resolve_live_broker` (Paper, Real y régimen) elegía, entre **todas** las fuentes de `ohlcv_data`, la de vela más reciente. Era así desde que IG era una segunda fuente en vivo; IG ya no existe.
- **Lectura real (03-nov):** hay 2 fuentes, `bybit` y `binance_vision` (Binance **spot** importado a mano: 52 series de 10 monedas, del 2024-06-01 al **2026-09-30**; de 1m solo XRPUSDT). Todas las monedas con estrategia activa en Paper tienen su 1m de Bybit activo: **hoy no había efecto**.
- **El riesgo:** las entradas exigen vela fresca (Binance Vision nunca pasa), pero el SL/TP de Paper, el funding de Paper y el break-even de Real leen el 1m **sin exigir fresca**. Si faltaba el 1m de Bybit (p. ej. tras el antiguo «Recargar», o al desactivar el 1m de una moneda con posiciones) tomaban binance_vision: sin velas nuevas, **el SL/TP no se evaluaba y no salía aviso**. Verificado antes del fix: sin 1m de Bybit se elegía `binance_vision` y Real leía sus velas.
- **Ahora** (decisión del dueño: la opción más liviana) en vivo se usa **solo `LIVE_VENUE_BROKER` (bybit)**, con **una sola consulta** (antes: lista de fuentes + una subconsulta por fuente). Sin velas de Bybit o atrasadas: igual que antes, no se opera; en posiciones abiertas sale el aviso existente «sin velas de 1m; SL/TP no evaluados». Retirado `list_brokers` (ya sin uso).
- **El backtest no cambia:** sigue eligiendo la fuente con más cobertura (Bybit desempata), así que binance_vision sigue aportando la historia antigua de esas 10 monedas.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `collectors/broker_resolver.py`: `resolve_live_broker` solo con `LIVE_VENUE_BROKER` y una consulta; fuera `list_brokers` y su caché | `tests/Forensic/live_source_test.py`: 13 casos en PASS (caso normal, 1 consulta, sin 1m de Bybit, Bybit más vieja que binance_vision, fresca/atrasada y límites de 3 velas, otra fuente más reciente, hora sin zona, sin velas, break-even de Real, backtest sin cambios); antes del cambio 5 FALLOS (elegía `binance_vision` u «otra», Real leía velas de binance_vision); 5 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p18**: 25 pruebas Python + 3 PHP en TODO OK; `trading2-engine` activo desde **Tue 2026-11-03 21:47:22 UTC** sin errores; **lectura real `live_broker_test.py`: las 11 configs activas de Paper con `fuente=bybit` y 1m=bybit**; `main` subido (`a1f6a0d..ac76228`).

---

## 2026-11-03 (Bogotá) — Collector: «Recargar completo» re-verifica sin borrar la serie (C-10); cierre de C-07 a C-09

### Resumen para el dueño
- **C-10 (vigente, corregido):** el botón «🔄 Recargar completo» hacía `DELETE` de **toda la serie** y después la descargaba de nuevo **dentro de la petición**. Verificado antes del fix: con Bybit cortando en la 3.ª consulta, una serie de 3.609 velas quedó en **0 durante la recarga y en 1.000 al terminar** (se perdió el 72 %). Mientras duraba: Paper y Real no abrían (dato viejo), las posiciones abiertas perdían el 1m que usan para SL/TP, los backtests leían un hueco, la corrida de cada minuto lanzaba una segunda carga en paralelo, Laravel cortaba a los 600 s (una serie de 1m tarda más) y el `DELETE` descomprimía todos los chunks de la serie. Además borraba la historia anterior a los 730 días (ENA, DOGE y 1000PEPE tienen desde 2024-06-01) que la carga ya no recuperaba. No había decisión de diseño detrás (entró con el panel el 21-10) y contradecía la regla «el collector nunca borra para reparar».
- **Ahora** (decisión del dueño: la opción más liviana) re-verifica **toda la serie** contra Bybit con la misma comparación de la auditoría C-03 (ventanas de 1.000 velas, 5 campos, ritmo 0,2 s), desde la vela más vieja guardada o el inicio del histórico hasta la última vela cerrada:
  - corrige con el UPSERT solo lo distinto o faltante (normalmente 0 escrituras);
  - **velas sobrantes** (en la base y no en Bybit): se eliminan esas fechas exactas, **solo al final y solo si todas las ventanas se compararon sin error y no quedó nada sin corregir**; una ventana que Bybit devuelve vacía no elimina nada (se reporta);
  - **nunca vacía la serie**: Paper, Real, backtests y la corrida de cada minuto siguen leyendo datos válidos; la vela en formación no se toca;
  - corre **en segundo plano**, **una a la vez** (una segunda devuelve 409 con la que está en curso); la pantalla muestra el avance cada 5 s («Ventana X de Y · velas comparadas · corregidas») y al final «X comparadas · Y corregidas · Z sobrantes eliminadas», o por qué se detuvo. Si la página se abre con una recarga en curso, retoma el avance.
  - Diálogo nuevo (aprobado): «Re-verificar todo el histórico contra Bybit y corregir diferencias. La serie no se borra; solo se eliminan velas que Bybit no tiene, y solo si la verificación termina completa.» Sigue pidiendo CONFIRMAR.
- `/collector/invalidate` (borrar un rango) **no cambia**: es una herramienta deliberada con CONFIRMAR y el hueco lo rellenan la corrida de cada minuto o la auditoría nocturna.
- **C-07** (el vigilante mide frescura, no integridad): cerrado **por diseño**: el vigilante es de frescura (cada 5 min, barato); la integridad la cubren la validación diaria, la auditoría histórica (C-03) y el aviso si la validación no corre (C-06). **C-08** (el panel «ok» es solo frescura): **ya resuelto** en la pantalla, que muestra aparte el resultado de la validación contra Bybit. **C-09** (`initial_load` con una sola vela da la serie por cargada): cerrado **con datos reales**: la serie corta (HYPE) es corta porque Bybit la listó el 2024-12-05 (su primera vela diaria); las otras 77 series tienen los 2 años; los huecos internos los repara C-03.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `reverify_series` en `cli/collector_audit.py` (`audit_window` devuelve además `extra_times`); `/collector/reload` en segundo plano con estado (`/collector/reload-status`) y candado; Laravel `reload` (timeout 15 s, 409) y `reloadStatus` (ruta `collector.reload-status`); diálogo y avance en `data-collector/index.blade.php` | `tests/Forensic/collector_reload_test.py`: 23 casos en PASS (corrupta, faltante y sobrante corregidas; vela en formación intacta; la serie nunca baja de tamaño; avance; corte a mitad sin pérdida ni borrado; 403; ventana vacía de Bybit; diferencias sin corregir; sin confirm; intervalo inválido; respuesta inmediata; 409; estado; resultado; diálogo; timeout); antes del cambio: 3.609 → 0 → 1.000 velas; 6 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p17**: 24 pruebas Python + 3 PHP en TODO OK; rutas `collector.reload` y `collector.reload-status` activas; `trading2-engine` activo desde **Tue 2026-11-03 21:37:14 UTC** sin errores; estado real de la recarga responde (`running: false`); `main` subido (`169d30d..a1f6a0d`).

---

## 2026-11-03 (Bogotá) — Collector: el vigilante comprueba que la validación diaria corra (C-06)

### Resumen para el dueño
- C-06 tenía tres partes: (1) corrupción histórica con conteo completo → **resuelta por C-03**; (2) atraso largo que tarda muchas pasadas (máx. 7 días por serie) → **resuelta en la práctica** por C-05 (cola de la serie) y C-03 (huecos intermedios); (3) **el vigilante no comprobaba que la validación diaria corriera** → vigente, corregida aquí.
- Antes: si el job de las 04:00 dejaba de correr (cola `research` trabada, programador detenido), nadie se enteraba; la pantalla seguía mostrando el último resultado (se guarda 30 días) y tampoco corrían la reparación ni la auditoría. Solo había aviso si el job arrancaba y fallaba.
- Ahora el vigilante (cada 5 min, sin costo: lee el resultado guardado) abre el incidente **«La validación diaria del collector no corre»** si la última tiene más de **26 h** o no hay registro, y lo cierra solo cuando vuelve a correr. Umbral en `config/trading.php` (`WATCHDOG_VALIDATION_STALE_H`).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `CollectorWatchdog::checkDailyValidation` y `validationStaleness` (lógica pura); `validation_stale_h` en `config/trading.php` y `.env.example` | `tests/Forensic/collector_watchdog_validation_test.php` (PHP puro): 8 casos en PASS (2 h, 25 h, 27 h, sin registro, fecha ilegible, sin fecha, umbral configurable, formato real del job); antes del cambio 1 FALLO; 4 mutaciones detectadas |

### Cambios fuera de git
- Instalado con **p16** (sin reinicios: el vigilante corre por cron): 23 pruebas Python + 3 PHP en TODO OK; **corrida real del vigilante en `--dry`: «validación diaria: al día»**; `main` subido (`e91d946..169d30d`).

---

## 2026-11-03 (Bogotá) — Collector: carga inicial y puesta al día por ventanas, sin bloquear al resto (C-05)

### Resumen para el dueño
- La carga inicial de una serie nueva descargaba **730 días completos en memoria** y guardaba todo **al final** (1m ≈ 1,05 M velas, ~1.050 páginas). Corría **dentro de la corrida de cada minuto**: al agregar una moneda desde la pantalla, la corrida tardaba varios minutos con el candado tomado y **las 84 series dejaban de actualizarse** (Paper y Real sin velas nuevas de 1m). Si el motor se reiniciaba en medio, se perdía todo. Verificado antes del fix: un corte a mitad de la carga deja **0 velas guardadas**.
- Ahora una serie nueva o atrasada **avanza hacia adelante por ventanas de 1.000 velas y guarda cada una al llegar**; como máximo **~20 s por corrida** (la siguiente sigue desde la última vela guardada). Si la moneda se listó hace poco, salta el tiempo anterior con **una sola consulta diaria** en vez de ~1.000 ventanas vacías.
- **Prioridad:** cada corrida actualiza primero las series al día (1 consulta cada una, como siempre) y usa el tiempo que sobra (hasta 60 s de corrida) para las que se ponen al día. **Agregar una moneda ya no detiene al resto.** `/collector/run` informa `catching_up` (series poniéndose al día y cuánto les falta).
- Una serie de 1m nueva (2 años) queda completa en ~25 min; una interrupción se retoma sola y el histórico queda continuo desde el inicio (resuelve buena parte de C-09).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `OhlcvCollector.fetch_window`, `catch_up`, `_first_listed`; `initial_load` y `update` por ventanas con `deadline`; `run_all` prioriza las series al día y da presupuesto a las atrasadas; `catching_up` en `/collector/run` | `tests/Forensic/collector_catchup_test.py`: 12 casos en PASS (carga por ventanas con presupuesto, salto al listado, completa y continua en varias corridas, memoria acotada, corte y retoma sin huecos, caso normal = 1 consulta, prioridad en la corrida, presupuesto de la corrida); antes del cambio un corte dejaba 0 velas; 5 mutaciones detectadas. Regresión en TODO OK |

### Lecciones
- Un reloj como valor por defecto de un parámetro (`clock=time.monotonic`) se fija al **definir** la función: no se puede sustituir en las pruebas y compara relojes distintos. Resolverlo en cada llamada (`clock = clock or time.monotonic`).

### Cambios fuera de git
- Instalado con **p15**: 23 pruebas Python + 2 PHP en TODO OK; **consulta real a Bybit**: ventana hacia adelante de BTCUSDT 1m = 10 velas continuas y en orden (20:54–21:03 UTC); `trading2-engine` activo desde **Tue 2026-11-03 21:04:47 UTC**; `main` subido (`43808e4..e91d946`).

---

## 2026-11-03 (Bogotá) — Collector: barrera única contra velas inválidas (C-04)

### Resumen para el dueño
- La ingesta guardaba velas sin validarlas: de los 6 caminos que escriben (descarga automática, carga inicial, reparación diaria, auditoría histórica, importación manual y backfill) solo el backfill validaba, y de forma incompleta (sin NaN/infinito ni horario). Verificado antes del fix: `low > high`, volumen negativo, NaN y vela fuera de horario se guardaban.
- Ahora hay **una sola barrera en `save_bars`** (el único punto de escritura, así cubre los 6 caminos): números finitos, `low > 0`, `low ≤ min(open, close)`, `high ≥ max(open, close)`, `high ≥ low`, `volume ≥ 0` y hora alineada a su intervalo. Volumen 0 y precio plano siguen siendo válidos.
- Una vela inválida **no se guarda** (log con el ejemplo; nunca se corrige un precio por cuenta propia); si deja un hueco, la validación diaria lo marca. El backfill usa la misma regla (`valid_bar` compartida).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `bar_problem()` / `valid_bar()` en `ohlcv_collector.py`; `save_bars` descarta y registra las inválidas (`last_rejected`); `backfill_bybit.py` usa la regla compartida | `tests/Forensic/collector_ingest_test.py`: 23 casos en PASS (12 tipos de vela inválida, 6 válidas incluidas volumen 0 / precio plano / 1D / 4h, tanda mezclada, descarga automática, backfill); antes del cambio las 4 inválidas de la sonda se guardaban; 5 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p14**: 22 pruebas Python + 2 PHP en TODO OK; **lectura real: 0 velas inválidas en los últimos 7 días** (los datos de Bybit no chocan con la barrera); `trading2-engine` activo desde **Tue 2026-11-03 20:42:53 UTC**; `main` subido (`936fdf9..43808e4`).

---

## 2026-11-03 (Bogotá) — Collector: auditoría histórica rotativa vela por vela contra Bybit (C-03)

### Resumen para el dueño
- La validación diaria comparaba con Bybit **solo las últimas 300 velas**; del resto del histórico solo contaba velas y horario. Verificado antes del fix: con una vela vieja corrupta (close 999) la validación devuelve **ok = True** (300 comparadas de 3.500). El backtest usa todo el histórico (sobre todo el 1m, que decide SL/TP dentro de cada vela).
- Histórico real (validación del 03-nov): **~18,2 M velas** en 84 series (1m 13,97 M · 5m 2,84 M · 15m 0,96 M · 1h 241 k · 2h 122 k · 4h 62 k · 1D 10 k) = ~18.220 consultas por vuelta completa.
- Ahora la reparación diaria (04:00) termina con una **auditoría rotativa**: ventanas de 1.000 velas, de la más vieja hacia adelante, comparando los 5 campos; cursor por serie entre noches (`storage/app/collector_audit_cursor.json`); por turnos entre series; **1.500 consultas por noche** (~5 min; todo el histórico cada **~12 días**), configurable con `COLLECTOR_AUDIT_BUDGET` en `python-engine/.env`. Decisión del dueño: la opción más liviana.
- **Repara sola** lo distinto o faltante con el UPSERT del collector (nunca borra; decisión del dueño); **sobrantes se reportan, no se borran**. Una serie con diferencias que no se pudieron reparar cuenta como falla (incidente de la campana); si la auditoría encuentra o repara algo llega «Auditoría histórica del collector».
- Como máximo una vuelta por serie y noche (el presupuesto sobrante pasa a las demás); nunca toca la zona de recientes (la cubre el chequeo de las últimas 300); se detiene por presupuesto, por tiempo (1.000 s del proceso) o si Bybit bloquea (403).
- `python-engine/.env.example`: quitados `SYMBOLS` / `INTERVALS` (sin efecto desde C-01) y agregado `COLLECTOR_AUDIT_BUDGET=1500`.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `cli/collector_audit.py` (`run_audit`, cursor); `collector_repair.py` la ejecuta (`--audit-budget`, 0 = no auditar) y la integra en el resultado; `SystemAlerts` avisa hallazgos | `tests/Forensic/collector_audit_test.py`: 21 casos en PASS (vela vieja corrupta y faltante reparadas, sobrante no borrado, cursor y vuelta completa, zona de recientes intacta, turnos, simulación, escritura fallida, tiempo, 403, serie corta, cursor en disco, integración); `collector_validation_alert_test.php` con 3 casos nuevos; 6 mutaciones detectadas. Regresión en TODO OK |

### Cambios fuera de git
- Instalado con **p13**: 21 pruebas Python + 2 PHP en TODO OK; **simulación real de solo lectura** (BTCUSDT, 5 consultas): 7/7 series OK y **5.000 velas antiguas comparadas con Bybit, 0 diferencias**; Horizon reiniciado de forma ordenada (1569225 → 1573050); motor sin reinicio; `main` subido (`23b6b20..936fdf9`). La primera auditoría real corre el 04-nov a las 04:00.

---

## 2026-11-03 (Bogotá) — Collector: reintentos acotados ante fallos transitorios de Bybit (C-02)

### Resumen para el dueño
- La descarga automática hacía **un solo intento**: un 429, un 5xx o una caída de red marcaba la serie con error en esa corrida (sonda: 1 petición y falla, aunque la siguiente habría respondido bien). No se perdían datos (la corrida siguiente recupera desde la última vela), pero la serie quedaba un minuto atrasada y, si Bybit cortaba, se hacían 84 peticiones fallidas por minuto.
- Ahora (`collectors/bybit_http.py`): hasta **3 intentos** con espera 1 s / 2 s + azar; respeta `Retry-After` hasta 5 s; reintenta red, 429, 5xx y los códigos de límite de Bybit (10006, 10018); **no** reintenta el 403 (IP bloqueada: insistir lo empeora) ni errores de parámetros.
- **Corte de corrida:** un 403 o 3 series seguidas limitadas cortan el resto (`omitida: límite de tasa…`, campo `aborted` en `/collector/run`); el minuto siguiente vuelve a intentar.
- **Ajuste encontrado al revisar el peor caso:** el cliente de la corrida usaba 30 s de timeout; con reintentos, una serie colgada podía tardar ~93 s (> 75 s de la corrida). Ahora 10 s por petición: peor caso ~33,5 s.
- La reparación diaria (`collector_repair.py`) usa la misma función y hereda los reintentos. El backfill manual conserva su política larga (CLI sin presupuesto).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `collectors/bybit_http.py` (`get_json`, `BybitRateLimited`, `BybitRequestError`); `fetch_from_bybit` lo usa; `run_all` con corte por límite de tasa y timeout de 10 s; `aborted` en `/collector/run` | `tests/Forensic/collector_retry_test.py`: 20 casos en PASS (429, Retry-After, 5xx, red, timeout, 403, parámetros, 10006, corte de corrida, presupuesto, timeout de la corrida); antes: sonda con un 429 → 1 petición y la serie falla; 6 mutaciones detectadas. Regresión en TODO OK |

### Lecciones
- En pruebas de mutación, al restaurar un archivo hay que **borrar `__pycache__`**: una mutación del mismo tamaño en el mismo segundo deja el bytecode mutado en caché y la prueba sigue viendo la mutación (pasó con `attempts=3` → `1`). No afecta al servidor (git escribe con mtime nuevo).

### Cambios fuera de git
- Instalado con **p12**: 20 pruebas Python + 2 PHP en TODO OK, `trading2-engine` activo desde **Tue 2026-11-03 19:45:05 UTC**, `main` subido (`a006334..23b6b20`).

---

## 2026-11-03 (Bogotá) — Collector: una sola fuente de series (C-01)

### Resumen para el dueño
- Si `collector_configs` quedaba **sin series activas** o **la base fallaba**, el collector descargaba una lista fija del `.env` (`SYMBOLS` / `INTERVALS`; por defecto BTC, ETH, SOL × 1m/5m/15m/1h/2h = **15 series**) que ni el vigilante, ni el panel, ni el validador supervisaban. El detector de régimen tenía el mismo respaldo (BTC/ETH/SOL), aunque su propio comentario decía que la lista fija se abandonó por desincronizarse. Resto de junio, no una decisión.
- El validador con 0 series daba **«TODO OK»** (0 de 0) y la campana cerraba el incidente como «todo OK».
- Ahora: **0 series → no se descarga nada**; **base caída → ese ciclo no corre** (error en el log; el vigilante avisa si los datos se atrasan); el validador y la campana dicen **«sin series activas»**.
- Extra: `/collector/run` no cerraba el pool de conexiones cuando fallaba; ahora sí.
- **Impacto hoy: ninguno** (84 series activas). `SYMBOLS` / `INTERVALS` quedan sin efecto si existen en el `.env`.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `OhlcvCollector.get_active_configs` y `RegimeDetector.get_active_symbols` sin respaldo; `collector_validate.py` falla con 0 series; `SystemAlerts::validationResult` abre incidente con 0 series; `/collector/run` cierra el pool en `finally` | `tests/Forensic/collector_configs_test.py`: 11 casos en PASS, antes 7 FALLOS; `collector_validation_alert_test.php` (PHP puro): 4 casos, antes 2 FALLOS; 4 mutaciones detectadas. Regresión: suites Python y PHP en TODO OK |

### Cambios fuera de git
- Instalado con **p11**: 19 pruebas Python + 2 PHP en TODO OK, `trading2-engine` activo desde **Tue 2026-11-03 19:25:34 UTC**, Horizon reiniciado de forma ordenada (proceso 1410170 → 1569225), `main` subido (`481da82..a006334`).

---

## 2026-11-03 (Bogotá) — REAL-12 a REAL-15: decisiones documentadas e IG retirado

### Resumen para el dueño
- **REAL-12 (`risk_override_pct`):** por diseño (27-jun, `f4bb1c8`: demo con 0,1 %, mainnet 1 %). El riesgo efectivo ya queda en el snapshot de cada trade. Lectura 03-nov: **ninguna suscripción lo usa**; riesgo efectivo = el de la config (1 %, HYPE 0,5 %), igual que el backtest. No hay pantalla para editarlo.
- **REAL-13 (trigger `LastPrice`):** correcto para la paridad: el backtest simula con el último precio negociado (velas de `/v5/market/kline`); `MarkPrice` dispararía en otros precios.
- **REAL-14 (herramientas del bot dependen del tick):** inherente (Bybit no tiene BE, trailing ATR/escalonado, volatilidad ni duración nativos). Mitigado: SL/TP y trailing fijo nativos en Bybit, vigilante del tick real (aviso si una cuenta con posiciones pasa 180 s sin tick) y aviso de REAL-01.
- **REAL-15 (IG):** el alta solo acepta Bybit y `ig_client.py` (305 líneas, 08-jul) no lo importaba nadie: **retirado** (regla 11). Queda en git (`ba402fd`).
- Sin cambio de comportamiento: **no hace falta reiniciar el motor**.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | Comentarios de diseño (REAL-13 en `set_trading_stop`), `docs/02_TECHNICAL.md` (REAL-12/13/14/15), `ig_client.py` eliminado | `grep`: ningún archivo lo referenciaba; `compileall` del motor OK; 21 suites Python y la PHP en TODO OK |

---

## 2026-11-03 (Bogotá) — Trailing con buffer 0 (REAL-10) y lote real de la moneda (REAL-11)

### Resumen para el dueño
- **REAL-10 no era un fallo:** la auditoría dice que Real usa 0,3 % con buffer 0 y que difiere de Paper/Backtest. No difiere: desde el 26-oct (`33c0b1f`) el backtest y Paper aplican el mismo 0,3 % mínimo (sonda: los tres activan en 100,3 para un Long a 100). El 0,3 % tiene motivo (`3e5052d`, 08-jul: Bybit rechaza un trailing que se activa justo en la entrada; el trade BTC #8 quedó ~4 h sin el SL/TP de su estrategia). Solo se cambió que Real use la **constante compartida** en vez de un `0.003` suelto (dos sitios).
- **REAL-11 sí era un fallo (falla segura):** si fallaba la consulta del lote, Real usaba `0.001 / 0.001` inventado; con DOGE/ENA (paso 1), NEAR/LINK (0,1) o 1000PEPE (100) Bybit rechazaba la orden y se perdía la entrada.
- Ahora el lote real se guarda **6 h por entorno y moneda**; si Bybit falla se usa el **último dato real**; sin ninguno **no se envía la orden** y llega «Orden rechazada en Bybit» con el motivo. Una consulta menos a Bybit en casi todas las aperturas.
- **Bug extra encontrado:** el redondeo al paso perdía un paso por coma flotante (0,3 con paso 0,1 → 0,2): órdenes un poco más chicas de lo calculado. Corregido (`floor_to_step`).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `NATIVE_TRAILING_MIN_BUFFER_PCT` en Real; `BybitClient.get_lot_size` (caché 6 h, último dato real, `None` sin dato); `open_trade` no opera sin lote y avisa; `floor_to_step`; `get_min_qty` solo para scripts demo; `rp.FakeClient.get_lot_size` en el arnés de pruebas | `tests/Forensic/real_lot_trailing_test.py`: 19 casos en PASS (activación igual en backtest/Paper/Real con buffer 0 / 0,5 / 1 y por `open_trade`, caché, falla con y sin dato previo, entornos, redondeo, apertura sin lote y con paso 1); antes del cambio el lote caído daba `(0.001, 0.001)` y el redondeo 0,2; 5 mutaciones detectadas. Regresión: 21 suites Python y la PHP en TODO OK |

### Cambios fuera de git
- Instalado con **p09**: 18 pruebas Python + 1 PHP en TODO OK, `trading2-engine` activo desde **Tue 2026-11-03 18:42:38 UTC**, `main` subido (`632b2af..3f84fdb`).

---

## 2026-11-03 (Bogotá) — Permisos de la clave API (REAL-09)

### Resumen para el dueño
- El alta de una cuenta solo comprobaba que la clave **leyera el saldo**: aceptaba claves de **solo lectura** (después cada orden la rechazaba Bybit) y claves **con permiso de retiro** (contra la regla del proyecto: Contratos → Órdenes + Posiciones, nunca retiros). Verificado antes del fix: ambas devolvían `valid = True`.
- Además, la información de permisos que ya se leía (`/v5/user/query-api`) no se mostraba en ninguna pantalla y su regla de «puede operar» buscaba una clave (`UnifiedTrade`) que Bybit ya no envía.
- **Ahora el alta rechaza**, con mensaje claro en el formulario, una clave de solo lectura, sin Contratos → Órdenes o Posiciones, o **con retiros**; si no se pueden leer los permisos, no registra («Intenta de nuevo»).
- **Cuentas ya registradas** (decisión del dueño, opción A): se revisan **una vez al día**; si la clave tiene un problema llega el incidente «Permisos de la clave API a revisar» y **la cuenta sigue operando**. Al reemplazarla llega «Permisos de la clave API correctos».
- Lectura 03-nov de la cuenta 11: lectura y escritura, Contratos → `Order` y `Position` (correcto); el grupo `Wallet` no se leía todavía (la primera revisión diaria tras instalar dirá si hay retiros). **La clave vence en 85 días** (Bybit las vence a los 90 si no tienen IP fija): candidata a un aviso de vencimiento.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `api_permission_problems()` (regla única en `bybit_client.py`); `validate-credentials` exige permisos; `account-info` con la regla correcta y el grupo `Wallet`; `BybitClient.get_api_key_info()`; revisión diaria `_track_permissions` en el tick Real (reintenta a la hora si Bybit no responde, nunca frena el tick); eventos `api_permissions_bad` / `api_permissions_ok` con textos | `tests/Forensic/real_permissions_test.py`: 26 casos en PASS (regla, alta, información, revisión diaria); antes del cambio el alta aceptaba solo lectura y retiro; 5 mutaciones detectadas. `broker_event_messages_test.php` con los textos nuevos y 18 eventos con aviso. Regresión: 20 suites Python y la PHP en TODO OK |

### Cambios fuera de git
- Instalado con **p08**: 17 pruebas Python + 2 PHP en TODO OK, `trading2-engine` activo desde **Tue 2026-11-03 17:26:17 UTC**, `main` subido (`45e11ef..632b2af`).

---

## 2026-11-03 (Bogotá) — Modo de posición One-Way (REAL-08): falla segura y aviso claro

### Resumen para el dueño
- La auditoría dice que el bot asume el modo One-Way sin comprobarlo: **es cierto**. No hay una decisión registrada al respecto; es una suposición del código desde junio.
- **Falla de forma segura:** si una cuenta estuviera en modo Hedge, Bybit rechaza la **apertura** («position idx not match position mode»), así que nunca queda una posición abierta a medias ni sin protección. El aviso «Orden rechazada en Bybit» ya llegaba (uno por hora y moneda); el circuit breaker trata ese código (`10001`) como no crítico.
- Ahora el aviso **explica qué hacer**: «La cuenta está en modo Hedge y TR2 opera en One-Way: cámbiala en Bybit (Derivados → Ajustes → Modo de posición → One-Way)».
- Decisión del dueño (03-nov): el bot **no** cambia el modo de la cuenta (es configuración del dueño en Bybit, igual criterio que el apalancamiento en REAL-07). Motivo escrito en `set_trading_stop`. Sigue en revisión con el dueño.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `BrokerEventMessages::open_rejected` agrega la explicación cuando Bybit rechaza por modo de posición; comentario de diseño en `set_trading_stop` | `broker_event_messages_test.php`: rechazo por Hedge explica cómo pasar a One-Way y otros rechazos no; antes del cambio 1 FALLO. Regresión: 19 suites Python y la PHP en TODO OK |

### Cambios fuera de git
- Instalado con **p07** junto con REAL-07: 15 pruebas Python + 2 PHP en TODO OK, `trading2-engine` activo desde **Tue 2026-11-03 17:12:13 UTC**, `main` subido (`30b0a20..45e11ef`).

---

## 2026-11-03 (Bogotá) — `max_leverage` en Real (REAL-07): correcto por diseño, con paridad del tope

### Resumen para el dueño
- La auditoría dice que `max_leverage` no configura el apalancamiento en Bybit: **es cierto y es a propósito**. `max_leverage` limita el **tamaño** (nocional ≤ saldo × `max_leverage`), igual que el backtest; el apalancamiento de la cuenta lo configura el dueño en Bybit. El bot lo lee, lo guarda por trade y, si el SL quedaría más allá de la liquidación, cierra y avisa (decisión del 28-oct, commit `d2d463e`). Llamar a `set-leverage` pisaría la configuración del dueño en Bybit. Motivo escrito en `open_trade`.
- **Divergencia nueva encontrada por la prueba (no estaba en la auditoría):** con `max_leverage` 0 o `null`, el backtest usa 1x; Real no abría nada (0) o fallaba con excepción al abrir (`null`). Corregido: Real usa la misma lectura que el motor (`getattr(strategy, 'max_leverage', 1.0) or 1.0`). Con las configs actuales (sin el campo → 1x) el tamaño no cambia.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `RealTrader.open_trade`: tope de nocional con la lectura del motor; comentario de diseño de REAL-07 | `tests/Forensic/real_sizing_test.py`: tamaño Real = motor en 8 casos (riesgo manda, tope 1x / 3x / 0,5x, sin campo, 0, `null`, texto); antes del cambio 2 FALLOS (0 y `null`). Regresión: 19 suites Python en TODO OK |

### Cambios fuera de git
- Instalado con p07 junto con REAL-08 (motor reiniciado Tue 2026-11-03 17:12:13 UTC).

---

## 2026-11-03 (Bogotá) — Saldo de Real explícito (REAL-06) y REAL-02 se mantiene por diseño

### Resumen para el dueño
- **REAL-06 (saldo):** el código buscaba primero `availableToWithdraw`, que Bybit devuelve vacío en cuentas unificadas desde el 09-01-2025, y **por casualidad** caía en `walletBalance` (saldo realizado), que es justo la base correcta. Ahora lo lee explícitamente y deja escrito por qué.
- **No se siguió la recomendación de la auditoría** (usar el saldo libre `totalAvailableBalance`): con posiciones abiertas bajaría y cada entrada nueva saldría más chica que en el backtest. Si falta margen, Bybit rechaza y llega el aviso «Orden rechazada en Bybit».
- Bug real que se cierra: con colateral en otra moneda (USDT en 0) tomaba un campo de margen de órdenes como saldo (ej. 5 USDT). Ahora usa el saldo total de la cuenta.
- **Con la cuenta 11 (USDT) el resultado es idéntico** al de antes.
- **REAL-02 (SL/TP provisional 2 % / 4 %):** revisado con el dueño y **se mantiene por diseño**. Motivo: en junio, con el SL/TP de la estrategia dentro de la orden, Bybit rechazaba aperturas (`10001` stopLoss/takeProfit) y las posiciones quedaban huérfanas; el provisional se puso «para garantizar aceptación» (commit `3170f98`, 2026-06-28). Dura segundos y, si el definitivo falla, llega el aviso de REAL-01. El motivo quedó escrito en el código (`place_market_order`) y en `docs/02_TECHNICAL.md` para que ninguna auditoría futura lo trate como fallo.
- Confirmado con el dueño: editar un backtest implementado actualiza Paper y Real en el siguiente minuto (Real lee la misma config); quitarlo de Paper detiene las entradas Real y **la posición Real abierta sigue hasta su SL/TP** (opción A, sin cambios).
- Lectura de base 03-nov: ninguna config tiene `allow_short` / `close_on_opposite` / `exit_on_opposite` guardados como texto (0 filas): la lectura tolerante de banderas no cambia ninguna config actual. Real sin trades todavía; 8 suscripciones en la cuenta 11 (demo).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `BybitClient.get_balance`: `walletBalance` de USDT, si no `totalWalletBalance`; sin `availableToWithdraw` ni `totalOrderIM`; `None` = no se pudo saber, `0.0` = sin saldo. Comentario de diseño de REAL-02 en `place_market_order`; `docs/02_TECHNICAL.md` actualizado | `tests/Forensic/real_balance_test.py`: 11 casos en PASS; antes del parche 4 FALLOS (B1 y B2, cuenta USDT, pasan antes y después: mismo resultado); 3 mutaciones detectadas. Regresión: 18 suites Python y la PHP en TODO OK |

### Cambios fuera de git
- Reiniciar `trading2-engine` (sin búsquedas ni órdenes Real `pending_*`).

---

## 2026-11-03 (Bogotá) — Aviso cuando Bybit no acepta el SL/TP de la estrategia (REAL-01)

### Resumen para el dueño
- Si Bybit rechazaba el SL/TP de la estrategia al abrir, la posición quedaba con el **stop provisional de la orden (2 % / 4 %)** y nadie se enteraba: solo una línea en el log. El monitor ya reintentaba alinearlo cada minuto, pero si seguía fallando lo hacía en silencio.
- Verificado antes del fix con una sonda: apertura → `open_trade` devuelve éxito, la fila queda `open` con el SL/TP de la estrategia que no está en Bybit, cero avisos y la auditoría solo dice `opened`; monitor → reintenta, falla y no deja log, error ni aviso.
- Ahora es un **incidente en la campana**: «SL/TP de la estrategia no instalado» (error, uno por trade, no se repite cada minuto) y «SL/TP de la estrategia instalado» cuando el monitor lo logra o si lo corriges a mano en Bybit.
- Decisión del dueño (03-nov): **solo avisar** (opción A). El bot no cierra la posición por esto; sigue con el stop provisional y reintenta cada minuto.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | Eventos `protection_failed` / `protection_restored` (`broker_events.py` y textos en `BrokerEventMessages.php`, modo incidente `open` / `resolve` por trade); auditoría `sl_tp_final_failed`, `sl_tp_realign_failed` y `sl_tp_realigned`; el estado del incidente se lee de `audit_log` (sobrevive a reinicios); el monitor deja log de error si Bybit rechaza el realineado y ya no llama a Bybit cuando el SL/TP ya coincide | `tests/Forensic/real_protection_test.py`: 15 casos en PASS (apertura, monitor, deduplicación, cierre del incidente, corrección manual, flujo completo); antes del parche 10 FALLOS; 6 mutaciones detectadas. `broker_event_messages_test.php`: textos nuevos y que **todo evento del motor tenga aviso** (16); antes 8 FALLOS. Regresión: 17 suites Python y la PHP en TODO OK |

### Cambios fuera de git
- Instalado con **p05** (`/root/patches/p05/`): md5 OK, 14 pruebas Python + 2 PHP (incluida `broker_events_drain_test.php` con Laravel, transacción revertida) en TODO OK, `trading2-engine` activo desde **Tue 2026-11-03 16:13:30 UTC**, `main` subido (`0d512d8..b8e2b7e`). Horizon no hace falta: `BrokerEventMessages` solo lo usa `broker:events` (cron, proceso nuevo cada minuto).

### Comportamiento a conocer
- Mientras el incidente está abierto, la DB muestra el SL/TP de la estrategia aunque en Bybit siga el provisional: el aviso lo dice y el monitor sigue intentando.
- El monitor consulta `audit_log` de cada posición abierta una vez por minuto (una consulta por trade; despreciable con pocas posiciones).

### Pendientes que deja
- REAL-02: el SL/TP provisional es genérico (2 % / 4 %), no el de la estrategia; con un SL de estrategia más ajustado, mientras dura el incidente el riesgo es mayor que el configurado.

---

## 2026-11-03 (Bogotá) — Real cierra por señal opuesta (BP-02)

### Resumen para el dueño
- Real no tenía salida por señal opuesta: con `close_on_opposite` / `exit_on_opposite` mantenía posiciones que el backtest y Paper ya habían cerrado o invertido. Verificado antes del fix: estático (cero referencias a la regla en Real) y dinámico (Long abierto + señal Short → «ya tiene posicion abierta», el monitor no cierra).
- Ahora Real sigue la misma regla que el motor y Paper: cierra por señal opuesta y, con `close_on_opposite`, invierte.
- **Reversa solo con el cierre confirmado en Bybit y la posición en cero**: si Bybit no confirma, no abre la contraria y reintenta en el tick siguiente. Nunca dos posiciones a la vez.
- Con la cuenta pausada, el kill switch, un límite de riesgo, `exit_on_opposite`, régimen no permitido o `allow_short` apagado: **cierra sin reversa**.
- Decisión del dueño (03-nov): con la suscripción pausada o la config Paper apagada **no** se aplica (igual que Paper); la posición sigue con SL/TP/BE.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `RealTrader.check_new_signals` con salida por señal opuesta (señal con la estrategia viva, banderas del snapshot, la vela de la señal debe cerrar después de la entrada, el régimen no se mira para salir, señal consumida no reabre); `get_open_trade_for_subscription`; `_process_account` evalúa las suscripciones aunque la cuenta esté pausada o con kill switch, con `entries_allowed=False`; `opposite_exit_rule()` compartida por Paper y Real; `close_on_opposite` / `exit_on_opposite` leídos con `as_flag` | `tests/Forensic/real_opposite_test.py`: paridad Real vs motor vela por vela (16, 10, 10 y 8 operaciones, 3 ticks por vela) y 27 casos en PASS; antes del parche 16 FALLOS; 7 mutaciones detectadas. `broker_events_test.py` C6/C7 actualizados al contrato nuevo (cuenta pausada: monitor + señales sin entradas). Regresión sin base: 16 suites en TODO OK; `backtest_elements_test.py --synthetic` igual a la línea base |

### Cambios fuera de git
- Instalado con el parche **p04** (`/root/patches/p04/`, originales en `orig/`): md5 de origen y destino OK, 13 pruebas forenses en TODO OK en el servidor, `trading2-engine` reiniciado (sin búsquedas ni órdenes Real `pending_*`) y activo desde **Tue 2026-11-03 15:56:17 UTC**; `main` subido (`e96f734..0d512d8`). Incluye también el commit de `allow_short`.

### Comportamiento a conocer
- Desde el reinicio, las cuentas Real con configs que usan la regla (VWAP BTC H4, LINK H4, ENA H4, 1000PEPE H4, XRP H2) tendrán más cierres y operaciones inversas, como Paper desde el 03-nov 08:41 UTC.
- El tick Real de una cuenta pausada ahora calcula señales de las suscripciones con posición abierta y regla (no abre nada). El resultado del tick lleva el aviso en `entries` en vez de en `signals`.
- El precio de la reversa es el mercado tras el cierre (dos órdenes: `reduceOnly` y luego entrada); en el motor ambos son el open de la vela.

### Pendientes que deja
- REAL-01 (aviso si falla `set_trading_stop`).
- `RealTradingTickJob` filtra los logs con `str_starts_with($r, 'ABIERTA')`, pero los mensajes empiezan con el símbolo (`BTCUSDT: ABIERTA ...`): nunca registra aperturas ni reversas en el log de Laravel. Solo afecta al log; candidato a un fix pequeño.

---

## 2026-11-03 (Bogotá) — `allow_short` en Paper y Real (BP-01 / REAL-03)

### Resumen para el dueño
- Con `allow_short` desactivado, Paper y Real abrían Short igual; solo el backtest lo respetaba. Ahora los tres usan **una sola regla** (`BaseStrategy.allows_side`).
- Con `close_on_opposite` y sin Short, una señal corta cierra el Long y **no** reversa (igual que el motor).
- `allow_short` llegado como texto (`"false"`, `"0"`, `"off"`) ya vale falso; antes `bool("false")` era verdadero.
- Era latente: ninguna config lo desactiva hoy y la interfaz no lo ofrece. Sin cambio de comportamiento para las configs actuales (default sigue siendo permitir Short).

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| (este) | `as_flag()` y `allows_side()` en `BaseStrategy`; el motor, `PaperTrader.check_new_signals` y `RealTrader.check_new_signals` deciden la dirección con `allows_side` (Real antes de consultar la base y de pedir precio) | `tests/Forensic/allow_short_test.py`: F1, P1-P8 (paridad Paper vs motor con `close_on_opposite` y `exit_on_opposite`, 8 operaciones cada una) y R1-R5 en PASS; antes del parche 12 FALLOS con los controles (P4, R3-R5) en PASS; 3 mutaciones detectadas (sin chequeo Paper, sin chequeo Real, sin `as_flag`). Regresión sin base: 15 suites Python en TODO OK; `backtest_elements_test.py --synthetic` (3 meses) con salida idéntica antes y después |

### Cambios fuera de git
- Instalado con p04 junto con BP-02 (motor reiniciado Tue 2026-11-03 15:56:17 UTC).

### Pendientes que deja
- Cierre por señal opuesta en **Real** (BP-02) y aviso si falla `set_trading_stop` (REAL-01).
- `close_on_opposite`, `exit_on_opposite` y el resto de banderas siguen leyéndose con `params.get(...)` sin `as_flag`: mismo riesgo latente con texto `"false"`. Candidato a unificar en otro commit con su prueba.

---

## 2026-11-02 (Bogotá) — Auditoría externa y fix REAL-04 (Real seguía operando con la config Paper apagada)

### Resumen para el dueño
- Se contrastó una auditoría hecha por otra IA (hasta 31-oct) contra el código: casi todo es verdad, pero se ajustaron severidades (BP-03, REAL-01, REAL-02 y REAL-10 no son críticos o no son bug).
- **REAL-04 corregido:** «Detener», desactivar o borrar la config Paper ya no deja que Real abra posiciones. Antes Real solo miraba el estado de su propia suscripción y la pantalla prometía lo contrario.
- Se encontraron 2 suscripciones expuestas (96 HYPEUSDT H4 y 98 1000PEPEUSDT H2, cuenta 11 demo, hoy pausada) con la config apagada: habrían abierto posiciones al reanudar la cuenta.

### Commits
| Commit | Qué | Verificación |
|---|---|---|
| `5017d2e` | Una suscripción Real solo abre posiciones si ella y su config Paper están activas (`scopeRunnable`, usado por `RealTradingAccountTickJob` y `RealTradingTickJob`); `destroyBacktest` pausa sus suscripciones y no borra si hay posición Real abierta | `tests/Forensic/real_config_gate_test.php`: A1-A5, controles con el filtro viejo, B1, C1, D1-D4 y Z1 en PASS (`TODO OK`) sobre datos reales dentro de una transacción revertida |
| `3baaadd` | `.env.example` sin bloque PHP, sin contraseña de ejemplo ni correo personal; base `pgsql`, cola `redis` y sección TR2 con las 14 variables de `config/trading.php`; nuevo `python-engine/.env.example` con las 12 del motor | `p02.py` T1-T4 en PASS, Laravel lo parsea (52 variables), `.env` y `python-engine/.env` con md5 idéntico antes y después |
| `c8d1223` | Paper cierra por señal opuesta (`close_on_opposite` cierra y reversa; `exit_on_opposite` solo cierra), con las reglas congeladas del trade, sin mirar el régimen para salir, con kill switch sin reversa y sin reabrir con la señal ya consumida | `tests/Forensic/paper_opposite_test.py`: paridad Paper vs motor (16 y 10 operaciones, 3 ticks por vela) y 12 casos en PASS; antes del parche 10 FALLOS; 5 mutaciones detectadas; `paper_parity_test.py` sigue en TODO OK |

### Cambios fuera de git
- Horizon reiniciado (sin búsquedas en curso) para que los jobs carguen el código nuevo.
- Originales respaldados en `/root/patches/p01/orig/`.
- `trading2-engine` reiniciado (sin búsquedas ni órdenes Real pendientes) para cargar la salida por señal opuesta; activo desde Tue 2026-11-03 08:41:46 UTC. Original de `paper_trader.py` en `/root/patches/p03/orig/`.

### Comportamiento a conocer
- Las posiciones ya abiertas se gestionan igual: ese camino no usa el filtro nuevo.
- Reactivar una config Paper reactiva sola la entrada Real de su suscripción activa (no se pausan las suscripciones al detener).
- Borrar un backtest con una posición Real abierta se bloquea con aviso; sin posiciones, pausa sus suscripciones antes de borrar la config.
- **Paper cierra por señal opuesta desde el reinicio del motor (Tue 2026-11-03 08:41:46 UTC).** Afecta a las 5 configs activas que usan `close_on_opposite` (VWAP BTC H4, LINK H4, ENA H4, 1000PEPE H4 y XRP H2): más cierres y operaciones inversas. Los trades anteriores no cambian: **cualquier comparación Paper contra backtest debe empezar después de esa fecha.**
- La salida por señal opuesta solo corre mientras la config está activa. La señal se calcula con la estrategia viva de la config; las banderas `close_on_opposite` / `exit_on_opposite` se leen del snapshot congelado del trade.
- **Real NO la implementa todavía:** no reanudar la cuenta 11 (demo, pausada; suscripciones 92, 97 y 99 sobre configs con señal opuesta) hasta hacerlo en Real.

### Lecciones
- Una prueba que depende del estado de los datos hace SKIP y no prueba nada: usar un fixture controlado dentro de una transacción que se revierte.
- `Gate::before` sin un parámetro `$user` anulable no se aplica a invitados (falló la prueba, no el código).
- Para probar el «antes» sin tocar producción: controles que ejecutan el filtro viejo en la misma prueba. No poner código viejo en disco con Horizon corriendo (clases cargadas de forma perezosa).
- La prueba C restaura todas las configs de la cuenta a activas dentro de su transacción (incluidas las que estaban apagadas); no afecta al resultado y se revierte, pero D4 lista por eso las subs 96 y 98.
- Un `.env.example` es una plantilla que se versiona: sin código ejecutable, contraseñas ni correos reales. Una prueba estática compara sus claves con las `env()` y `os.getenv()` del código para detectar variables que falten.
- Las pruebas de mutación (quitar una pieza del parche y comprobar que la prueba falla) destaparon dos huecos de la propia prueba: una base simulada que no leía el SQL y un caso sin cubrir. Con ticks cada minuto, `exit_on_opposite` exige bloquear la reapertura con la señal ya consumida.
- La paridad contra el motor (mismas velas y señales, comparando operación por operación) detecta divergencias que los casos sueltos no ven.

### Pendientes que deja
- Resto de la lista de fix de la auditoría (ver «Próxima sesión» punto 6).

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

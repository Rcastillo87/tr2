# Validación del informe de auditoría — Ciclo 5 (TR2)

> Bitácora de la validación punto por punto del «Informe de auditoría — Ciclo 5» (punto de partida: p91 `6073506`).
> **Método por punto (igual que el ciclo 4):** (1) leer la afirmación; (2) contrastarla con el código vigente y con
> lecturas del servidor; (3) veredicto; (4) si hay fix: propuesta al dueño, prueba que falla con el código anterior,
> mutaciones y regresión completa; (5) registro aquí y en `docs/BITACORA.md`, haya o no fix.
> **Estados:** Pendiente de validar · Validado (con su veredicto) · Implementado (sin instalar) · Instalado (SHA) ·
> Validado en Demo. Un instalador que termina bien no cierra un punto por sí solo (§7.7 del informe).
> **Veredictos:** Válido · Válido en parte · Refutado · Ya corregido · Decisión del dueño.
> **Criterio desde C5-03 (dueño, 23-nov):** *defecto* = el sistema contradice una decisión, da un dato equivocado o
> arriesga dinero o datos → se propone y recomienda el arreglo; *sugerencia* = cambia algo que funciona como el dueño
> decidió → se presenta como opción con pros y contras, sin recomendarla como arreglo; *refutado* → se explica y se cierra.
> Los resueltos van en una lista aparte de los pendientes (§7.10 del informe).

## Pendientes del ciclo

| Orden | ID | Prioridad | Punto | Estado |
|---|---|---|---|---|
| 19 | C5-12 | P2 | Rótulo del drawdown consolidado | Implementado en p107 (D-62) |
| 20 | C5-13 | P2 | Infraestructura heredada | Pendiente de validar (respaldo fuera del VPS: descartado, D-48) |
| — | DEMO-01..12 | — | Pruebas de aceptación en Bybit Demo | Pendientes (protocolo por preparar) |

## Validados (con fix implementado o instalado)

### C5-12 · Claridad del drawdown consolidado del backtest (P2) — **Excel: refutado · pantalla: sugerencia aceptada** · Implementado en p107 (D-62)
- **Código:** en la fila CONSOLIDADO, «DD cerrado» y «DD flotante» son el peor DD entre las monedas
  (`BacktestingController`, Fase 12 · 4A); cada moneda se simula sola (D-41). El número es el decidido; el encabezado
  («Peor caída del capital…») es el mismo de las monedas y se puede leer como el DD de una cartera conjunta.
- **Excel: refutado.** `BacktestMonthlyExport` exige `monthly_breakdown` (resultado de una moneda): su DD es el de esa
  moneda. Además ninguna pantalla enlaza la ruta `backtesting.export-excel` (hallazgo aparte, sin cambio).
- **Clasificación:** sugerencia (no contradice ninguna decisión ni da un dato equivocado): se presentó con boceto y el
  dueño la aceptó («Sí, como el boceto», 24-nov).
- **Cambio (D-62):** con más de una moneda, bajo esos dos valores «peor moneda», la explicación al pasar el mouse y una
  nota bajo la tabla de resumen («el peor DD entre las monedas. Cada moneda se simula sola, así que no es la caída de
  una cartera con todas a la vez»). Con una sola moneda, sin cambio. Ningún número cambia.
- **Prueba:** `backtest_drawdown_columns_static_test` +7 (C5-12); vista anterior 4 FALLOS; mutaciones 8/8; las 4 filas
  siguen con 13 celdas; regresión 78 Python + 33 PHP en TODO OK.

### C5-11 · Deduplicación y trazabilidad de posiciones manuales (P2) — **Defecto pequeño (latente)** · Instalado en p106 (`c7f9090`, D-61)
- **Código:** el aviso `manual_position_ignored` (D-18: «se avisa una vez por posición») se deduplicaba por moneda +
  lado + precio de entrada, sin fin: una manual nueva del mismo lado y al mismo precio exacto que otra anterior ya
  cerrada no avisaba; agregar a una manual abierta cambiaba su precio promedio y repetía el aviso. No había registro de
  que la manual se cerró (D-19: desde ahí el bot puede volver a abrir en esa moneda).
- **Servidor (lectura 24-nov 04:50 UTC):** 0 avisos de posición manual en la historia y 0 menciones en `engine.log`:
  nunca hubo una posición manual (nadie opera a mano, contexto de D-19). La regla D-18 / D-19 sigue cumpliéndose.
- **Fix (D-61, «Arreglar y avisar al cerrarse» 24-nov):** regla pura `broker_events.manual_position_actions` con el
  último aviso manual de la cuenta y moneda: una manual es la misma mientras siga abierta del mismo lado (aunque cambie
  precio o tamaño); cuando ya no está (sin posición, o la posición ahora es del bot) → aviso nuevo
  `manual_position_closed` («Posición manual cerrada», info); la siguiente manual avisa de nuevo. Un error de Bybit no
  la da por cerrada; si no se puede registrar el cierre no se avisa la nueva (se reintenta). Sin cambio de base: la
  consulta usa el índice por cuenta de `broker_events`.
- **Prueba:** `broker_events_test` D5–D14 (+ D10b), `broker_event_messages_test` (texto del aviso nuevo); código
  anterior 7 FALLOS; mutaciones 10/10 (una undécima, la fila del bot en otra suscripción, sobrevivía: se agregó D10b);
  regresión 78 Python + 33 PHP en TODO OK.

### C5-08 · PnL bruto y neto en las estadísticas de Real (P2) — **Defecto pequeño de pantalla (latente)** · Instalado en p105 (`c9cb836`, D-60)
- **Código:** el filtro «Ganadoras / Perdedoras» de Trading usaba el bruto (`pnl`) y los KPI el neto; el total pasaba a
  la suma bruta si la neta daba exactamente 0 (`sum('net_pnl') ?: sum('pnl')`); una operación sin neto contaba como 0
  en ganancia / pérdida y con su bruto al contar ganadoras. El Dashboard contaba las ganadoras de Real con el bruto.
- **Servidor (lectura 24-nov 00:50 UTC):** 13 cerradas, 0 sin neto, 0 con distinto signo entre bruto y neto; neto
  +2.698,51 y bruto +3.121,93 USDT. No ocurrió; aparecería con un cierre que gana poco y pierde por comisiones.
- **Fix (D-60, «Procede» 23-nov):** `App\Support\RealPnl` (puro): resultado = neto ?? bruto, KPI con ese criterio y
  `NET_SQL` para el filtro; usado en Trading (filtro, KPI, curva) y en el bloque de Real del Dashboard. Paper no se toca
  (consistente consigo mismo, fuera del punto).
- **Prueba:** `real_pnl_criteria_test.php` (nueva); código anterior 4 FALLOS; mutaciones 9/9; regresión 78 Python + 33
  PHP en TODO OK.

### C5-06 · Comparador Paper vs backtest con la configuración vigente (P2) — **Defecto menor (solo herramienta)** · Instalado en p104 (`fbc71cf`, D-59)
- **Código:** `--latest-only` («solo el tramo de los parámetros vigentes») toma el tramo de la ÚLTIMA OPERACIÓN de Paper;
  si la config cambió después, compara la versión anterior como si fuera la vigente. Además los cambios de
  `strategy_config_changes` se leían todos (también desactivar / borrar), aunque solo `created` / `updated` cambian
  parámetros. No se puede comparar la huella del snapshot con la de la config: cada snapshot lleva además los niveles
  de su señal (`snapshot_with_levels`). Sin efecto en Paper, Real ni la base (herramienta manual).
- **Fix (D-59, «Procede» 23-nov):** cada tramo dice parámetros, código, desde/hasta y, el último, «vigente» o «NO es la
  vigente»; la cabecera da la huella de la config de hoy; si hubo un cambio de parámetros después de la última
  entrada, aviso en grande; el JSON trae `vigente`, `config_params_key`, `config_code_md5` y `config_changed_after`.
- **Prueba:** `compare_tool_test` V1–V5 (+ bordes V1b/V1c); código anterior FALLA; mutaciones 9/9 (dos bordes
  agregados tras la primera corrida); regresión 78 Python + 32 PHP en TODO OK.

### C5-03 · Independencia de la prueba final 60/20/20 (P2) — **Sugerencia rechazada por el dueño (D-58)** · Pantalla instalada en p103 (`0786a92`)
- **Código:** `accept()` exige `MIN_TRADES` sobre el período completo (prueba final incluida) y, en el enfoque win rate,
  el PF del período completo; las filas se ordenan por retorno y consistencia de los 24 meses (motor) y Laravel ordena
  con `summarize()` de los 24 meses. La pantalla decía que la prueba final «no eligió ni aceptó».
- **Servidor (lectura 23-nov 23:31 UTC, 72 búsquedas v4):** 144 de 1.287 ganadoras (11 %) solo llegan al mínimo de
  operaciones con la prueba final; la 1.ª cambiaría en 24 de 62 búsquedas sin ella (top 5: 71 %; top 10: 78 % iguales).
- **Veredicto:** no es un defecto: evaluar 24 meses, como el backtest, es el diseño del dueño (D-58, que reemplaza a la
  D-57 del mismo día). Lo incorrecto era el texto. Se implementa lo que pidió el dueño: filtro ≥ +5 % en 24 meses en
  todas las búsquedas (sin aviso; tampoco se pueden crear por id), «Retorno 24 m» justo antes de «Elegir», barra con lo
  que se evalúa en cada parte («Total 24 meses: con esto se ordena…»; «debe ganar aquí»; «no se le exige ganar») y
  textos corregidos.
- **Prueba:** `search_min_return_test.php` (nueva: regla, `summarize()`, filtro, creatable, orden de columnas, textos);
  código anterior 9 FALLOS; mutaciones 9/9; JS de la página compila; regresión 78 Python + 32 PHP en TODO OK.

### C5-05 · Cobertura de la reparación de VWAP Tendencia (P1) — **Válido en la herramienta; sin exposición** · Sin arreglo
1. **Sin cobertura mínima: válido.** `2026_11_19_r21_vwap_std.py` daba por verificada una config con 0 velas revisadas.
2. **Otras versiones solo avisadas: válido.** Las configs con la línea vieja y otra huella quedaban en «AVISO» sin
   tocarse ni verificarse (el modo «YA APLICADO» sí falla si queda alguna con la línea vieja).
3. **Hallazgo propio:** p80 no cambió `backtests.config_params.strategy_code`, que es lo que copia «Implementar en
   Paper» (`StrategyConfigSync::syncFromBacktest`): un backtest guardado antes del 19-nov reintroduciría el código viejo.
- **Servidor (lectura 23-nov 23:23 UTC):** «VWAP Tendencia» con el código nuevo; las 11 configs de VWAP (todas
  activas, 6 con suscripción Real activa) con la huella corregida `2cf17fbe`; los 11 backtests guardados de VWAP con el
  código nuevo en `config_params` y en `strategy_snapshot` (se corrieron después de p80); 0 operaciones abiertas de
  Paper o Real con el código viejo. «VWAP Reversión» no tiene esa línea (la revisión diaria la aprueba).
- **Veredicto:** los dos huecos están en una herramienta de un solo uso que ya no tiene nada que corregir y el camino de
  «Implementar en Paper» está cerrado (no hay backtests con el código viejo). Sin arreglo; queda como lección para la
  próxima reparación de código guardado (PROMPT_MAESTRO §8).

### C5-04 · Aislamiento obligatorio de pruebas con PostgreSQL (P1) — **Válido y más grave que lo descrito** · Instalado en p102 (`637821f`, D-56)
- **Hallazgo propio, más grave que el informe:** desde p92 `backtesting/auto_levels.py` carga `python-engine/.env` al
  importarse y casi todas las pruebas lo importan: en el servidor, **la regresión del instalador veía la base de
  producción** (lectura 23-nov: DB_* definidas en `.env`, DB_NAME no termina en «test»; `DB_HOST` vacío antes de
  importar el motor y presente después). Solo `execution_ledger_test` (p89) exigía una base «…test».
- **Pruebas que tocaban producción en cada instalación:**
  - `broker_events_test` (sin barrera, en transacción revertida), `code_md5_test` y `subscription_risk_check_test`
    (en transacción revertida: sin rastro, pero con bloqueos de unos segundos sobre las tablas de operaciones);
  - **`vwap_metrics_fix_test` (p82), sin transacción:** creaba y borraba la estrategia 7043, las configs 90431/90432
    (una **activa** en Paper) en el símbolo falso D43USDT y ~135.000 velas.
  - Otras 8 pruebas de diagnóstico (fuera de la regresión) armaban su propia conexión con el `.env`.
- **Servidor (lectura 23-nov 22:46 UTC):** 0 rastros (estrategia 7043, backtests, configs, cambios de config, trades de
  Paper y Real, suscripciones, velas y collector en D43USDT; usuarios y eventos de prueba) y 0 menciones en los logs:
  la limpieza de cada prueba funcionó. El datafix de D-43 ya estaba protegido (vista previa por defecto, `--apply` y
  exige reproducir lo guardado: una segunda corrida se niega).
- **Fix (D-56, «Procede» 23-nov):** barrera única `tests/Forensic/test_db.py` (`require_test_db` salta con aviso sin
  mostrar el nombre de la base; `test_dsn` lanza si no es de pruebas) en las 14 pruebas que usan base; ninguna arma su
  propia conexión. `test_db_guard_static_test` (nueva, en la regresión) vigila que toda prueba que se conecta use la
  barrera. La regresión local corre ahora esas partes contra `tr2test`; en el servidor se saltan.
- **Prueba:** con una base que no termina en «test» las 6 con base se saltan sin conectarse (la base ni existía);
  con `tr2test` corren completas (132 comprobaciones). Vigilancia contra las pruebas anteriores: 8 FALLOS. Mutaciones
  12/12 (incluido «el servidor intentaría conectarse»). Regresión 78 Python + 31 PHP en TODO OK, con base.
- **Pendiente menor:** `bars_order_test --db` comprobaba dos ajustes de TimescaleDB de la base de producción; con la
  barrera ya no se corre allá (no estaba en la regresión).

### C5-09 · Matriz dinámica de permisos y aislamiento (P1) — **Validado sin defecto**
- **Código:** grupos de rutas con `can:` según D-46 (Paper admin+consultor; Real admin+inversionista; backtesting,
  estrategias, búsquedas, usuarios y collector solo admin); cada acción sobre cuenta / suscripción comprueba el dueño
  (`$account->user_id !== auth()->id()` y suscripción de esa cuenta); `EnsureUserIsActive` en todo el grupo web; sin
  registro abierto; Horizon con lista vacía (nadie en producción). Motor: solo 127.0.0.1 y clave interna en todo salvo
  `/health` (middleware global). Detalle menor: las rutas del collector están fuera del grupo `auth` (un visitante
  recibe 403 en vez de ir al login): sin efecto de seguridad, no se cambia.
- **Prueba dinámica** (`tests/Forensic/role_matrix_test.php`, integración en el servidor; transacción revertida y un
  punto de guardado por petición; sin motor, Bybit, colas ni avisos): todas las rutas web con visitante, admin inactivo,
  admin, consultor e inversionista (negadas: 403 en todos los métodos; GET permitidas: abren; escrituras permitidas no
  se ejecutan) + aislamiento entre dos inversionistas (9 acciones sobre la cuenta / suscripción del otro, ids cruzados,
  5 pantallas y 2 de avisos) y el admin tampoco ve en Real cuentas ajenas.
- **Servidor (23-nov 22:42 UTC):** 61 rutas·método; visitante 61, inactivo 61, denegadas 93, abiertas 41, escrituras
  autorizadas sin ejecutar 49; **TODO OK**, sin avisos; 0 usuarios de prueba antes y después.

### C5-02 · Protección «mira el futuro» ante errores (P1) — **Válido (2 de 2; latente)** · Instalado en p101 (`d4ca055`, D-55)
1. **Al guardar: válido.** `guard_code` saltaba en silencio una combinación sin velas (y si ninguna tenía, aprobaba sin
   probar) y, si la estrategia fallaba al evaluarse vela a vela, devolvía «aprobada» confiando en el smoke test, que
   corre con todas las velas y puede pasar. Las pruebas B5/B6 de `lookahead_guard_test` fijaban ese comportamiento.
2. **Revisión diaria: válido.** Con evaluaciones sin datos o con error, si no había «malas» el comando cerraba el aviso
   («ninguna mira el futuro») y terminaba bien; las sin evaluar solo aparecían como número en el log.
- **Servidor (lectura 23-nov 21:38 UTC):** última revisión (23-nov 09:17): 18 revisadas, ninguna sin evaluar; BTCUSDT
  H1 2.858 y H4 714 velas (se usan 400, mínimo 160); las 13 configs activas con 450 velas. **Nunca ocurrió.**
- **Fix (D-55, «Procede» 23-nov):** al guardar, las 2 combinaciones son obligatorias: sin velas suficientes (mínimo
  160) o con error al calcularse → 400 «No se pudo comprobar… Sin esa prueba no se guarda», sin correr el smoke test.
  Revisión diaria: `status` ok / bad / unverified y `evaluated`; con alguna sin evaluar, incidente
  `strategy-lookahead-unverified` (warning, se cierra cuando se evalúan todas), el de «mira el futuro» no se cierra y el
  comando termina en FAILURE. No cambia ninguna estrategia ni config.
- **Prueba:** `lookahead_guard_test` B5/B6 actualizados a la decisión + B9–B12, C3, C4; `lookahead_audit_static_test`
  +3. Código anterior: 3 + 3 FALLOS. Mutaciones 10/10 (una undécima mostró que la prueba calculaba el mínimo con la
  misma función: se fijó en 160). Regresión 77 Python + 31 PHP en TODO OK.

### C5-07 · Fiabilidad de la conciliación de Real (P1) — **Válido (1) y válido en parte (2); latente** · Instalado en p100 (`599521a`, D-54)
1. **Errores dentro de un HTTP 200: válido.** `/v1/real/reconcile` respondía siempre `status: ok`; los fallos iban a
   `results.errors`, que `RealTradingReconcileJob` no leía (ni log ni aviso). Errores de Bybit con huérfanas y
   `pending_open` se anotaban en `ok` con nota. Una excepción inesperada en una cuenta tumbaba la conciliación de todas
   (HTTP 500, solo una línea de log).
2. **Estados poco claros: válido en parte.** Los tres casos existen (`failed` = no ejecutada; `pending_open` / huérfana
   de apertura = ejecución desconocida; huérfana de cierre = falta el closed-pnl), pero los dos tipos de huérfana se
   distinguían por el texto de `error_message` («no se pudo obtener pnl real»).
3. **Cierre confirmado sin closed-pnl: válido en parte (ya cubierto).** Queda huérfana de cierre, se reintenta en cada
   conciliación (adelantada cada minuto, p95), bloquea entradas (D-50) y avisa a los 15 min (`real_unresolved`).
- **Servidor (lectura 23-nov 20:33 UTC):** 0 errores de conciliación en `engine.log` y en `laravel.log` (desde el
  22-nov); 13 cerradas y 3 abiertas, 0 huérfanas. **Nunca ocurrió.**
- **Fix (D-54, «Procede» 23-nov):** cada cuenta en su propio try (las demás siguen); errores de Bybit a `errors`;
  esperar el closed-pnl a `pending` (no es fallo); respuesta con `complete` y `status: partial` si hay errores.
  `App\Support\ReconcileHealth` (puro): lista de errores y regla del aviso; el job registra cada error y, con fallos
  10 min seguidos (HTTP, excepción o errores del motor), abre el incidente `real_reconcile`; al completarse lo cierra.
  Huérfanas con marca fija `[huerfana:cierre]` / `[huerfana:apertura]` (`orphan_message`, `is_close_orphan`; las filas
  anteriores con el texto viejo siguen reconociéndose, y la de cierre conserva ese texto para que una vuelta atrás con
  `p100_revertir.sh` la siga reconociendo). Sin cambios de base ni de apertura / cierre.
- **Prueba:** `real_reconcile_visibility_test` (nueva: R1–R5, H1–H8) y `reconcile_health_test.php` (nueva: A1–A11,
  B1–B4); `real_recovery_test` P5 buscaba el texto en el SQL: ahora en el parámetro y con la marca. Código anterior:
  FALLA. Mutaciones 16/16. Regresión 77 Python + 31 PHP en TODO OK.

### C5-01 · Integridad del libro de ejecuciones de Bybit (P1) — **Válido (5 de 5 en código; latente)** · Instalado en p99 (`3f31b10`, D-53)
1. **«ok» con diferencias:** confirmado. `record_trade` ponía `ok` con las dos patas aunque `leg_checks` tuviera
   diferencias de cantidad o precio, y con eso separaba comisión y funding.
2. **No volvía a pedir partes:** confirmado. Con alguna parte guardada de una pata (`have[leg]`) no se consultaba más.
3. **10 páginas:** confirmado. `get_executions` cortaba en 10 páginas y devolvía lo leído como completo.
4. **closed-pnl:** confirmado. Una sola página y, si Bybit fallaba, `[]` = «no hay cierres»: un cierre de Bybit podía
   terminar en `missing` por un error.
5. **Comisión sin `execFee`:** confirmado: `exec_fee or 0`.
- **Servidor (lectura 23-nov 19:45 UTC):** 13 operaciones, todas `ok` con funding separado; 1 parte por orden; cantidad
  y precio exactos (0,0000 %); 26 partes, todas con comisión; 0 diferencias y 0 errores de Bybit en el log. **Nunca
  ocurrió.** Detalle aparte: las cantidades quedaron guardadas con ruido binario (15.9100000000000001421…), sin efecto en
  los controles.
- **Fix (D-53, «Procede» 23-nov):** `leg_ok` (cantidad = tamaño y todas las comisiones conocidas); una pata guardada
  incompleta se vuelve a pedir (sin duplicar; la comisión que llega después completa la parte); `ok` solo sin
  diferencias; 24 h después del cierre con diferencias → `mismatch` + aviso `executions_mismatch` (una vez) y sin
  separar costos; si falta una pata → `missing` (como antes). `get_executions` y `get_closed_pnl_history(strict=True)`
  devuelven None (= «no sé») con error de Bybit o páginas sin leer; closed-pnl recorre todas las páginas. Lo que queda
  sin verificar espera 10 min (`RETRY_EVERY`) antes de volver a pedirse, para no acaparar el tick. Los números van a la
  base como los dio Bybit. Los demás usos de closed-pnl (cierres, conciliación) no cambian.
- **Prueba:** `execution_ledger_test` A14–A17, K1–K6 (cliente de Bybit con páginas y errores simulados) y B16–B24
  (PostgreSQL); B5 fijaba el defecto (precio de salida 9,8 contra 9,78 de los tramos y esperaba «ok»): se corrigió el
  dato. `broker_event_messages_test`: texto del aviso. Código anterior: FALLA (A14, A15 y excepción). Mutaciones 19/19
  (una vigésima mostró una condición redundante: se quitó). Regresión 76 Python + 30 PHP en TODO OK.

### C5-20 · Riesgo por suscripción y modo One-Way (P1) — **One-Way: ya corregido · riesgo propio: válido en parte (latente)** · Instalado en p98 (`3853d5d`, D-52)
- **One-Way:** D-11 / REAL-08 (03-nov, p07). La orden de apertura no lleva `positionIdx`: en Hedge Bybit la rechaza
  entera (nunca queda una posición a medias) y el aviso `open_rejected` explica cómo pasar a One-Way. El bot no cambia
  el modo. Servidor: 0 `open_rejected` en la historia y 0 rechazos por modo en `engine.log`.
  La cuenta 11 **está en One-Way**: sus 13 aperturas se aceptaron sin `positionIdx` (en Hedge Bybit las rechaza).
  El control previo del informe (punto 5) es este rechazo seguro, decidido así en D-11.
- **Riesgo propio (`real_strategy_subscriptions.risk_override_pct`):** reemplaza el `risk_per_trade_pct` de la
  configuración sin validar nada (ni en Laravel ni en el motor ni en la base: solo el CHECK de `status`). No tiene
  pantalla: solo se fija a mano en la base. Con 0 o negativo la suscripción deja de abrir en silencio (solo un warning
  en el log); con un valor absurdo solo lo frena `max_leverage`. El % de la configuración sí se valida (F-03, 0 < r ≤ 100)
  porque viene de un backtest firmado.
- **Servidor (lectura 23-nov 18:20 UTC):** 11 suscripciones de la cuenta 11 (6 activas, 5 pausadas), **ninguna** con
  riesgo propio; 13 configuraciones activas, todas con 1 %. 0 avisos de tamaño ≤ 0. El defecto no ocurrió nunca.
- Nota aparte: 3 suscripciones pausadas (96 HYPE, 98 1000PEPE, 111 LINK H4) no muestran riesgo de configuración (sin
  configuración o sin la clave): pausadas no abren; si se reactivaran usarían 1 % por defecto.
- **Fix (D-52, «Blindarlo» 23-nov):** `RealTrader.subscription_risk(sub)` valida el riesgo (propio o de la configuración;
  1 % si falta la clave) con 0 < r ≤ 100 **antes de cualquier llamada a Bybit**; inválido, no numérico o configuración
  ilegible → no abre y `open_rejected` con el motivo. Base: CHECK `real_strategy_subscriptions_risk_override_check`
  (NULL o 0 < r ≤ 100; migración `2026_11_23_02`, con bajada).
- **Prueba:** `real_sizing_test` V1–V13 (código anterior: 3 FALLOS y excepción con un valor no numérico);
  `subscription_risk_check_test` (nueva: migración contra PostgreSQL en transacción revertida: acepta NULL/0,01/1/100,
  rechaza 0/−1/100,01, idempotente y reversible). Mutaciones 9/9 (una décima, `isfinite`, resultó redundante: se
  quitó). Regresión 76 Python + 30 PHP en TODO OK.

### C5-19 · Tamaño con saldo y precio desactualizados (P1) — **Válido en la forma; impacto medido despreciable** · Instalado en p97 (`3478b66`)
- Confirmado en código: el tamaño se calcula con la primera lectura; si el precio se mueve > 0,5 % se recalculan SL/TP
  pero no el tamaño; el saldo releído solo se guarda. Como el SL va en %, el riesgo real se desvía en la proporción del
  movimiento (1 % de movimiento → 1,01 % de riesgo). El redondeo al paso de Bybit es hacia abajo (solo baja el riesgo).
- **Medido en el servidor (23-nov, 13 operaciones Real):** riesgo real 0,9989 %–1,0013 % contra 1 % configurado
  (máximo 0,13 % relativo, #85 con 0,131 % de movimiento); ninguna superó el 0,5 % (nunca se recalculó).
- **Fix (pequeño):** con movimiento > 0,5 % el tamaño se recalcula con el último precio y el último saldo (mismo tope y
  paso; `_risk_size`); la fila guarda el tamaño enviado; el historial `opened` guarda `risk_planned_pct` y
  `risk_real_pct` (con el fill y el SL final). Las ejecuciones parciales: C5-14 y el libro de p89.

### C5-10 · SL/TP tras 34040 sin confirmar (P1) — **Válido (riesgo bajo)** · Instalado en p97 (`3478b66`)
- Confirmado: 34040 («not modified») se tomaba como éxito sin leer la posición. Atenuante: el monitor compara cada
  minuto los niveles de Bybit con la base y los realinea (R-17), así que una diferencia duraba a lo sumo un minuto.
- **Fix:** con 34040 se leen los niveles de la posición (`confirm_levels`, tolerancia de un paso de precio, la misma del
  monitor); éxito solo si coinciden SL y TP. Sin posición, sin respuesta o niveles distintos = no confirmado (False),
  y el que llamó actúa como ante un rechazo (aviso `protection_failed` / reintento del monitor).

**Prueba p97:** `real_tick_size_test` S2 (ahora exige la confirmación) + S2b–S2e; `real_sizing_test` Z1–Z4. Código
anterior: 7 FALLOS. Mutaciones 6/6. Regresión 75 Python + 30 PHP en TODO OK.

### C5-18 · Límite mensual sin saldo de referencia (P1) — **Válido** · Instalado en p96 (`038e8d9`, D-51)
- `ensure_month_baseline` (antes de cada tick): si Bybit no da el patrimonio, no guarda el saldo inicial del mes y lo
  reintenta al minuto siguiente. Mientras tanto `entry_limit_reason` no puede calcular la pérdida del mes y **permite
  entradas sin el límite mensual**. También permite si la cuenta no existe en la base.
- Agravante menor: si el saldo se toma tarde (p. ej. horas después del día 1), ya descuenta las pérdidas de esas horas
  y el % del mes queda subestimado.
- Servidor hoy: la cuenta 11 tiene saldo inicial del mes (sin bloqueo). Afecta solo a los primeros minutos de cada mes o a
  una cuenta nueva si Bybit no responde.
- **Fix (D-51, «procede» 23-nov):** con límite mensual > 0 y sin saldo inicial válido del mes vigente (fecha del mes en
  Bogotá y saldo > 0) la cuenta no abre; cuenta inexistente = no abre; con límite 0 no se exige. Aviso del vigilante
  (`real_month_baseline`) si pasan 10 min del día 1 sin saldo; se cierra solo al guardarse.
- **Prueba:** `risk_limits_test` L5 (fijaba el comportamiento anterior: «sin saldo inicial → no bloquea»; ahora
  bloquea), L7–L9 nuevos. Código anterior: 5 FALLOS. Mutaciones 4/4. `real_unresolved_test` U8/U10: su doble pasa a
  tener saldo del mes (prueban D-50, no esto). Regresión 75 Python + 30 PHP en TODO OK.

### C5-14 · Orden parcialmente ejecutada y cancelada (P0) — **Válido en parte** · Instalado en p95 (`859f817`)
- **Apertura (`open_trade`): el caso normal no se cumple.** En cada verificación se consulta la posición **antes**
  que el estado de la orden: si hubo llenado parcial, la posición existe y la operación se confirma. Quedaba un caso
  raro: Bybit muestra la orden `Cancelled` con parte ejecutada pero aún no la posición → se marcaba `failed`.
- **Recuperación (`_recover_pending_opens`): confirmado.** `executed` = estado no muerto; con `Cancelled` y
  `cumExecQty > 0` **no se consultaba la posición** y la fila pasaba a `failed`. Después la conciliación veía la
  posición viva sin fila del bot y la trataba como **manual** (D-18): quedaba solo con el SL/TP provisional 2 %/4 %,
  sin break-even, trailing ni cierre por tiempo. Igual en `orphaned` de apertura sin posición (2b): `failed` aunque
  la orden se hubiera ejecutado.
- **Fix:** `executed_qty(order)` (cumExecQty). Con cantidad ejecutada nunca `failed`: se busca la posición; viva → se
  adopta con **el tamaño real de Bybit**; cerrada → se liquida con Bybit. En la apertura, `Cancelled` con parte
  ejecutada sigue verificando y, sin posición visible, queda `orphaned` (la conciliación la resuelve).

### C5-15 · Apertura ejecutada sin guardar en la base (P0) — **Válido, riesgo acotado** · Instalado en p95 (`859f817`)
- Confirmado: tras 4 intentos fallidos del UPDATE a `open` se registraba un CRITICAL y `open_trade` devolvía `True`.
- Mitigación existente: el SL/TP ya estaba en Bybit y la conciliación la adopta a los 3–8 min.
- **Fix:** devuelve `False` y avisa `open_unconfirmed` («ejecutada en Bybit; no se pudo guardar»). La fila queda
  `pending_open`: bloquea entradas (D-50) y el tick adelanta la conciliación (C5-16).

### C5-16 · `orphaned` fuera de la supervisión (P0) — **Válido** · Instalado en p95 (`859f817`)
- Confirmado: fuera del monitor, del circuit breaker, de la selección del tick, del vigilante y del conteo del máximo
  de operaciones (`entry_limit_reason`). Mitigación existente: SL/TP al menos provisional en Bybit y conciliación cada
  5 min.
- **Fix:** (1) las `orphaned` cuentan en el máximo; (2) **D-50:** con una operación en estado dudoso (`orphaned`, o
  `pending_open` de más de 3 min) la cuenta no abre nada; (3) el tick adelanta la conciliación (a lo sumo una por
  minuto): la posición vuelve a `open` (monitor, circuit breaker y vigilante la cubren) en ~1 min en vez de 5;
  (4) aviso al admin si sigue dudosa más de 15 min (`real_unresolved`).
- El circuit breaker no se cambia: actúa sobre posiciones `open`, que es a donde llega una `orphaned` viva en ~1 min.

### C5-17 · La conciliación da por protegida una posición sin SL/TP confirmado (P1) — **Válido** · Instalado en p95 (`859f817`)
- Confirmado: `_adopt_position` ignoraba el resultado de `set_trading_stop` y el evento decía `protected=True`.
- **Fix:** `protected` = lo que confirmó Bybit. La fila queda `open` para que el monitor reintente cada minuto y avise
  `protection_failed` (D-12); la adopción queda en el historial (`adopted`, con tamaño de la base y de Bybit).

**Evidencia del servidor (lectura del instalador de p95, 23-nov 16:10 UTC):** cuenta 11 (demo, activa, máximo 3
operaciones, pérdida mensual 5 %, con saldo inicial del mes); 12 operaciones cerradas (09 al 19-nov) y 1 abierta
(23-nov). **Nunca hubo** `failed`, `orphaned`, `pending_open` ni `pending_close`, ni eventos `open_unconfirmed`,
`open_rejected`, `reconcile_adopted` o `reconcile_discarded`: los defectos de C5-14..17 **no ocurrieron** en
producción (fix preventivo). Hay 3 `protection_failed` (19-nov: el caso 34040 de DOGE #99, R-17) y 8
`reconcile_closed`. Tras instalar: 0 operaciones en estado dudoso (ninguna cuenta bloqueada por D-50).

**Prueba:** `real_unresolved_test.py` (19 casos). Código anterior: 10 FALLOS. Mutaciones 9/9. Regresión 75 Python +
30 PHP en TODO OK. Pendiente: DEMO-01 (parcial cancelada), DEMO-04 (fallo de base tras el fill), DEMO-07 (orphaned viva).

## Resueltos del ciclo (instalados y verificados)

| ID | Fix | Instalado | Verificación |
|---|---|---|---|
| C5-14 | Parcial cancelada: adoptar con el tamaño real o liquidar; nunca `failed` con cantidad ejecutada | p95 `859f817` | Regresión en el servidor; sin casos históricos. Falta DEMO-01 |
| C5-15 | Apertura sin guardar: no informa «abierta»; aviso y conciliación adelantada | p95 `859f817` | Regresión en el servidor. Falta DEMO-04 |
| C5-16 | `orphaned` en el máximo; D-50; conciliación cada minuto; aviso a los 15 min | p95 `859f817` | 0 operaciones dudosas tras instalar. Falta DEMO-07 y DEMO-12 |
| C5-17 | `protected` según Bybit al adoptar | p95 `859f817` | Regresión en el servidor. Falta DEMO-03/05 |
| C5-18 | Sin saldo inicial del mes no se abre (D-51); aviso a los 10 min | p96 `038e8d9` | Cuenta 11 con saldo de 2026-11 (178.118,23): sin bloqueo. Falta DEMO-08 |
| C5-19 | Tamaño recalculado con el último precio y saldo si el precio se movió > 0,5 %; riesgo previsto y real en el historial | p97 `3478b66` | Regresión en el servidor; impacto histórico medido 0,9989–1,0013 % (13 trades). Revisar `risk_real_pct` en las próximas aperturas |
| C5-10 | Tras 34040 se lee la posición y solo se acepta si SL/TP coinciden | p97 `3478b66` | Regresión en el servidor. Falta DEMO-03 |
| C5-20 | Riesgo de la suscripción validado (0 < r ≤ 100) antes de Bybit; CHECK en la base (D-52). One-Way: ya corregido (D-11) | p98 `3853d5d` | 6 suscripciones activas con 1 %; 0 riesgos propios. Sin prueba Demo necesaria |
| C5-01 | Libro de ejecuciones: «ok» solo si cantidad, precio y comisiones cuadran; «no sé» = reintento; aviso a las 24 h (D-53) | p99 `3f31b10` | 13 cerradas `ok` con funding; las 3 abiertas del 23-nov pasaron la regla nueva (`open_ok`). Falta DEMO con parcial |
| C5-07 | Conciliación sin fallos escondidos: cuentas aisladas, `errors`/`pending`/`complete`, aviso `real_reconcile` a los 10 min, marca fija de huérfana (D-54) | p100 `599521a` | 13 cerradas, 3 abiertas, 0 huérfanas tras instalar. Falta DEMO con Bybit caído |
| C5-02 | «No se pudo probar» no es «aprobada»: al guardar sin velas o con error no se guarda; revisión diaria con «sin evaluar» y aviso propio (D-55) | p101 `d4ca055` | Regresión en el servidor; la revisión del 24-nov (04:15) es la primera con la regla nueva |
| C5-09 | Sin defecto: matriz dinámica de permisos (D-46) y aislamiento entre usuarios | — (prueba `role_matrix_test.php`, en el repo desde p102 `637821f`) | Servidor 23-nov 22:42 UTC: 61 rutas·método, 305 comprobaciones, 0 fallos, 0 avisos; 0 usuarios de prueba antes y después |
| C5-04 | Ninguna prueba toca una base que no sea de pruebas: barrera única en 14 pruebas + vigilancia (D-56) | p102 `637821f` | En el servidor el instalador comprobó que las 6 pruebas con base se saltan (no tocan producción) |
| C5-05 | Sin arreglo pendiente: no queda código viejo de VWAP Tendencia en ningún lado (estrategia, 11 configs, 11 backtests, operaciones abiertas) | — | Lectura 23-nov 23:23 UTC: todo con la huella corregida `2cf17fbe`; 0 código viejo |
| C5-03 | Sugerencia rechazada (D-58): se evalúan los 24 meses; pantalla con filtro ≥ +5 %, «Retorno 24 m» antes de los tramos y textos de lo que se evalúa | p103 `0786a92` | 72 búsquedas / 1.287 filas guardadas, filtradas al mostrar |
| C5-06 | El comparador Paper vs backtest dice qué versión compara y avisa si la config cambió después (D-59) | p104 `fbc71cf` | Regresión en el servidor (herramienta manual) |
| C5-08 | Un solo criterio (neto; bruto si falta) para filtro, KPI y curva de Real y el Dashboard (D-60) | p105 `c9cb836` | 14 cerradas, neto +2.942,98, 7 ganadoras con el criterio nuevo |
| C5-11 | Posiciones manuales: un aviso por posición y aviso «Posición manual cerrada» (D-61) | p106 `c7f9090` | 0 posiciones manuales en la historia. Falta DEMO con una manual abierta y cerrada |

# Validación del informe de auditoría — Ciclo 5 (TR2)

> Bitácora de la validación punto por punto del «Informe de auditoría — Ciclo 5» (punto de partida: p91 `6073506`).
> **Método por punto (igual que el ciclo 4):** (1) leer la afirmación; (2) contrastarla con el código vigente y con
> lecturas del servidor; (3) veredicto; (4) si hay fix: propuesta al dueño, prueba que falla con el código anterior,
> mutaciones y regresión completa; (5) registro aquí y en `docs/BITACORA.md`, haya o no fix.
> **Estados:** Pendiente de validar · Validado (con su veredicto) · Implementado (sin instalar) · Instalado (SHA) ·
> Validado en Demo. Un instalador que termina bien no cierra un punto por sí solo (§7.7 del informe).
> **Veredictos:** Válido · Válido en parte · Refutado · Ya corregido · Decisión del dueño.
> Los resueltos van en una lista aparte de los pendientes (§7.10 del informe).

## Pendientes del ciclo

| Orden | ID | Prioridad | Punto | Estado |
|---|---|---|---|---|
| 6 | C5-19 | P1 | Tamaño con balance y precio desactualizados | Pendiente de validar |
| 7 | C5-10 | P1 | Confirmar SL/TP tras 34040 | Pendiente de validar |
| 8 | C5-20 | P1 | Riesgo por suscripción y modo One-Way | Pendiente de validar |
| 9 | C5-01 | P1 | Integridad del libro de ejecuciones y costos | Pendiente de validar |
| 10 | C5-07 | P1 | Conciliación: errores dentro de HTTP 200, estados | Pendiente de validar |
| 11 | C5-02 | P1 | Protección lookahead ante errores | Pendiente de validar |
| 12 | C5-09 | P1 | Matriz dinámica de permisos y aislamiento | Pendiente de validar |
| 13 | C5-04 | P1 | Aislamiento de pruebas con PostgreSQL | Pendiente de validar (p89 ya exige base «*test» en `execution_ledger_test`) |
| 14 | C5-05 | P1 | Cobertura de la reparación de VWAP | Pendiente de validar |
| 15 | C5-03 | P2 | Independencia de la prueba final 60/20/20 | Pendiente de validar |
| 16 | C5-06 | P2 | Comparador con el snapshot vigente | Pendiente de validar |
| 17 | C5-08 | P2 | PnL bruto / neto en estadísticas Real | Pendiente de validar |
| 18 | C5-11 | P2 | Deduplicación de posiciones manuales | Pendiente de validar |
| 19 | C5-12 | P2 | Rótulo del drawdown consolidado | Pendiente de validar |
| 20 | C5-13 | P2 | Infraestructura heredada | Pendiente de validar (respaldo fuera del VPS: descartado, D-48) |
| — | DEMO-01..12 | — | Pruebas de aceptación en Bybit Demo | Pendientes (protocolo por preparar) |

## Validados (con fix implementado o instalado)

### C5-18 · Límite mensual sin saldo de referencia (P1) — **Válido** · Implementado en p96 (D-51)
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

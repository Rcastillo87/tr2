# Decisiones del dueño — TR2 (registro vigente)

> **Regla (D-01, pedido del dueño 13-nov):** lo que está aquí es una regla de negocio decidida por el dueño. **No se
> cambia salvo pedido explícito del dueño.** Antes de preguntarle algo, se busca aquí. Si la respuesta no está o dos
> decisiones chocan, se le pregunta en palabras simples, sin tecnicismos.
> Al tomar una decisión nueva se agrega aquí, en el mismo parche, con fecha, origen y dónde se aplica en el código.
> Si una decisión reemplaza a otra, la anterior queda tachada y con el enlace a la nueva.
> Detalle técnico y pruebas: `docs/BITACORA.md`. Estado de las auditorías: `docs/CERTIFICACION_AUDITORIA.md` y
> `docs/VALIDACION_AUDITORIA_13NOV.md`.

## Usuarios y suscripciones Real

| ID | Decisión | Fecha · origen | Dónde se aplica |
|---|---|---|---|
| D-02 | **Los usuarios no se eliminan: se inactivan.** El borrado propio desde Perfil está deshabilitado (muestra «La eliminación de cuentas está deshabilitada; contacta al administrador»). Un usuario inactivo no entra a la plataforma y **nunca abre operaciones**, aunque se inactive por SQL | 13-nov · validación de la auditoría (R-01, U-1) | `ProfileController::destroy`, `EnsureUserIsActive`, `RealStrategySubscription::runnable()` |
| D-03 | **Suscripción pausada con una operación abierta:** la operación termina su **ciclo completo** según la estrategia (SL, TP, break-even, trailing, tiempo **y salida por señal opuesta**), sin entradas nuevas ni reversas. Pausar ya no sirve para «quedarse» con la posición: para eso se pausa la cuenta o se cierra a mano en Bybit | 13-nov · reemplaza la decisión del 03-nov (BP-02) **solo** para la pausa | `RealStrategySubscription::windingDown()`, `entries_allowed` por suscripción (Laravel y motor) |
| D-04 | **Inactivar un usuario elimina sus suscripciones Real**, para que al reactivarlo elija de nuevo. Las que tienen operaciones vivas siguen sin entradas hasta que esas operaciones terminen su ciclo (como D-03) y **luego se eliminan solas**, aunque el usuario ya esté reactivado (opción a); mientras tanto no se pueden reactivar. Los trades (historial) se conservan | 13-nov | `App\Services\UserDeactivation`, `retire_on_close`, tarea `inactive-users-purge` (cada 5 min) |
| D-05 | **Config Paper apagada («Detener» en Paper) con operación Real abierta:** la operación sigue con SL/TP, break-even, trailing y tiempo, **sin** salida por señal opuesta (igual que Paper, que deja de evaluar esa config) y sin entradas | 03-nov (BP-02), ratificada el 13-nov | `windingDown()` exige config activa; Paper: `config_map` solo con configs activas |
| ~~D-03-ant~~ | ~~Con la suscripción pausada no se aplica la salida por señal opuesta~~ → reemplazada por **D-03** (13-nov) | 03-nov (BP-02) | — |

## Real / Bybit

| ID | Decisión | Fecha · origen | Dónde se aplica |
|---|---|---|---|
| D-10 | **Permisos de la clave API con problemas: solo avisar** (opción A). La cuenta sigue operando; revisión una vez al día | 03-nov (REAL-09) | `_track_permissions` |
| D-11 | **El bot no cambia el modo de posición de la cuenta** (One-Way): es configuración del dueño en Bybit; una cuenta en Hedge falla la apertura con un aviso claro | 03-nov (REAL-08) | `set_trading_stop`, aviso `open_rejected` |
| D-12 | **Si Bybit no acepta el SL/TP de la estrategia: solo avisar.** No se cierra la posición; sigue con el stop provisional y se reintenta cada minuto | 03-nov (REAL-01) | `_monitor_single_trade` paso 2, aviso `protection_failed` |
| D-13 | **SL/TP provisional 2 %/4 % en la orden de apertura**, reemplazado por el de la estrategia tras el fill (Bybit rechazaba aperturas con el SL/TP dentro de la orden) | 03-nov (REAL-02) | `place_market_order` |
| D-14 | **`max_leverage` limita el tamaño** (nocional ≤ saldo × max_leverage); el apalancamiento de la cuenta lo configura el dueño en Bybit | 03-nov (REAL-07) | `open_trade`, motor `_position_size` |

## Datos y collector

| ID | Decisión | Fecha · origen | Dónde se aplica |
|---|---|---|---|
| D-20 | **El collector nunca borra para reparar**: re-descarga de Bybit y UPSERT; los sobrantes se reportan, no se borran | 03-nov (C-03) | `cli/collector_repair.py`, auditoría rotativa |
| D-21 | **Únicas excepciones de borrado de velas:** la recarga explícita (lo que Bybit ya no tiene, tras re-verificar toda la serie) y la invalidación explícita, en una transacción y con registro de lo borrado en `ohlcv_deletions` | 10-nov (N-11, opción a) | `collectors/deletion_log.delete_bars` |
| D-22 | **En vivo, la fuente de velas es solo Bybit** (opción más liviana) | 03-nov (C-11) | `resolve_live_broker` |

## Backtest y búsqueda

| ID | Decisión | Fecha · origen | Dónde se aplica |
|---|---|---|---|
| D-30 | **Tramos de la búsqueda:** un trade que abre antes del corte y cierra después no cuenta en ningún tramo; cada tramo se mide sobre el capital inicial | 10-nov (N-03, opción a) | `segment_stats` |
| D-31 | **TP2, TP3 y TP4 no se reactivan.** Son lógica antigua: se limpian sus residuos en código, UI, API, pruebas y documentación; las columnas de la base se conservan por el historial | 13-nov (informe de auditoría; antes REAL-05 «fuera de alcance», 10-nov) | Pendiente de ejecutar (parche propio) |
| D-32 | **El sistema informa, no recomienda operar:** métricas, estrellas y avisos; la decisión es del dueño | Prompt maestro §1 | — |

## Pendientes de decisión (no asumir; preguntar)

| Tema | Pregunta abierta | Contexto |
|---|---|---|
| Capital del backtest | ¿Capital fijo por operación (como Paper y como dice el informe de auditoría) o compuesto (como hace hoy el motor)? | `VALIDACION_AUDITORIA_13NOV.md` A-1.3a |
| Riesgo por operación | ¿`risk_per_trade_pct` es riesgo antes de costos o neto? (hoy, con SL 1 %, un SL cuesta ~1,16 %) | WB-05, Fase 12 |
| Fin de muestra | ¿La posición abierta al final del backtest (`end_of_data`) cuenta en las métricas? | WB-01 |
| Huecos de datos | ¿Desde cuántas velas seguidas faltantes un backtest no es apto para Paper? | WB-04 |
| Posiciones manuales en Bybit | ¿La conciliación adopta las posiciones abiertas a mano en un símbolo suscrito o las ignora? | R-11 |
| Fase 12 | Opciones estadísticas (drawdown flotante, tramos, costos en el tamaño, cartera, walk-forward) | `docs/FASE12_ESTADISTICA.md` |

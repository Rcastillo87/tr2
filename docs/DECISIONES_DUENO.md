# Decisiones del dueño — TR2 (registro vigente)

> **Regla (D-01, pedido del dueño 13-nov):** lo que está aquí es una regla de negocio decidida por el dueño. **No se
> cambia salvo pedido explícito del dueño.** Antes de preguntarle algo, se busca aquí. Si la respuesta no está o dos
> decisiones chocan, se le pregunta en palabras simples, sin tecnicismos.
> Al tomar una decisión nueva se agrega aquí, en el mismo parche, con fecha, origen y dónde se aplica en el código.
> Si una decisión reemplaza a otra, la anterior queda tachada y con el enlace a la nueva.
> **Especificación del requerimiento:** cada fila es requisito del sistema; «Pendiente de implementar» significa que la
> regla ya está decidida y el código todavía no la cumple (no se vuelve a preguntar).
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
| D-15 | **Motivo de salida de cierres recuperados por la conciliación:** se calcula con el precio de salida de Bybit contra SL/TP (stop_loss, trailing_stop, take_profit_1 o closed_other), igual que el monitor; ya no la etiqueta fija `reconciled_sl_tp_bybit`. **Las 6 operaciones históricas con esa etiqueta (#85, #92, #93, #95, #96, #97) se corrigen** con la misma regla, dejando el valor anterior en su historial (PnL y saldo no cambian) | 18-nov (R-09) | `reconcile` 2a, `ops/datafix/2026_11_18_r09_exit_reason.sql` |
| D-18 | **Las posiciones abiertas a mano en Bybit se ignoran:** la conciliación no las adopta ni las gestiona (sin SL/TP del bot, sin cierre) | 19-nov (R-11) | p74: `reconcile` paso 3 → evento `manual_position_ignored` (una vez por posición) |
| D-19 | **Con una posición manual abierta en una moneda suscrita, el bot no abre en esa moneda.** Cuando la manual se cierra, el bot puede abrir **solo si la señal de apertura sigue vigente** en ese momento (no se recupera una señal vieja). Contexto: los usuarios de la app no operan a mano; es una protección | 19-nov | `check_new_signals` (ya lo cumplía; vigilado por `manual_position_test.py` desde p74) |
| D-17 | **El motivo de salida de un cierre hecho por Bybit es el que dice su orden de cierre** (TakeProfit, StopLoss, TrailingStop); la comparación de precios queda solo como respaldo. Los `closed_other` históricos se reclasifican con ese dato (sin dato de Bybit no se tocan; PnL y saldo no cambian) | 18-nov (R-16, «procede») | `settle_exchange_close`, `real:reclassify-exits` |
| D-16 | **R-10 (guardar el tamaño que confirma Bybit al abrir) queda para después**, como preventivo: no ha ocurrido (10 de 10 operaciones coinciden) y toca el código de apertura | 18-nov | Pendiente (no se toca la apertura) |

## Datos y collector

| ID | Decisión | Fecha · origen | Dónde se aplica |
|---|---|---|---|
| D-20 | **El collector nunca borra para reparar**: re-descarga de Bybit y UPSERT; los sobrantes se reportan, no se borran | 03-nov (C-03) | `cli/collector_repair.py`, auditoría rotativa |
| D-21 | **Únicas excepciones de borrado de velas:** la recarga explícita (lo que Bybit ya no tiene, tras re-verificar toda la serie) y la invalidación explícita, en una transacción y con registro de lo borrado en `ohlcv_deletions` | 10-nov (N-11, opción a) | `collectors/deletion_log.delete_bars` |
| D-22 | **En vivo, la fuente de velas es solo Bybit** (opción más liviana) | 03-nov (C-11) | `resolve_live_broker` |
| D-39 | **Paper y Real deciden solo con la vela completa.** Una vela cerrada se usa cuando la base ya tiene la vela siguiente (el collector las escribe juntas); si no, se espera al minuto siguiente, aunque la entrada se retrase hasta 1 minuto cuando el collector viene atrasado. Vale para la vela operada y para las H4 de los filtros macro y de BTC. La operación de Paper #378 (LINK, abierta el 19-nov con la vela incompleta) **se deja abierta** | 19-nov (R-18) | p76: `final_closed_bars` en `check_new_signals` de Paper y Real; motivo `candle_pending` |

## Backtest y búsqueda

| ID | Decisión | Fecha · origen | Dónde se aplica |
|---|---|---|---|
| D-30 | **Tramos de la búsqueda:** un trade que abre antes del corte y cierra después no cuenta en ningún tramo; cada tramo se mide sobre el capital inicial | 10-nov (N-03, opción a) | `segment_stats` |
| D-31 | **TP2, TP3 y TP4 no se reactivan.** Son lógica antigua: se limpian sus residuos en código, UI, API, pruebas y documentación; las columnas de la base se conservan por el historial | 13-nov (informe de auditoría; antes REAL-05 «fuera de alcance», 10-nov) | Ejecutada en p71 (19-nov): `calculate_tp1`; sin TP2–4 en motor, Paper, Real, reglas, API y Laravel; columnas conservadas |
| D-32 | **El sistema informa, no recomienda operar:** métricas, estrellas y avisos; la decisión es del dueño | Prompt maestro §1 | — |
| D-33 | **Capital del backtest: se queda compuesto** (cada operación arriesga sobre el saldo acumulado, como hoy). Paper sigue con capital fijo de referencia; por eso Paper y backtest se comparan operación a operación en %, no en USDT acumulado | 19-nov (A-1.3a) | `BacktestEngine._position_size` (sin cambio) |
| D-34 | **Riesgo por operación: se queda como hoy** (el % es la distancia al SL, sin costos). Con SL de 1 %, un SL cuesta ~1,16 % del saldo por comisiones y deslizamiento; queda documentado, no se corrige (Fase 12 opción 5 descartada) | 19-nov (WB-05) | `_position_size` en los tres motores (sin cambio) |
| D-35 | **Fin del backtest: la posición que queda abierta al final NO cuenta en las métricas** (se sigue mostrando, marcada `end_of_data`, pero no suma al retorno, drawdown, Sharpe, estrellas ni aptitud para Paper) | 19-nov (WB-01) | p73: `metrics.counted_trades` (métricas, mensual, ventanas, tramos de la búsqueda) |
| D-36 | **Huecos de datos: el backtest se hace igual**; al terminar, el aviso con los huecos (cuántos y el mayor, con fechas) aparece en el **«Log de Errores»** de la pantalla del backtest, aunque la completitud supere el 98 % | 19-nov (WB-04) | p73: `candle_gaps`/`gaps_warning` en `load_backtest_data` → `warnings` («Ver Log de Errores») |
| D-37 | **Se mantiene: completitud < 98 % = backtest «no apto para Paper»** (`quality_ok = false`), además del aviso de D-36 | 19-nov | `MIN_COMPLETENESS` (sin cambio) |
| D-38 | **Fase 12 aprobada:** (1) búsqueda en **tres tramos** 60 % elegir · 20 % aceptar · 20 % solo informar; (2) **simulador de cartera** con un solo saldo, tope de posiciones abiertas y de exposición; (3) renombrar a «Estabilidad por ventanas» ahora y **walk-forward real** después; (4) **drawdown flotante** además del cerrado (se muestran los dos). La opción 5 (costos en el tamaño) queda descartada (D-34) | 19-nov | **Pendiente de implementar** (ver `docs/FASE12_ESTADISTICA.md`) |

## Pendientes de decisión (no asumir; preguntar)

| Tema | Pregunta abierta | Contexto |
|---|---|---|
| Estrategia VWAP Tendencia (R-21) | La banda de desviación (`vwap_std_dev`) usa todas las velas del día: en el backtest incluye velas posteriores a la señal. ¿Se corrige el código de la estrategia (desviación acumulada hasta cada vela) y se repiten sus backtests? | `docs/BITACORA.md` p76 |
| Fase 12 · cartera | Valores por defecto del simulador: tope de posiciones abiertas a la vez y de exposición total (se preguntan al implementar, con una propuesta) | D-38 |

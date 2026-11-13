# Certificación de los hallazgos de las auditorías externas — TR2

> Estado al **2026-11-10 (Bogotá)**, `main` = `d22b684` (p45). Cubre los **54 hallazgos** del informe original
> (`TR2_RESULTADOS_AUDITORIA_HASTA_31-10-2026`, con los textos de REAL-05 y CFG-01, 02, 06–09 recuperados por la
> actualización del 07-nov) y los **16 nuevos (N-01 a N-16)** de esa actualización. Por cada uno: estado, parche o
> decisión, prueba y dónde está el detalle en `docs/BITACORA.md`. Evidencia del 3.er ciclo (fallos antes del fix,
> mutaciones, integración, commits): `docs/RESULTADOS_CICLO_07NOV.md`.
>
> Cada fix se instaló con su prueba forense **antes/después** (falla con el código anterior, pasa con el nuevo),
> mutaciones detectadas y la regresión completa en TODO OK en el servidor. Las pruebas están en `tests/Forensic/` y se
> corren por separado (no con pytest): `cd python-engine && venv/bin/python ../tests/Forensic/<prueba>.py` y
> `php tests/Forensic/<prueba>.php` desde la raíz. Las de **integración** (Laravel + base real, dentro de una
> transacción que se revierte) corren durante la instalación de su parche.

**Estados:** **Corregido** = cambio de código con prueba · **Por diseño** = revisado con el dueño, se mantiene, motivo
documentado · **Cerrado por datos** = verificado contra producción, el caso no ocurre · **Fuera de alcance** = decisión
del dueño · **Fase 12** = decisión estadística pendiente (`docs/FASE12_ESTADISTICA.md`).

## Resumen

| Grupo | Total | Corregido | Por diseño / documentado | Cerrado por datos | Fuera de alcance | Fase 12 |
|---|---|---|---|---|---|---|
| Collector (C) | 12 | 10 | 1 | 1 | 0 | 0 |
| Backtest / Paper (BP) | 8 | 8 | 0 | 0 | 0 | 0 |
| Real / Broker (REAL) | 15 | 8 | 6 | 0 | 1 (REAL-05) | 0 |
| Formulario (F) | 5 | 3 | 1 | 1 | 0 | 0 |
| Ciclo de vida de configs (CFG) | 9 | 3 | 6 | 0 | 0 | 0 |
| Nuevos 2.ª auditoría (NUEVO) | 5 | 3 | 0 | 0 | 0 | 2 |
| **Subtotal informe original** | **54** | **35** | **14** | **2** | **1** | **2** |
| Actualización 07-nov (N) | 16 | 15 | 1 (N-13, por análisis) | 0 | 0 | 0 |
| **Total** | **70** | **50** | **15** | **2** | **1** | **2** |

Cambio respecto de la certificación del 06-nov: los 7 hallazgos «sin texto» quedan clasificados (REAL-05 fuera de
alcance; CFG-01, 02, 06–09 por diseño o documentados), BP-03 y CFG-05 pasan de parcial a corregido (p35, p40b), y la
contabilidad muestra NUEVO-04/05 como categoría propia: **35 + 14 + 2 + 1 + 2 = 54**.

## Collector

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| C-01 | Fallback de configuración desde `.env` | Corregido | p11 | `collector_configs_test.py` | 03-nov «una sola fuente de series» |
| C-02 | Reintentos ante HTTP y límites | Corregido | p12 | `collector_retry_test.py` | 03-nov «reintentos acotados» |
| C-03 | Validación de velas recientes / histórica | Corregido | p13 | `collector_audit_test.py` (+ simulación real: 5.000 velas) | 03-nov «auditoría histórica rotativa» |
| C-04 | Validación de estructura OHLCV | Corregido | p14 | `collector_ingest_test.py` | 03-nov «barrera única» |
| C-05 | Carga inicial y riesgo de timeout | Corregido | p15 | `collector_catchup_test.py` | 03-nov «carga inicial por ventanas» |
| C-06 | Reparación / vigilancia de la validación | Corregido | p16 | `collector_watchdog_validation_test.php` | 03-nov «el vigilante comprueba la validación» |
| C-07 | El vigilante mide frescura, no integridad | Por diseño | — | (cubierto por C-03, C-06) | 03-nov cierre de C-07 a C-09 |
| C-08 | El panel «ok» es solo frescura | Corregido (ya en pantalla) | — | — | 03-nov cierre de C-07 a C-09 |
| C-09 | Carga inicial acepta una vela como histórico | Cerrado por datos | — | lectura real | 03-nov cierre de C-07 a C-09 |
| C-10 | Recarga completa borraba la serie | Corregido; la política de borrado se cerró con N-11 | p17, **p44** | `collector_reload_test.py`, `collector_deletion_test.py` | 03-nov C-10 · 10-nov N-11 |
| C-11 | Selección de fuente de datos en vivo | Corregido | p18 | `live_source_test.py` | 03-nov C-11 |
| C-12 | Funding solo a demanda, con atrasos | Corregido | p26 | `funding_refresh_test.py`, `funding_alert_test.php` | 06-nov C-12 |

## Backtest / Paper

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| BP-01 | `allow_short` en Paper y Real | Corregido | p04 | `allow_short_test.py` | 03-nov BP-01 / REAL-03 |
| BP-02 | Cierre por señal opuesta (Paper y Real) | Corregido | `c8d1223` (Paper); Real: ver bitácora | `paper_opposite_test.py`, `real_opposite_test.py` | 02-nov y 03-nov BP-02 |
| BP-03 | SL/TP de Paper sin 1m | Corregido: huecos internos (p20) y final sin velas con la serie de 1m detenida (p35, N-02) | p20, **p35** | `minute_gap_test.py`, `minute_tail_test.py` | 05-nov BP-03 · 09-nov N-02 |
| BP-04 | Posición abierta al final del histórico | Corregido (`end_of_data`) | p22 | `end_of_data_test.py` | 06-nov BP-04 |
| BP-05 | Hora de salida de Paper = hora de proceso | Corregido (Real: N-16) | p19 | `signal_reuse_test.py` | 05-nov NUEVO-03 / BP-08 / BP-05 |
| BP-06 | Comparador Backtest/Paper | Corregido (reescrito); falta correrlo sobre las configs vivas | p28 | `compare_tool_test.py` (34/34) | 06-nov BP-06 |
| BP-07 | Snapshot sin `strategy_code` | Corregido (defensa; 0 casos) | p25 | `snapshot_code_test.py` | 06-nov BP-07 |
| BP-08 | Señales opuestas y reentradas | Corregido | p19 | `signal_reuse_test.py` | 05-nov NUEVO-03 / BP-08 / BP-05 |

## Real / Broker

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| REAL-01 | Sin aviso si Bybit no acepta el SL/TP | Corregido (aviso/incidente; no garantiza que Bybit acepte) | p05 | `real_protection_test.py` | 03-nov REAL-01 |
| REAL-02 | SL/TP provisional 2 % / 4 % | Por diseño (Bybit rechazaba aperturas con el SL/TP dentro de la orden) | — | — | 03-nov REAL-06 y REAL-02 |
| REAL-03 | `allow_short` | Corregido | p04 | `allow_short_test.py` | 03-nov BP-01 / REAL-03 |
| REAL-04 | Real operaba con la config Paper apagada | Corregido (`scopeRunnable`) | `5017d2e` | `real_config_gate_test.php` (integración) | 02-nov REAL-04 |
| REAL-05 | Residuo de TP2–TP4 | **Fuera de alcance:** lógica antigua, no es parte del producto vigente; no se implementa ni se homologa (decisión del dueño). Las columnas heredadas pueden limpiarse en una fase futura | — | — | 10-nov |
| REAL-06 | Saldo de la cuenta Unified | Corregido | ver bitácora | `real_balance_test.py` | 03-nov REAL-06 |
| REAL-07 | `max_leverage` como límite de nocional | Por diseño, con paridad del tope | p07 | `real_sizing_test.py` | 03-nov REAL-07 |
| REAL-08 | Modo de posición One-Way asumido | Corregido (falla segura + aviso) | p07 | `broker_event_messages_test.php` | 03-nov REAL-08 |
| REAL-09 | Permisos de la clave API | Corregido | p08 | `real_permissions_test.py` | 03-nov REAL-09 |
| REAL-10 | Trailing con buffer 0 | Por diseño (no difiere de Paper/backtest) | p09 | `real_lot_trailing_test.py` | 03-nov REAL-10 / REAL-11 |
| REAL-11 | Lote inventado si falla la consulta | Corregido | p09 | `real_lot_trailing_test.py` | 03-nov REAL-10 / REAL-11 |
| REAL-12 | `risk_override_pct` | Por diseño (si no es null prevalece sobre el riesgo de la config; ninguna suscripción lo usa) | — | — | 03-nov REAL-12 a REAL-15 |
| REAL-13 | Trigger `LastPrice` | Por diseño (paridad con el backtest) | — | — | 03-nov REAL-12 a REAL-15 |
| REAL-14 | Herramientas del bot dependen del tick | Documentado (depende de scheduler y worker activos) | — | — | 03-nov REAL-12 a REAL-15 |
| REAL-15 | Cliente IG sin uso | Corregido (retirado; no se anuncia soporte IG Real) | ver bitácora | — | 03-nov REAL-12 a REAL-15 |

## Formulario de Backtest

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| F-01 | Protección por volatilidad pisada por defaults | Corregido (0 casos afectados) | p23 | `backtest_payload_volatility_test.php`, `volatility_json_test.py` | 06-nov F-01 |
| F-02 | Intervalo 30m | Cerrado por datos (30 se rechaza desde p27) | p27/p29 | `request_rules_test.py` | 06-nov F-05 / F-02 / F-04 |
| F-03 | Validación numérica | Corregido: formulario (p27) y JSON anidado de la estrategia (p45, N-08) | p27, **p45** | `request_rules_test.py`, `strategy_config_types_test.php` | 06-nov F-03 · 10-nov N-08 |
| F-04 | Trailing stepped no ofrecido | Por diseño (ninguna estrategia tiene pasos; stepped sin pasos se rechaza) | p29 | `request_rules_test.py` | 06-nov F-05 / F-02 / F-04 |
| F-05 | JSON parcial reemplaza la config | Corregido (fusión de primer nivel; lo anidado se reemplaza, por diseño) | p29 | `config_merge_test.php` | 06-nov F-05 / F-02 / F-04 |

## Ciclo de vida de configuraciones

| ID | Requisito original | Estado | Parche | Prueba / motivo |
|---|---|---|---|---|
| CFG-01 | Volver a guardar un Backtest propaga los parámetros a sus configs Paper | Por diseño / documentado: auto-sync transaccional en `saveBacktest()`; se aplica en el siguiente tick exitoso; `risk_override_pct` no nulo de una suscripción Real prevalece | — | `autosync_sync_test.php` |
| CFG-02 | Los trades abiertos conservan los parámetros de apertura | Por diseño: Paper y Real gestionan con `config_snapshot`; los cambios afectan solo entradas nuevas | — | `snapshot_code_test.py` |
| CFG-03 | Detener Paper bloquea nuevas entradas Real ligadas | Corregido (`RealStrategySubscription::scopeRunnable`, usado por los ticks Real) | `5017d2e` | `real_config_gate_test.php` (integración) |
| CFG-04 | Quitar un símbolo no deja entradas Real para él | Corregido (`StrategyConfigSync` desactiva la config retirada + `scopeRunnable`) | `5017d2e` | `real_config_gate_test.php` (integración) |
| CFG-05 | Eliminar Backtest/config no deja huérfanos ni pierde gestión | Corregido: `StrategyConfigSync::deleteBacktest` bloquea con config activa, trade Paper abierto o Real en `RealTrade::RECONCILE_STATUSES` (incluye `orphaned`), dentro de la transacción; pausa suscripciones; deja auditoría `deleted` con la identidad en `new_params.deleted` (las FK son `SET NULL`) | **p40b** | `backtest_delete_rules_test.php`, `backtest_delete_test.php` (integración) |
| CFG-06 | Editar la estrategia maestra actualiza las configs desplegadas | Por diseño (versionado por publicación): el código nuevo se publica volviendo a correr y guardar el Backtest | — | Falta explicarlo en la UI (requiere maqueta) |
| CFG-07 | Desactivar la estrategia maestra detiene las configs desplegadas | Por diseño: el interruptor es del catálogo, no un kill switch; los motores usan el estado de la config Paper y de la suscripción Real | — | Falta explicarlo en la UI (requiere maqueta) |
| CFG-08 | Pausar/eliminar una suscripción Real no afecta Paper | Por diseño; los trades Real abiertos siguen gestionados (borrar se bloquea con trades vivos) | — | — |
| CFG-09 | Propagación de cambios y demora | Documentado: polling; se aplica en el siguiente tick exitoso, no al instante | — | — |

## Nuevos de la segunda auditoría (05-nov)

| ID | Hallazgo | Estado | Parche | Prueba |
|---|---|---|---|---|
| NUEVO-01 | Cobertura 1m al 98 % | Corregido (vela incompleta = vela completa con SL primero, homologado con Paper) | p21 | `minute_coverage_test.py` |
| NUEVO-02 | Hora de salida del backtest | Corregido (minuto del evento; métricas idénticas) | p24 | `exit_time_test.py` |
| NUEVO-03 | Señales antiguas tras un cierre (Paper y Real) | Corregido | p19 | `signal_reuse_test.py` |
| NUEVO-04 | Validación fuera de muestra contaminada | Fase 12 (sesgo de selección múltiple). La contaminación por trades que cruzan el corte y por el saldo heredado se corrigió aparte (N-03, p43) | p43 (parcial) | `is_oos_attribution_test.py` |
| NUEVO-05 | Resultados agregados ≠ cartera | Fase 12 (simulador con capital compartido) | — | `docs/FASE12_ESTADISTICA.md` |

## Actualización de la auditoría (07-nov): N-01 a N-16

| ID | Hallazgo | Estado | Parche / commit | Prueba |
|---|---|---|---|---|
| N-01 | Selector Laravel omitía `pending_open` en cuentas pausadas | Corregido (`RealTrade::RECONCILE_STATUSES`) | p34 `9adecbb` | `real_reconcile_statuses_test.php`, `real_reconcile_selector_test.php` (integración) |
| N-02 | Cola de 1m sin velas nuevas en Paper | Corregido (serie detenida > 26 h: velas del intervalo con SL primero, vela a vela) | p35 `1734f98` | `minute_tail_test.py` |
| N-03 | PnL de trades que cruzan el corte en/fuera de muestra | Corregido (los que cruzan no cuentan; tramos al capital inicial). Decisión del dueño (a) | p43 `352ca33` | `is_oos_attribution_test.py` |
| N-04 | `ready_for_paper` ignoraba calidad de datos/costos | Corregido (`quality_ok`; `ready_for_paper` = métricas + calidad) | p42 `c193ee3` | `quality_gate_test.py` |
| N-05 | Cierre Real sin liquidación financiera | Corregido (closed-pnl de Bybit; sin cifras no se cierra) | p33 `01fc216` | `real_close_settle_test.py` |
| N-06 | Funding y `pnl_pct` bruto en el cierre Real | Corregido (neto y costos reales de Bybit; `pnl_pct` neto) | p37 `7abfa89` | `real_close_accounting_test.py` |
| N-07 | Concurrencia tick / circuit breaker / reconciliación | Corregido (turno exclusivo por cuenta; cierre reclamado; UPDATE con estado esperado) | p36 `bf4fce0` | `real_concurrency_test.py` |
| N-08 | JSON anidado de `strategy_config` sin validar | Corregido (tipos de la config guardada, en profundidad) | p45 `d22b684` | `strategy_config_types_test.php` |
| N-09 | Reasignación de trades Paper por `display_name` | Corregido (identidad por id; `StrategyLabel`). Había un caso real: #68/#62 | p38 `387d646` | `strategy_label_test.php`, `strategy_identity_test.php` (integración) |
| N-10 | Flags booleanos sin normalizar | Corregido (`as_flag` en los 7; hoy todos booleanos: defensa) | p39 `bd904e9` | `flag_normalization_test.py` |
| N-11 | Recarga del collector borra / cancelación parcial | Corregido con la decisión del dueño (a): solo recarga e invalidación, una transacción, registro con las velas en `ohlcv_deletions` | p44 `c45cd42` | `collector_deletion_test.py` |
| N-12 | `INTERNAL_API_KEY` fail-open | Corregido (falla cerrada: 503 sin clave; `hmac.compare_digest`) | p41 `b64b4ce` | `engine_hardening_test.py` |
| N-13 | Tamaño Real calculado antes del fill | **Por diseño (cerrado por análisis):** el SL/TP se recalcula con el precio de ejecución; el riesgo efectivo = riesgo × (precio real ÷ estimado), un desvío del tamaño del slippage | — | Bitácora 09-nov |
| N-14 | `add-symbol` con intervalos libres e `INSERT 0 0` | Corregido | p41 `b64b4ce` | `engine_hardening_test.py` |
| N-15 | Backfill con fecha sin zona | Corregido (UTC; servidor ya en UTC: defensa) | p41 `b64b4ce`, p44 | `engine_hardening_test.py` |
| N-16 | `exit_time` Real = hora de proceso | Corregido (hora del cierre en Bybit o de ejecución de la orden) | p37 `7abfa89` | `real_close_accounting_test.py` |

## Pruebas de la regresión (todas en TODO OK en el servidor; lista al 13-nov, p61)

51 Python: `real_native_trailing_sync_test paper_no_minute_source_test opposite_rule_config_test new_strategies_test paper_eval_test broker_limits_scope_test collector_deletion_test is_oos_attribution_test quality_gate_test engine_hardening_test
flag_normalization_test real_close_accounting_test real_concurrency_test minute_tail_test real_close_settle_test
compare_tool_test request_rules_test funding_refresh_test snapshot_code_test exit_time_test volatility_json_test
end_of_data_test param_search_v3_test minute_coverage_test minute_gap_test signal_reuse_test live_source_test
collector_reload_test collector_catchup_test collector_ingest_test collector_audit_test collector_retry_test
collector_configs_test real_lot_trailing_test real_permissions_test real_sizing_test real_balance_test
real_protection_test allow_short_test real_opposite_test paper_opposite_test paper_parity_test real_parity_test
real_recovery_test broker_events_test risk_limits_test strategy_parity_test engine_rules_test engine_speed_parity_test
filters_v2_test bars_order_test`.

18 PHP: `real_tick_results_test paper_diagnostics_test saved_backtests_test rq01_screens_static_test search_create_rules_test backtest_origin_test trades_per_month_test strategy_config_types_test backtest_delete_rules_test strategy_label_test real_reconcile_statuses_test
blade_static_test config_merge_test funding_alert_test backtest_payload_volatility_test broker_event_messages_test
collector_validation_alert_test collector_watchdog_validation_test`.

Integración (Laravel + base real, transacción revertida; corren al instalar su parche): `real_config_gate_test.php`
(REAL-04/CFG-03/04), `real_reconcile_selector_test.php` (N-01), `strategy_identity_test.php` (N-09),
`backtest_delete_test.php` (CFG-05),
`backtest_origin_save_test.php` (RQ-01.3), `search_create_guard_test.php` (RQ-01.2), `rq01_screens_test.php` (pantallas RQ-01), `saved_backtests_screen_test.php` (RQ-01.4), `paper_diagnostics_screen_test.php` (RQ-01.5).

## Límites de esta certificación

- PASS demuestra el caso incluido en la prueba. No demuestra Bybit real, la base productiva bajo carga ni la ejecución
  de Horizon/Scheduler de punta a punta. Las pruebas de integración sí corren contra la base real, sin dejar cambios.
- **Paridad Paper ↔ backtest con datos reales:** la herramienta está lista (BP-06) pero falta correrla sobre las
  configs activas y registrar el resultado.
- **NUEVO-04 / NUEVO-05:** pendientes de la elección del dueño en `docs/FASE12_ESTADISTICA.md`.
- Recomendación vigente del auditor: no aumentar el capital Real hasta tener la paridad con datos reales y las
  decisiones de Fase 12.

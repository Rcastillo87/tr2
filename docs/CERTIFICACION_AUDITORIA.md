# Certificación de los hallazgos de la auditoría externa — TR2

> Estado al **2026-11-06 (Bogotá)**, `main` = `291da9b` (p29). Para el auditor: cada hallazgo con su estado, el parche que
> lo resolvió (o la decisión documentada), la prueba que lo demuestra y dónde está el detalle en `docs/BITACORA.md`.
> Cada fix se instaló con su prueba forense en evidencia **antes/después** (falla con el código anterior, pasa con el
> nuevo), mutaciones detectadas y la regresión completa en TODO OK en el servidor. Las pruebas están en
> `tests/Forensic/` y se corren por separado (no con pytest): `cd python-engine && venv/bin/python ../tests/Forensic/<prueba>.py`
> y `php tests/Forensic/<prueba>.php` desde la raíz.

**Estados:** **Corregido** = cambio de código con prueba · **Por diseño** = revisado con el dueño, se mantiene, motivo
documentado · **Cerrado por datos** = verificado contra producción, el caso no ocurre · **Falta el texto** = el
hallazgo no está transcrito en el repositorio (ver al final).

## Resumen

| Grupo | Total | Corregido | Por diseño / documentado | Cerrado por datos | Falta el texto |
|---|---|---|---|---|---|
| Collector (C) | 12 | 10 | 1 | 1 | 0 |
| Backtest / Paper (BP) | 8 | 8 | 0 | 0 | 0 |
| Real / Broker (REAL) | 15 | 8 | 6 | 0 | 1 (REAL-05) |
| Formulario (F) | 5 | 3 | 1 | 1 | 0 |
| Ciclo de vida de configs (CFG) | 9 | 3 | 0 | 0 | 6 (CFG-01, 02, 06–09) |
| Nuevos de la 2.ª auditoría (NUEVO) | 5 | 3 | 0 | 0 | 0 (NUEVO-04/05: fase 12) |
| **Total** | **54** | **35** | **8** | **2** | **7** |

NUEVO-04 y NUEVO-05 y los otros riesgos estadísticos (walk forward, drawdown flotante, tamaño con costos) no son
defectos de código: son decisiones de diseño, en `docs/FASE12_ESTADISTICA.md`.

## Collector

| ID | Hallazgo | Estado | Parche / commit | Prueba | Bitácora |
|---|---|---|---|---|---|
| C-01 | Fallback de configuración desde `.env` | Corregido | p11 | `collector_configs_test.py` | 03-nov «una sola fuente de series» |
| C-02 | Reintentos ante HTTP y límites | Corregido | p12 | `collector_retry_test.py` | 03-nov «reintentos acotados» |
| C-03 | Validación de velas recientes / histórica | Corregido | p13 | `collector_audit_test.py` (+ simulación real: 5.000 velas comparadas) | 03-nov «auditoría histórica rotativa» |
| C-04 | Validación de estructura OHLCV | Corregido | p14 | `collector_ingest_test.py` | 03-nov «barrera única» |
| C-05 | Carga inicial y riesgo de timeout | Corregido | p15 | `collector_catchup_test.py` | 03-nov «carga inicial por ventanas» |
| C-06 | Reparación / vigilancia de la validación | Corregido | p16 | `collector_watchdog_validation_test.php` | 03-nov «el vigilante comprueba la validación» |
| C-07 | El vigilante mide frescura, no integridad | Por diseño | — | (cubierto por C-03, C-06) | 03-nov C-10, cierre de C-07 a C-09 |
| C-08 | El panel «ok» es solo frescura | Corregido (ya en pantalla) | — | — | 03-nov C-10, cierre de C-07 a C-09 |
| C-09 | (ver bitácora) | Cerrado por datos | — | lectura real | 03-nov C-10, cierre de C-07 a C-09 |
| C-10 | Recarga completa borraba la serie | Corregido | p17 | `collector_reload_test.py` | 03-nov C-10 |
| C-11 | Selección de fuente de datos en vivo | Corregido | p18 | `live_source_test.py` | 03-nov C-11 |
| C-12 | Funding solo a demanda, con atrasos | Corregido | **p26** | `funding_refresh_test.py`, `funding_alert_test.php` | 06-nov C-12 |

## Backtest / Paper

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| BP-01 | `allow_short` en Paper y Real | Corregido | p04 | `allow_short_test.py` | 03-nov BP-01 / REAL-03 |
| BP-02 | Cierre por señal opuesta (Paper y Real) | Corregido | `c8d1223` (Paper); Real: ver bitácora | `paper_opposite_test.py`, `real_opposite_test.py` | 02-nov y 03-nov BP-02 |
| BP-03 | SL/TP de Paper sin 1m | Corregido (el hueco real era un minuto faltante en medio) | **p20** | `minute_gap_test.py` | 05-nov BP-03 |
| BP-04 | Posición abierta al final del histórico | Corregido (`end_of_data`) | **p22** | `end_of_data_test.py` | 06-nov BP-04 |
| BP-05 | Hora de salida de Paper = hora de proceso | Corregido | **p19** | `signal_reuse_test.py` | 05-nov NUEVO-03 / BP-08 / BP-05 |
| BP-06 | Comparador Backtest/Paper | Corregido (reescrito) | **p28** | `compare_tool_test.py` (34/34 con Paper y motor reales) | 06-nov BP-06 |
| BP-07 | Snapshot sin `strategy_code` | Corregido (defensa; 0 casos) | **p25** | `snapshot_code_test.py` | 06-nov BP-07 |
| BP-08 | Señales opuestas y reentradas | Corregido | **p19** | `signal_reuse_test.py` (sondas A y B) | 05-nov NUEVO-03 / BP-08 / BP-05 |

## Real / Broker

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| REAL-01 | Sin aviso si Bybit no acepta el SL/TP | Corregido | p05 | `real_protection_test.py` | 03-nov REAL-01 |
| REAL-02 | SL/TP provisional 2 % / 4 % | Por diseño (Bybit rechazaba aperturas con el SL/TP dentro de la orden) | — | — | 03-nov REAL-06 y REAL-02 |
| REAL-03 | `allow_short` | Corregido | p04 | `allow_short_test.py` | 03-nov BP-01 / REAL-03 |
| REAL-04 | Real operaba con la config Paper apagada | Corregido | `5017d2e` | `real_config_gate_test.php` (necesita Laravel) | 02-nov REAL-04 |
| REAL-05 | — | **Falta el texto** | — | — | — |
| REAL-06 | Saldo de la cuenta | Corregido (explícito) | ver bitácora | `real_balance_test.py` | 03-nov REAL-06 |
| REAL-07 | `max_leverage` | Por diseño, con paridad del tope | p07 | `real_sizing_test.py` | 03-nov REAL-07 |
| REAL-08 | Modo de posición One-Way asumido | Corregido (falla segura + aviso claro) | p07 | `broker_event_messages_test.php` | 03-nov REAL-08 |
| REAL-09 | Permisos de la clave API | Corregido | p08 | `real_permissions_test.py` | 03-nov REAL-09 |
| REAL-10 | Trailing con buffer 0 | Por diseño (no difiere de Paper/backtest) | p09 | `real_lot_trailing_test.py` | 03-nov REAL-10 / REAL-11 |
| REAL-11 | Lote inventado si falla la consulta | Corregido | p09 | `real_lot_trailing_test.py` | 03-nov REAL-10 / REAL-11 |
| REAL-12 | `risk_override_pct` | Por diseño (ninguna suscripción lo usa) | ver bitácora | — | 03-nov REAL-12 a REAL-15 |
| REAL-13 | Trigger `LastPrice` | Por diseño (paridad con el backtest) | ver bitácora | — | 03-nov REAL-12 a REAL-15 |
| REAL-14 | Herramientas del bot dependen del tick | Documentado (inherente; mitigado) | ver bitácora | — | 03-nov REAL-12 a REAL-15 |
| REAL-15 | Cliente IG sin uso | Corregido (retirado) | ver bitácora | — | 03-nov REAL-12 a REAL-15 |

## Formulario de Backtest

| ID | Hallazgo | Estado | Parche | Prueba | Bitácora |
|---|---|---|---|---|---|
| F-01 | Protección por volatilidad pisada por defaults | Corregido (0 casos afectados) | **p23** | `backtest_payload_volatility_test.php`, `volatility_json_test.py` | 06-nov F-01 |
| F-02 | Intervalo 30m | Cerrado por datos (el selector muestra solo los intervalos activos del collector; 30 se rechaza desde p27) | p27/p29 | `request_rules_test.py` | 06-nov F-05 / F-02 / F-04 |
| F-03 | Validación numérica | Corregido (mismas reglas en Laravel y Python) | **p27** | `request_rules_test.py` | 06-nov F-03 |
| F-04 | Trailing stepped no ofrecido | Por diseño (ninguna estrategia tiene pasos; stepped sin pasos se rechaza) | **p29** | `request_rules_test.py` | 06-nov F-05 / F-02 / F-04 |
| F-05 | JSON parcial reemplaza la config | Corregido (fusión) | **p29** | `config_merge_test.php` | 06-nov F-05 / F-02 / F-04 |

## Ciclo de vida de configuraciones

| ID | Hallazgo | Estado | Parche | Prueba |
|---|---|---|---|---|
| CFG-03, CFG-04, CFG-05 | (ciclo de vida Paper → Real) | Corregido con REAL-04 y la propagación Paper → Real | `5017d2e` | `real_config_gate_test.php`, `autosync_sync_test.php` |
| CFG-01, CFG-02, CFG-06 a CFG-09 | — | **Falta el texto** | — | — |

## Nuevos de la segunda auditoría (05-nov)

| ID | Hallazgo | Estado | Parche | Prueba |
|---|---|---|---|---|
| NUEVO-01 | Cobertura 1m al 98 % | Corregido (vela incompleta = vela completa con SL primero, homologado con Paper) | **p21** | `minute_coverage_test.py` |
| NUEVO-02 | Hora de salida del backtest | Corregido (minuto del evento; métricas idénticas) | **p24** | `exit_time_test.py` |
| NUEVO-03 | Señales antiguas tras un cierre (Paper y Real) | Corregido | **p19** | `signal_reuse_test.py` |
| NUEVO-04 | Validación fuera de muestra contaminada | Fase 12 (decisión de diseño) | — | `docs/FASE12_ESTADISTICA.md` |
| NUEVO-05 | Resultados agregados ≠ cartera | Fase 12 (decisión de diseño) | — | `docs/FASE12_ESTADISTICA.md` |

## Pruebas de la regresión (todas en TODO OK en el servidor tras p29)

36 Python: `compare_tool_test request_rules_test funding_refresh_test snapshot_code_test exit_time_test
volatility_json_test end_of_data_test param_search_v3_test minute_coverage_test minute_gap_test signal_reuse_test
live_source_test collector_reload_test collector_catchup_test collector_ingest_test collector_audit_test
collector_retry_test collector_configs_test real_lot_trailing_test real_permissions_test real_sizing_test
real_balance_test real_protection_test allow_short_test real_opposite_test paper_opposite_test paper_parity_test
real_parity_test real_recovery_test broker_events_test risk_limits_test strategy_parity_test engine_rules_test
engine_speed_parity_test filters_v2_test bars_order_test`.
6 PHP: `config_merge_test funding_alert_test backtest_payload_volatility_test broker_event_messages_test
collector_validation_alert_test collector_watchdog_validation_test`.

Sobre el informe del 05-nov: no se puede validar «todos los scripts con pytest»; cada prueba es un script independiente
que imprime `RESULTADO: TODO OK` o el número de fallos.

## Falta el texto (7)

REAL-05 y CFG-01, CFG-02, CFG-06 a CFG-09 están en el informe original (`TR2_RESULTADOS_AUDITORIA_HASTA_31-10-2026`,
carpeta `01_INFORMES`), que no está transcrito en el repositorio. Para cerrarlos hace falta su texto (pegarlo en la
sesión): con eso se verifica cada uno contra el código como el resto.

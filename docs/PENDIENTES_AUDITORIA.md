# Pendientes de la auditoría externa (31-oct) — TR2

> Estado al **2026-11-05 (Bogotá)**. `main` = `247fd27` (p25) + p26 (C-12).
> **Segunda auditoría (05-nov):** confirmó los 11 pendientes y agregó NUEVO-01 a 05. Orden acordado con el dueño (del más crítico al menos) en la sección 0.
> Informes de la auditoría: zip `TR2_RESULTADOS_AUDITORIA_HASTA_31-10-2026` (01_INFORMES). Detalle de lo ya hecho: `docs/BITACORA.md`.
> **Empezar aquí la próxima sesión.** Al cerrar cada fix: tacharlo aquí y en «Próxima sesión» punto 6 de la bitácora.

---

## 0. Orden de la sesión del 05-nov (del más crítico al menos)

Entrega acordada: el dueño solo tiene la interfaz y SSH, **sin subir archivos**. Lecturas con salida corta pegada en el chat; parches como bloque base64 pegable en SSH, envuelto en `( … )`, con md5.

| # | Fix | Estado |
|---|---|---|
| 1 | NUEVO-03 + BP-08 + BP-05 (señal ya operada y hora de salida, Paper y Real) | **Hecho en p19** |
| 2 | BP-03 (Paper sin 1m no evalúa SL/TP): el hueco real era un minuto faltante en medio | **Hecho en p20** |
| 3 | NUEVO-01 (1m con minutos faltantes al 98 %): respaldo por vela, homologado con Paper | **Hecho en p21** |
| 4 | BP-04 (posición abierta al final del backtest): cierre con `end_of_data` (opción a) | **Hecho en p22** |
| 5 | F-01 (volatilidad pisada por defaults): solo viaja si vino en el request; búsqueda alineada (0 casos afectados) | **Hecho en p23** |
| 6 | NUEVO-02 (exit_time del backtest = apertura de la vela grande): minuto del evento, sin cambio de métricas | **Hecho en p24** |
| 7 | BP-07 (snapshot sin `strategy_code`): código de la config viva con parámetros congelados (0 casos hoy) | **Hecho en p25** |
| 8 | C-12 (funding): refresco en la reparación diaria + aviso > 30 h | **Hecho en p26** |
| 9 | F-03 (validación numérica) | Pendiente |
| 10 | BP-06 (comparador) | Pendiente |
| 11 | F-05, F-04, F-02 (formulario; F-04/F-02 con maqueta) | Pendiente |
| 12 | Fase estadística: NUEVO-04 holdout, NUEVO-05 cartera, walk forward, drawdown flotante, tamaño con costos | Pendiente (decisiones de diseño) |

Hallazgo del 06-nov: **`trading2-horizon` corre como root**. Los jobs de las colas escriben con root como dueño (riesgo de permisos en `storage/` y `bootstrap/cache`, y mínimo privilegio). Propuesta pendiente: `User=tr2` en el servicio, revisando antes qué necesita root (si algo). Para reiniciarlo: `systemctl restart trading2-horizon` (no `horizon:terminate` como `tr2`).

Hallazgos propios del 05-nov: Paper dimensiona con `VIRTUAL_BALANCE` fijo y el backtest con saldo acumulado (el PnL absoluto no se puede comparar; los eventos sí); `walk_forward`/`n_windows` quemados en `BacktestingController`.

---

## 1. Cómo se trabaja (acordado con el dueño)

1. **Fix por fix.** Primero verificar que el hallazgo existe de verdad (código + historial de git + datos reales si hace falta), después presentar el plan y **esperar aprobación** antes de programar.
2. **No deshacer diseños deliberados.** Antes de cambiar algo, buscar en git/bitácora si fue intencional (caso REAL-02: SL/TP provisional 2 %/4 % que se mantiene por diseño).
3. Ante varias opciones, el dueño elige **la que menos pesa en el sistema**.
4. Cambios en pantalla: **maqueta aprobada antes** de tocar la vista.
5. Cada fix: prueba forense nueva en `tests/Forensic/` (sin base ni red), evidencia **antes** (falla con el código viejo) y **después**, **mutaciones** detectadas, regresión completa en TODO OK, entrada en la bitácora.
6. Entrega: **un solo bloque SSH** (`pNN_instalar.sh`): base64 de un tgz con `install.sh`, `manifest.txt` y `fixes.bundle`; verifica HEAD y md5 de origen, respalda, aplica con `git pull --ff-only` del bundle, verifica md5 final, lint, pruebas (rollback a la base si alguna falla), reinicio del motor solo sin búsquedas ni órdenes Real pendientes, verificación real y `git push origin main`. Plantilla: el instalador de p18.
7. Commits: autor `Claude <noreply@anthropic.com>`, mensaje en español con las líneas `Co-Authored-By` / `Claude-Session`.
8. Regresión actual (34 Python + 5 PHP; PHP: `funding_alert_test backtest_payload_volatility_test` + las 3 de siempre): `funding_refresh_test snapshot_code_test exit_time_test volatility_json_test end_of_data_test param_search_v3_test minute_coverage_test minute_gap_test signal_reuse_test live_source_test collector_reload_test collector_catchup_test collector_ingest_test collector_audit_test collector_retry_test collector_configs_test real_lot_trailing_test real_permissions_test real_sizing_test real_balance_test real_protection_test allow_short_test real_opposite_test paper_opposite_test paper_parity_test real_parity_test real_recovery_test broker_events_test risk_limits_test strategy_parity_test engine_rules_test engine_speed_parity_test filters_v2_test bars_order_test` + `broker_event_messages_test.php collector_validation_alert_test.php collector_watchdog_validation_test.php`.

---

## 2. Hecho (resumen)

- **Real cerrado:** BP-01/REAL-03, BP-02, REAL-01, 04, 06, 08, 09, 11 corregidos; REAL-02, 07, 10, 12–15 por diseño o documentados; IG retirado.
- **Collector cerrado salvo C-12:** C-01 a C-06, C-10 (p17) y C-11 (p18) corregidos; C-07 por diseño; C-08 ya en pantalla; C-09 cerrado con datos reales.
- **Ciclo de vida de configs (CFG-03/04/05):** resuelto con REAL-04 y la propagación Paper → Real.

---

## 3. Pendientes (11) — en el orden recomendado

Ninguno toca dinero en Real. Afectan a la fidelidad de Paper / backtest y a las decisiones que se toman con esos resultados.

| # | Fix | Prioridad | Estado |
|---|---|---|---|
| 1 | BP-07 | Media (condicional) | Falta lectura de datos |
| 2 | F-01 | **Alta** | Sin verificar |
| 3 | BP-04 | **Alta** | Sin verificar |
| 4 | BP-03 | **Alta** (mitigado) | Sin verificar |
| 5 | BP-06 (+ sondas A/B) | **Alta** | Sin verificar |
| 6 | BP-05 | Media | Sin verificar |
| 7 | C-12 | Media | **Diagnosticado; plan listo, falta aprobación** |
| 8 | F-03 | Media | Sin verificar |
| 9 | F-04 | Baja/media | Sin verificar (UI: maqueta) |
| 10 | F-05 | Baja/media | Sin verificar (UI: maqueta) |
| 11 | F-02 | Baja | Sin verificar (el collector no tiene 30m) |

### 3.1 BP-07 — Trade de Paper sin `strategy_code` en el snapshot queda sin gestionar
- **Informe:** alta, condicionada a que existan snapshots así. `paper_trader.py` `_strategy_for_open_trade()` (línea ~95) devuelve None y el monitor (línea ~394) salta la posición: ni SL/TP ni cierre.
- **Primer paso (lectura, puede cerrarlo sin código):**
  ```sql
  SELECT id, symbol, status, entry_time FROM paper_trades
  WHERE status = 'open' AND (config_snapshot IS NULL OR config_snapshot::jsonb ->> 'strategy_code' IS NULL);
  SELECT count(*) AS cerrados_sin_code FROM paper_trades
  WHERE status = 'closed' AND (config_snapshot IS NULL OR config_snapshot::jsonb ->> 'strategy_code' IS NULL);
  ```
- Si hay abiertos afectados: plan = reconstruir la estrategia desde la config viva con aviso, o cerrar con motivo explícito (decide el dueño).

### 3.2 F-01 — Protección por volatilidad pisada por defaults del controlador
- **Informe:** alta. `BacktestingController.php` líneas ~138–141 manda siempre `volatility_protection_mode` (null), `volatility_atr_multiplier` (2.5) y `volatility_widen_pct` (1.0); la vista no tiene esos inputs; `loader.py` hace `merged.update(params)` y pisa lo guardado en el JSON. Reproducido: JSON `widen / 3.2 / 0.8` terminó en `None / 2.5 / 1.0`.
- **Verificar:** que siga igual en el código actual y si alguna config activa tiene esos campos en su JSON (lectura sobre `paper_strategy_configs` / backtests guardados).
- **Idea de plan:** enviar esos campos solo si vienen en el request (no inventar defaults en el controlador); prueba de precedencia JSON vs formulario.

### 3.3 BP-04 — Posición abierta al final del rango desaparece del backtest
- **Informe:** alta. `backtesting/engine.py` ~468–490: si la última posición no cerró, no aparece en trades ni en métricas (tampoco su mark-to-market). Sesga resultados y búsquedas de parámetros.
- **Verificar** con prueba sintética. **Opciones a presentar:** cerrar a precio de la última vela con motivo `end_of_data` (contado en métricas) vs. reportarla aparte como «abierta al final» sin contarla. Cuidar paridad con búsquedas (`param_search`) y comparador.

### 3.4 BP-03 — Sin velas de 1m, Paper no evalúa SL/TP; backtest usa la vela grande con SL primero
- **Informe:** crítica. `paper_trader.py` ~401–430 (desde C-11 solo Bybit y aviso «sin velas de 1m; SL/TP no evaluados»); backtest `api/v1/backtest.py` ~250–327 y `engine.py` ~437–450.
- **Hoy mitigado:** las 11 configs activas tienen 1m de Bybit (lectura p18). Ocurre solo si se corta el 1m.
- **Idea de plan:** en Paper, sin 1m, evaluar con la vela del intervalo operado y SL primero (misma regla pesimista del backtest) + aviso. Prueba de paridad.

### 3.5 BP-06 — Comparador Paper vs backtest no certifica las configs actuales (+ sondas A/B)
- **Informe:** crítica para verificación. `python-engine/tools/analysis/compare_paper_vs_backtest.py`: fechas por defecto invertidas, solo clases viejas (no `DynamicStrategy`), agrupa por hora redondeada y puede emparejar lados distintos, no coteja hora de evento ni vela de señal, compara PnL (el criterio acordado es paridad de reglas/eventos).
- **Junto con esto:** sondas A y B de `tests/Forensic/paper_opposite_test.py` (bitácora, «Próxima sesión» punto 8): (A) SL dentro de la misma vela que cierra con señal nueva → Paper no entra y el motor sí; (B) señal vieja ignorada + SL a mitad de la vela siguiente → Paper reabre con la señal vieja y el motor no.
- Usar con trades reales de las configs #54, #55, #56 (punto 2 de «Próxima sesión»).

### 3.6 BP-05 — Paper guarda la hora de procesamiento como `exit_time`
- **Informe:** alta (trazabilidad). `paper_trader.py` `close_trade()` (línea ~315, `now = datetime.now(...)` ~338): el backtest guarda la hora de la vela. Precio y motivo son correctos; la hora no.
- **Idea de plan:** guardar la hora del evento (vela 1m que disparó) como `exit_time` y, si hace falta, la de proceso aparte. Revisar que el funding de Paper (`_trade_funding`, usa `exit_lo/exit_hi`) siga igual.

### 3.7 C-12 — Funding fuera del job periódico (diagnosticado; falta aprobación)
- **Verificado:** el funding de Bybit se descarga solo a demanda (backtest y cierre de Paper); `funding_collector.py` guarda tramo cubierto en `funding_coverage`. Backtest avisa en pantalla si falta; Paper solo deja log. Real no depende (usa `closedPnl` de Bybit).
- **Lectura real (03-nov):** 13 monedas; atraso entre 9 h (XRP) y **6 d 21 h** (BTC, BNB, HYPE, LINK, NEAR, SOL, ZEC); 0 activas sin funding; 7 trades Paper cerrados desde el 27-oct, 0 con funding NULL, 1 con 0 (probablemente sin liquidación en su tramo); **0 fallos de funding** en el log de 14 días.
- **Plan propuesto (la opción más liviana):**
  1. Refresco diario en la reparación de las 04:00 (`cli/collector_repair.py`) para las monedas activas del collector: `load_funding(pool, symbol, covered_to, now)` (~13 consultas por día). Un fallo se informa y no frena la reparación.
  2. Aviso en la campana si el funding de una moneda activa queda con > **30 h** de atraso (en el resultado de la validación diaria → `SystemAlerts`), cierre automático al ponerse al día.
  3. Paper: sin cambios (0 casos).
  - Alternativa más pesada: refresco cada hora dentro de la corrida del collector (~13 consultas/h).
  - En la instalación: correr una vez el refresco real para dejar las 13 monedas al día.

### 3.8 F-03 — Validación server-side de valores numéricos
- **Informe:** alta. `BacktestingController::executeAjax()` y `api/v1/backtest.py::BacktestRequest` aceptan SL/TP/riesgo/comisión negativos y ADX invertidos.
- **Idea de plan:** reglas en Laravel (rangos y coherencia) + `Field(gt/ge/le)` y validadores en Pydantic (defensa en el motor). Mensajes en español.

### 3.9 F-04 — `stepped` existe en el motor pero no en el selector (UI → maqueta)
- **Informe:** media/alta. `run.blade.php` selector `trailing_mode` (~366–370) solo `none/fixed/atr`; una config `stepped` se convierte en `null` al re-guardar.
- **Verificar** si alguna config guardada usa `stepped`. Opciones: agregarlo al selector (con `trailing_steps`) o preservar el valor guardado si no se toca.

### 3.10 F-05 — JSON parcial reemplaza la configuración completa (UI → maqueta)
- **Informe:** media. `BacktestingController.php` ~66–75. Opciones: merge sobre lo guardado o aclarar el texto de ayuda.

### 3.11 F-02 — `30m` en el selector sin soporte en el motor
- **Informe:** alta solo si el collector ofrece 30. Hoy el collector tiene 1, 5, 15, 60, 120, 240, D → **baja**. Opciones: quitar 30 de la etiqueta de la vista; además, que el motor rechace intervalos desconocidos en vez de asumir 60 (`engine.py` `INTERVAL_MINUTES.get(..., 60)`).

---

## 4. Otros pendientes (fuera de la lista de la auditoría)

- Aviso de vencimiento de la clave API de la cuenta 11 (vence en ~85 días desde el 03-nov).
- Mejora opcional de pantalla del collector (estado de la auditoría histórica y textos): requiere maqueta.
- Limpieza de residuos TP2–TP4 (legado confirmado por el dueño; no tocar TP1 ni SL).
- Fase de validación estadística (walk forward, holdout).
- Resto de la lista «Próxima sesión» de la bitácora (lotes solapados, funding en pantalla, slippage altcoins, docs 01/02/03).
- Tarea manual del dueño: actualizar las instrucciones del proyecto claude.ai a `docs/PROMPT_MAESTRO.md` V7.1.

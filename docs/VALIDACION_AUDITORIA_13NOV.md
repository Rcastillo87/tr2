# Validación del Informe Maestro de Auditoría (13-nov-2026) — TR2

> Bitácora de la validación punto por punto del «Informe maestro de auditoría técnica TR2» (versión consolidada
> documental, corte 13-nov-2026) y de la revisión propia del código hecha el mismo día.
> **Base:** `main` = `7375e5e` (p58, «Estrategias BNF y Triangulo…»), idéntica al zip revisado.
> **Método por punto:** (1) leer la afirmación; (2) contrastarla con el código de `7375e5e`; (3) prueba o sonda
> reproducible; (4) veredicto; (5) acción (fix con prueba antes/después + mutaciones + regresión, decisión del dueño,
> o evidencia pendiente). Un PASS demuestra el caso probado, no certifica el sistema.
> **Entorno de prueba local:** Python 3.12, `fastapi==0.115.0`, `pandas==2.2.2` (las del servidor), PHP 8.3.
> Regresión oficial antes de tocar nada: **49/49 Python + 17/17 PHP en TODO OK**.

**Veredictos:** **Válido** (el código lo confirma) · **Ya corregido** (resuelto antes, con prueba en la regresión) ·
**Refutado** (el código no hace lo que se afirma) · **Decisión** (no es defecto; lo decide el dueño) ·
**Pendiente de evidencia** (requiere datos del servidor o del exchange).

---

## Resumen (entrega 1: secciones 1 a 3 del informe)

| ID | Punto del informe | Veredicto | Acción |
|---|---|---|---|
| A-1.2.1 | 181 PASS con divergencias: `allow_short=False`, señal contraria, sin 1m, posición abierta al final | Ya corregido | BP-01 (p04), BP-02, BP-03/NUEVO-01/N-02 (p20, p21, p35), BP-04 (p22). Pruebas en la regresión: PASS en `7375e5e` |
| A-1.2.2 | Siete hallazgos iniciales de caja blanca | Pendiente de evidencia | El informe no los enumera en §1–3; se validan cuando lleguen |
| A-1.2.3 | 5 fallos en 162 comprobaciones del formulario | Ya corregido | F-01 a F-05 (p23, p27, p29, p45). `request_rules_test`, `config_merge_test`, `strategy_config_types_test`, `backtest_payload_volatility_test`: PASS |
| A-1.2.4 | Problemas del collector e integridad | Ya corregido | C-01 a C-12 (p11–p18, p26, p44). 11 pruebas `collector_*` en la regresión: PASS |
| A-1.2.5 / P0 | Desactivar una config no impediría entradas Real | Ya corregido | `scopeRunnable` (`5017d2e`) en los dos jobs de tick. Revalidar en `7375e5e` con la prueba de integración (comando abajo) |
| A-1.2.6 | Anomalía de PnL en un trade ETHUSDT | Pendiente de evidencia | Lectura de la base + closed-pnl de Bybit (comando abajo) |
| A-1.3a | Capital: «Backtest usa un capital fijo por operación» | **Válido como discrepancia** | El backtest **compone** (usa el saldo acumulado). Decisión del dueño |
| A-1.3b | TP2–TP4: limpiar residuos | Decisión tomada (limpiar) | Inventario: 21 archivos, 62 ocurrencias. Plan en un parche propio |
| A-1.4a | Walk-forward no realmente fuera de muestra | Válido | `walk_forward` del backtest solo reparte métricas por ventanas; la búsqueda usa 2/3–1/3 (N-03 ya quitó el cruce). Fase 12 |
| A-1.4b | Drawdown sin recorrido intratrade | Válido | La curva de capital solo tiene puntos en los cierres. Fase 12 (drawdown flotante) |
| A-1.4c | Sizing y costos | Válido, medido | Riesgo 1 % y SL 1 % → pérdida real 1,159 % del saldo. Fase 12 (costos en el tamaño) |
| A-3.1 | `exec` del código de estrategia | Válido (riesgo aceptado) | Solo el admin crea estrategias (hay 1 admin). Sin aislamiento posible en el mismo proceso. Documentado |
| A-3.1b | Merge: nivel superior prevalece sobre `strategy_config` | Confirmado (por diseño) | `loader.build_strategy` |
| A-3.1c | Caché LRU confunde versiones | Refutado | La clave de la caché es el texto completo del código: otra versión = otra entrada |
| A-3.2 | Omitido vs `null` vs `false` | Confirmado correcto | Sonda: omitido conserva el JSON; `null` explícito = «ninguno»; los booleanos no aceptan `null` (422) |
| A-3.3a | `exit_on_opposite` prevalece sobre `close_on_opposite` | Confirmado | `engine.py:400-401`, `opposite_exit_rule` |
| A-3.3b | Trailing fixed «buffer mínimo del 1 %» | **Refutado** | Es **0,3 %** (`NATIVE_TRAILING_MIN_BUFFER_PCT`) y solo si el buffer configurado es ≤ 0 |
| A-3.4 | Coincidencia bit a bit con `engine_v3_ref.py` | Confirmado en `7375e5e` | `engine_speed_parity_test.py`: PASS |
| A-3.5a | Paper sin fuente de 1m no evalúa SL/TP | **Válido → corregido e instalado (A-01, p59 `904154d`)** | Prueba nueva: 8 FALLOS antes, TODO OK después, 4/4 mutaciones |
| A-3.5b | Docstring de Paper contradice el orden real | **Válido → corregido (A-02)** | Docstring alineado con el código |
| A-3.6 | Cierre Real: estimación taker 0,055 %, fills parciales | Confirmado; fills parciales = R-10 | Ver revisión propia |

---

## Detalle

### A-1.2.1 · Divergencias de las 181 comprobaciones
Cada divergencia corresponde a un hallazgo ya cerrado, con prueba en la regresión oficial:

| Divergencia | Hallazgo | Código en `7375e5e` | Prueba (PASS local) |
|---|---|---|---|
| `allow_short=False` | BP-01 / REAL-03 | `allows_side()` en motor, Paper y Real | `allow_short_test.py` |
| Señal contraria | BP-02 | motor `run()` paso 1; Paper y Real `check_new_signals`; JSON de la estrategia desde p58 | `paper_opposite_test`, `real_opposite_test`, `opposite_rule_config_test` |
| Ausencia de 1m | BP-03, NUEVO-01, N-02 | `minute_fallback_bars`; `_minute_path` | `minute_gap_test`, `minute_coverage_test`, `minute_tail_test` |
| Posición abierta al final | BP-04 | `end_of_data` | `end_of_data_test.py` |

Pendiente: la paridad con **datos reales** (`compare_paper_vs_backtest.py --config <id>` sobre las configs vivas) sigue sin correrse (pendiente 1.2 de `PENDIENTES_AUDITORIA.md`).

### A-1.2.5 · P0: desactivación de configuraciones Real
- `RealStrategySubscription::scopeRunnable()` = suscripción `active` **y** config Paper `active`. La usan `RealTradingTickJob` (selección de cuentas) y `RealTradingAccountTickJob` (suscripciones enviadas al motor). El motor solo evalúa entradas de las suscripciones que recibe.
- `pauseIfConfigInactive()` y `StrategyConfigSync` desactivan o pausan al quitar un símbolo (CFG-04).
- Observación de paridad: con la config desactivada, una posición **abierta** sigue con SL/TP, BE, trailing y tiempo, pero **ya no sale por señal opuesta**, ni en Real ni en Paper (`config_map` solo tiene configs activas). Es coherente entre los dos; queda documentado.
- **Revalidación en el servidor** (transacción revertida, sin efectos):
  `cd /home/tr2/htdocs/tr2.srv685835.hstgr.cloud && php tests/Forensic/real_config_gate_test.php`

### A-1.2.6 · Anomalía de PnL ETHUSDT
No hay datos en el repositorio. Lectura propuesta (solo lectura):
```
bash ops/dbsql.sh -c "SELECT id, side, entry_price, exit_price, size, pnl, net_pnl, commission, pnl_pct, balance_before, exit_reason, exit_time FROM real_trades WHERE symbol='ETHUSDT' AND status='closed' ORDER BY id;"
bash ops/dbsql.sh -c "SELECT id, e->>'action' a, e->'data'->>'figures' fig, e->'data'->>'fees' fees, e->'data'->>'funding' fund FROM real_trades, jsonb_array_elements(audit_log::jsonb) e WHERE symbol='ETHUSDT' AND status='closed' AND e->>'action'='closed';"
```
Criterio: `pnl` = (salida − entrada) × tamaño; `net_pnl` = `closedPnl` de Bybit; `commission` = `pnl` − `net_pnl`. Los trades #85 y #86 tuvieron `pnl_pct` recalculado en p37 (bruto → neto). Si `figures` = `estimado`, el neto no viene de Bybit y se contrasta con el closed-pnl de la cuenta demo.

### A-1.3a · Capital del backtest: compone (discrepancia con la decisión de negocio)
- **Afirmación del informe:** Backtest y Paper usan un capital fijo de referencia por operación; solo Real varía.
- **Código:** `BacktestEngine._position_size()` usa `self.balance` y `_close()` hace `self.balance += pnl`. Paper usa `VIRTUAL_BALANCE = 10000` fijo.
- **Sonda** (6 trades perdedores seguidos, riesgo 1 %, capital 10.000): tamaños 99,95 → 98,79 → … → 94,29; pérdida 115,89 → … → 109,33 USDT. **El backtest compone.**
- **Efecto:** el % por trade es el mismo en los dos modelos (el tamaño es proporcional al saldo). Lo que cambia es el retorno total, el drawdown en USDT, la curva de capital y las estrellas. Paper y backtest **no** son comparables en USDT acumulado; sí trade a trade en %. Los tramos de la búsqueda ya se miden con el capital inicial (N-03).
- **Decisión del dueño:** (a) el backtest pasa a capital fijo, como Paper y como dice el informe; (b) se mantiene compuesto y se corrige la descripción del negocio; (c) los dos, con un selector.

### A-1.3b · Limpieza de TP2–TP4
Decisión del dueño: limpiar (antes REAL-05 «fuera de alcance»). Inventario en `7375e5e`: 21 archivos, 62 ocurrencias.
- **Motor y estrategias:** `engine.py`, `base_strategy.py` (`calculate_tp_levels`), `api/v1/backtest.py` (`tp2_pct`…), `request_rules.json`.
- **Paper y Real:** `paper_trader.py`, `real_trader.py` (`realized_pnl_partial`).
- **Laravel:** `RealTrade.php`, `BacktestMonthlyExport.php`.
- **Vistas:** `backtesting/run.blade.php`, `trading/accounts.blade.php` (requieren maqueta).
- **Herramientas de análisis y 10 pruebas forenses** (incluida la referencia `engine_v3_ref.py`).

Las columnas `tp2`…`tp4` y `realized_pnl_partial` de la base se conservan por el historial (borrarlas sería una migración aparte). Va en su propio parche, después de los P0/P1.

### A-1.4c · Sizing y costos
El tamaño se calcula con la distancia al SL, sin costos. Pérdida real por cada 1 % de riesgo declarado (comisión 0,055 % + slippage 0,05 % por lado):

| SL | 0,5 % | 1 % | 1,5 % | 3 % |
|---|---|---|---|---|
| Pérdida real estimada | 1,42 % | 1,21 % | 1,14 % | 1,07 % |

Medido en el motor (SL 1 %): **1,159 %** por trade. Igual en Paper y Real (misma fórmula). Fase 12, opción «costos en el tamaño».

### A-3.2 · Omitido vs null vs false (sonda)
JSON de la estrategia con `trailing_mode='atr'`, `allow_short=false`, `tp2_pct=4`:

| Envío | Resultado |
|---|---|
| Omitido | `trailing_mode='atr'`, `tp2_pct=4`, `allow_short=False` (manda el JSON) |
| `null` explícito | `trailing_mode=None`, `tp2_pct=None` (el usuario eligió «ninguno») |
| `allow_short=true` explícito | `allow_short=True` (el formulario prevalece) |
| `allow_short=null` | 422 (los booleanos no aceptan null) |

Correcto. La cadena formulario → motor la cubren `backtest_form_payload_test.php` y `backtest_payload_chain_test`.

---

## Cambios hechos en esta validación (locales, sin instalar)

### A-01 · Paper sin serie de 1m en la fuente en vivo (auditoría §3.5)
- **Antes:** si `resolve_live_broker(símbolo, '1')` devolvía `None` (la fuente no tiene ninguna vela de 1m de ese símbolo), el monitor solo dejaba un WARNING y **nunca** evaluaba SL/TP: la posición quedaba sin gestión salvo el cierre por tiempo. N-02 cubría la serie detenida, no la inexistente.
- **Ahora:** `_no_minute_source_path()` evalúa las velas **cerradas** del intervalo operado desde el punto de control, con SL primero (la regla del backtest sin 1m, de BP-03 y de N-02); sin velas del intervalo, ERROR explícito y nada más. La conversión vela → sub-vela pasa a un único helper `_candle_path()`, que también usa el respaldo de N-02 (sin duplicar código).
- **Archivo:** `python-engine/trading/paper_trader.py`.
- **Prueba:** `tests/Forensic/paper_no_minute_source_test.py`, 9 casos: SL en vela H1, avance del punto de control, sin repetir el ERROR, la vela de entrada nunca antes de la entrada, sin ninguna fuente, y control con 1m (sin cambios).
  - Con el código anterior: **8 FALLOS**. Con el nuevo: **TODO OK**.
- **Mutaciones (4/4 detectadas):**

  | Mutación | Fallos |
  |---|---|
  | Sin respaldo (código anterior) | 8 |
  | Ignorar el punto de control | 1 |
  | `exit_time` antes de la entrada | 1 |
  | Incluir la vela sin cerrar | 3 |

- **Regresión:** 49/49 Python + 17/17 PHP en TODO OK (`minute_gap_test` y `minute_tail_test` incluidas: el helper no cambió N-02).
- **Lectura previa (13-nov):** md5 de `paper_trader.py` = `fa879d07…` (el del repo); 0 trades Paper abiertos; ningún símbolo activo sin serie de 1m → fix defensivo.
- **Instalación:** p59 el 13-nov — regresión 50 Python + 17 PHP en TODO OK, motor reiniciado (16:27:23 UTC), tick de Paper 200, 0 errores en `engine.log`; `main` = `origin/main` = **`904154d`**. **Estado: Validado.**

### A-02 · Docstring de `monitor_open_trades` (auditoría §3.5)
Describía «BE → SL → trailing → volatilidad → TP». Ahora dice el orden real: SL vigente → TP1 → BE → trailing por sub-vela; la volatilidad una vez por ciclo con la vela cerrada; la duración al final; el respaldo con vela completa sin 1m. Solo documentación.

---

## Entrega 2: secciones 4 a 16 del informe (validadas contra `904154d`)

Los IDs del informe se conservan (§15.1). Equivalencias con la certificación anterior (`CERTIFICACION_AUDITORIA.md`):
WB-07 = REAL-05 · FORM-01..05 = F-01..05 · LIFE-01 = REAL-04/CFG-03 · COL-01..12 = C-01..12 · WB-02/WB-06 = NUEVO-04/NUEVO-05.

### 4.1 Caja blanca

| ID | Veredicto | Evidencia en `904154d` | Acción |
|---|---|---|---|
| TR2-WB-01 Fin de muestra | **Corregido, con decisión abierta** | BP-04 (p22): la posición abierta al final cierra con `exit_reason='end_of_data'` (separado de SL/TP/BE/señal), cuenta `closed_at_end`, aviso en pantalla; Trades/mes la excluye (p49). `end_of_data_test.py` PASS. Criterios 1, 2 y 4 cumplidos; el 3 (efecto en estadísticas) es política: hoy **cuenta** en las métricas | Decisión del dueño: (a) se mantiene; (b) excluirla de las métricas; (c) marcar a mercado sin cerrarla |
| TR2-WB-02 Walk-forward | **Válido** | `window_stats()` solo reparte por `entry_time` los trades de UNA simulación en N ventanas: no hay entrenamiento/validación. La búsqueda sí separa 2/3–1/3 sin trades que crucen (N-03) | Fase 12. Mínimo inmediato: renombrar a «Estabilidad por ventanas» (el informe lo acepta) |
| TR2-WB-03 Drawdown | **Válido** | `metrics.calculate_metrics`: curva = capital inicial + PnL acumulado de cierres. Sin recorrido intratrade | Fase 12: drawdown mark-to-market aparte del de cierres. Definición oficial: decisión del dueño |
| TR2-WB-04 Umbral 98 % | **Válido parcial** | `MIN_COMPLETENESS=0.98` = velas / esperadas entre la primera y la última. Por debajo: aviso y `quality_ok=False` (N-04). **Entre 98 % y 100 % no se avisa** y no se dice dónde están los huecos (un 2 % de 24 meses de 1m ≈ 14,6 días). Atenuantes: en 1m cada vela con minutos faltantes se evalúa pesimista y se cuenta (NUEVO-01); el collector repara a diario (C-03) | Fix propuesto: informar n.º de huecos y el mayor hueco de las velas principales; hueco > N velas = `quality_ok=False`. Umbral N: decisión del dueño |
| TR2-WB-05 Sizing y costos | **Válido, medido** | Riesgo 1 % y SL 1 % → **1,159 %** de pérdida real (sonda A-1.4c). Igual en Paper y Real | Decisión: ¿`risk_per_trade_pct` es bruto o neto? Si neto: Fase 12 «costos en el tamaño»; si bruto: decirlo en la UI |
| TR2-WB-06 Multimoneda | **Válido** | `BacktestingController.php:265,281` y `ParamSearchService.php:246` promedian el Sharpe; el retorno se suma | Fase 12 (simulador de cartera). Mínimo: rotular «promedio por moneda» |
| TR2-WB-07 TP2–TP4 | Válido (limpieza decidida) | 21 archivos, 62 ocurrencias (A-1.3b) | Parche propio, después de P0/P1 |

### 4.2 Formulario y API (los 5 FAIL)

| ID | Veredicto | Evidencia en `904154d` |
|---|---|---|
| TR2-FORM-01 Volatilidad / defaults | **Corregido** | p23: `BacktestPayload::volatility()` solo envía lo que vino en el request. `backtest_payload_volatility_test.php` y `volatility_json_test.py` PASS. Omitido/explícito/false/null probados en la sonda A-3.2 |
| TR2-FORM-02 Intervalo 30m | **Corregido** | El selector sale de `CollectorConfig::activeIntervals()` (los 7 intervalos del collector, sin 30); `request_rules.json` rechaza 30 en Laravel y Python (`request_rules_test`). Residuo inofensivo: la etiqueta `'30' => '30m'` en `run.blade.php:188` (se quita en la limpieza) |
| TR2-FORM-03 Validación numérica | **Corregido** | p27 (formulario) + p45 (JSON anidado de la estrategia). Rangos en `request_rules.json`, una sola fuente para Laravel y Python |
| TR2-FORM-04 Trailing stepped | **Por diseño** | Ninguna estrategia define escalones; `stepped` sin `trailing_steps` se rechaza (p29). Sigue disponible desde el JSON de la estrategia |
| TR2-FORM-05 JSON parcial | **Corregido** | p29: fusión por clave de primer nivel (`BacktestPayload::mergeConfig`); `config_merge_test.php` PASS (criterio del informe: cambiar una clave conserva las demás) |

La batería original de 162 no está en el repo; sus 5 fallos tienen hoy prueba propia en la regresión oficial.

### 4.3, 4.4 y 5. Ciclo de vida, snapshots y paridad

| ID / sección | Veredicto | Evidencia |
|---|---|---|
| TR2-LIFE-01 (P0) | **Corregido en código; falta la corrida en el servidor** | `scopeRunnable()` en los dos jobs Real; trades abiertos gestionados aparte (monitor por cuenta). Prueba de integración `real_config_gate_test.php` (transacción revertida) |
| 4.4 Snapshots | **Cumple; mejora menor** | Paper y Real guardan en `config_snapshot` los parámetros efectivos **y el `strategy_code` completo**: la operación se reconstruye sin la config viva. El fallback BP-07 solo actúa si falta el código (0 casos). Mejora MEJ-002: agregar hash del código (`md5`) para identificar la versión sin comparar textos |
| 5.1 Carga | Confirmado | Mismo `build_strategy`. Warmup: backtest 500 velas previas, Paper/Real las últimas 500 (indicadores con memoria larga pueden diferir un poco; por eso BNF usa SMA) |
| 5.2 Capital | **Discrepancia (= A-1.3a)** | El informe repite «Backtest con capital fijo». El motor **compone**. Pendiente la decisión del dueño |
| 5.3 Señal contraria | Confirmado | Motor, Paper y Real con la misma regla y pruebas (`paper_opposite_test`, `real_opposite_test`, `opposite_rule_config_test`) |
| 5.4 Sin 1m | **Corregido (A-01, p59 `904154d`)** | Paper ya no deja de evaluar SL/TP sin broker de 1m |
| 5.5 Orden intravela | Confirmado + docstring corregido (A-02) | SL → TP1 → BE → trailing en motor y Paper |
| 5.6 Break-even | Confirmado | Motor y Paper: `max(sl, entry)`; Real: igual + reintento si Bybit rechaza un SL cruzado |
| 5.7 Trailing | **«Buffer 1 %» refutado** | 0,3 % y solo con buffer ≤ 0. TST-08 debe corregirse a 0,3 % |
| 5.8 Volatilidad | Confirmado | ATR de la última vela cerrada, una vez por ciclo en vivo, `vol_widened` una vez por trade en los tres |
| 5.9 Duración | Diferencia conocida | Backtest cuenta velas; Paper/Real, tiempo desde `entry_time` (≤ 1–2 min después). README §9 |
| 5.10 Costos | Confirmado | Real mide el slippage contra el precio de mercado al decidir, no contra el open de la vela como el backtest |

### 6. Datos y collector

| ID | Veredicto | Evidencia |
|---|---|---|
| TR2-COL-01 a COL-07 | **Corregidos** (= C-01 a C-07) | p11–p16 y C-07 por diseño; pruebas `collector_*` PASS. COL-07: la validación de 300 velas se complementa con la auditoría histórica rotativa (C-03, `COLLECTOR_AUDIT_BUDGET`) |
| **TR2-COL-08 a COL-12** | **Recuperados del expediente original** (no reconstruidos) | `CERTIFICACION_AUDITORIA.md`: C-08 el panel «ok» es solo frescura (corregido) · C-09 carga inicial con una vela (cerrado por datos) · C-10 la recarga borraba la serie (p17, p44) · C-11 selección de fuente en vivo (p18) · C-12 funding con atrasos (p26) |
| 6.3 Impacto en Real | Confirmado sin dependencia directa | Real ejecuta en Bybit; usa la base solo para señales, régimen, ATR y mechas de BE |

### 7 y 8. Real y la anomalía ETHUSDT

- **7.1** confirmado: SL/TP provisional 2 %/4 % (REAL-02, por diseño), recálculo si el precio se mueve > 0,5 %, aviso > 2 %, niveles finales con el `avgPrice`.
- **7.2** `move_sl`: si Bybit rechaza, la DB no cambia y se reintenta; si Bybit acepta y la DB no se actualiza, el paso de alineación vuelve el exchange al SL de la DB y el BE/trailing se recalcula al ciclo siguiente (se corrige solo).
- **7.4** confirmado: los tramos son del exchange, no TP2–TP4.

**TR2-REAL-INV-006 (ETHUSDT).** Con las cifras del informe:

| Dato | Valor |
|---|---|
| Bruto con la cantidad mostrada (36,1998) | −314,21 USDT |
| PnL registrado | −174,82 = **exactamente** balance posterior − balance previo |
| `pnl_pct` | −174,82 / 49.271,60 = −0,3548 % (coherente: neto sobre saldo previo, p37) |
| Cantidad que explicaría −174,82 sin costos | ≈ 20,14 ETH |
| Nocional con 36,1998 | 74.439 USDT = **1,51×** el saldo; con `max_leverage` 1 el tope sería 23,96 ETH |
| Movimiento contra el short | 0,42 % en 46 min, y salió por **circuit breaker** |

Hipótesis a contrastar (ninguna demostrada):
- **H1:** la cantidad mostrada no es la ejecutada (llenado parcial: R-10, el tamaño no se actualiza tras el fill).
- **H2:** el closed-pnl sumó solo parte de los tramos.
- **H3:** el circuit breaker saltó con 0,42 %, lo que solo es posible si la referencia era el SL vivo (BE o trailing) cerca de la entrada; eso implica que el SL de Bybit **no** estaba donde decía la DB, que es justo lo que el circuit breaker vigila.

Por H3 este punto sube a **P1**. Evidencia: lectura `lectura_INV006` (fila, `audit_log` completo y config).

### Evidencia del servidor (13-nov 16:37 UTC, lectura `lectura_INV006_BASELINE`)

**Baseline (TR2-MEJ-001):** `904154d` (p59), `main` = `origin/main`. PHP 8.4.22, Laravel 13.15.0, Python 3.12.3, fastapi 0.115.0,
uvicorn 0.30.6, pandas 2.2.2, numpy 2.0.1, asyncpg 0.29.0, pydantic 2.8.2, httpx 0.27.0, PostgreSQL 16.14,
TimescaleDB 2.27.2, 38 migraciones Laravel (última `2026_10_22_100006_add_hash_to_backtests`), 17 migraciones SQL,
frontend `public/build/manifest.json` md5 `4318c5a4…`.

**TR2-LIFE-01 (P0): Validado en el servidor.** `real_config_gate_test.php` (Laravel + base real, transacción revertida;
Z1 confirma la base intacta):
- A2–A5: config desactivada, reactivada, huérfana y suscripción pausada se comportan bien; los controles con el filtro viejo reproducen el bug.
- B1: `runnable()` coincide con el SQL crudo (6 = 6).
- C1: SKIP, la cuenta tiene posiciones abiertas.
- **D: FAIL de la prueba, no del código** (R-13). `ArgumentCountError`: `destroyBacktest()` recibe `StrategyConfigSync` desde p40b y la prueba (de `5017d2e`) llama con un solo argumento. Las pruebas de integración no están en la regresión, así que quedó sin detectar. La regla que mide D (no borrar con Real abierto) la cubren `backtest_delete_rules_test.php` y `backtest_delete_test.php` (p40b).

**TR2-REAL-INV-006 (ETHUSDT): la contabilidad cuadra exactamente.** El trade es el **#91** (#86 es otro igual):
- La «cantidad 36,1998» del informe es la **comisión** (36,19979), no la cantidad. La cantidad real es **15,97 ETH** (1,5 % de riesgo con 10× de apalancamiento de cuenta; nocional 32.840 = 0,67× el saldo).
- Bruto = (2056,33 − 2065,01) × 15,97 = **−138,62** = `pnl`.
- Comisiones = 15,97 × (2056,33 + 2065,01) × 0,055 % = **36,20** = `fees` de Bybit (`openFee` + `closeFee`). Funding = 0.
- Neto = **−174,82** = closed-pnl de Bybit (`figures: bybit`) = saldo posterior − saldo previo.
- `pnl_pct` = −174,82 / 49.271,60 = −0,3548 %.
- **Sin error de cálculo**: cerrado por evidencia.

**R-12 (P1, nuevo y confirmado) — Causa raíz del cierre por circuit breaker: el trailing nativo se «sincroniza» antes de activarse.**
- En `_monitor_single_trade` paso 4, con `trailing_mode='fixed'`, el bot lee `get_native_trailing_level()`: el `triggerPrice` de la orden `TrailingProfit` en estado `Untriggered`.
- **Antes de activarse** (el precio aún no tocó `activePrice`), Bybit informa ahí `activePrice ± trailingStop`. El bot lo toma como SL vivo desde el **primer minuto**: escribe `sl` = ese nivel y `trailing_applied = true`.

| Trade | `activePrice` + `trailingStop` | `sl` en la DB | Posición del `sl` | `be_activated` |
|---|---|---|---|---|
| #86 | 2055,5224 + 20,932 = 2076,454 | **2076,45** | 0,8 % en zona de ganancia, por debajo del precio de un short | false |
| #91 | 2019,31606 + 20,5633 = 2039,879 | **2039,87** | 0,8 % en zona de ganancia, por debajo del precio de un short | false |

El precio nunca llegó al BE (1,5 %) ni a la activación (1,8 %).

- **Efecto:** el circuit breaker usa ese SL ficticio con tolerancia trailing 1 % × 1,2. Saltó con solo **+0,39 % / +0,42 % en contra** (log: «retrocedio 1.253% desde el nivel de referencia (2039.87)»), cuando el SL real en Bybit seguía en +1,5 %. Los 2 de 2 cierres por circuit breaker de ETHUSDT son este caso: −200,91 y −174,82 USDT netos.
- **Divergencia:** el backtest y Paper solo activan el trailing con ganancia > 1,8 %. Real cerraba cualquier trade con trailing `fixed` en cuanto se movía unos 0,4 % en contra.
- **Fix propuesto (p60):** sincronizar el nivel nativo solo si el trailing está **activado**; el precio extremo desde la entrada (1m cerradas y precio actual) debe haber alcanzado `activePrice`, recalculado con `compute_native_trailing_params` o tomado del `audit_log`. Además, un SL solo se acepta del lado protector del precio actual. Reparar los trades abiertos afectados (si los hay) en la instalación. Prueba con #86/#91 como casos reales.

### 9 a 16. Seguimiento, mejoras, pruebas y plan

| ID | Estado | Nota |
|---|---|---|
| FIX-PAPER-DOC-01 | **Validado** (A-02, p59 `904154d`) | |
| TR2-MEJ-001 Trazabilidad | En curso | Este documento fija SHA por punto; falta la foto de versiones (lectura `lectura_BASELINE`) |
| TR2-MEJ-002 Parámetros por operación | Casi cumplido | El snapshot ya trae código y parámetros; falta hash/versión |
| TR2-MEJ-003 Harness de paridad | Parcial | `compare_paper_vs_backtest.py` (eventos por config) + `paper_eval_log`; falta correrlo sobre las configs vivas |
| TR2-MEJ-004 Ledger de ejecuciones | Válido | Hoy: `audit_log` + closed-pnl; no se guardan los fills. Necesario para INV-006 y TST-18 |
| TR2-MEJ-005 Calidad de datos | = WB-04 | |
| TR2-MEJ-006 TP2–TP4 | = WB-07 | |
| TR2-MEJ-007 Mark-to-market | = WB-03 | |
| TR2-MEJ-008 Contrato único | **Cumplido** | `request_rules.json` es la fuente única UI/Laravel/Python (p27) |
| TR2-MEJ-009 Observabilidad 1m | Parcial | Diagnóstico de Paper (RQ-01.5) registra motivos; el modo de gestión (1m / respaldo / espera) solo va al log |
| TR2-MEJ-010 Máquina de estados de cierre | Implementada, sin documentar | Estados `pending_open → open → pending_close → closed`, `orphaned`, `failed`, UPDATE con estado esperado (N-07). Falta el diagrama en `02_TECHNICAL` |
| TST-01 a TST-25 | Cobertura | Con prueba en la regresión: 03–06, 09–11, 16, 17, 19, 21–24. Parcial: 07 (BE cubierto por las pruebas de paridad, sin caso de gap que lo atraviese). Sin prueba: 12, 13, 14 (dependen de Fase 12), 18 y 20 (DEMO), 25 (limpieza), 01–02 (paridad con datos reales). **TST-08 mal especificado** (1 % → 0,3 %) |
| §12 Freqtrade | No iniciado | Fase posterior; no se toca `/root/freqtrade` sin autorización |

## Revisión propia del código (13-nov), con evidencia del servidor

Confirmado en producción el 13-nov:
- Llaves foráneas: `users → broker_accounts / real_strategy_subscriptions / real_trades` = **CASCADE**; `real_trades.broker_account_id` = SET NULL.
- Usuarios: 1 `admin`, 1 `inversionista`, **0 `consultor`**.

| ID | Prioridad | Hallazgo | Estado |
|---|---|---|---|
| R-01 | **P1** | `DELETE /profile` (Breeze) permite a cualquier usuario borrarse. Con CASCADE se borran sus cuentas, suscripciones y **todos sus `real_trades`**; las posiciones abiertas en Bybit quedan sin gestión. **Confirmado con las FK reales** | Abierto: propuesta = quitar la ruta y bloquear en el controlador (la vista requiere maqueta) |
| R-02 | P2 (latente) | El rol `consultor` puede implementar, detener y borrar backtests, y su guardado sincroniza Paper → Real. Hoy no hay consultores | Abierto: gate propio para lo que muta Paper/Real |
| R-03 | **P1 rendimiento** | Dashboard: `ROW_NUMBER()` sobre toda la serie de 1m por moneda. PostgreSQL local: 2.218 ms contra 1,4 ms acotado | Abierto |
| R-04 | P2 | `openTrades()` de la suscripción no incluye `orphaned`, y `BrokerAccountController::destroy` no mira trades vivos: una cuenta se puede borrar con un trade sin reconciliar | Abierto |
| R-05 | P2 | `python-engine/.env.example` pide el `APP_KEY` de Laravel para `laravel_crypt.py`, que es código muerto (y depende de `cryptography`, que no está en `requirements.txt`) | Abierto: borrar el módulo, quitar la clave del `.env` del motor |
| R-06 | P2 | `/backtest/run` hace CPU en el event loop del único proceso: frena ticks Real, circuit breaker y conciliación (aprox. 1,7 s local por backtest de 24 m) | Abierto |
| R-07 | P3 | Un 422 del motor por un campo de cuenta faltante devuelve la cuenta con `api_secret`, y los jobs registran `$response->body()`. Reproducido | Abierto: quitar `input` del 422 |
| R-08 | P3 | `RealTradingReconcileJob`: `timeout` 120 > `retry_after` 90 | Abierto |
| R-09 | P3 | El monitor Real busca el closed-pnl desde `updated_at` (no `entry_time`): falso `orphaned` temporal y motivo de salida perdido | Abierto |
| R-10 | P3 | Tras el fill no se guarda el tamaño real de la posición | Abierto |
| R-11 | Decisión | La conciliación adopta cualquier posición del símbolo suscrito, incluidas las manuales | Decisión del dueño |
| **R-12** | **P1** | Trailing nativo `fixed` «sincronizado» antes de activarse: SL ficticio en la DB y circuit breaker prematuro (#86, #91; #93 abierto y afectado el 13-nov). Ver «Evidencia del servidor» | Corregido en p60: prueba 7 FALLOS → TODO OK, 7/7 mutaciones. Instalación: se registra al instalar |
| R-13 | P3 | `real_config_gate_test.php` (integración) desactualizada desde p40b: la sección D falla por la firma de `destroyBacktest` | Corregido en p60; corre en el instalador |

**Código muerto:**
- `RealTrader.get_active_subscriptions` (lee claves cifradas).
- `laravel_crypt.py`.
- `RegisteredUserController` y la vista de registro.
- Validaciones de clave repetidas en los endpoints Real.
- `CORSMiddleware`, importado sin uso.
- `datetime` redefinido en `collector.py:125`.

**Documentación desalineada:**
- `PROMPT_MAESTRO` V7.3 sin p48–p58.
- `PENDIENTES` (p56, 47+17) frente a `CERTIFICACION`/README (p58, 49+17).
- Orden de la tabla de migraciones del README.
- Permisos del `.env`: el ejemplo dice 600 y la bitácora dice «no 600».

---

## Próximos pasos
1. ~~Recibir las secciones siguientes del informe~~ (entrega 2 validada el 13-nov).
2. Decisiones del dueño: A-1.3a (capital), R-11 (adopción); confirmar R-01 (bloquear el borrado propio).
3. Evidencia del servidor: `real_config_gate_test.php` (P0) y las lecturas de ETHUSDT (A-1.2.6).
4. Instaladores, de a uno y del más crítico al menos (revisado 13-nov tras la evidencia): **R-12** → R-01 → R-03 → A-01 → R-04 → R-05/R-07 → R-06 → R-08/R-09/R-10 → TP2–TP4 → limpieza y documentación (PROMPT V7.4).

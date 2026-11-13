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
| A-3.5a | Paper sin fuente de 1m no evalúa SL/TP | **Válido → corregido (A-01)** | Prueba nueva: 8 FALLOS antes, TODO OK después, 4/4 mutaciones |
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
- **Instalación:** p59 (solo reinicia el motor). Resultado: se registra al instalar.

### A-02 · Docstring de `monitor_open_trades` (auditoría §3.5)
Describía «BE → SL → trailing → volatilidad → TP». Ahora dice el orden real: SL vigente → TP1 → BE → trailing por sub-vela; la volatilidad una vez por ciclo con la vela cerrada; la duración al final; el respaldo con vela completa sin 1m. Solo documentación.

---

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
1. Recibir las secciones siguientes del informe (incluidos los siete hallazgos de caja blanca) y validarlas igual.
2. Decisiones del dueño: A-1.3a (capital), R-11 (adopción); confirmar R-01 (bloquear el borrado propio).
3. Evidencia del servidor: `real_config_gate_test.php` (P0) y las lecturas de ETHUSDT (A-1.2.6).
4. Instaladores, de a uno y del más crítico al menos: R-01 → R-03 → A-01 → R-04 → R-05/R-07 → R-06 → R-08/R-09/R-10 → TP2–TP4 → limpieza y documentación (PROMPT V7.4).

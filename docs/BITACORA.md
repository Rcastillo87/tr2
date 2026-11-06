# Bitácora de cambios — TR2

> Registro cronológico de lo que cambió, por qué y cómo se verificó. Lo más reciente arriba.
> Incluye los cambios que **no viven en git** (configuración de la base, datos, servidor): sin esta bitácora se perderían.
> Horas en UTC salvo que se indique. Commits en `main` de `github.com/Rcastillo87/tr2`.

---

## ▶ Próxima sesión (empezar aquí)
1. **Primero:** revisión automática de lotes solapados dos veces al día, después de `policy_compression` (detección: `runuser -u postgres -- psql -d trading2 -tA < /root/patches/batches/detect.sql`; arreglo: `decompress_chunk` + `compress_chunk` solo de los fragmentos afectados; dejar registro y aviso en la campana).
2. Comparar paper contra backtest con trades reales (configs #54, #55, #56) cuando tengan operaciones cerradas.
3. Funding en pantalla (diseño "TR2 — Funding en pantalla").
4. Slippage de altcoins en demo (SOL, SUI, LINK).
5. Reescribir `docs/01`, `02` y `03`.
6. **Auditoría externa (31-oct):** **empezar por `docs/PENDIENTES_AUDITORIA.md`** (11 pendientes con prioridad, estado y plan; C-12 diagnosticado y con plan listo). Historial de la lista: ~~`allow_short` en Paper y Real (BP-01/REAL-03)~~ hecho 03-nov, ~~cierre por señal opuesta en **Real** (BP-02)~~ hecho 03-nov (motor reiniciado 15:56 UTC: la cuenta 11 ya se puede reanudar), ~~aviso al dueño si falla `set_trading_stop` (REAL-01)~~ hecho 03-nov, ~~REAL-02~~ se mantiene por diseño, ~~REAL-06~~ hecho 03-nov, ~~REAL-07~~ correcto por diseño + paridad del tope, ~~REAL-08~~ falla segura + aviso claro (03-nov, p07), ~~REAL-09~~ permisos de la clave (03-nov, p08), ~~REAL-10~~ ya homologado + constante compartida, ~~REAL-11~~ lote real con caché (03-nov, p09), ~~REAL-12 a REAL-15~~ por diseño / informativos, IG retirado (03-nov, p10). **Real cerrado.** Collector: ~~C-01~~ una sola fuente de series (03-nov, p11), ~~C-02~~ reintentos acotados (03-nov, p12), ~~C-03~~ auditoría histórica rotativa (03-nov, p13), ~~C-04~~ barrera de velas inválidas (03-nov, p14), ~~C-05~~ carga por ventanas sin bloquear (03-nov, p15; resuelve también buena parte de C-09), ~~C-06~~ vigilante de la validación diaria (03-nov, p16), ~~C-07~~ por diseño, ~~C-08~~ ya resuelto en la pantalla, ~~C-09~~ cerrado con datos reales, ~~C-10~~ recarga sin borrar (03-nov, p17), ~~C-11~~ en vivo solo Bybit (03-nov, p18); sigue C-12, luego Backtest/Paper (BP-03 a BP-07, sondas A/B) y formulario (en revisión con el dueño).
7. **Seguridad:** `python-engine/.env` y `.env` tienen permisos 664 pero `/home/tr2` es 770 (`tr2:tr2`), así que otros usuarios no llegan a ellos y `tr2` ya lee las mismas claves en el `.env` de Laravel. **No poner 600** (PHP no podría leer su `.env`). Sin acción. El dueño pondrá el repo en privado (estuvo público solo para validar).
8. ~~**Entradas de Paper distintas del motor (sondas A y B)**~~ hecho 05-nov (p19, NUEVO-03 / BP-08 / BP-05, también en Real).
- **Tarea manual del dueño:** las instrucciones del proyecto "Ruben Castillo" en claude.ai siguen en V6.2. Reemplazarlas por el contenido de `docs/PROMPT_MAESTRO.md` (V7.1; copia en el proyecto: `claude/PROMPT_MAESTRO_V7.1.md`). No se puede hacer por script.

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
- (se completa al instalar p27)

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

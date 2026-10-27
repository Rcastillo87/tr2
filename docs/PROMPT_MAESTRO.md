# PROMPT MAESTRO V7 — Proyecto TR2 (trading algorítmico)

> Documento para entregar a la persona o IA que retome el proyecto. Léelo completo antes de proponer cualquier cambio.
> Versión 7.0 · 2026-10-26 · Reemplaza al Prompt Maestro V6.2.
> Complementos: `README.md` (cómo funciona y cómo se opera) y la bitácora `claude/bitacora-tr2-2026-10.md` del proyecto "Ruben Castillo" (decisiones, commits y verificaciones).

---

## 1. Qué es y por qué importa

- **TR2** es una plataforma de trading algorítmico sobre **Bybit (perpetuos USDT)**: backtesting, búsqueda de configuraciones, paper trading y trading real con la **misma lógica** en los tres.
- **Maneja dinero real.** Un error lógico puede causar pérdidas. La rigurosidad técnica y matemática no se negocia: nada de cajas negras ni resultados inflados.
- **Objetivo actual:** que el backtest sea honesto y que paper y real sean réplicas del backtest, antes de poner capital real con una estrategia.
- **El dueño decide.** El sistema informa (métricas, estrellas, avisos); no recomienda operar. "Para eso es el backtesting: al final yo decido."

---

## 2. Tu rol

Actúas como **ingeniero de software senior y arquitecto** (Laravel, Python, PostgreSQL, APIs de exchanges, dominio financiero):

- Soluciones listas para producción, no demos. Rendimiento, escalabilidad y mantenibilidad primero; SOLID y DRY.
- Piensa en concurrencia, memoria (el servidor tiene 2 núcleos y ~3 GB libres compartidos con otros bots) y volumen de datos.
- Optimiza consultas (índices, sin N+1, cuidado con funciones de ventana sobre chunks comprimidos).
- Integraciones robustas: timeouts, reintentos **idempotentes**, manejo de errores.
- Si la idea del dueño es incorrecta o mejorable, **díselo** con argumentos. Si falta contexto crítico, **pregunta**. Sugiere mejoras aunque no las pida, pero no las apliques sin su visto bueno.
- Busca y elimina código muerto; depura el proyecto (respaldos `.bak_NN` viejos, documentos obsoletos) con su autorización.

---

## 3. Cómo comunicarte con el dueño

- **Español**, directo, técnico y sin relleno. Explica en palabras simples lo que el dueño verá o deberá decidir; los detalles técnicos van en los comandos y en el código.
- **Paso a paso:** un bloque de comandos, esperar su salida, validar, y recién entonces el siguiente. Nunca cinco scripts de golpe.
- Cada entrega dice: qué cambia, cómo se instala, **qué salida esperar** (valores concretos) y cómo se prueba.
- Antes de construir algo grande, **recapitula los cambios** y espera confirmación. Para pantallas: **maqueta primero** (HTML interactivo, computador y celular).
- Si te equivocas, dilo claramente, corrige y sigue.

---

## 4. Infraestructura

| Elemento | Valor |
|---|---|
| Servidor | VPS `srv685835` (CloudPanel), acceso root por SSH. 2 núcleos. Corre también otros bots en el crontab de root: no tocarlos. |
| Raíz | `/home/tr2/htdocs/tr2.srv685835.hstgr.cloud` |
| Web | Laravel 13 · PHP 8.4 · Blade + Tailwind (ya compilado) · SweetAlert2 |
| Colas | Horizon + Redis. `supervisor-1` (`high`, `default`) y `supervisor-research` (`research`, 1 proceso) |
| Motor | FastAPI · Python 3.12 · `python-engine/` · `127.0.0.1:8002`, 1 worker |
| Base | PostgreSQL 16 + TimescaleDB 2.27 (`ohlcv_data` comprimida). Cache de Laravel: `database` |
| Servicios | systemd `trading2-engine` y `trading2-horizon` (`Restart=always`) |
| Programador | crontab de root: `php artisan schedule:run` cada minuto |
| Repositorio | `github.com/Rcastillo87/tr2` (rama `main`) |
| Exchange | Bybit v5. Demo: `api-demo.bybit.com` (precios reales, dinero ficticio) |

**Reinicios permitidos (nunca reiniciar el servidor completo):**
- Motor: `systemctl restart trading2-engine` (no `uvicorn` a mano, no `fuser -k`).
- Horizon: `systemctl restart trading2-horizon` — ⚠️ **mata la búsqueda que esté corriendo**. Antes, comprobar:
  `bash ops/dbsql.sh -c "SELECT id, status FROM param_search_runs WHERE status IN ('queued','running');"`

**Base de datos:** `bash ops/dbsql.sh [-c "SQL"]` (lee las credenciales del `.env` sin imprimirlas). Tablas principales: `ohlcv_data`, `collector_configs`, `strategies`, `backtests`, `paper_strategy_configs`, `paper_trades`, `broker_accounts`, `real_strategy_subscriptions`, `real_trades`, `risk_controls`, `param_search_runs`, `notifications`.

---

## 5. Reglas de oro (obligatorias)

1. **Cero asumir.** Todo cambio se valida con logs, pruebas forenses o consultas. Si no se probó, no funciona.
2. **Simulación pesimista.** Peor escenario: cero look-ahead, comisión 0.055 % por lado, slippage 0.05 % por lado, SL primero si SL y TP se tocan en la misma vela.
3. **Cero parámetros quemados.** Todo valor de la UI viaja intacto al motor; umbrales operativos en `config/` + `.env`.
4. **Integridad de datos.** Si el 1m no cubre el rango, se descarta. El collector **nunca borra** para reparar: re-descarga de Bybit y UPSERT.
5. **Misma lógica en backtest, paper y real** (`strategy_params` + `build_strategy` + `compute_signals`).
6. **No romper el diseño.** Prohibido modificar Blade/HTML sin autorización explícita y maqueta aprobada.
7. **Flujo git:** `git status` antes; tras un cambio probado, `git add -A && git commit`; si falla, `git checkout -- <archivo>` o el `.bak_NN`.
8. **Lectura previa:** antes de proponer un cambio, pedir comandos de lectura y ver el estado real del archivo.
9. **Validación obligatoria** antes del commit: `php -l`, `venv/bin/python -m py_compile`, `php artisan view:cache` si hubo Blade.
10. **Seguridad:**
    - Nunca imprimir claves API ni secretos (cargarlas en variables con `eval "$(php artisan tinker …)"` y `unset` al terminar).
    - Scripts que envían órdenes: **solo contra `api-demo.bybit.com`**.
    - Nunca usar la función de depósito de Bybit.
    - Claves API con permisos **Contratos: Órdenes + Posiciones**; nunca retiros.
11. **Mejoras:** investigar, sugerir, optimizar, quitar lo que no se usa.

---

## 6. Protocolo de trabajo (la IA no tiene acceso al servidor)

### 6.1 Leer
- Dar un comando que **guarde la salida en un archivo** y pedir que lo adjunte (la terminal pierde el principio de salidas largas):
  ```bash
  cd /home/tr2/htdocs/tr2.srv685835.hstgr.cloud && O=/root/lectura_X.txt; { echo "=== git"; git status --short; echo "=== archivo"; cat ruta/archivo; } > $O 2>&1; wc -l $O
  ```
- Si no puede adjuntar: partes de 300 líneas con `sed -n '1,300p' $O`.
- Pedir el `md5sum` de los archivos que se reemplazarán completos.

### 6.2 Parchar
- Script Python `patch_NN.py` dentro de un `.tgz` en **base64** con su **md5** (el dueño lo pega en `/root/patches/pNN/`).
- El script:
  - **verifica md5** de los archivos que reemplaza completos y **aborta sin escribir** si no coinciden;
  - edita con **anclas exactas** (`replace()` de bloques únicos; aborta si el ancla aparece 0 o más de 1 vez);
  - es **idempotente** (si ya se aplicó, dice "YA APLICADO" y no escribe);
  - deja respaldo `archivo.bak_NN`.
- **Nunca** `sed` con regex complejos ni scripts con problemas de comillas o indentación (rompieron el HTML en el pasado).
- Correcciones de una línea: `python3 - <<'EOF' … EOF` con el mismo patrón ancla/abortar.

### 6.3 Probar antes de entregar
- Reconstruir los archivos del servidor (de las lecturas) y correr el parche en una copia, **dos veces** (la segunda debe decir "YA APLICADO").
- `php -l` / `py_compile` local.
- JavaScript y vistas: arnés con Playwright (páginas con los endpoints simulados), en 1280 px y 390 px, sin errores de consola ni desborde horizontal.
- Lógica Python crítica: arnés con datos simulados.

### 6.4 Instalar y validar en el servidor
Bloque estándar: `git status` → extraer y verificar md5 → `python3 patch_NN.py` → lint → migración (si hay) → `config:clear` / `route:clear` / `view:clear` / `view:cache` → reinicio del servicio que corresponda → **prueba real** con la salida esperada escrita → commit con el mensaje en español.

### 6.5 Migraciones
SQL a mano en `database/sql-migrations/AAAA_MM_DD_NN_nombre.up.sql` y `.down.sql`. Aplicar con:
`bash ops/dbsql.sh -v ON_ERROR_STOP=1 -1 -f database/sql-migrations/<archivo>.up.sql`

---

## 7. Estado actual (2026-10-26)

### Módulos
| Módulo | Estado |
|---|---|
| Backtesting | Motor V3 honesto; 24 meses calendario; 1m si cubre; estrellas `RatingHelper`. Auto-Sync de configs implementadas a Paper/Real (`StrategyConfigSync`). |
| Búsqueda de configuración | `cli/param_search.py` + `ParamSearchService`. **Regla del dueño:** se quedan las monedas con retorno > 0 y ≥ 30 operaciones; sin ninguna, se descarta. Modos por temporalidad / por moneda; "buscar en todas" en cola; tope 3 h; pantallas nuevas. |
| Paper | Tick cada minuto, mismo motor. Sistema en cero de configs (decisión del dueño). |
| Real | Bybit, demo validada (comisión al centavo, SL/TP exactos). Conciliación cada 5 min, circuit breaker, kill switch manual. |
| Data Collector | 10 monedas × 7 temporalidades = 65 series, idénticas a Bybit. Vigilante cada 5 min (sin Horizon), validación + reparación diaria 04:00 Bogotá. |
| Avisos | Campana 🔔 + `/avisos`. Sistema → admin; broker → dueño de la cuenta (eventos pendientes de definir). |

### Archivos clave
- `python-engine/api/v1/backtest.py` (`load_backtest_data`: camino único de datos para backtest y búsqueda).
- `python-engine/backtesting/` (motor y estrategias), `python-engine/trading/` (paper, real, risk_manager).
- `python-engine/cli/` (`param_search`, `collector_validate`, `collector_repair`, `backfill_bybit`).
- `app/Services/` (`ParamSearchService`, `BacktestFromSearch`, `StrategyConfigSync`, `SystemAlerts`).
- `app/Console/Commands/CollectorWatchdog.php`, `routes/console.php` (tareas programadas).
- `config/trading.php` (motor, clave interna, vigilante), `config/horizon.php`, `config/queue.php`.

---

## 8. Lecciones aprendidas (no repetir)

| Error | Regla |
|---|---|
| Cambiar el formato de datos rompió la pantalla vieja | Al cambiar el formato de un JSON, mantener compatibilidad con la UI actual o cambiar ambas a la vez; probar la pantalla, no solo el endpoint. |
| `max(...$arr)` con claves de texto → 500 en PHP 8 | Usar `array_values()` antes de `...`. |
| Clases Tailwind nuevas no aparecen | Tailwind está compilado: en vistas nuevas usar CSS propio o estilos en línea. |
| Job re-entregado mientras corría | `timeout` del job < `retry_after` de su conexión (normal: 80 < 90; research: 11100 < 11400). |
| Huecos "falsos" en la auditoría | No usar `lag()` sobre chunks comprimidos: contar esperadas vs alineadas, o `time_bucket` por día. |
| Vela "distinta" recién cerrada | No comparar velas cerradas hace < 2 min (SETTLE). |
| Búsqueda muerta "signal 15" | Reiniciar Horizon mata la búsqueda: comprobar antes. |
| Búsqueda "24 meses" usaba 25 | Usar exactamente el periodo de la UI (`ui_period`). |
| Salidas largas perdidas | Guardar en archivo y adjuntar. |
| Parche "instalado" que no estaba | Verificar con `grep -c` / md5 al final de cada instalación. |
| `get_order` de Bybit fallaba siempre | Firmar los GET con los parámetros en el mismo orden en que se envían. |

---

## 9. Pendientes (orden sugerido)

1. Prueba de punta a punta de la búsqueda en el navegador (ventana → aviso en la campana → crear en historial).
2. Avisos de broker por usuario: orden rechazada, circuit breaker, claves API inválidas, descuadre de conciliación, (opcional) aperturas/cierres — el dueño elige.
3. `place_market_order`: reintento que puede duplicar órdenes → `orderLinkId` idempotente.
4. Funding de Bybit en el backtest.
5. Slippage de altcoins en demo (`real_demo_roundtrip.py` con SOL, SUI, LINK).
6. Reconciliación paper vs backtest tras 2–4 semanas de paper.
7. Etiqueta "código desactualizado" en paper (requiere maqueta).
8. Vectorizar el motor (`engine.py`, de ~7 s a ~1 s por backtest).
9. Limpieza: `.bak_NN` antiguos, documentos de la raíz y `docs/` de julio, `QUEUE_CONNECTION` duplicado en `.env`.

---

## 10. Plantilla de cada intervención

1. **Entender:** qué pide el dueño; si es ambiguo o caro de rehacer, preguntar.
2. **Leer:** comando de lectura → archivo adjunto.
3. **Proponer:** qué cambiará, riesgos, alternativas; maqueta si toca pantallas. Esperar visto bueno.
4. **Construir y probar en local** (§6.3).
5. **Entregar:** parche + instalación + salida esperada + prueba.
6. **Verificar** con la salida real del dueño.
7. **Commit** y actualizar la bitácora del proyecto.

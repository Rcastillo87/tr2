# tr-bot V2 — Documentación General

> Documento 1 de 3. Visión completa del proyecto: qué es, cómo está construido, cómo fluye la información entre sus partes, y qué hace cada módulo de negocio. Escrito para que cualquier persona (técnica o no) entienda el sistema completo sin tener que leer código.

---

## 1. Qué es tr-bot V2

tr-bot V2 es una plataforma de trading algorítmico para criptomonedas. Permite diseñar, probar, simular y ejecutar estrategias de trading automatizadas sobre el exchange Bybit, con tres niveles de riesgo progresivos:

1. **Backtesting** — probar una estrategia contra datos históricos reales, sin dinero de por medio, para saber si habría sido rentable.
2. **Paper Trading** — correr la estrategia en tiempo real contra el mercado actual, simulando operaciones con dinero virtual, para validar que funciona también con datos en vivo (no solo en retrospectiva).
3. **Real Trading** — una vez validada, conectar una cuenta real de Bybit (demo o con dinero real) y dejar que el bot opere de forma autónoma, con controles de seguridad.

El sistema es multiusuario, con tres roles (administrador, consultor, inversionista) y cada usuario de tipo inversionista puede conectar su propia cuenta de Bybit y operar de forma independiente con las estrategias que el administrador haya validado y dejado activas.

---

## 2. Stack tecnológico

El proyecto está dividido en dos aplicaciones que se comunican entre sí por HTTP interno, corriendo en el mismo servidor:

| Capa | Tecnología | Rol |
|---|---|---|
| Backend web | Laravel 13 (PHP 8.3+) | Interfaz de usuario, autenticación, autorización, programación de tareas, persistencia de configuración |
| Motor de trading | Python 3 + FastAPI | Lógica de estrategias, backtesting, ejecución de órdenes en Bybit, cálculo de indicadores técnicos |
| Base de datos | PostgreSQL + extensión TimescaleDB | Almacenamiento de velas de mercado (como hypertable optimizada para series de tiempo), configuraciones, trades, usuarios |
| Cache / mensajería ligera | Redis | Cacheo del régimen de mercado calculado periódicamente |
| Broker | Bybit (API v5, REST) | Exchange de criptomonedas donde se ejecutan las órdenes reales; se usa tanto el entorno testnet (demo) como mainnet (real) |
| Servidor | VPS Hostinger (Ubuntu) | `tr2.srv685835.hstgr.cloud` |

**Dependencias clave de Laravel** (de `composer.json`): `laravel/framework ^13.8`, `laravel/horizon` (para colas), `phpoffice/phpspreadsheet` (exportación a Excel), `predis/predis` (cliente Redis), `guzzlehttp/guzzle`.

**Dependencias clave del motor Python** (de `requirements.txt`): `fastapi 0.115`, `uvicorn 0.30` (servidor ASGI), `asyncpg 0.29` (driver PostgreSQL asíncrono), `httpx 0.27` (cliente HTTP asíncrono para hablar con Bybit), `pandas 2.2` / `numpy 2.0` (cálculo numérico de indicadores y simulación), `redis 5.0`.

No hay frontend de JavaScript framework (React/Vue): la interfaz es HTML renderizado por Laravel (Blade) con JavaScript vanilla embebido para interactividad puntual (filtros, formularios dinámicos, SweetAlert2 para confirmaciones).

---

## 3. Cómo se comunican Laravel y Python

Esta es la pieza más importante para entender la arquitectura. **Laravel nunca ejecuta lógica de trading directamente** — todo pasa por el motor Python vía HTTP.

```
Usuario (navegador)
       │
       ▼
  Laravel (PHP) — corre con PHP-FPM/Nginx, puerto público
       │
       │  HTTP interno, header X-Internal-API-Key
       ▼
  Motor Python (FastAPI) — uvicorn, escucha SOLO en 127.0.0.1:8002
       │
       ▼
  PostgreSQL (datos compartidos) + Bybit API (órdenes reales)
```

- El motor Python **no es accesible desde fuera del servidor**: escucha únicamente en `127.0.0.1:8002` (ver `start.py`). Solo Laravel, corriendo en la misma máquina, puede llamarlo.
- Toda petición de Laravel al motor incluye el header `X-Internal-API-Key`, y el motor rechaza con `401 Unauthorized` cualquier petición que no traiga la clave correcta (middleware en `main.py`, excepto el endpoint `/health` que queda abierto para monitoreo).
- Laravel guarda la URL del motor y la clave en `config/trading.php`, que lee de variables de entorno: `PYTHON_ENGINE_URL` (default `http://127.0.0.1:8002`) y `PYTHON_INTERNAL_API_KEY`.
- **Ambas aplicaciones leen y escriben en la misma base de datos PostgreSQL.** No hay una API de datos entre ellas — Laravel inserta filas en `paper_strategy_configs` y el motor Python las lee directamente con SQL (vía `asyncpg`). Esto significa que la "fuente de verdad" de cualquier configuración de estrategia es siempre una fila en esa tabla, nunca un archivo de configuración ni una variable de entorno.

### Credenciales de Bybit: quién las desencripta

Las API keys de las cuentas de Bybit de los usuarios se guardan en la tabla `broker_accounts`, encriptadas con el cast `encrypted` de Eloquent (usa la `APP_KEY` de Laravel). Cuando el motor Python necesita operar con una cuenta, **Laravel desencripta las credenciales antes de enviarlas** en el payload HTTP hacia Python — el motor Python nunca lee la tabla `broker_accounts` directamente ni tiene acceso a la `APP_KEY` de Laravel para desencriptar nada por su cuenta. Esto es intencional (ver comentario en `real_trading.py`): evita duplicar la lógica de encriptación en dos lenguajes distintos.

---

## 4. Los tres roles de usuario

Definidos en `app/Models/User.php` con un campo `role` (enum: `admin`, `consultor`, `inversionista`) y reforzados con 5 Gates de Laravel (`app/Providers/AppServiceProvider.php`):

| Gate | Quién pasa | Qué protege |
|---|---|---|
| `viewPaperTrading` | admin, inversionista | Ver el módulo de Paper Trading |
| `viewAnalysisTools` | admin, consultor | Ver Backtesting y Data Collector |
| `viewRealTrading` | admin, inversionista | Ver y operar Trading Real (sus propias cuentas) |
| `manageUsers` | solo admin | Gestionar usuarios, activar/desactivar configs de Paper Trading |
| `createDemoAccounts` | admin (o si `ALLOW_INVESTOR_DEMO_ACCOUNTS=true`) | Crear cuentas de tipo demo en Bybit |

En la práctica:
- El **administrador** es quien diseña y valida estrategias (Backtesting), las activa en Paper Trading, y también puede operar su propia cuenta real.
- El **consultor** solo puede ver y correr backtests — no toca dinero real ni paper trading. Es un rol de análisis puro.
- El **inversionista** no ve Backtesting ni Data Collector. Solo ve el resumen de Paper Trading (sin poder modificar configuraciones) y puede conectar su propia cuenta de Bybit para operar en real con las estrategias que el admin dejó activas.

Adicionalmente hay dos middlewares de negocio que se aplican a usuarios autenticados:

- **`EnsureUserIsActive`** — si un admin desactiva la cuenta de un usuario (campo `is_active`), la próxima petición de ese usuario cierra su sesión automáticamente y lo redirige al login con un mensaje. Al desactivar un usuario, además, todas sus suscripciones activas de Trading Real se pasan a `paused` automáticamente (lógica en `UserManagementController::toggleActive`) — esto detiene la apertura de nuevas posiciones para esa cuenta sin tocar las posiciones que ya estuvieran abiertas.
- **`ExpireSessionAtMidnightColombia`** — cierra la sesión de cualquier usuario en la primera medianoche de Colombia (`America/Bogota`) que ocurra después de su login, con un tope duro de 24 horas independientemente de la hora a la que inició sesión. Es una política de seguridad de sesión, no de negocio de trading.

---

## 5. Los cuatro módulos principales

### 5.1 Backtesting

Permite elegir una estrategia, un par (BTCUSDT/ETHUSDT/SOLUSDT), un intervalo (1m/5m/15m/H1/H2/H4/D1) y un conjunto de parámetros (Stop Loss, hasta 4 niveles de Take Profit, Break-even, filtros de régimen de mercado, filtros de tendencia macro, filtros de volumen, filtros de horas/días bloqueados, trailing stop, protección por volatilidad), y correr una simulación contra todo el histórico de velas disponible en la base de datos (hasta 2 años).

El resultado incluye métricas agregadas (win rate, Sharpe ratio, profit factor, drawdown máximo, retorno total), un desglose mes a mes, y una calificación de 1 a 5 estrellas calculada en base a 5 métricas con igual peso (20% cada una): Win Rate, Sharpe Ratio, Retorno promedio mensual, Consistencia (% de meses positivos) y Profit Factor.

El backtest internamente usa **walk-forward validation**: en vez de correr la simulación una sola vez sobre todo el histórico (lo que puede sobreajustar los parámetros a ese período exacto), divide los datos en 5 ventanas consecutivas, entrena/valida cada ventana con un 70%/30% de los datos, y agrega los resultados solo de los tramos "fuera de muestra" (test). Esto da una medida más honesta de si la estrategia generalizaría a datos que nunca vio. Por separado, también corre la simulación completa sin walk-forward para generar el desglose mensual legible (que necesita continuidad cronológica) y para que los KPIs mostrados al usuario coincidan exactamente con ese desglose.

Cuando una configuración resulta satisfactoria, el botón **"Implementar en Paper Trading"** la guarda como una fila nueva en `paper_strategy_configs` — desde ese momento, esa configuración exacta empieza a evaluarse en tiempo real cada 5 minutos.

### 5.2 Paper Trading

Una vez que existe al menos una configuración activa en `paper_strategy_configs`, un job de Laravel (`PaperTradingTickJob`) llama cada 5 minutos al motor Python, que:

1. Lee todas las configuraciones marcadas como activas.
2. Revisa las posiciones simuladas abiertas: si el precio actual de mercado tocó el Stop Loss, algún nivel de Take Profit, el nivel de Break-even, o si ya pasó el tiempo máximo permitido, cierra la posición y calcula la ganancia/pérdida.
3. Para cada estrategia sin posición abierta, revisa si el régimen de mercado actual permite operar, calcula las señales con los datos más recientes, y si hay señal nueva, abre una posición simulada con un balance virtual fijo de 10.000 USDT.

No hay dinero real involucrado — todo se registra en la tabla `paper_trades`. Esto sirve como prueba de fuego: una estrategia puede verse excelente en backtesting (datos pasados) pero comportarse distinto con datos en vivo, latencia real de mercado, y condiciones actuales. Paper Trading es el filtro intermedio antes de arriesgar capital real.

### 5.3 Trading Real

Funciona en paralelo y con la misma lógica de señales que Paper Trading, pero coloca órdenes reales en Bybit. Para que un usuario opere en real necesita:

1. Conectar una **cuenta de broker** (`broker_accounts`) con su API key/secret de Bybit (validadas contra la API real antes de guardarse), de tipo `real` o `demo` (testnet).
2. Crear **suscripciones** (`real_strategy_subscriptions`) que vinculan esa cuenta con una o varias configuraciones activas de `paper_strategy_configs`.

Cada 5 minutos, `RealTradingTickJob` envía a Python el listado de cuentas activas con sus credenciales (desencriptadas por Laravel) y sus suscripciones, y el motor:

1. Revisa el *circuit breaker* de la cuenta (ver sección 7).
2. Monitorea posiciones abiertas en Bybit: si ya no existe la posición (fue cerrada por el SL/TP nativo de Bybit), reconcilia el cierre en la base de datos consultando el historial de PnL cerrado de Bybit para saber el precio exacto y la razón.
3. Para cada suscripción sin posición abierta, genera la señal con la estrategia correspondiente y, si hay señal, coloca una orden de mercado real en Bybit con un flujo de varios pasos pensado para tolerar fallos de red y rechazos del exchange (ver sección 6).

Adicionalmente, `RealTradingReconcileJob` corre también cada 5 minutos como una capa de seguridad extra: detecta posiciones que existen en Bybit pero no en la base de datos (huérfanas) y las adopta, y detecta trades marcados como abiertos en la base de datos que ya no existen en Bybit y los cierra con el precio real obtenido del historial del exchange.

### 5.4 Data Collector

Es la base de todo: sin datos históricos no hay backtesting, y sin datos recientes no hay señales en vivo. `CollectOhlcvDataJob` corre **cada minuto** y descarga velas (OHLCV: open/high/low/close/volume) desde la API pública de Bybit para cada combinación símbolo/intervalo marcada como activa en `collector_configs`.

Actualmente están activos: BTCUSDT, ETHUSDT y SOLUSDT en los intervalos 1m, 5m, 15m, H1 (60) y H2 (120). Los intervalos H4 y D1 existen en la configuración pero están desactivados (se dejaron preparados para backtests puntuales bajo demanda). BNB y XRP fueron descartados como pares operativos pero sus datos históricos se conservan inactivos por si se quieren retomar.

La tabla `ohlcv_data` es una **hypertable de TimescaleDB** particionada por tiempo — una elección de diseño pensada para que las consultas de rango de fechas sobre series de millones de velas sigan siendo rápidas a medida que crece el histórico.

---

## 6. El flujo de apertura de una orden real, paso a paso

Esta es la pieza de lógica más cuidadosamente diseñada del sistema, porque es donde dinero real está en juego y cualquier fallo de red puede dejar una posición sin protección. El flujo completo (en `trading/real_trader.py`, método `open_trade`):

1. **Consultar balance real** en Bybit. Si falla, se aborta sin tocar nada.
2. **Consultar el precio de mercado actual** (no el precio de la señal, que pudo quedar desactualizado por el tiempo que tomó procesar el tick) y calcular SL/TP/Break-even sobre ese precio.
3. **Calcular el tamaño de la posición** según el balance real y el porcentaje de riesgo configurado (por defecto el de la estrategia, pero una suscripción individual puede tener un `risk_override_pct` propio que tiene prioridad).
4. **Verificar el lote mínimo permitido** por Bybit para ese símbolo y redondear el tamaño calculado al "step size" exacto que el exchange acepta (cada par tiene su propio incremento mínimo, p. ej. 0.001 para BTC, 0.1 para SOL).
5. **Insertar una fila en `real_trades` con estado `pending_open`** *antes* de enviar nada a Bybit — esto deja un rastro en la base de datos incluso si la llamada siguiente falla por completo.
6. **Recalcular SL/TP** si el precio se movió más de 0.5% entre el cálculo inicial y este punto (el mercado no espera).
7. **Enviar la orden de mercado a Bybit**, incluyendo un Stop Loss y Take Profit *provisionales* calculados como un porcentaje amplio alrededor del precio (en testnet: SL al 5%, TP al 10%; en mainnet: SL al 2%, TP al 4%) — esto es una protección de emergencia: si todo lo que viene después falla, la posición igual queda protegida contra un movimiento catastrófico, aunque no con el SL/TP exacto de la estrategia. Si Bybit rechaza la orden, se reintenta hasta 3 veces con 2 segundos de espera entre intentos.
8. **Esperar 1 segundo y confirmar** consultando si la posición ya aparece abierta en Bybit. Si no, se espera 5 segundos más y se vuelve a chequear. Si sigue sin confirmar, se reintenta hasta 3 veces más (con 10 segundos entre cada intento), verificando antes de cada reintento que la señal original siga vigente — si el mercado ya invirtió la señal, se aborta en vez de insistir. Si después de unos 38 segundos totales nunca se confirma la posición, el trade se marca como `orphaned` para que el job de reconciliación lo investigue más tarde.
9. **Una vez confirmada la posición**, se recalculan SL/TP/Break-even/TP2/TP3/TP4 *exactos* usando el precio de ejecución real (`avgPrice` que devuelve Bybit, que puede diferir levemente del precio de la señal por slippage), y se llama a `set_trading_stop` para reemplazar los valores provisionales por los reales en la posición ya abierta en Bybit.
10. **Se actualiza la fila a estado `open`** con el precio real de ejecución, el slippage calculado, y los niveles definitivos de SL/TP.
11. Se registra todo el proceso en un **log de auditoría** (`audit_log`, columna JSONB) — qué pasó, en qué momento, con qué precios.

El cierre de posiciones (`close_trade`) sigue una lógica espejo: marca la fila como `pending_close`, envía la orden de cierre en sentido contrario, espera confirmación consultando el estado de la orden hasta 6 veces (5 segundos entre intentos), y al confirmar calcula la comisión estimada de Bybit (0.055% tipo *taker*) y el PnL neto antes de marcar la fila como `closed`.

---

## 7. Protecciones de seguridad del sistema

El proyecto tiene **dos capas de protección completamente separadas** que conviene no confundir:

### Risk Manager (solo Paper Trading)

`trading/risk_manager.py` implementa drawdown diario (pausa automática si una estrategia pierde más del 3% del balance virtual en el día, con reactivación automática a la medianoche siguiente), drawdown total (pausa si pierde más del 10% acumulado, esta requiere reactivación manual), pausa por volatilidad extrema (si el ATR actual de un símbolo supera 2x su promedio histórico) y un *kill switch* manual global. Todas estas pausas se guardan en la tabla `risk_controls` y se evalúan al inicio de cada tick de Paper Trading.

**Esta protección no existe en Trading Real.** El motor de trading real no importa ni llama a `RiskManager` en ningún punto del código — confía exclusivamente en la siguiente capa.

### Circuit Breaker (solo Trading Real)

Implementado directamente en `real_trading.py`/`real_trader.py`: si una cuenta de broker acumula 3 o más trades marcados con estado `error` en las últimas 2 horas, el sistema clasifica esos errores. Si son errores "no críticos" (problemas de parámetros, firma, SL/TP inválido, rechazo de Bybit por validación) los limpia y sigue operando con normalidad. Si detecta errores de otra naturaleza (potencialmente más graves), **pausa automáticamente la cuenta entera** (`broker_accounts.status = paused`), lo que detiene cualquier nueva apertura de posición hasta que un administrador la reactive manualmente.

En resumen: Paper Trading se protege contra pérdidas excesivas de la estrategia en sí (drawdown), mientras que Trading Real se protege contra fallos técnicos repetidos de conexión con el exchange — pero **no tiene actualmente un mecanismo de drawdown automático propio**. Esto es relevante de cara a operar con capital real: es una pieza pendiente de construir si se quiere paridad de protecciones entre ambos módulos (ver documento de hallazgos).

---

## 8. Régimen de mercado

Tanto el backtesting como Paper Trading y Trading Real consultan el "régimen de mercado" actual antes de decidir si una estrategia puede operar. Se calcula con tres indicadores técnicos clásicos sobre velas H1 (`indicators/regime_indicators.py`):

- **ADX** (Average Directional Index) — mide la fuerza de una tendencia, independientemente de su dirección.
- **ATR** (Average True Range) — mide la volatilidad absoluta.
- **Bollinger Band Width** — mide qué tan comprimido o expandido está el rango de precios reciente.

La clasificación resultante es una de tres etiquetas:

- **VOLATILE** — si el ATR actual supera 1.8 veces su promedio histórico (tiene prioridad sobre las otras dos condiciones).
- **TRENDING** — si el ADX es mayor a 25.
- **RANGING** — en cualquier otro caso (mercado lateral, sin tendencia clara).

Cada estrategia declara en qué régimen(es) le permiten operar (`allowed_regimes`). Por ejemplo, las estrategias de tendencia (VWAP Tendencia, EMA/Donchian) suelen restringirse a TRENDING, mientras que Reversión a la Media está pensada para RANGING. Este filtro puede activarse o desactivarse por configuración individual (`regime_filter: true/false`) — en la práctica, varias de las configuraciones actualmente activas en producción lo tienen desactivado porque los backtests mostraron mejor desempeño sin él en los pares operados.

Para Paper Trading y Backtesting el régimen se calcula al vuelo sobre los datos disponibles en cada evaluación. Adicionalmente existe un job independiente (`DetectMarketRegimeJob`, cada 15 minutos) que calcula y cachea en Redis el régimen actual de cada símbolo, accesible desde el dashboard para que el usuario vea de un vistazo en qué condición está el mercado en cada par — este caché es solo informativo para la interfaz, no es lo que consultan los motores de ejecución (que recalculan en cada tick sobre los datos más recientes de cada estrategia específica).

---

## 9. Las cuatro estrategias disponibles

Todas heredan de una clase base común (`backtesting/strategies/base_strategy.py`) que centraliza el cálculo de Stop Loss, hasta 4 niveles de Take Profit (con prioridad TP4 > TP3 > TP2 > TP1 — el motor cierra en el nivel más favorable que se haya alcanzado), Break-even, trailing stop (fijo o escalonado), protección por volatilidad, y un conjunto de filtros opcionales de entrada (volumen mínimo, rango horario permitido, fin de semana bloqueado, horas específicas bloqueadas, días específicos bloqueados).

| Estrategia | Lógica de entrada | Régimen típico |
|---|---|---|
| **VWAP Tendencia** | Cruce del precio sobre/bajo el VWAP acumulado del día, en la dirección de una EMA de tendencia | TRENDING |
| **VWAP Reversión** | El precio se aleja más de 2 desviaciones estándar del VWAP — se apuesta a que regresa al centro | TRENDING (paradójicamente, validado así en backtests) |
| **Reversión a la Media** | Rebote desde los extremos de las Bandas de Bollinger, confirmado con RSI | RANGING |
| **Tendencia EMA/Donchian** | Ruptura del canal de Donchian seguida de un cruce de EMAs rápida/lenta dentro de una ventana de tiempo | TRENDING |

VWAP Tendencia y VWAP Reversión están técnicamente implementadas como una sola clase (`VwapStrategy`) con un parámetro `mode` que alterna el comportamiento — se presentan como dos estrategias distintas en la interfaz porque su comportamiento y parámetros óptimos son completamente distintos en la práctica.

Existen además dos archivos de estrategias antiguas (`vwap_intraday.py`, `vwap_reversion.py`) que fueron los predecesores de la versión unificada actual y que ya no son invocados por ningún endpoint — se conservan en el repositorio pero no forman parte del sistema en funcionamiento.

---

## 10. Tareas programadas (resumen)

Todo el "latido" del sistema corre por el *scheduler* de Laravel (`routes/console.php`), que en producción se dispara vía un cron del sistema operativo que ejecuta `php artisan schedule:run` cada minuto:

| Job | Frecuencia | Qué hace |
|---|---|---|
| `CollectOhlcvDataJob` | Cada minuto | Descarga velas nuevas de Bybit para todos los símbolos/intervalos activos |
| `DetectMarketRegimeJob` | Cada 15 minutos | Calcula y cachea en Redis el régimen de mercado de cada símbolo |
| `PaperTradingTickJob` | Cada 5 minutos | Monitorea posiciones simuladas abiertas y busca nuevas señales |
| `RealTradingTickJob` | Cada 5 minutos | Monitorea posiciones reales abiertas y busca nuevas señales en Bybit |
| `RealTradingReconcileJob` | Cada 5 minutos | Detecta y corrige discrepancias entre la base de datos y el estado real en Bybit |

---

## 11. Glosario rápido de tablas de base de datos

Para orientarse sin tener que leer las migraciones completas:

- **`ohlcv_data`** — velas de mercado históricas (hypertable TimescaleDB).
- **`collector_configs`** — qué combinaciones símbolo/intervalo está recolectando el sistema activamente.
- **`paper_strategy_configs`** — la fuente de verdad de cada estrategia configurada: clase Python, símbolo, intervalo, todos los parámetros en JSON, si está activa, y las métricas/calificación de su último backtest.
- **`paper_trades`** — historial de operaciones simuladas (Paper Trading).
- **`broker_accounts`** — cuentas de Bybit conectadas por los usuarios (credenciales encriptadas).
- **`real_strategy_subscriptions`** — qué configuración de estrategia está conectada a qué cuenta de broker, para un usuario.
- **`real_trades`** — historial de operaciones reales, con todo el detalle de ejecución (orden, slippage, comisión, balance antes/después, log de auditoría).
- **`risk_controls`** — pausas activas o históricas del Risk Manager (solo Paper Trading).
- **`users`** — usuarios del sistema, con rol y estado activo/inactivo.

---

## 12. Qué NO hace (todavía) el sistema

Para tener expectativas claras del estado actual:

- No tiene notificaciones (Telegram, email, push) cuando se abre, cierra o falla una operación.
- No tiene un dashboard consolidado de balance/PnL en tiempo real para Trading Real (existe la vista de listado de operaciones, pero no un resumen ejecutivo tipo panel de control).
- No tiene reactivación automática del circuit breaker de Trading Real — una cuenta pausada por errores críticos requiere intervención manual de un administrador.
- No opera actualmente con capital real en mainnet — todo el trading real en producción corre sobre el entorno testnet (demo) de Bybit, como fase de validación previa a comprometer dinero real.
- No tiene protección de drawdown automática en Trading Real (esa capa solo existe para Paper Trading, ver sección 7).

---

*Fin del Documento 1. El Documento 2 (Técnico) detalla función por función, ruta por ruta y campo por campo cada pieza mencionada aquí. El Documento 3 (Contexto para IA) condensa todo esto en un formato optimizado para que otro asistente de IA retome el proyecto sin tener que re-explorar el código.*

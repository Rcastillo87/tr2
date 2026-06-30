# tr-bot V2 — Documentación Técnica

> Documento 2 de 3. Referencia exhaustiva: cada ruta HTTP, cada función, cada campo de base de datos, cada job programado. Escrito para desarrolladores que necesitan modificar o depurar el sistema sin tener que leer el código fuente completo primero.

---

## Índice

1. Rutas HTTP (Laravel)
2. Esquema de base de datos completo
3. Modelos Eloquent (Laravel)
4. Controllers (Laravel) — función por función
5. Jobs programados (Laravel)
6. Export a Excel
7. Middlewares y Gates
8. API del motor Python — endpoint por endpoint
9. Núcleo de backtesting (Python)
10. Estrategias de trading (Python)
11. Ejecución: Paper Trader (Python)
12. Ejecución: Real Trader (Python)
13. Risk Manager y Circuit Breaker
14. Collectors e indicadores
15. Configuración y variables de entorno
16. Scripts de análisis sueltos

---

## 1. Rutas HTTP (Laravel)

Definidas en `routes/web.php`, todas dentro de `Route::middleware(['auth', 'verified'])`. El prefijo de cada grupo está indicado.

### Raíz
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/` | `dashboard` | `DashboardController@index` |

### Paper Trading — middleware `can:viewPaperTrading`, prefijo `paper-trading`
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/paper-trading/` | `paper-trading.index` | `PaperTradingController@index` |
| GET | `/paper-trading/live` | `paper-trading.live` | `PaperTradingController@live` |

### Configs de Paper Trading — middleware `can:manageUsers`, prefijo `paper-trading/configs`
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| PATCH | `/paper-trading/configs/{config}/toggle` | `paper-trading.configs.toggle` | `PaperStrategyConfigController@toggleActive` |
| POST | `/paper-trading/configs/implement` | `paper-trading.configs.implement` | `PaperStrategyConfigController@implement` |
| POST | `/paper-trading/configs/` | `paper-trading.configs.store` | `PaperStrategyConfigController@store` |
| DELETE | `/paper-trading/configs/{config}` | `paper-trading.configs.destroy` | `PaperStrategyConfigController@destroy` |

### Data Collector — middleware `can:manageUsers`, prefijo `collector/configs`
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/collector/configs/` | `collector.configs.index` | `CollectorConfigController@index` |
| PATCH | `/collector/configs/{config}/toggle` | `collector.configs.toggle` | `CollectorConfigController@toggleActive` |

### Backtesting — middleware `can:viewAnalysisTools`, prefijo `backtesting`
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/backtesting/` | `backtesting.index` | `BacktestingController@index` |
| GET | `/backtesting/run` | `backtesting.run` | `BacktestingController@run` |
| POST | `/backtesting/run` | `backtesting.execute` | `BacktestingController@run` |
| POST | `/backtesting/run-ajax` | `backtesting.run-ajax` | `BacktestingController@runAjax` |
| GET | `/backtesting/data-range/{symbol}/{interval}` | `backtesting.data-range` | `BacktestingController@dataRange` |
| POST | `/backtesting/export-excel` | `backtesting.export-excel` | `BacktestingController@exportExcel` |
| GET | `/backtesting/retest/{config}` | `backtesting.retest` | `BacktestingController@retest` |

> Nota: la misma ruta `/backtesting/run` está registrada dos veces con nombres distintos (`backtesting.run` para GET, `backtesting.execute` para POST), ambas apuntando al mismo método `run()`, que internamente distingue el verbo HTTP (`$request->isMethod('post')`) para decidir si solo muestra el formulario vacío o además ejecuta el backtest.

### Usuarios — middleware `can:manageUsers`, prefijo `users`
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/users/` | `users.index` | `UserManagementController@index` |
| PATCH | `/users/{user}/toggle-active` | `users.toggle-active` | `UserManagementController@toggleActive` |

### Trading Real — middleware `can:viewRealTrading`, prefijo `trading`
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/trading/` | `trading.index` | `TradingController@index` |
| GET | `/trading/live-prices` | `trading.live-prices` | `TradingController@livePrices` |
| GET | `/trading/accounts` | `trading.accounts` | `TradingController@accounts` |
| POST | `/trading/accounts` | `trading.accounts.store` | `BrokerAccountController@store` |
| PATCH | `/trading/accounts/{account}/toggle-status` | `trading.accounts.toggle-status` | `BrokerAccountController@toggleStatus` |
| DELETE | `/trading/accounts/{account}` | `trading.accounts.destroy` | `BrokerAccountController@destroy` |
| POST | `/trading/accounts/{account}/subscriptions` | `trading.subscriptions.store` | `RealStrategySubscriptionController@store` |
| POST | `/trading/accounts/{account}/subscriptions/all` | `trading.subscriptions.store-all` | `RealStrategySubscriptionController@storeAll` |
| PATCH | `/trading/accounts/{account}/subscriptions/{subscription}/toggle` | `trading.subscriptions.toggle` | `RealStrategySubscriptionController@toggle` |
| DELETE | `/trading/accounts/{account}/subscriptions/{subscription}` | `trading.subscriptions.destroy` | `RealStrategySubscriptionController@destroy` |

### Perfil — sin prefijo de grupo adicional
| Método | Ruta | Nombre | Controller@método |
|---|---|---|---|
| GET | `/profile` | `profile.edit` | `ProfileController@edit` |
| PATCH | `/profile` | `profile.update` | `ProfileController@update` |
| DELETE | `/profile` | `profile.destroy` | `ProfileController@destroy` |

### Auth
Definidas en `routes/auth.php` (no exploradas en detalle — siguen el patrón estándar de Laravel Breeze: login, register, password reset, email verification, confirm password).

---

## 2. Esquema de base de datos completo

### `ohlcv_data` (hypertable TimescaleDB, sin modelo Eloquent — se consulta con SQL crudo desde Python)
| Columna | Tipo | Notas |
|---|---|---|
| `time` | TIMESTAMPTZ | Parte de la clave de partición de TimescaleDB |
| `symbol` | TEXT | Ej. `BTCUSDT` |
| `interval` | TEXT | Ej. `1`, `5`, `15`, `60`, `120`, `240`, `D` |
| `open`, `high`, `low`, `close` | NUMERIC(20,8) | |
| `volume` | NUMERIC(30,8) | |

Índice único: `(symbol, interval, time DESC)`. Se crea como hypertable con `SELECT create_hypertable('ohlcv_data', 'time', if_not_exists => TRUE)`. Inserciones usan `ON CONFLICT DO NOTHING` para idempotencia.

### `collector_configs`
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `symbol` | string(20) | |
| `interval` | string(10) | |
| `active` | boolean | default true |
| `notes` | text nullable | |
| `created_at`, `updated_at` | timestamps | |

Único: `(symbol, interval)`.

### `paper_strategy_configs` — la fuente de verdad del sistema
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `display_name` | string | Ej. "VWAP Tendencia — BTCUSDT H1" |
| `strategy_class` | string | `VwapStrategy` \| `MeanReversionStrategy` \| `EmaDonchianStrategy` |
| `symbol` | string | |
| `interval` | string(10) | |
| `params` | jsonb | Todos los parámetros de la estrategia (ver sección 9) |
| `active` | boolean | default true |
| `audited_months` | integer nullable | Meses cubiertos en el último backtest |
| `avg_win_rate` | decimal(5,2) nullable | |
| `avg_monthly_pnl` | decimal(7,4) nullable | |
| `avg_monthly_trades` | decimal(6,2) nullable | |
| `total_return_pct` | decimal(8,4) nullable | |
| `star_wr`, `star_sharpe`, `star_ret`, `star_consistency`, `star_pf` | decimal(3,1) nullable | Calificación individual 1-5 de cada métrica |
| `star_rating` | decimal(3,1) nullable | Promedio de las 5 anteriores |
| `backtest_range_from`, `backtest_range_to` | string(7) nullable | Formato `YYYY-MM` |
| `sharpe_ratio` | decimal | Agregada en migración `2026_06_29` |
| `consistency_pct` | decimal | |
| `profit_factor` | decimal | |
| `created_at`, `updated_at` | timestamps | |

**Importante sobre unicidad**: la migración original (`2026_06_18`) define `unique(['strategy_class', 'symbol', 'interval'])`. Sin embargo el método `PaperStrategyConfig::implementFromBacktest()` (capa de aplicación) fue modificado para **no respetar exclusividad por esa tripleta** — permite múltiples configuraciones del mismo símbolo/estrategia/intervalo con parámetros distintos, y solo bloquea la creación de una nueva fila si los `params` JSON son *exactamente* idénticos a una ya existente (comparación bidireccional JSONB `@>` y `<@`, insensible al orden de las claves). Si la constraint de base de datos de la migración original sigue activa físicamente, cualquier intento de Eloquent de insertar una segunda fila con la misma tripleta fallaría a nivel de base de datos a pesar de que el código de aplicación lo permite — esto debe verificarse directamente contra el esquema real en producción (no quedó confirmado en las migraciones leídas si una migración posterior eliminó esa constraint).

### `paper_trades`
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `strategy` | string | Coincide con `paper_strategy_configs.display_name` |
| `symbol` | string | |
| `interval` | string | |
| `side` | enum('long','short') | |
| `entry_price`, `exit_price` | decimal(20,8) | `exit_price` nullable |
| `sl`, `tp` | decimal(20,8) | |
| `tp2` | decimal(15,8) nullable | Agregada en migración `2026_06_19` |
| `be_level` | decimal(20,8) | |
| `be_activated` | boolean | default false |
| `size` | decimal(20,8) | |
| `pnl`, `pnl_pct` | decimal nullable | |
| `max_profit_pct`, `max_loss_pct` | decimal(10,4) | default 0, MFE/MAE — Maximum Favorable/Adverse Excursion, actualizadas en cada tick mientras el trade está abierto |
| `exit_reason` | string nullable | `stop_loss` \| `take_profit` \| `take_profit_1` \| `take_profit_2` \| `time_exit` |
| `regime` | string nullable | Régimen al momento de entrada |
| `entry_time`, `exit_time` | timestamp | `exit_time` nullable |
| `status` | enum('open','closed') | default open |
| `created_at`, `updated_at` | timestamps | |

Índices: `(strategy, symbol, status)`, `(status)`.

### `risk_controls`
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `strategy` | string nullable | null = aplica a todo (kill switch global) |
| `symbol` | string nullable | null = aplica a toda la estrategia |
| `reason` | enum | `daily_drawdown` \| `total_drawdown` \| `volatility_extreme` \| `kill_switch_manual` |
| `value` | decimal(10,4) nullable | Valor que disparó la pausa |
| `threshold` | decimal(10,4) nullable | Umbral configurado |
| `active` | boolean | default true |
| `paused_at` | timestamp | |
| `auto_resume_at` | timestamp nullable | Para drawdown diario, medianoche siguiente |
| `resumed_at` | timestamp nullable | |
| `created_at`, `updated_at` | timestamps | |

Índice: `(strategy, symbol, active)`.

### `users` (extendida sobre la tabla estándar de Laravel)
Campos añadidos en `2026_06_14_220220`:
| Columna | Tipo | Notas |
|---|---|---|
| `role` | enum('admin','consultor','inversionista') | default `inversionista` |
| `is_active` | boolean | default true |

### `broker_accounts`
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `user_id` | FK → users, cascadeOnDelete | |
| `broker` | string | default `bybit` |
| `account_type` | enum('real','demo') | default `real` |
| `label` | string | Autogenerado: "Bybit Real" / "Bybit Demo" |
| `api_key`, `api_secret` | text nullable, **cast `encrypted`** | |
| `status` | enum('active','paused') | default `active` |
| `created_at`, `updated_at` | timestamps | |

Único: `(user_id, broker, account_type)` — un usuario solo puede tener 1 cuenta real y 1 demo por broker (migración `2026_06_23_100000`). Índice: `(user_id, status)`.

### `real_strategy_subscriptions`
Estructura final tras 3 migraciones (`2026_06_14`, `2026_06_15`, `2026_06_23`):
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `user_id` | FK → users, cascadeOnDelete | |
| `broker_account_id` | FK → broker_accounts, cascadeOnDelete | Reemplazó al campo `broker` original |
| `paper_strategy_config_id` | FK → paper_strategy_configs, nullOnDelete | Agregado en `2026_06_23` |
| `strategy` | string | |
| `symbol` | string | |
| `interval` | string nullable | Agregado en `2026_06_23` |
| `risk_override_pct` | decimal(5,2) nullable | Agregado en `2026_06_27`, sobrescribe el `risk_per_trade_pct` de la config para esta suscripción específica |
| `status` | enum('active','paused') | default `active` |
| `created_at`, `updated_at` | timestamps | |

Único: `(broker_account_id, paper_strategy_config_id)` (constraint `real_subs_unique_v2`, reemplazó la versión anterior basada en `strategy+symbol+broker`).

### `real_trades` — la tabla más extensa del sistema
Estructura final tras 4 migraciones (`2026_06_14`, `2026_06_15`, `2026_06_23`, `2026_06_26`, `2026_06_27`):
| Columna | Tipo | Notas |
|---|---|---|
| `id` | bigint PK | |
| `user_id` | FK → users, cascadeOnDelete | |
| `subscription_id` | FK → real_strategy_subscriptions, nullOnDelete | |
| `broker_account_id` | FK → broker_accounts, nullOnDelete | |
| `paper_strategy_config_id` | FK → paper_strategy_configs, nullOnDelete | FK directa a la config (fuente de verdad) |
| `order_id`, `close_order_id` | string nullable | IDs de orden en Bybit |
| `strategy`, `symbol`, `interval` | string | |
| `broker` | string | default `bybit` |
| `side` | enum('long','short') | |
| `entry_price`, `entry_price_signal`, `exit_price` | decimal(20,8) | `entry_price_signal` = precio de la señal antes de ejecución; `exit_price` nullable |
| `sl`, `tp`, `tp2`, `tp3`, `tp4` | decimal(20,8) nullable (excepto sl/tp) | |
| `be_level` | decimal(20,8) | |
| `be_activated` | boolean | default false |
| `size` | decimal(20,8) | |
| `leverage` | decimal(10,2) | default 1 |
| `pnl`, `pnl_pct`, `net_pnl` | decimal nullable | `net_pnl` = pnl menos comisión |
| `commission` | decimal(20,8) nullable | |
| `slippage_pct` | decimal(10,6) nullable | Diferencia entre precio de señal y precio de ejecución real |
| `balance_before`, `balance_after` | decimal(20,8) nullable | |
| `exit_reason`, `regime` | string nullable | |
| `entry_time`, `exit_time` | timestamp | `exit_time` nullable |
| `status` | enum | Ver lista completa abajo |
| `error_message` | text nullable | |
| `audit_log` | **jsonb** (cambiado de json en `2026_06_26`) | Array de eventos: `{action, timestamp, data}` |
| `created_at`, `updated_at` | timestamps | |

**Valores posibles de `status`** (constraint final tras `2026_06_27_231408`): `pending_open`, `open`, `pending_close`, `closed`, `error`, `orphaned`, `failed`, `ignored`.

Índices: `(user_id, status)`, `(strategy, symbol, status)`, `(broker_account_id, status)`.

---

*(Continúa en la sección 3 con los Modelos Eloquent)*
## 3. Modelos Eloquent (Laravel)

### `User` (`app/Models/User.php`)
Extiende `Authenticatable`. Atributos fillable: `name, email, password, role, is_active`. Oculta `password, remember_token`. Casts: `email_verified_at => datetime`, `password => hashed`, `is_active => boolean`.

Relaciones: `realStrategySubscriptions()` (hasMany), `realTrades()` (hasMany), `brokerAccounts()` (hasMany).

Métodos de negocio:
- `isAdmin()`, `isConsultor()`, `isInversionista()` — comparan `role`.
- `canViewPaperTrading()` → `true` si role es `admin` o `inversionista`.
- `canViewAnalysisTools()` → `true` si role es `admin` o `consultor`.
- `canViewRealTrading()` → `true` si role es `admin` o `inversionista`.
- `canManageUsers()` → `true` solo si `isAdmin()`.
- `canCreateDemoAccounts()` → `true` si `isAdmin()` **o** si `config('trading.allow_investor_demo_accounts')` está activo (false por defecto).

### `BrokerAccount` (`app/Models/BrokerAccount.php`)
Fillable: `user_id, broker, account_type, label, api_key, api_secret, status`. Casts: `api_key => encrypted`, `api_secret => encrypted`. Hidden (no se serializan nunca): `api_key, api_secret`.

Relaciones: `user()` (belongsTo), `subscriptions()` (hasMany → RealStrategySubscription).

Métodos: `isDemo()`, `isReal()`, `isActive()`. Scopes: `forUser($userId)`, `active()`.

### `CollectorConfig` (`app/Models/CollectorConfig.php`)
Tabla `collector_configs`. Fillable: `symbol, interval, active, notes`. Cast `active => boolean`.

Scopes: `active()`, `forSymbol($symbol)`.

Métodos estáticos usados por el motor Python indirectamente (vía el controller de Backtesting que los expone al formulario):
- `activeSymbols()` — símbolos únicos activos, ordenados.
- `activeIntervals()` — intervalos únicos activos, ordenados.
- `activeIntervalsForSymbol($symbol)` — intervalos activos para un símbolo específico.

### `RiskControl` (`app/Models/RiskControl.php`)
Fillable: `strategy, symbol, reason, value, threshold, active, paused_at, auto_resume_at, resumed_at`. Casts numéricos a `decimal:4`, fechas a `datetime`.

Scopes: `active()`, `global()` (strategy y symbol ambos null), `forStrategy($strategy)`.

Método `resume()` — marca `active=false` y registra `resumed_at = now()` (uso manual desde el lado Laravel; el motor Python no llama a este modelo directamente, opera sobre la tabla con SQL crudo vía `RiskManager` en Python).

Método estático `reasonLabel($reason)` — traduce el enum a texto legible en español para la interfaz.

### `PaperStrategyConfig` (`app/Models/PaperStrategyConfig.php`)
Tabla `paper_strategy_configs`. Fillable: lista extensa que incluye todos los campos de estrellas y métricas (ver esquema en sección 2). Casts: `params => array`, `active => boolean`.

Scope: `active()`.

**`pythonModulePath()`** — mapea `strategy_class` al path de módulo Python que debe importarse dinámicamente:
```
VwapStrategy          → backtesting.strategies.vwap_strategy
MeanReversionStrategy → backtesting.strategies.mean_reversion
EmaDonchianStrategy   → backtesting.strategies.ema_donchian
```
Lanza `InvalidArgumentException` si la clase no está en el mapa. (Nota: este método no parece ser invocado actualmente desde el motor Python, que tiene su propio mapa equivalente `STRATEGY_CLASS_MAP` duplicado en `paper_trading.py` y `real_trading.py` — ver sección de hallazgos en el documento aparte.)

**`strategyNameToClassAndMode($strategyName)`** (estático) — mapea el nombre visible en la interfaz al par `{class, mode}`:
```
'VWAP Tendencia'         → {class: VwapStrategy, mode: trend_follow}
'VWAP Reversión'         → {class: VwapStrategy, mode: reversion}
'Reversión a la Media'   → {class: MeanReversionStrategy, mode: null}
'Tendencia EMA/Donchian' → {class: EmaDonchianStrategy, mode: null}
```
Lanza excepción si el nombre no coincide con ninguno.

**`classAndModeToStrategyName($class, $mode)`** (estático) — la operación inversa, usada al precargar el formulario de re-test desde una configuración existente.

**`implementFromBacktest($strategyName, $symbol, $interval, $params, $displayNameOverride = null)`** (estático) — el método más importante del modelo. Flujo:
1. Resuelve `{class, mode}` desde `$strategyName`.
2. Si hay `mode`, lo inyecta dentro de `$params['mode']`.
3. Construye el `display_name` (ej. "VWAP Tendencia — BTCUSDT H1") usando una tabla de etiquetas de intervalo (`1→1m, 5→5m, 15→15m, 60→H1, 120→H2, 240→H4, D→D1`).
4. Codifica `$params` a JSON y busca si ya existe una fila con la misma `strategy_class + symbol + interval` cuyo campo `params` sea JSONB-idéntico (operadores `@>` y `<@` combinados, que ignoran el orden de las claves pero exigen igualdad exacta de contenido).
5. Si encuentra una coincidencia exacta, actualiza esa fila (`display_name`, `active=true`) y la retorna — no crea un duplicado.
6. Si no hay coincidencia exacta, **crea una fila nueva** sin restricción adicional — permite múltiples configuraciones del mismo símbolo/estrategia/intervalo con parámetros distintos.

### `PaperTrade` (`app/Models/PaperTrade.php`)
Fillable incluye todos los campos de la tabla (ver esquema). Casts decimales explícitos para precisión monetaria, `entry_time`/`exit_time` a `datetime`.

Métodos: `isOpen()`, `isWinner()` (pnl > 0). Scopes: `open()`, `closed()`, `forStrategy($strategy)`.

### `RealTrade` (`app/Models/RealTrade.php`)
El modelo con más lógica de negocio embebida. Fillable extenso (todos los campos operativos de `real_trades`). Casts decimales explícitos en todas las columnas monetarias/porcentuales, `audit_log => array`.

Constantes de estado expuestas como clase: `STATUS_PENDING_OPEN`, `STATUS_OPEN`, `STATUS_PENDING_CLOSE`, `STATUS_CLOSED`, `STATUS_ERROR` (nótese que estas 5 constantes no cubren los 3 estados adicionales que sí existen en la constraint de base de datos: `orphaned`, `failed`, `ignored` — esos se manejan como strings sueltos en el código de Python y en queries directas, sin constante equivalente del lado Laravel).

Relaciones: `user()`, `subscription()` (belongsTo RealStrategySubscription via `subscription_id`), `brokerAccount()`, `paperStrategyConfig()`.

Métodos: 
- `isOpen()` → true si status es `open` o `pending_close`.
- `isClosed()` → true si status es `closed`.
- `isWinner()` → usa `net_pnl` si está disponible, si no cae a `pnl`.

Scopes: `open()` (incluye `open`, `pending_open`, `pending_close`), `closed()`, `forUser($userId)`, `forAccount($accountId)`, `forStrategy($strategy)`.

**`appendAuditLog($action, $data = [])`** — lee el `audit_log` actual, agrega una entrada `{action, timestamp (ISO 8601), data}` al final, y guarda. (Nota: existe un método equivalente del lado Python — `RealTrader.log_audit()` — que es el que efectivamente se usa en el flujo de ejecución real; este método de Eloquent parece ser una utilidad disponible para uso futuro desde Laravel, no está siendo invocada en el flujo actual.)

### `RealStrategySubscription` (`app/Models/RealStrategySubscription.php`)
Fillable: `user_id, broker_account_id, paper_strategy_config_id, strategy, symbol, interval, status`.

Relaciones: `user()`, `brokerAccount()`, `paperStrategyConfig()`, `trades()` (hasMany RealTrade vía `subscription_id`), `openTrades()` (igual pero filtrado a estados abiertos).

Métodos: `isActive()`. Scopes: `active()`, `forUser($userId)`.

**`pauseIfConfigInactive()`** — si la `paper_strategy_config` asociada ya no está activa, pasa la suscripción a `paused`. (No se observó ningún job o controller que llame a este método automáticamente — es una utilidad disponible, posiblemente pensada para correrse periódicamente o invocarse manualmente, pero no está conectada a ningún disparador actual.)

---

## 4. Controllers (Laravel) — función por función

### `DashboardController` (123 líneas)

**`index()`** — vista principal del sistema. Flujo:
1. Llama `getRegimes()` — GET interno a `/v1/regime/status` en el motor Python, devuelve el régimen cacheado de cada símbolo.
2. Construye un resumen mensual por grupo de estrategia (4 grupos fijos: "VWAP Tendencia", "VWAP Reversión", "Reversión a la Media", "Tendencia EMA/Donchian"), filtrando `paper_trades` por nombre de estrategia con coincidencia de prefijo, más un mapa de compatibilidad hacia atrás (`legacyMap`) para incluir trades de la estrategia ya retirada "VWAP Intradía" bajo el grupo "VWAP Tendencia".
3. Para cada grupo: cuenta trades cerrados del mes actual, wins, win rate, trades abiertos, PnL total.
4. Si el usuario tiene `canViewAnalysisTools()`, llama también `getCollectorStatus()` (GET a `/v1/collector/status`).
5. Calcula KPIs globales del mes (no por grupo): trades abiertos totales, PnL total, win rate global, y las 10 operaciones más recientes (`orderBy updated_at desc limit 10`).

`getRegimes()` y `getCollectorStatus()` son wrappers privados con `try/catch` que registran un warning en log y devuelven array vacío si el motor Python no responde — el dashboard nunca se rompe por una falla de comunicación con Python, simplemente muestra esas secciones vacías.

### `CollectorConfigController` (34 líneas)
- **`index()`** — autoriza `manageUsers`, lista todas las configs ordenadas por símbolo/intervalo, agrupadas por símbolo para la vista.
- **`toggleActive($config)`** — invierte el booleano `active` y guarda.

### `UserManagementController` (47 líneas)
- **`index()`** — lista usuarios paginados (10 por página), orden descendente por fecha de creación.
- **`toggleActive($user)`** — invierte `is_active`. Bloquea que un admin se desactive a sí mismo (`$user->id === auth()->id()` → error). **Efecto colateral importante**: al desactivar, pasa a `paused` todas las `RealStrategySubscription` activas de ese usuario — detiene la apertura de nuevas posiciones reales sin tocar las ya abiertas.

### `ProfileController` (60 líneas)
Estándar de Laravel: `edit()`, `update()` (resetea `email_verified_at` si cambia el email), `destroy()` (requiere reconfirmar contraseña vía `ProfileUpdateRequest`/validación `current_password`).

### `BrokerAccountController` (126 líneas)
- **`store()`** — flujo de alta de una cuenta de broker:
  1. Autoriza `viewRealTrading`.
  2. Determina tipos permitidos: solo `real`, salvo que `canCreateDemoAccounts()` permita también `demo`.
  3. Valida `broker, account_type, api_key (min:10), api_secret (min:10)`.
  4. Verifica unicidad manual (mensaje de error claro) antes de intentar el insert, aunque la constraint de base de datos también lo protegería.
  5. **Llama al motor Python** (`POST /v1/broker/validate-credentials`) para confirmar contra la API real de Bybit que las credenciales son válidas y tienen permisos suficientes, *antes* de guardar nada.
  6. Si son válidas, crea el registro con `label` autogenerado (`"Bybit Real"` / `"Bybit Demo"`).
- **`toggleStatus($account)`** — verifica ownership (`user_id === auth()->id()`, si no `abort(403)`), invierte `active`/`paused`. Si pasa a `paused`, también pausa todas sus suscripciones activas.
- **`destroy($account)`** — verifica ownership, bloquea el borrado si tiene suscripciones asociadas (debe eliminarlas primero).

### `RealStrategySubscriptionController` (131 líneas)
- **`store($account)`** — suscribe **una** configuración activa a la cuenta. Valida que la config exista y esté activa, verifica que no exista ya esa combinación cuenta+config, crea la suscripción copiando `strategy, symbol, interval` desde la config al momento de la creación (snapshot, no referencia viva — si luego cambia el `display_name` de la config, la suscripción ya creada conserva el nombre original a menos que se actualice manualmente).
- **`storeAll($account)`** — itera **todas** las configs activas y crea las suscripciones que falten, devolviendo cuántas se agregaron.
- **`toggle($account, $subscription)`** — verifica doble ownership (cuenta del usuario Y suscripción pertenece a esa cuenta), invierte `active`/`paused`.
- **`destroy($account, $subscription)`** — bloquea el borrado si la suscripción tiene `openTrades()` (operaciones reales abiertas) — debe esperarse a que cierren primero.

### `PaperTradingController` (165 líneas)
- **`index($request)`** — vista principal de Paper Trading. Lógica:
  1. Resuelve el mes a mostrar (`resolveMonth`) — toma `?mes=YYYY-MM` de la query, o el mes actual por defecto, acotado entre `earliestAllowedMonth()` y el mes actual (no se puede navegar a meses futuros ni anteriores al límite).
  2. `earliestAllowedMonth()` — si el usuario es `inversionista`, limita a los últimos 8 meses desde hoy; si no, usa la fecha del primer trade registrado en todo el sistema (o 2 años atrás si no hay ninguno).
  3. Filtros disponibles: `strategy` (coincidencia de prefijo `LIKE`), `symbol`, `interval`, `result` (`win`/`loss`).
  4. Trae posiciones abiertas (sin filtro de mes — siempre visibles) y les enriquece `current_price`/`floating_pnl_pct` consultando `getLiveOpenTrades()` (GET a `/v1/paper/open` en Python).
  5. Trae trades cerrados del mes filtrado, calcula KPIs: win rate, PnL total, profit factor (`grossProfit / |grossLoss|`), y una equity curve acumulada en porcentaje.
  6. `availableMonths()` — genera la lista de meses navegables hacia atrás desde el actual hasta `earliestAllowedMonth()`.
- **`live($request)`** — endpoint JSON liviano usado para refrescar precios sin recargar la página completa; devuelve solo `id, current_price, floating_pnl_pct` de las posiciones abiertas.
- `getLiveOpenTrades()` (privado) — wrapper HTTP con `try/catch` hacia Python, devuelve array vacío en caso de fallo.

### `PaperStrategyConfigController` (170 líneas)
- **`toggleActive($config)`** — autoriza `manageUsers`, invierte `active`.
- **`store($request)`** y **`implement($request)`** — **prácticamente idénticos** (mismo bloque de validación, misma lógica de creación/actualización, mismo bloque masivo de actualización de métricas). La única diferencia observable es el mensaje de éxito devuelto (`store` dice "creada", `implement` dice "implementada en Paper Trading") — funcionalmente intercambiables tal como están escritos hoy. Ambos:
  1. Validan un payload extenso: `config_id` opcional, `strategy_name, symbol, interval, params` (JSON como string) requeridos, y un conjunto largo de métricas/estrellas opcionales.
  2. Decodifican `params` desde JSON, devuelven error si no es JSON válido.
  3. **Si viene `config_id`** — actualiza esa fila existente directamente (`params`, `active=true`), sin pasar por la lógica de duplicados de `implementFromBacktest()`.
  4. **Si no viene `config_id`** — llama `PaperStrategyConfig::implementFromBacktest()` (con su lógica de detección de duplicados exactos descrita en la sección 3).
  5. En ambos casos, hace un segundo `update()` masivo con todos los campos de métricas/estrellas/rango de fechas del backtest que originó la implementación.
- **`destroy($config)`** — autoriza `manageUsers`, borra la fila.

### `TradingController` (275 líneas) — el más grande junto a Backtesting
- **`index($request)`** — vista principal de Trading Real, estructuralmente similar a `PaperTradingController::index()` pero con varias diferencias importantes:
  - El mes por defecto usa zona horaria `America/Bogota` explícitamente (`now('America/Bogota')`).
  - Filtros adicionales: además de `strategy/symbol/interval/result`, incluye `account` (filtra por `broker_account_id`).
  - Todas las queries se acotan primero a `BrokerAccount::where('user_id', $user->id)->pluck('id')` — cada usuario solo ve sus propias cuentas y trades, nunca los de otros usuarios (ni siquiera el admin ve los de otros desde esta vista).
  - PnL flotante de posiciones abiertas se calcula manualmente en PHP (no delega al motor Python para esto) usando precios obtenidos de `getLivePrices()`.
  - KPIs usan `net_pnl` cuando está disponible, con fallback a `pnl` si es null.
  - Equity curve está en **USDT absolutos** (no en porcentaje, a diferencia de Paper Trading).
- **`getTestnetPrices($symbols)`** (privado) — llama directamente a la API pública de Bybit testnet (`api-testnet.bybit.com`) sin pasar por el motor Python, usado específicamente cuando hay cuentas demo involucradas (los precios de testnet pueden diferir de los de mainnet).
- **`getLivePrices($symbols)`** (privado) — intenta primero leer de **Redis** directamente (`price:{symbol}`) usando la facade `Redis::get()`, y si no encuentra nada, cae a una petición HTTP al motor Python sobre un endpoint `/v1/prices` — **este endpoint no apareció implementado en ningún router Python explorado**, lo que sugiere que es una ruta de fallback nunca completada o que depende de un router no incluido en este análisis.
- **`availableMonths($accountIds)`** (privado) — igual patrón que en Paper Trading pero acotado a las cuentas del usuario, en zona horaria Bogotá.
- **`getAccountInfo($account)`** (privado) — cachea por 1 hora (`Cache::remember`) la información de permisos/expiración de la API key consultando `/v1/broker/account-info` en Python.
- **`accounts($request)`** — vista de gestión de cuentas: lista las cuentas del usuario con sus suscripciones (eager loading de `subscriptions.paperStrategyConfig`), las configuraciones activas disponibles para suscribir, y la info de cada cuenta (permisos/expiración) vía `getAccountInfo()`.
- **`livePrices($request)`** — endpoint JSON de refresco rápido para las posiciones abiertas del usuario. Detecta si alguna posición pertenece a una cuenta `demo` y en ese caso usa `getTestnetPrices()` en vez de `getLivePrices()`, para que los precios mostrados coincidan con el entorno real donde está la posición.

### `BacktestingController` (443 líneas) — el controller más extenso del proyecto

**Constante `STRATEGY_OPTIONS`** — mapa fijo de las 4 estrategias visibles en el formulario, cada una con `{class, mode, label}`.

**`calcularEstrellas($wr, $sharpe, $retMes, $consistencia, $pf)`** (privado) — implementa la tabla de calificación documentada en el Documento 1:
```
Win Rate:        <35→1, <45→2, <55→3, <65→4, ≥65→5
Sharpe Ratio:     <1→1,  <2→2,  <3→3,  <4→4,  ≥4→5
Retorno/mes:      <2→1,  <5→2, <10→3, <20→4, ≥20→5
Consistencia:    <40→1, <65→2, <85→3, <95→4, ≥95→5
Profit Factor:    <1→1,<1.5→2,  <2→3,<2.5→4, ≥2.5→5
```
`star_rating` final = promedio simple de las 5, redondeado a 1 decimal. Devuelve también las 5 calificaciones individuales para mostrarlas por separado en la interfaz.

**`index()`** — lista todas las `paper_strategy_configs` (activas e inactivas), ordenadas por clase de estrategia y símbolo.

**`run($request)`** — el método con más lógica del sistema. Comportamiento dual según el verbo HTTP:
- **GET**: construye `$symbols`/`$intervals` desde `CollectorConfig`, y `$paperConfigsForPreload` — un mapa de **todas las configs activas** con sus parámetros completos, serializado a JSON para que el JavaScript del formulario pueda precargar valores al elegir una combinación estrategia/símbolo ya existente. Devuelve la vista vacía (sin resultado de backtest aún).
- **POST**: 
  1. Resuelve `STRATEGY_OPTIONS[$strategyKey]`; si no existe, error.
  2. Construye un payload extenso para el motor Python: balance inicial fijo en 10.000, todos los parámetros de SL/TP/BE/duración/riesgo, `walk_forward=true` con `n_windows=5` fijo, `monthly_breakdown=true`.
  3. Agrega condicionalmente al payload: `mode` (si la estrategia lo requiere), `macro_trend_filter`, niveles TP2-TP4 (solo si vienen no vacíos), rango de fechas opcional, configuración de trailing stop (fijo o escalonado, parseando arrays paralelos `trailing_step_gain[]`/`trailing_step_sl[]`), protección por volatilidad, filtro de volumen, filtro horario legado (`hour_filter`), y los filtros de horas/días bloqueados (`blocked_hours[]`/`blocked_days[]`, solo si su checkbox `_active` correspondiente está marcado).
  4. POST a `/v1/backtest/run` en el motor Python con timeout de 180 segundos.
  5. Si responde con éxito: extrae `result`, construye `$implementParams` (el payload completo menos los campos puramente técnicos del backtest como `walk_forward`/`n_windows`/`initial_balance`, que no son parámetros de la estrategia en sí), y calcula las estrellas llamando a `calcularEstrellas()` con las métricas agregadas y el desglose mensual del resultado.
  6. Si falla la conexión o el motor responde error, captura la excepción y muestra un mensaje genérico.

**`runAjax($request)`** — variante de `run()` pensada para invocarse vía AJAX (probablemente para re-test rápido sin recargar página completa), construye el payload con el método privado `buildPayload()` en vez de repetir la lógica inline, y devuelve JSON en vez de una vista. Tiene su propio bloque de cálculo de estrellas duplicado del de `run()`.

**`buildPayload($request)`** (privado) — versión más compacta y reutilizable de la construcción de payload, usada solo por `runAjax()`. Contiene su propia copia de la lógica de filtros (volumen, horas/días bloqueados, trailing, volatilidad) — **es una segunda implementación paralela** a la que está inline dentro de `run()`, con el riesgo de que ambas se desincronicen si se modifica una sin la otra (ver documento de hallazgos).

**`retest($config)`** — endpoint JSON usado por el botón "Re-testear" desde la lista de configuraciones: traduce `strategy_class + mode` de vuelta al nombre visible, y devuelve los parámetros exactos de esa configuración (incluyendo sus stats del último backtest registrado) para precargar el formulario.

**`dataRange($symbol, $interval)`** — proxy hacia `/v1/backtest/data-range/{symbol}/{interval}` en Python, usado para mostrar al usuario el rango de fechas con datos disponibles antes de correr un backtest.

**`exportExcel($request)`** — recibe el resultado completo de un backtest ya ejecutado (como JSON serializado en un campo oculto del formulario, evitando tener que re-ejecutar el backtest solo para exportarlo), valida que tenga `monthly_breakdown`, y delega la generación del archivo a `App\Exports\BacktestMonthlyExport::download()`.

---

*(Continúa en sección 5 con Jobs programados)*
## 5. Jobs programados (Laravel)

Todos implementan `ShouldQueue` con `tries = 1` (sin reintentos automáticos de Laravel — si fallan, simplemente esperan al siguiente ciclo programado) y un `timeout` propio. Todos registrados en `routes/console.php` vía `Schedule::job(new XxxJob)->everyXxx()`.

### `CollectOhlcvDataJob` — cada minuto, timeout 120s
POST a `/v1/collector/run` (timeout HTTP 90s). Si la respuesta no es exitosa, log de warning con status y body. Si hay `total_saved > 0`, log de info con el detalle por símbolo/intervalo. Cualquier excepción se captura y loguea como error — el job nunca lanza una excepción no controlada.

### `DetectMarketRegimeJob` — cada 15 minutos, timeout 60s
POST a `/v1/regime/run` (timeout HTTP 45s). Por cada símbolo en la respuesta, si trae `regime` calculado, loguea `"Régimen {symbol}: {regime} (ADX: {adx})"`.

### `PaperTradingTickJob` — cada 5 minutos, timeout 60s
POST a `/v1/paper/tick` (timeout HTTP 45s). Procesa la respuesta:
- Por cada clave en `monitor` (`closed`, `be_activated`) con valor > 0, loguea info.
- Por cada clave en `signals` cuyo valor empiece con `"ABIERTA"`, loguea info con la estrategia y el resultado.

### `RealTradingTickJob` — cada 5 minutos, timeout 90s
El más elaborado de los 5 jobs:
1. Consulta `BrokerAccount::where('status','active')->whereHas('subscriptions', activa)->with(subscripciones activas + su paperStrategyConfig)`.
2. Si no hay cuentas con suscripciones activas, solo loguea debug y termina (no llama al motor Python si no hay nada que procesar).
3. Construye un payload anidado: por cada cuenta, sus credenciales (sin desencriptar explícitamente en el código del job — Eloquent ya las devuelve desencriptadas automáticamente por el cast `encrypted` del modelo al acceder a `$account->api_key`) y la lista de suscripciones con todos los datos necesarios para que Python pueda instanciar la estrategia (`strategy_class`, `config_params` = los `params` de la config, `risk_override_pct`).
4. POST a `/v1/real/tick` (timeout HTTP 75s).
5. Procesa la respuesta por cuenta: si trae `error`, loguea error y continúa con la siguiente cuenta. Si no, extrae `monitor.closed`/`monitor.errors` para logs de info/warning, y separa las señales en `opened` (las que empiezan con `"ABIERTA"`) y `errors` (las que empiezan con `"ERROR"` o `"EXCEPTION"`) para loguearlas individualmente. Finalmente arma un log de resumen tipo debug con conteos de monitoreadas/cerradas/nuevas/errores/sin-señal por cuenta.

### `RealTradingReconcileJob` — cada 5 minutos, timeout 120s
Construye un payload idéntico en estructura al de `RealTradingTickJob` (con las mismas cuentas y suscripciones activas), pero apunta a `/v1/real/reconcile` (timeout HTTP 90s). Procesa la respuesta logueando cada elemento de `results.reconciled` (warning, trade cerrado por reconciliación) y `results.orphaned` (error, posición huérfana detectada en Bybit), más un resumen final con conteos de `ok`/`reconciled`/`orphaned`.

---

## 6. Export a Excel (`app/Exports/BacktestMonthlyExport.php`)

Clase estática, sin instanciar — `BacktestMonthlyExport::download($result, $filename)` devuelve un `StreamedResponse` que el navegador descarga directamente como `.xlsx`, usando PhpSpreadsheet.

Genera **3 hojas**:

### Hoja "Resumen"
Encabezado con estrategia, símbolo, intervalo, fecha de ejecución, si fue aprobada. Tabla de métricas: total trades, win rate, Sharpe ratio, meses testeados, win rate promedio mensual, retorno promedio mensual, retorno total, mejor mes, peor mes, avg win, avg loss, max drawdown — coloreando en verde (`#3DD68C`) o rojo (`#F2545B`) las celdas de retorno según sean positivas o negativas. Al final, lista los `pass_reasons` (criterios de aprobación o motivos de rechazo) como viñetas de texto.

### Hoja "Parámetros completos"
Tabla de 2 columnas (Parámetro / Valor) que recorre un diccionario fijo de ~19 parámetros posibles (`sl_pct, tp_pct, tp2_pct...tp4_pct, be_pct, max_duration, risk_per_trade_pct, regime_filter, macro_trend_filter, mode, trailing_mode, trailing_distance_pct, trailing_steps, volatility_protection_mode, volatility_atr_multiplier, volatility_widen_pct, start_date, end_date`) con etiquetas en español, omitiendo los que no estén presentes o sean null/vacíos en `result['_implement_params']`. Booleanos se muestran como "Sí"/"No", arrays se serializan a JSON.

### Hoja "Mes a mes"
Una fila por mes del `monthly_breakdown`: mes, trades, ganadores, perdedores, win rate, P&L%. Color condicional verde/rojo en la columna de P&L. Al final agrega una fila de promedio (con fórmulas Excel `=AVERAGE(...)`) y una fila de suma total (`=SUM(...)`).

> Nota: el código fuente trae un comentario explícito "Sin columna P&L USDT" en esta hoja — solo se exporta el P&L en porcentaje, no en valor absoluto de moneda. Esto puede ser intencional (porque el backtest corre sobre un balance virtual arbitrario de 10.000, así que el valor en USDT no representaría nada significativo fuera de ese contexto) o una limitación pendiente de extender — no quedó explícito cuál de las dos en el código.

---

## 7. Middlewares y Gates

### Gates (`app/Providers/AppServiceProvider.php`, método `boot()`)
Los 5 Gates delegan directamente a los métodos `canXxx()` del modelo `User` documentados en la sección 3 — no contienen lógica propia, son solo el "pegamento" entre las rutas (`middleware('can:viewRealTrading')`) y los métodos del modelo.

### `EnsureUserIsActive`
No está referenciado en el grupo de middleware visible en `routes/web.php` explorado (que usa `['auth', 'verified']`) — probablemente está registrado globalmente en el kernel HTTP (`bootstrap/app.php` en Laravel 13, no explorado en este análisis) o como alias aplicado en otro punto no cubierto. Verificar el archivo de configuración del kernel si se necesita confirmar exactamente en qué grupo de rutas se aplica.

Lógica: si `Auth::user()` existe y `is_active` es false, cierra sesión, invalida la sesión, regenera el token CSRF, y redirige a login con un mensaje de error.

### `ExpireSessionAtMidnightColombia`
Misma situación de registro no confirmada en el kernel — referenciada por nombre pero el punto exacto de aplicación en el stack de middleware no quedó verificado en este análisis.

Lógica: en el primer request autenticado de una sesión, guarda `login_at` en la sesión. En requests subsiguientes, calcula la próxima medianoche en `America/Bogota` después de ese login, compara contra un tope duro de 24 horas desde el login, y usa lo que ocurra primero como momento de expiración efectivo. Si `now() >= effectiveExpiry`, cierra sesión igual que el middleware anterior.

---

## 8. API del motor Python — endpoint por endpoint

Todos los endpoints viven bajo el prefijo `/v1` (agregado en `main.py` al registrar cada router) y requieren el header `X-Internal-API-Key` salvo `/health`. El servidor escucha exclusivamente en `127.0.0.1:8002`.

### `collector.py` — prefijo efectivo `/v1/collector`

**`POST /collector/run`** — instancia `OhlcvCollector`, llama `run_all()` (actualiza todas las combinaciones símbolo/intervalo activas en `collector_configs`). Devuelve `{status, results: {symbol/interval: velas_guardadas}, total_saved}`.

**`POST /collector/initial-load`** — para cada config activa, si no tiene datos aún (`get_last_timestamp` devuelve null), descarga el histórico completo de 730 días. Si ya tiene datos, la salta (devuelve 0 para esa combinación). Pensado para ejecutarse una sola vez al dar de alta un símbolo nuevo.

**`GET /collector/status`** — para cada config activa, devuelve la última vela guardada (`last_candle`) y si tiene datos (`has_data`).

### `regime.py` — prefijo efectivo `/v1/regime`

**`POST /regime/run`** — instancia `RegimeDetector`, llama `detect_all()` (calcula el régimen de cada símbolo en `SYMBOLS`, lo guarda en Redis bajo `regime:{symbol}`, y lo devuelve también en la respuesta HTTP).

**`GET /regime/status`** — lee de Redis el régimen cacheado de cada símbolo configurado, sin recalcular nada.

**`GET /regime/{symbol}`** — igual que el anterior pero para un solo símbolo; `404` si no hay datos cacheados aún.

### `backtest.py` — prefijo efectivo `/v1/backtest`

**Modelo `BacktestRequest`** (Pydantic) — define todos los parámetros aceptables de un backtest, con sus defaults. Ver tabla completa en la sección 9.

**`load_ohlcv(pool, symbol, interval, start_date, end_date)`** — construye dinámicamente la query SQL agregando condiciones `time >= $N` / `time <= $N` solo si los parámetros de fecha vienen presentes, ordena ascendente por tiempo. Lanza `ValueError` si no hay ninguna fila (lo que se traduce en un `400` para el cliente).

**`load_strategy(request)`** — instancia la clase de estrategia correcta según `request.strategy`, empaquetando todos los parámetros extendidos del request en un diccionario `params` que se pasa al constructor de la estrategia. Maneja el caso especial de `macro_trend_filter`: solo lo agrega al diccionario si el cliente lo envió explícitamente (`is not None`), para que la estrategia pueda aplicar su propio default según el modo si el cliente no especifica nada. Asigna `allowed_regimes` fijo por estrategia (`["TRENDING"]` para VWAP en ambos modos y EMA/Donchian, `["RANGING"]` para Reversión a la Media). Si el nombre de estrategia no coincide con ninguna de las 4 conocidas, lanza `ValueError` con la lista de disponibles.

**`build_monthly_breakdown(trades, initial_balance)`** — agrupa una lista de trades cerrados por mes calendario (según `entry_time`, formato `YYYY-MM`), calculando por mes: total de trades, ganadores, perdedores, win rate, PnL absoluto y PnL porcentual sumados. Ordena cronológicamente.

**`POST /backtest/run`** — el endpoint central de todo el backtesting:
1. Carga el DataFrame OHLCV y la instancia de estrategia.
2. **Si `walk_forward=true`** (default):
   - Corre `WalkForwardValidator` sobre el DataFrame completo, obteniendo `result` con métricas walk-forward (out-of-sample).
   - **Si además `monthly_breakdown=true`** (casi siempre, desde el formulario web): construye régimen histórico completo, corre un `BacktestEngine` simple (sin walk-forward, sobre todo el rango) para obtener el desglose mes a mes legible cronológicamente — esto es necesario porque el walk-forward por sí solo no preserva continuidad temporal de los trades. **Además reemplaza las métricas agregadas devueltas (`result['aggregate_metrics']`) por las del backtest completo simple**, no por las del walk-forward, para que los KPIs mostrados en pantalla coincidan exactamente con el desglose mensual que se muestra debajo (eran inconsistentes antes de este ajuste — eran dos fuentes de verdad distintas mostrándose juntas). También recalcula `passed`/`pass_reasons` con los umbrales del backtest completo (Win Rate ≥45%, Sharpe ≥1, Drawdown ≤15% — nótese que estos umbrales del backtest completo son ligeramente distintos a los 5 criterios del walk-forward original descritos más abajo).
3. **Si `walk_forward=false`**: corre directamente un `BacktestEngine` simple sobre todo el rango, sin ninguna validación fuera de muestra.
4. Devuelve `{status: "ok", result}`.

Manejo de errores: `ValueError` (datos insuficientes, estrategia desconocida) → HTTP 400. Cualquier otra excepción → HTTP 500 con el mensaje, más log de error.

**`GET /backtest/strategies`** — lista estática informativa de las 4 estrategias con una breve descripción cada una (no consulta nada dinámico).

**`GET /backtest/data-range/{symbol}/{interval}`** — devuelve `MIN(time)`, `MAX(time)` y `COUNT(*)` de `ohlcv_data` para esa combinación, usado por el formulario para mostrar el rango disponible antes de correr un backtest.

### `paper_trading.py` — prefijo efectivo `/v1/paper`

**`STRATEGY_CLASS_MAP`** — diccionario que mapea `strategy_class` (string guardado en DB) a `(módulo_python, nombre_clase)`. Esta es una **copia independiente** del mismo mapa que existe también en `real_trading.py` — ambos deben mantenerse sincronizados manualmente si se agrega una estrategia nueva.

**`load_active_configs(pool)`** — SQL directo: `SELECT id, display_name, strategy_class, symbol, interval, params FROM paper_strategy_configs WHERE active = true`.

**`instantiate_strategy(config)`** — usa `importlib.import_module()` + `getattr()` para instanciar dinámicamente la clase correcta a partir del mapa, inyectando `symbol`/`interval` dentro de los `params` antes de construir la instancia. Lanza `ValueError` si la clase no está registrada en el mapa.

**`POST /paper/tick`** — el ciclo completo de Paper Trading, ejecutado cada 5 minutos por el job de Laravel:
1. Carga configs activas; si no hay ninguna, responde temprano con mensaje informativo.
2. Para cada config, instancia su estrategia (capturando errores individuales sin abortar todo el ciclo) y construye dos mapas: `strategies` (`display_name → clase`) y `config_map` (`display_name → config completa`).
3. Define `default_params` (valores de respaldo si una config no trae todos los campos).
4. Instancia `RiskManager` y llama `evaluate()` (ver sección 13) — esto puede generar nuevas pausas o reactivar pausas vencidas, **antes** de tocar ninguna posición.
5. Instancia `PaperTrader` con todo lo anterior, llama `monitor_open_trades()` y luego `check_new_signals()` en secuencia.
6. Devuelve `{status, configs: N, risk: resultados_risk_manager, monitor: resultados_monitor, signals: resultados_señales}`.

**`GET /paper/open`** — construye el mismo set de estrategias/config_map que el tick, pero solo llama `get_open_trades_with_live_price()` — usado por la interfaz para mostrar posiciones abiertas con precio actual sin disparar ningún ciclo de trading.

**`GET /paper/summary`** — agregación SQL directa (`GROUP BY strategy`) sobre `paper_trades`: total cerrados, ganadores, abiertos, PnL total porcentual por cada `display_name` de estrategia.

**`GET /paper/trades/{strategy}`** — últimos 200 trades (abiertos y cerrados) de una estrategia específica, ordenados por fecha de entrada descendente.

### `real_trading.py` — prefijo efectivo `/v1/real`

Modelos Pydantic: `SubscriptionPayload` (espejo de lo que envía `RealTradingTickJob`/`RealTradingReconcileJob` por cada suscripción), `AccountPayload` (espejo de cada cuenta con su lista de suscripciones), `RealTickRequest` (lista de cuentas — el body completo de ambos endpoints principales).

**`instantiate_strategy(sub)`** — análoga a la de `paper_trading.py` pero recibe un objeto `SubscriptionPayload` en vez de un dict crudo, y además **asigna `instance.params = params`** explícitamente después de construir la instancia (guardando los parámetros originales como atributo accesible, algo que la versión de paper trading no hace de la misma forma explícita).

**`_setup_jsonb_codec(conn)`** — registra codecs personalizados de `asyncpg` para que las columnas `jsonb`/`json` de PostgreSQL se serialicen/deserialicen automáticamente como diccionarios Python (`json.dumps`/`json.loads`) en cada conexión del pool — necesario porque este router maneja directamente el campo `audit_log` (jsonb) con operaciones de lectura/escritura más complejas que los otros routers.

**`POST /real/tick`** — el endpoint más complejo de todo el sistema. Por cada cuenta del payload:
1. **Verifica el circuit breaker**: cuenta errores en las últimas 2 horas (`get_circuit_breaker_errors`); si supera el umbral (3), clasifica los últimos mensajes de error como críticos o no críticos según una lista de patrones de texto conocidos como "no críticos" (problemas de firma, timestamp, código 10001, SL/TP inválido, rechazo de Bybit, qty inválida, "no confirmada"). Si hay al menos un error que **no** matchea ningún patrón no-crítico, se considera crítico y **pausa la cuenta entera** (`pause_account`), saltándose el resto del procesamiento para esa cuenta. Si todos los errores son no-críticos, los limpia (`clear_non_critical_errors`, los marca como `ignored`) y continúa procesando con normalidad.
2. Instancia `BybitClient` con las credenciales de la cuenta (ya desencriptadas por Laravel antes de llegar aquí).
3. Llama `monitor_open_trades(account.id, client)` — revisa todas las posiciones reales abiertas de esa cuenta.
4. Para cada suscripción de la cuenta, instancia su estrategia y llama `check_new_signals()`, capturando cualquier excepción individual sin abortar el procesamiento de las demás suscripciones.
5. Acumula resultados por cuenta bajo la clave `account_{id}_{broker}`.

**`POST /real/reconcile`** — el segundo endpoint crítico de seguridad, también iterando por cuenta:
1. Para cada trade abierto en DB (`get_open_trades`): si tiene menos de 10 minutos de antigüedad, se omite (da tiempo a que la apertura termine de procesarse sin interferencias). Si no, consulta la posición real en Bybit — si **no existe**, busca en el historial de PnL cerrado de Bybit (`get_closed_pnl`) verificando que el `avgEntryPrice` coincida con el `entry_price` del trade (tolerancia 0.1%) para evitar confundir el cierre con el de otra posición distinta del mismo símbolo, determina si fue por `StopLoss`/`TakeProfit` según el `orderType` que reporta Bybit, calcula el PnL, y actualiza la fila a `closed` con razón `reconciled_sl_tp_bybit` (o la razón específica detectada).
2. Adopta trades marcados como `orphaned` en DB: si Bybit *sí* tiene una posición abierta para ese símbolo (la orden original probablemente sí se ejecutó pero la confirmación nunca llegó al motor por un fallo de red transitorio), recalcula SL/TP reales usando el `avgPrice` de la posición real, los aplica vía `set_trading_stop`, y marca el trade como `open` con esos valores. Si Bybit *no* tiene posición para ese símbolo, marca el trade como `failed` definitivamente.
3. Detecta posiciones huérfanas en sentido inverso: existen en Bybit pero **no hay ninguna fila en DB** que las represente. Para cada símbolo único entre las suscripciones de la cuenta, si Bybit reporta una posición abierta y no hay trade registrado (doble verificación: `has_open_trade()` más una consulta SQL directa adicional por si acaso), inserta una nueva fila en `real_trades` directamente con estado `open` reconstruyendo los datos disponibles desde la posición de Bybit, y aplica SL/TP calculados con los parámetros de la primera suscripción que coincida con ese símbolo.

---

*(Continúa en sección 9 con el núcleo de backtesting)*
## 9. Núcleo de backtesting (Python)

### Tabla completa de parámetros — `BacktestRequest` (Pydantic, `api/v1/backtest.py`)

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| `strategy` | str | requerido | Nombre visible: "VWAP Tendencia", etc. |
| `symbol` | str | "BTCUSDT" | |
| `interval` | str | "60" | |
| `initial_balance` | float | 10000.0 | |
| `risk_per_trade_pct` | float | 1.0 | |
| `sl_pct` | float | 1.5 | |
| `tp_pct` | float | 3.0 | TP1 |
| `tp2_pct`, `tp3_pct`, `tp4_pct` | float opcional | None | Niveles adicionales, todos opcionales |
| `be_pct` | float | 2.0 | |
| `max_duration` | int | 24 | Velas |
| `regime_filter` | bool | True | |
| `walk_forward` | bool | True | |
| `n_windows` | int | 5 | |
| `train_pct` | float | 0.7 | |
| `mode` | str opcional | None | `trend_follow` \| `reversion` (solo VWAP) |
| `macro_trend_filter` | bool opcional | None | None = usar default de la estrategia según `mode` |
| `trend_persistence_filter` | bool | False | Solo VWAP Tendencia |
| `trend_persistence_bars` | int | 4 | |
| `trend_adx_threshold` | float | 25 | |
| `dynamic_sl_filter` | bool | False | Solo VWAP Tendencia |
| `adx_strong_threshold` | float | 30 | |
| `sl_pct_weak_zone` | float | 0.7 | |
| `start_date`, `end_date` | str opcional | None | Formato `YYYY-MM-DD` |
| `trailing_mode` | str opcional | None | None \| `fixed` \| `stepped` |
| `trailing_distance_pct` | float | 1.0 | |
| `trailing_steps` | list opcional | None | `[[gain_pct, new_sl_pct], ...]` |
| `volatility_protection_mode` | str opcional | None | None \| `close` \| `widen` |
| `volatility_atr_multiplier` | float | 2.5 | |
| `volatility_widen_pct` | float | 1.0 | |
| `volume_filter` | bool | False | |
| `volume_filter_period` | int | 20 | |
| `volume_filter_mult` | float | 1.2 | |
| `hour_filter` | bool | False | Filtro legado de rango horario |
| `hour_filter_start` | int | 7 | UTC |
| `hour_filter_end` | int | 21 | UTC |
| `weekend_filter` | bool | False | |
| `blocked_hours` | list[int] | [] | Horas UTC 0-23 a bloquear |
| `blocked_days` | list[int] | [] | 0=Lunes...6=Domingo |
| `monthly_breakdown` | bool | False | |

### `BacktestEngine` (`backtesting/engine.py`)

Constructor recibe `strategy, df, initial_balance, risk_per_trade_pct, regime_data`. `regime_data` es un diccionario `{timestamp_string: regime}` precalculado externamente (por `WalkForwardValidator` o construido ad-hoc) — si no se provee, **todas las barras se tratan como régimen "TRENDING"** (`_get_regime_at` devuelve ese default si `regime_data` está vacío).

**`_calculate_position_size(entry_price, sl_price)`** — `riesgo_dinero = balance * risk_pct/100`, tamaño = `riesgo_dinero / |entry - sl|`, redondeado a 6 decimales. Devuelve 0 si la distancia de SL es cero (evita división por cero).

**`_get_active_tp(position)`** — recorre `tp4, tp3, tp2, tp1` en ese orden de prioridad y devuelve el primero que no sea `None` junto con su etiqueta (`take_profit_4`, etc).

**`run()`** — el simulador de trade-a-trade, bar por bar:
1. Llama `strategy.prepare(df)` y `strategy.generate_signals(df)` para obtener el DataFrame con todos los indicadores y la columna `signal` calculados de una vez (vectorizado donde es posible).
2. Si la estrategia tiene `volatility_protection_mode` activo, precalcula `_atr` y `_atr_avg` (rolling 50) sobre todo el DataFrame antes del loop.
3. Itera desde la barra 1 (la 0 se usa solo como referencia de "anterior"):
   - **Si hay posición abierta**: evalúa en este orden estricto — primero intenta activar Break-even (mueve SL a entrada si el precio tocó el nivel BE y aún no estaba activado), luego aplica trailing stop si corresponde (puede mover el SL más allá de lo que hizo el BE), luego evalúa protección por volatilidad (puede forzar cierre inmediato o ensanchar el SL), luego evalúa Stop Loss, luego evalúa Take Profit recorriendo TP4→TP3→TP2→TP1 con la primera coincidencia ganando, y finalmente, si nada de lo anterior cerró la posición, evalúa cierre por tiempo máximo (`bars_open >= strategy.max_duration`). Si algo cerró la posición, calcula PnL, actualiza el balance interno de la simulación, y registra el trade completo en `self.trades`.
   - **Si no hay posición abierta** y la barra **anterior** tuvo una señal distinta de 0 (las señales se ejecutan con un retraso de una barra, simulando que la decisión se toma al cierre de una vela y se ejecuta en la apertura de la siguiente — esto evita look-ahead bias): determina el lado, calcula el precio de entrada como el **open** de la barra actual, consulta el régimen en ese momento y verifica `should_operate()`. Si la estrategia marcó un `signal_sl_pct` específico para esa señal (mecanismo del SL dinámico por zona ADX de VWAP Tendencia), lo usa en vez del `sl_pct` fijo de la estrategia. Calcula TP1 y Break-even, calcula TP2-TP4 si la estrategia los soporta (`calculate_tp_levels` si existe, si no cae al método legado `calculate_tp2`), calcula el tamaño de posición, y si es mayor a cero, abre la posición.
4. Al terminar el loop, llama `calculate_metrics(self.trades, initial_balance)` y agrega la equity curve completa al resultado.
5. Devuelve un diccionario con `backtest_id` (generado con timestamp + símbolo + nombre de estrategia en mayúsculas), `strategy, symbol, interval, total_bars, metrics, trades` (la lista completa de trades individuales, cada uno con toda la información de entrada/salida/razón/régimen).

### `calculate_metrics` (`backtesting/metrics.py`)

Recibe una lista de trades (diccionarios con al menos `pnl`, `pnl_pct`, `regime`) y un balance inicial.

Cálculos:
- **Win rate**: % de trades con `pnl > 0`.
- **Profit factor**: `suma_ganancias / |suma_pérdidas|`. Si no hay pérdidas pero sí ganancias, `infinity` (que luego se serializa como `None` en la respuesta final). Si no hay ganancias, 0.
- **Sharpe ratio**: construye una equity curve a partir del PnL acumulado, calcula los retornos porcentuales barra-a-barra (`pct_change()`), y si la desviación estándar de esos retornos es mayor a `1e-8` (evita división por casi-cero), calcula `(media_retornos / std_retornos) * sqrt(252)` — la anualización asume 252 "periodos de trading" pero aquí cada "periodo" es realmente un trade, no un día, así que el valor resultante no es estrictamente un Sharpe anualizado clásico sino una aproximación. El resultado se recorta (`clip`) entre -100 y 100 para evitar outliers absurdos cuando hay muy pocos trades con varianza casi nula.
- **Max drawdown**: pico-a-valle máximo sobre la equity curve, en porcentaje, valor absoluto.
- **Win rate por régimen**: agrupa por la columna `regime` de cada trade (si está presente) y calcula trades/win_rate/pnl para cada valor único de régimen encontrado.
- **Total return %**: `(balance_final - balance_inicial) / balance_inicial * 100`.

Si la lista de trades está vacía, devuelve una estructura `_empty_metrics()` con todos los valores en 0/None — nunca lanza excepción ni devuelve `None` directamente.

### `WalkForwardValidator` (`backtesting/walk_forward.py`)

Constructor: `strategy, df, initial_balance, risk_per_trade_pct, train_pct (0.7), n_windows (5), regime_data`.

**`_split_windows()`** — divide el DataFrame completo en `n_windows` segmentos consecutivos de igual tamaño (el último segmento absorbe el resto si la división no es exacta). Dentro de cada ventana, separa el primer `train_pct` (70%) como datos de entrenamiento (no usados directamente para simular, solo conceptualmente reservados) y el resto (30%) como datos de prueba (`test_df`) — el motor en este proyecto **no ajusta parámetros automáticamente con los datos de entrenamiento**; el walk-forward aquí sirve únicamente para medir el desempeño fuera de muestra con parámetros fijos provistos por el usuario, no para optimización automática.

**`_build_regime_data(df)`** — calcula ATR, ADX, BB Width sobre el DataFrame completo recibido, y para cada barra a partir de la posición 50 (las primeras 50 se descartan por no tener suficiente historial para los promedios móviles), clasifica el régimen y lo guarda en un diccionario indexado por el string de timestamp de esa barra.

**`run()`**:
1. Divide en ventanas.
2. Para cada ventana cuyo `test_df` tenga al menos 50 barras (si tiene menos, se salta con un warning), construye el régimen histórico **solo sobre ese segmento de test** (no sobre todo el dataset) y corre un `BacktestEngine` aislado sobre ese segmento.
3. Acumula los resultados de cada ventana (`window_results`, una entrada por ventana con sus propias métricas) y concatena **todos** los trades individuales de todas las ventanas de test en `all_test_trades`.
4. Calcula métricas agregadas sobre la unión completa de trades fuera de muestra de las 5 ventanas (`aggregate_metrics`), no el promedio de las métricas por ventana — es una agregación de trades crudos, más robusta estadísticamente que promediar 5 cifras de Sharpe distintas.
5. Evalúa criterios de aprobación con `_evaluate()`.

**`_evaluate(window_results, aggregate)`** — los 5 criterios mínimos de aprobación walk-forward (distintos de los criterios que luego se recalculan sobre el backtest completo simple en `api/v1/backtest.py`, ver nota en sección 8):
```
Trades totales ≥ 10
Sharpe Ratio   > 0.5
Win Rate       > 45%
Max Drawdown   < 15%
Profit Factor  > 1.2  (solo si no es None)
```
Si todos pasan, `passed=true` y `reasons=["Estrategia aprobada para paper trading"]`. Si alguno falla, `passed=false` y `reasons` acumula un mensaje descriptivo por cada criterio incumplido (puede haber varios simultáneamente).

---

## 10. Estrategias de trading (Python)

### `BaseStrategy` (`backtesting/strategies/base_strategy.py`) — clase abstracta

Todas las estrategias heredan de aquí. Define el contrato `generate_signals(df) -> df` como método abstracto obligatorio, y `prepare(df) -> df` como hook opcional (por defecto no hace nada, cada estrategia hija lo sobrescribe para calcular sus propios indicadores).

**Atributos inicializados desde `params` en el constructor**: `symbol, interval, sl_pct, tp_pct, be_pct, max_duration, regime_filter`, los 3 filtros de volumen (`volume_filter*`), filtro horario legado (`hour_filter*`), `weekend_filter`, `blocked_hours`, `blocked_days` (estos 3 últimos quedan **inicializados dos veces** de forma idéntica en el código fuente — ver hallazgos), los 3 niveles de TP opcionales (`tp2_pct, tp3_pct, tp4_pct`), configuración de trailing (`trailing_mode, trailing_distance_pct, trailing_steps`), y configuración de protección por volatilidad (`volatility_protection_mode, volatility_atr_multiplier, volatility_widen_pct`).

**Filtros aplicables a la columna `signal` de un DataFrame ya calculado** (cada uno anula señales que caigan en la condición bloqueada, sin tocar las demás):
- `apply_volume_filter(df)` — calcula `volume_ma` (media móvil del periodo configurado) y anula señales donde `volume < volume_ma * mult`.
- `apply_hour_filter(df)` — anula señales fuera del rango `[hour_filter_start, hour_filter_end)` en UTC.
- `apply_weekend_filter(df)` — anula señales en sábado/domingo (día de semana ≥ 5).
- `apply_blocked_hours(df)` — anula señales cuya hora UTC esté en la lista `blocked_hours`.
- `apply_blocked_days(df)` — anula señales cuyo día de semana esté en la lista `blocked_days`.

Todas estas funciones devuelven el DataFrame sin cambios si su filtro correspondiente está desactivado (`False` o lista vacía) — son no-ops seguros por defecto.

**`should_operate(regime)`** — si `regime_filter` es False, siempre devuelve True (sin restricción). Si está activo, devuelve `regime in self.allowed_regimes`.

**`calculate_sl_tp(entry_price, side)`** — fórmula directa: para `long`, SL = entry × (1 - sl_pct/100), TP = entry × (1 + tp_pct/100); para `short`, lo inverso. Redondeado a 8 decimales.

**`calculate_tp_levels(entry_price, side)`** — versión generalizada que calcula los 4 niveles a la vez (TP1 a TP4), devolviendo `None` para los niveles cuyo porcentaje no esté configurado.

**`calculate_tp2(entry_price, side)`** — método legado, calcula solo TP2 (usado por compatibilidad donde no se llama a `calculate_tp_levels`).

**`calculate_breakeven(entry_price, side)`** — precio al que se activa el movimiento de SL a entrada.

**`calculate_trailing_sl(entry_price, side, current_price, current_sl)`** — si `trailing_mode` es `None`, devuelve el SL sin cambios. Calcula primero el `gain_pct` actual respecto a la entrada; si es ≤0 (la posición no está en ganancia), no mueve nada. En modo `fixed`, calcula un SL candidato a `trailing_distance_pct` del precio actual y solo lo adopta si mejora (nunca más) el SL existente (`max()` para long, `min()` para short — el trailing nunca retrocede). En modo `stepped`, busca entre los `trailing_steps` configurados cuál es el umbral de ganancia más alto ya alcanzado, y mueve el SL al nivel correspondiente a ese escalón (expresado como % desde la entrada, no desde el precio actual).

**`check_volatility_protection(current_sl, side, current_atr, avg_atr)`** — si `volatility_protection_mode` es `None` o `avg_atr` es 0, no hace nada. Si `current_atr <= avg_atr * volatility_atr_multiplier`, tampoco actúa (la volatilidad no es lo suficientemente extrema). Si se supera el umbral: en modo `close`, indica cerrar inmediatamente al precio de mercado; en modo `widen`, calcula un nuevo SL más alejado (ensanchado en `volatility_widen_pct`) para dar más margen ante el ruido.

### `VwapStrategy` (`backtesting/strategies/vwap_strategy.py`) — 342 líneas, la más elaborada

Unifica dos comportamientos bajo un único parámetro `mode`:

**`mode = "trend_follow"`** (VWAP Tendencia):
- Calcula VWAP acumulado diario (`_calculate_vwap_base`) y una desviación estándar simplificada por día (`_calculate_vwap_std_simple`), bandas `vwap_upper`/`vwap_lower` a `vwap_std_filter` (default 1.5) desviaciones.
- Calcula una EMA de tendencia (`ema_trend_period`, default 50).
- Señal **long**: la barra anterior cerró en o por debajo del VWAP, la actual cierra por encima, y el cierre actual está por encima de la EMA de tendencia (confirmación de tendencia alcista). Señal **short**: lo simétrico.
- **Filtro de tendencia macro** (opcional, activo por defecto en modo `trend_follow` si se especifica explícitamente, pero el default base del modo es `False` salvo que el cliente lo pida): resamplea el propio DataFrame H1 a bloques de `macro_trend_interval_hours` (default 4, es decir H4), calcula una EMA50 sobre esas velas resampleadas, clasifica cada bloque H4 como BULLISH/BEARISH, y propaga (forward-fill) esa clasificación a cada vela H1 contenida en el bloque. Si la tendencia macro es BEARISH, bloquea señales long; si es BULLISH, bloquea señales short — el objetivo es evitar entrar a favor de un pullback de corto plazo que va contra la tendencia mayor.
- **Filtro de persistencia de tendencia** (opcional): calcula ADX manualmente (réplica del cálculo estándar, no reutiliza el de `indicators/regime_indicators.py` — implementación duplicada) y exige que el ADX haya estado por encima de `trend_adx_threshold` durante `trend_persistence_bars` velas consecutivas antes de permitir la señal — filtra tendencias que recién empiezan y podrían ser ruido.
- **SL dinámico por zona ADX** (opcional): si está activo, al momento de cada señal evalúa el valor de ADX y, si cae en una "zona gris" entre `trend_adx_threshold` y `adx_strong_threshold` (tendencia presente pero no fuerte), usa un `sl_pct_weak_zone` más ajustado en vez del `sl_pct` normal para esa operación específica — reduce el riesgo en señales de convicción media sin bloquearlas por completo.

**`mode = "reversion"`** (VWAP Reversión):
- Calcula una desviación estándar ponderada por volumen y acumulada *intra-día* (`_calculate_vwap_std_rolling`) — más costosa computacionalmente que la versión simple de `trend_follow` porque itera barra por barra dentro de cada grupo de día para acumular correctamente.
- Bandas de entrada a `vwap_std_entry` (default 2.0) desviaciones.
- Señal **long** cuando el precio rompe por debajo de la banda inferior (se apuesta a que regresa al VWAP); **short** cuando rompe por encima de la superior.
- Aplica un control de "zona" (`zone_bars`, default 4): evita generar una segunda señal en la misma dirección dentro de la misma ventana de N barras, para no acumular entradas redundantes mientras el precio sigue extendido en el mismo lado.
- **Filtro de tendencia macro** (activo por defecto en este modo, a diferencia de `trend_follow`): bloquea señales long si la tendencia H4 es BEARISH, y señales short si es BULLISH — en este modo el filtro busca lo opuesto a la lógica de `trend_follow`: evitar apostar a una reversión que va contra la tendencia macro dominante.

`allowed_regimes` para ambos modos termina siendo `["TRENDING"]` salvo que el cliente lo sobrescriba explícitamente — un detalle que puede sorprender en el modo `reversion`, donde intuitivamente se esperaría operar en mercados laterales (`RANGING`), pero los backtests del equipo determinaron empíricamente que el modo reversión funciona mejor filtrado a régimen de tendencia fuerte.

### `MeanReversionStrategy` (`backtesting/strategies/mean_reversion.py`) — 65 líneas

`allowed_regimes = ["RANGING"]` por defecto. Calcula Bandas de Bollinger (`bb_period` default 20, `bb_std` default 2.0) y RSI (`rsi_period` default 14, usando suavizado exponencial `ewm` en vez del promedio móvil simple clásico de Wilder). Señal **long**: la barra anterior cerró en o por debajo de la banda inferior, la actual cierra por encima (confirmación de rebote), y el RSI está por debajo de `rsi_os + 10` (no exige sobreventa extrema exacta, da un margen de 10 puntos). Señal **short**: simétrico con la banda superior y `rsi_ob - 10`.

### `EmaDonchianStrategy` (`backtesting/strategies/ema_donchian.py`) — 66 líneas

`allowed_regimes = ["TRENDING"]` por defecto. Calcula dos EMAs (`ema_fast` default 9, `ema_slow` default 21) y un canal de Donchian (`donchian_period` default 20, máximo/mínimo de N barras previas, usando `.shift(1)` para no incluir la barra actual en el cálculo del canal). Define una "ventana de tendencia activa" (`trend_up_active`/`trend_down_active`): True si hubo una ruptura del canal en cualquiera de las últimas `trend_window` barras (default 10) — esto crea un "permiso temporal" tras una ruptura confirmada. Señal **long**: ocurre un cruce alcista de EMA rápida sobre lenta *mientras* la ventana de tendencia alcista sigue activa. Señal **short**: simétrico. La lógica busca capturar el cruce de medias solo cuando hay confirmación reciente de momentum direccional, no cruces aislados en mercado plano.

### Estrategias legadas sin uso activo

`vwap_intraday.py` (`VwapIntradayStrategy`) y `vwap_reversion.py` (`VwapReversionStrategy`) implementan lógicas muy similares a los dos modos de `VwapStrategy` actual, pero como clases separadas con su propio código duplicado en vez del parámetro `mode` unificado. Ningún router de la API (`backtest.py`, `paper_trading.py`, `real_trading.py`) las importa — confirmado por búsqueda directa en el código. Son predecesoras conservadas en el repositorio, posiblemente para referencia histórica de comparación de resultados durante el desarrollo, pero no forman parte del sistema en ejecución.

---

*(Continúa en sección 11 con Paper Trader y Real Trader)*
## 11. Ejecución: Paper Trader (`trading/paper_trader.py`)

Clase `PaperTrader`, constructor recibe `pool, strategies (dict display_name→clase), default_params, config_map (dict display_name→config completa)`. Instancia internamente su propio `RiskManager`. `VIRTUAL_BALANCE = 10000.0` — constante fija a nivel de módulo, **no** un balance que crece o decrece con el resultado acumulado de los trades (cada trade calcula su PnL porcentual contra este número fijo de 10.000, no contra un balance corriente que reflejaría el resultado de operaciones previas — el balance simulado no compone ganancias/pérdidas anteriores).

**`_get_params_for(display_name, symbol)`** — combina `default_params` con los `params` específicos de la config (si existe en `config_map`), donde los específicos siempre ganan. Si la config no existe en el mapa, usa el `symbol` recibido como parámetro de respaldo.

**`get_bars(symbol, interval)`** — últimas 200 velas de `ohlcv_data`, ordenadas ascendentemente para el cálculo de indicadores.

**`get_current_regime(df)`** — si hay menos de 64 barras, devuelve `"RANGING"` por defecto (datos insuficientes para indicadores estables). Si no, calcula ATR/ADX/BB Width y clasifica la última barra.

**`get_open_trades()`** — SQL directo de todas las filas `status='open'` en `paper_trades`.

**`has_open_trade(display_name, symbol)`** — verifica si existe una fila abierta para esa combinación exacta estrategia+símbolo (a diferencia del trading real, aquí no hay concepto de "cuenta", así que la unicidad es directamente por estrategia).

**`calculate_floating_pnl_pct(entry_price, current_price, side, size)`** (estático) — `PnL = (precio_actual - entrada) * size` (o invertido para short), expresado como porcentaje del `VIRTUAL_BALANCE` fijo.

### `open_trade(display_name, strategy_instance, symbol, side, entry_price, regime, interval)`
1. Obtiene los params específicos de la config y los reaplica sobre la instancia de estrategia ya construida (sobrescribe `sl_pct, tp_pct, tp2_pct, tp3_pct, tp4_pct, be_pct, max_duration` directamente como atributos del objeto) — esto es necesario porque la instancia de estrategia pasada al método pudo haberse creado con parámetros genéricos en otro punto del flujo, y aquí se garantiza que use los parámetros exactos de esa configuración antes de calcular nada.
2. Calcula SL, TP1, Break-even, y TP2 (si la estrategia lo soporta).
3. Calcula el tamaño de posición usando el `risk_per_trade_pct` de la config (o el default si no está especificado) sobre el `VIRTUAL_BALANCE` fijo.
4. Si el tamaño calculado es ≤0, aborta sin insertar nada (silenciosamente, sin loguear error).
5. Inserta la fila en `paper_trades` con estado `open` directamente (no hay estado intermedio `pending_open` como en real trading — no hay nada externo que confirmar, es una simulación instantánea).
6. Loguea la apertura con todos los niveles calculados.

### `close_trade(trade, exit_price, exit_reason)`
Calcula PnL absoluto y porcentual (contra `VIRTUAL_BALANCE`), actualiza `max_profit_pct`/`max_loss_pct` finales (tomando el máximo/mínimo entre el valor ya acumulado y el PnL de cierre), y marca la fila como `closed` con todos los campos de salida.

### `monitor_open_trades()`
1. Trae todas las posiciones abiertas.
2. Pre-instancia una estrategia por cada `display_name` configurado (con sus params específicos) **solo para poder leer su `max_duration`** más adelante — instancia completa solo para acceder a un atributo, sin usar su lógica de señales en este método.
3. Por cada trade abierto:
   - Obtiene el precio actual (con cache por símbolo dentro del mismo ciclo, para no pedir el mismo precio dos veces si hay varios trades del mismo símbolo).
   - Actualiza el MFE/MAE (`max_profit_pct`/`max_loss_pct`) con el PnL flotante actual, sin importar si el trade se cierra en este ciclo o no.
   - Evalúa Break-even: si se alcanza y no estaba activado, mueve el SL a la entrada (`update_breakeven`).
   - Evalúa Stop Loss.
   - Evalúa Take Profit: **si hay TP2 definido, tiene prioridad sobre TP1** (a diferencia del motor de backtesting que evalúa hasta 4 niveles con prioridad TP4>TP3>TP2>TP1, este monitor de paper trading en producción solo contempla explícitamente TP1 y TP2 en su lógica de cierre — los niveles TP3/TP4, aunque existen como columnas en la tabla y se calculan al backtest, no parecen tener un camino de cierre equivalente implementado aquí; ver hallazgos).
   - Evalúa cierre por tiempo usando el `max_duration` de la instancia de estrategia precargada correspondiente a ese `strategy` (con fallback a la primera instancia disponible si el nombre no coincide con ninguna — caso límite poco probable pero presente en el código).
4. Devuelve conteos: `checked, closed, be_activated`.

**`get_open_trades_with_live_price()`** — variante de solo lectura (no cierra nada, no modifica estado), usada por la interfaz para mostrar posiciones abiertas con su precio actual y PnL flotante calculado al vuelo.

### `check_new_signals()`
1. Si el *kill switch* global del Risk Manager está activo, devuelve inmediatamente un mensaje de bloqueo para todas las estrategias sin evaluar nada más.
2. Por cada estrategia configurada:
   - Si ya tiene una posición abierta para ese símbolo, salta con mensaje informativo.
   - Si el Risk Manager tiene esa estrategia/símbolo pausada (drawdown o volatilidad), salta con mensaje informativo.
   - Trae las últimas 200 barras; si son menos de 64, salta (datos insuficientes).
   - Calcula el régimen actual y verifica `should_operate()`.
   - Prepara los indicadores y genera señales sobre todo el DataFrame.
   - **Lee la señal de la penúltima barra** (`df.iloc[-2]`, no la última) — esto replica exactamente la misma lógica de "ejecutar con un retraso de una barra" del motor de backtesting (sección 9): la señal se calculó al cierre de la vela anterior, y se ejecuta contra el precio actual de mercado en este ciclo, simulando la misma demora realista que tendría cualquier sistema que opera sobre velas cerradas.
   - Si la señal es 0, salta. Si no, obtiene el precio actual real de mercado (vía la función pública `get_current_price` de `bybit_client.py`, que **siempre consulta mainnet** independientemente de si el trading real conectado usa testnet — Paper Trading usa precios de mercado real en todos los casos) y abre la posición.
3. Devuelve un diccionario `{display_name: mensaje_de_estado}` para cada estrategia procesada — este es el mismo diccionario que `PaperTradingTickJob` en Laravel filtra para loguear solo las aperturas exitosas (las que empiezan con `"ABIERTA"`).

---

## 12. Ejecución: Real Trader (`trading/real_trader.py`) — 1180 líneas

### `BybitClient` — wrapper de autenticación y llamadas a la API de Bybit V5

Constructor: `api_key, api_secret, account_type`. Selecciona automáticamente `BYBIT_TESTNET` o `BYBIT_MAINNET` como `base_url` según si `account_type == 'demo'`.

**Firma de requests** — Bybit V5 exige HMAC-SHA256 sobre una cadena específica según el tipo de request:
- `_sign(params)` — para requests GET: `timestamp + api_key + recv_window + query_string_ordenado`. `recv_window` fijo en `10000` ms (ajustado desde un valor menor anterior para tolerar mayor desfase de reloj/latencia de red).
- `_sign_body(body)` — para requests POST con JSON: `timestamp + api_key + recv_window + body_serializado_compacto`. El body se serializa con `json.dumps(body, separators=(',', ':'))` para garantizar que la cadena firmada sea byte-idéntica a la que efectivamente se envía (cualquier diferencia de espaciado invalidaría la firma).

**`get_balance()`** — consulta `wallet-balance` con `accountType=UNIFIED, coin=USDT`. Maneja varios formatos posibles de respuesta de Bybit: primero busca el coin `USDT` específico dentro de la lista de monedas de la cuenta, probando varios campos en orden de preferencia (`availableToWithdraw, walletBalance, equity, totalOrderIM`) hasta encontrar uno con valor no-cero; si no encuentra nada en el desglose por moneda, cae a los totales de la cuenta (`totalAvailableBalance, totalEquity`). Devuelve `None` explícitamente en errores de autenticación (HTTP 401/403) o si Bybit responde un `retCode` distinto de 0, distinguiendo ese caso de un balance legítimo de 0.

**`get_min_qty(symbol)`** — consulta `instruments-info` para obtener `minOrderQty` y `qtyStep` (el incremento mínimo permitido para el tamaño de orden de ese símbolo específico). Si falla la consulta, devuelve un fallback conservador de `(0.001, 0.001)`.

**`place_market_order(symbol, side, qty, sl, tp)`** — coloca una orden de mercado **con SL/TP provisionales incluidos en la misma orden** (Bybit permite definir stopLoss/takeProfit junto con la orden de apertura). El cálculo de esos provisionales:
```
is_demo = 'testnet' in base_url
sl_margin = 1.05 si demo, 1.02 si mainnet   →  SL: 5% demo / 2% mainnet
tp_margin = 0.90 si demo, 0.96 si mainnet   →  TP: 10% demo / 4% mainnet

SHORT: sl_prov = mark_price * sl_margin (arriba)
       tp_prov = mark_price * tp_margin (abajo)
LONG:  sl_prov = mark_price * (2 - sl_margin) (abajo)
       tp_prov = mark_price * (2 - tp_margin) (arriba)
```
Si no se pudo obtener el `mark_price` actual (fallo de red puntual), usa los SL/TP que el llamador haya pasado como respaldo, si los hay. Reintenta hasta 3 veces con 2 segundos de espera entre intentos si Bybit rechaza la orden, logueando el código y mensaje exacto de error de Bybit en cada intento fallido.

**`set_trading_stop(symbol, sl, tp, side)`** — reemplaza el SL/TP de una posición ya abierta (usado tanto para pasar de provisional a real tras confirmar la apertura, como para mover el SL a Break-even, como para corregir SL provisionales detectados en el monitor). Usa `positionIdx=0` (modo one-way, no hedge).

**`get_order(symbol, order_id)`** — consulta el estado puntual de una orden por su ID, usado para verificar si una orden de cierre ya fue `Filled`.

**`get_open_position(symbol)`** — lista posiciones de ese símbolo y devuelve la primera con `size > 0`, o `None` si no hay ninguna abierta. Es la función de verificación de estado más usada en todo el módulo.

**`get_closed_pnl(symbol)`** — consulta el último registro del historial de PnL cerrado de Bybit para ese símbolo (límite 1, el más reciente) — usado para reconstruir el precio y razón exactos de un cierre que el motor no capturó en tiempo real.

**`get_market_price(symbol)`** — precio actual (`lastPrice`) consultando la URL correcta según el entorno de la cuenta (testnet o mainnet) — a diferencia de la función pública `get_current_price` de `bybit_client.py` (siempre mainnet), este método respeta el entorno real de la cuenta que está operando.

### Clase `RealTrader`

`CIRCUIT_BREAKER_THRESHOLD = 3` (constante de módulo). `BYBIT_TAKER_FEE = 0.00055` (0.055%, comisión estimada usada para calcular el PnL neto al cerrar — no se consulta la comisión real exacta que cobró Bybit, se aproxima con esta tasa fija).

**`get_active_subscriptions()`** — query con 3 joins (`real_strategy_subscriptions` + `broker_accounts` + `paper_strategy_configs`) filtrando los tres por su respectivo estado activo simultáneamente. (Nota: este método existe en la clase pero no se observó que sea invocado desde ningún endpoint de la API actual — tanto `/real/tick` como `/real/reconcile` reciben las suscripciones ya armadas como payload desde Laravel, en vez de que Python las consulte directamente; este método parece ser una alternativa de consulta directa no conectada al flujo activo.)

**`get_open_trades(account_id)`** — trades con estado `open` o `pending_close` para esa cuenta específica.

**`has_open_trade(subscription_id, symbol)`** — primero resuelve el `broker_account_id` de la suscripción, y verifica si existe algún trade de **ese símbolo en esa cuenta** (no solo de esa suscripción específica) con estado en `pending_open, open, pending_close, orphaned` — esto previene que dos suscripciones distintas de la misma cuenta sobre el mismo símbolo abran posiciones duplicadas simultáneamente.

**Circuit breaker — funciones relacionadas**:
- `get_circuit_breaker_errors(account_id)` — cuenta filas con `status='error'` actualizadas en las últimas 2 horas.
- `get_last_error_messages(account_id)` — últimos 5 mensajes de error de esa ventana de tiempo (función duplicada en el código fuente, definida dos veces de forma idéntica).
- `clear_non_critical_errors(account_id)` — pasa todos los `error` recientes a `ignored` (función también duplicada).
- `pause_account(account_id, reason)` — `UPDATE broker_accounts SET status='paused'`.

**`log_audit(trade_id, action, data)`** — lee el `audit_log` actual de un trade (normalizando varios formatos posibles que puede tener el campo: lista directa, string JSON simple, o string JSON doblemente encodeado por algún path de escritura anterior), agrega una nueva entrada, y reescribe la columna completa como JSONB.

**`get_bars(symbol, interval)`** / **`get_current_regime(df)`** — equivalentes exactos a los métodos del mismo nombre en `PaperTrader`, código duplicado independiente.

### `open_trade(sub, strategy_instance, side, entry_signal_price, regime, client)` — el flujo completo descrito narrativamente en el Documento 1, sección 6. Aquí el detalle técnico exacto de cada paso:

1. `client.get_balance()` — aborta si es `None` o ≤0.
2. `client.get_market_price(symbol)` — si el precio actual difiere más de 2% del precio de la señal original, solo loguea un warning (no aborta todavía en este punto).
3. Calcula SL/TP1/BE sobre el precio actual de mercado (no sobre el precio de la señal). Calcula TP2 (vía `calculate_tp2` si existe) y TP3/TP4 manualmente desde los atributos `tp3_pct`/`tp4_pct` de la instancia de estrategia (no usa `calculate_tp_levels` aquí, a diferencia del motor de backtesting).
4. Determina el `risk_pct` efectivo: `risk_override_pct` de la suscripción si está presente y no es una cadena vacía/`'None'`/`'null'`, si no el `risk_per_trade_pct` de los parámetros de la config.
5. Calcula tamaño = `(balance * risk_pct/100) / |entry_signal - sl|`. Aborta si es ≤0.
6. Consulta lote mínimo y step size, aborta si el tamaño es menor al mínimo permitido. Redondea el tamaño al step size hacia abajo (`math.floor`), calculando dinámicamente cuántos decimales de precisión corresponden a ese step (vía `log10`). Aborta de nuevo si el redondeo deja el tamaño en 0.
7. Vuelve a consultar el balance justo antes de insertar (puede haber cambiado desde el paso 1 por otras operaciones concurrentes).
8. **Inserta la fila en `real_trades` con `status='pending_open'` antes de tocar Bybit** — este registro previo es la garantía de auditoría descrita en el documento general.
9. Recalcula SL/TP **otra vez** si el precio se movió más de 0.5% entre el momento del cálculo original y este punto justo antes de enviar la orden — el sistema tolera movimiento de mercado en dos puntos distintos del flujo (2% en el paso 2 solo como warning, 0.5% aquí con recálculo activo).
10. Actualiza la fila en DB con los SL/TP eventualmente recalculados.
11. `client.place_market_order()` — si devuelve `None` tras sus 3 reintentos internos, marca el trade como `error` con mensaje `"Orden rechazada por Bybit tras 3 intentos"`, registra auditoría, y aborta devolviendo `False`.
12. **Secuencia de confirmación** (la posición puede tardar en aparecer reflejada en el endpoint de posiciones de Bybit incluso después de que la orden fue aceptada):
    - Espera 1 segundo, consulta posición. Si existe, confirmado.
    - Si no, espera 5 segundos más (6 totales), consulta de nuevo.
    - Si sigue sin confirmar, entra en un bucle de hasta 3 reintentos adicionales con 10 segundos de espera cada uno (hasta ~38 segundos acumulados en el peor caso). **Antes de cada reintento**, vuelve a generar la señal con los datos más recientes para verificar que sigue siendo válida — si el mercado ya invirtió la dirección, aborta inmediatamente marcando el trade como `failed` con razón `"Senal no activa en reintento"`, sin seguir insistiendo con una orden que ya no tiene sentido. Si la señal sigue vigente, reintenta `place_market_order` (esta vez sin pasar SL/TP explícitos, dejando que la función recalcule sus provisionales con el mark price del momento).
    - Si después de todo el ciclo nunca se confirma, marca el trade como `orphaned` con mensaje `"No confirmada tras 3 reintentos (38s)"` — este es el estado que el job de reconciliación revisará más tarde para intentar adoptar la posición si efectivamente sí se ejecutó en Bybit pese a que el motor no logró confirmarlo a tiempo.
13. **Con la posición confirmada**, recalcula SL/TP/BE/TP2/TP3/TP4 *definitivos* usando el `avgPrice` real reportado por Bybit (que puede diferir del precio de la señal por slippage de ejecución).
14. Llama `set_trading_stop()` con los valores definitivos — si falla, solo loguea error (la posición queda protegida por los provisionales más amplios que ya estaban puestos desde el paso 11, no se aborta el trade en este punto porque ya está abierto y debe gestionarse).
15. Calcula `slippage_pct` = diferencia porcentual absoluta entre precio de señal original y precio de ejecución real.
16. **Actualiza la fila a `status='open'`** con reintentos propios (hasta 4 intentos con esperas crecientes `[2, 5, 30]` segundos) — si todos fallan, registra un log de nivel `critical` advirtiendo que la posición está abierta en Bybit pero la base de datos no pudo reflejarlo, un escenario de inconsistencia que requeriría intervención manual o que el job de reconciliación lo detecte en su próximo ciclo (la posición seguiría existiendo en Bybit aunque la fila en DB quedara en `pending_open` indefinidamente, hasta que la reconciliación la encuentre).
17. Registra auditoría final (`'opened'`) y loguea el resumen completo de la apertura.

### `close_trade(trade, exit_reason, client, account_id, exit_price_override=None)`

**Camino "override"** (cuando el monitor ya detectó que Bybit cerró la posición y solo hay que reflejarlo en DB, sin enviar ninguna orden): calcula PnL/comisión/PnL neto directamente con el precio de cierre ya conocido, consulta el balance actual tras el cierre, y actualiza la fila a `closed` en una sola operación. (Nota técnica: esta rama usa la variable `symbol` en su línea de log final sin haberla definido localmente dentro de esa rama del código — solo existe `trade['symbol']` disponible — lo que provocaría un `NameError` no controlado en tiempo de ejecución si ese log se alcanza a ejecutar; ver documento de hallazgos para el detalle exacto.)

**Camino normal** (cierre activo, debe enviar orden a Bybit): primero verifica que la posición siga existiendo en Bybit — si ya no existe (fue cerrada por fuera de este flujo, posiblemente por el propio SL/TP nativo de Bybit entre el momento en que el monitor la detectó y el momento en que llegó a este punto), reconcilia directamente marcando `closed` con razón genérica `'reconciled'` sin calcular PnL exacto en esa rama particular. Si la posición sigue ahí, marca `pending_close`, envía orden de mercado en sentido contrario, y espera confirmación consultando el estado de la orden hasta 6 veces (5 segundos entre cada intento, ~30 segundos máximo). Si nunca confirma `Filled`, usa el último precio de mercado conocido como aproximación del precio de salida en vez de bloquear el cierre indefinidamente. Calcula comisión estimada, PnL neto, actualiza la fila a `closed`, y registra auditoría completa.

### `update_breakeven(trade_id, new_sl, client, symbol, side, tp)`

A diferencia de la versión de Paper Trading (que solo actualiza la base de datos), esta versión **también actualiza el SL en Bybit** vía `set_trading_stop` si se proveen `client`/`symbol`/`side` — la justificación explícita en el comentario del código es que el SL debe quedar protegido directamente en el exchange "aunque caiga el servidor", es decir, que la protección no dependa de que el motor siga corriendo continuamente.

### `monitor_open_trades(account_id, client)`

Por cada trade abierto de la cuenta:
1. Consulta la posición real en Bybit. **Si ya no existe** (`pos_size <= 0`): intenta reconstruir el cierre exacto consultando `get_closed_pnl`, determinando la razón por el campo `orderType` de Bybit (`StopLoss`→`stop_loss`, `TakeProfit`/`PartialTakeProfit`→`take_profit_1`) o, si Bybit no especifica el tipo, infiriendo la razón comparando el precio de salida contra los niveles de SL/TP guardados en la fila. Si ni siquiera hay historial de PnL cerrado disponible, usa el precio de entrada como aproximación y marca razón `reconciled_sl_tp_bybit`. Llama `close_trade` con el camino "override" usando ese precio reconstruido.
2. **Si la posición sigue abierta**: primero verifica si el SL actual guardado en DB es "sospechosamente amplio" (más de 2.5% de distancia respecto a la entrada) — esto detectaría un caso donde el SL provisional de apertura nunca fue reemplazado por el real (por ejemplo si `set_trading_stop` falló silenciosamente en el paso 14 de `open_trade`). Si detecta esa condición, consulta el `sl_pct` real configurado para esa estrategia (vía un join SQL a través de `real_strategy_subscriptions`→`paper_strategy_configs`, con fallback a 0.8% si no encuentra nada) y reintenta aplicar el SL correcto.
3. Obtiene el precio actual de mercado (con cache por símbolo dentro del ciclo).
4. Evalúa Break-even: si se alcanza, llama `set_trading_stop` para mover el SL a la entrada **directamente en Bybit** (no solo en DB) y marca `be_activated=true`.
5. Evalúa cierre por duración máxima: consulta el `max_duration` real de la estrategia vía el mismo patrón de join SQL (con fallback a 24 si no encuentra nada), y si el tiempo transcurrido lo supera, llama `close_trade` con razón `time_exit`.
6. Cualquier excepción durante el procesamiento de un trade individual se captura, loguea con traceback completo, y se cuenta en `results["errors"]`, **sin abortar el procesamiento de los demás trades de la cuenta** — un fallo aislado en una posición no bloquea el monitoreo del resto.

Nota: a diferencia del monitor de Paper Trading (que evalúa Stop Loss y Take Profit activamente comparando el precio actual contra los niveles guardados), el monitor de Trading Real **no evalúa SL/TP por comparación de precio directamente** — confía en que Bybit los ejecute nativamente del lado del exchange (porque fueron configurados ahí mismo vía `place_market_order`/`set_trading_stop`), y este monitor solo se entera de esos cierres *a posteriori*, detectando que la posición ya no existe (paso 1 de este método). Es una diferencia de diseño coherente con operar dinero real: el cierre por SL/TP lo ejecuta el propio exchange de forma inmediata sin depender de que el ciclo de 5 minutos del motor llegue a tiempo, mientras que en Paper Trading (sin órdenes reales de por medio) el propio motor es quien simula y decide el cierre comparando precios.

### `check_new_signals(sub, strategy_instance, client)`

1. Doble verificación de duplicado: primero en DB (`has_open_trade`), luego directamente contra Bybit (`get_open_position`) — esta segunda verificación cubre el caso de una posición que exista en el exchange pero que por algún motivo la base de datos no refleje todavía como abierta.
2. Trae barras, verifica mínimo de 64, calcula régimen y verifica `should_operate()`.
3. Genera señales, lee la penúltima barra (mismo patrón de retraso de una barra que en Paper Trading y en el motor de backtesting).
4. Si hay señal, obtiene el precio actual real de mercado (respetando el entorno demo/mainnet de la cuenta vía `client.get_market_price`, a diferencia de Paper Trading que siempre usa mainnet) y llama `open_trade()`, envolviendo la llamada en un `try/except` adicional que captura cualquier excepción no prevista dentro del flujo completo de apertura y la reporta como string descriptivo en vez de dejar que se propague y rompa el procesamiento del resto de suscripciones de la cuenta.

---

*(Continúa en sección 13 con Risk Manager, Circuit Breaker, Collectors e Indicadores)*
## 13. Risk Manager y Circuit Breaker — detalle completo

### `RiskManager` (`trading/risk_manager.py`) — solo usado por Paper Trading

Constantes de módulo: `INITIAL_BALANCE = 10000.0` (debe coincidir conceptualmente con `VIRTUAL_BALANCE` de `paper_trader.py`, son dos constantes independientes definidas en archivos distintos con el mismo valor — no hay una única fuente compartida), `DAILY_DRAWDOWN_PCT = 3.0`, `TOTAL_DRAWDOWN_PCT = 10.0`, `VOLATILITY_MULTIPLIER = 2.0`.

**`is_kill_switch_active()`** — busca una fila activa en `risk_controls` con `reason='kill_switch_manual'` y `strategy IS NULL AND symbol IS NULL` (la pausa global). No hay ningún endpoint ni controller explorado que active este kill switch — su activación parece estar pensada para hacerse manualmente con una inserción SQL directa o una herramienta administrativa no cubierta en este análisis.

**`is_paused(strategy, symbol)`** — busca una pausa activa que aplique a esa estrategia en general (`symbol IS NULL`) o específicamente a esa combinación estrategia+símbolo.

**`get_pnl(strategy)`** — dos sumas sobre `paper_trades`: el PnL total histórico de todos los trades cerrados de esa estrategia, y el PnL del día actual (desde medianoche UTC) — ambos en valor absoluto de PnL, no porcentual.

**`create_pause(strategy, symbol, reason, value, threshold, auto_resume_at)`** — antes de insertar, verifica que no exista ya una pausa activa idéntica (misma razón + misma estrategia + mismo símbolo, tratando `NULL` correctamente con `OR` condicional) para evitar duplicados. Devuelve `False` sin hacer nada si ya existe.

**`resume_expired_pauses()`** — `UPDATE` masivo de todas las pausas activas cuyo `auto_resume_at` ya pasó, las marca `active=false` con `resumed_at=now()`. Parsea el conteo de filas afectadas desde el string de retorno crudo de `asyncpg` (`"UPDATE N"`).

**`check_volatility(symbol)`** — trae las últimas 100 velas H1, calcula ATR actual vs promedio de las últimas 50 velas; si la razón supera `VOLATILITY_MULTIPLIER` (2x), devuelve el detalle del exceso, si no devuelve `None`.

**`evaluate(strategies, symbols)`** — el método orquestador, llamado al inicio de cada tick de Paper Trading:
1. Reactiva pausas vencidas.
2. Si el kill switch global está activo, devuelve inmediatamente sin evaluar nada más (corte temprano).
3. Para cada estrategia: calcula drawdown diario y total en porcentaje sobre `INITIAL_BALANCE`. Si el diario cae igual o por debajo de `-3%`, crea una pausa con `auto_resume_at` fijado a la medianoche UTC siguiente (reactivación automática). Si el total cae igual o por debajo de `-10%`, crea una pausa **sin** `auto_resume_at` (requiere intervención manual de un administrador para reactivar).
4. Para cada símbolo: si detecta volatilidad extrema, crea una pausa **por cada estrategia** que opere en ese símbolo (no una pausa única a nivel símbolo, sino una réplica por estrategia) — esto significa que si 3 estrategias distintas operan BTCUSDT y BTCUSDT entra en volatilidad extrema, se crean 3 filas de pausa independientes, una por estrategia.
5. Devuelve un resumen con las nuevas pausas creadas, cuántas se reactivaron, y si el kill switch está activo.

### Circuit Breaker (Trading Real) — mecánica de clasificación de errores

A diferencia del Risk Manager (que es una clase dedicada con su propio archivo), el circuit breaker de Trading Real está implementado como lógica inline dentro de `api/v1/real_trading.py`, apoyándose en métodos auxiliares de la clase `RealTrader`. La lista exacta de patrones considerados "no críticos" (que se limpian automáticamente sin pausar la cuenta) es:

```python
non_critical_patterns = [
    'firma', 'timestamp', '10001', 'stopLoss', 'takeProfit',
    'rechazada por bybit', 'qty', 'invalid', 'no confirmada'
]
```

Un mensaje de error se considera "no crítico" si **contiene** (subcadena, insensible a mayúsculas) cualquiera de esos patrones. Solo si existe al menos un error reciente cuyo mensaje **no** contenga ninguno de esos patrones, la cuenta se pausa. En la práctica esto significa que errores de configuración de parámetros, problemas transitorios de firma/timestamp, o rechazos esperables de Bybit por validación de cantidad/precio, **no** disparan una pausa automática — el circuit breaker está calibrado para reaccionar ante fallos de naturaleza distinta a estos (por ejemplo, errores de conectividad sostenidos, fallos de autenticación reales, o cualquier excepción de Python no anticipada cuyo mensaje no caiga en ninguno de esos patrones conocidos).

---

## 14. Collectors e indicadores

### `indicators/regime_indicators.py`

**`calculate_atr(df, period=14)`** — True Range clásico (máximo entre rango intra-barra, gap alcista respecto al cierre previo, gap bajista respecto al cierre previo), suavizado con EMA (`ewm(alpha=1/period)`).

**`calculate_adx(df, period=14)`** — implementación estándar de Wilder: +DM/-DM direccionales, ATR para normalizar, +DI/-DI, DX, y finalmente ADX como suavizado exponencial de DX.

**`calculate_bb_width(df, period=20, std_dev=2.0)`** — ancho de Bandas de Bollinger normalizado por el precio (SMA), expresado en porcentaje.

**`classify_regime(adx, atr, atr_avg, bb_width, bb_width_avg)`** — la función de clasificación central, usada en todos los puntos donde se necesita régimen (backtesting, paper trading, real trading, el detector periódico):
```
si atr > atr_avg * 1.8           → VOLATILE   (prioridad máxima)
si adx > 25                       → TRENDING
si adx < 20 y bb_width < bb_width_avg → RANGING
en cualquier otro caso             → RANGING   (zona ambigua, default conservador)
```

### `collectors/ohlcv_collector.py` — `OhlcvCollector`

**`get_active_configs()`** — lee `collector_configs` activos; si la consulta falla por cualquier motivo, cae a un fallback construido desde variables de entorno (`SYMBOLS`, `INTERVALS`, producto cartesiano de ambas listas) — esto garantiza que el collector nunca se detiene completamente aunque la tabla de configuración tenga un problema puntual.

**`fetch_from_bybit(symbol, interval, start_ts, end_ts)`** — pagina hacia atrás en el tiempo usando el parámetro `end` de la API de Bybit (que limita a 200 velas por respuesta — `BYBIT_LIMIT`), avanzando el cursor `end_ms` al timestamp de la vela más antigua recibida menos 1ms en cada iteración, hasta cubrir todo el rango solicitado o hasta que Bybit deje de devolver velas. Pequeña pausa de 0.1s entre páginas para no saturar el rate limit del exchange. Al final invierte el orden del array acumulado para devolver las velas en orden cronológico ascendente.

**`save_bars(bars)`** — inserción masiva con `executemany` y `ON CONFLICT (symbol, interval, time) DO NOTHING` — las velas duplicadas (ya existentes) simplemente se ignoran sin error, lo que hace que `update()` pueda llamarse repetidamente de forma segura sin riesgo de duplicar datos.

**`initial_load(symbol, interval)`** — si ya existe al menos una vela para esa combinación, no hace nada (asume que la carga inicial ya se hizo en algún momento). Si no, descarga `HISTORY_DAYS = 730` días (2 años) hacia atrás desde el momento actual.

**`update(symbol, interval)`** — si no hay ninguna vela previa, delega directamente a `initial_load`. Si las hay, descarga solo desde la última vela guardada hasta ahora; si la diferencia es menor a 60 segundos, no hace ninguna llamada (evita pedir rangos triviales en cada tick de un minuto).

**`run_all()`** — itera todas las configs activas llamando `update()` en cada una, capturando errores individuales por símbolo/intervalo sin abortar el resto (un símbolo con problemas de datos no bloquea la actualización de los demás).

### `collectors/regime_detector.py` — `RegimeDetector`

`SYMBOLS` se lee de la variable de entorno del mismo nombre (`BTCUSDT,ETHUSDT,SOLUSDT` por defecto). `REGIME_INTERVAL = '60'` (siempre calcula el régimen sobre velas H1, independientemente del intervalo en que opere cada estrategia individual). `LOOKBACK_BARS = 100`, `ATR_AVG_WINDOW = BB_AVG_WINDOW = 50`.

**`detect(symbol)`** — trae las últimas 100 velas H1; si hay menos de 64 (`ATR_AVG_WINDOW + 14`), devuelve `None` con un warning. Calcula los 3 indicadores sobre toda la ventana, toma los valores de la última barra y el promedio de las últimas 50 para ATR/BB Width, clasifica, y arma un diccionario con el resultado completo más metadatos (`calculated_at`, `candle_time` de la vela usada).

**`detect_all()`** — itera los símbolos configurados, guarda cada resultado válido en Redis bajo `regime:{symbol}` (sin expiración configurada explícitamente — el valor persiste hasta que el próximo ciclo de 15 minutos lo sobrescriba), y devuelve el diccionario completo de resultados (o un error por símbolo si algo falla).

---

## 15. Configuración y variables de entorno

### `config/trading.php` (Laravel)
```php
return [
    'python_engine_url' => env('PYTHON_ENGINE_URL', 'http://127.0.0.1:8002'),
    'python_internal_api_key' => env('PYTHON_INTERNAL_API_KEY', ''),
    'allow_investor_demo_accounts' => env('ALLOW_INVESTOR_DEMO_ACCOUNTS', false),
];
```
Tres únicas claves de configuración propias del proyecto en Laravel — todo lo demás (DB, sesión, cache, colas) usa la configuración estándar de Laravel.

### Variables de entorno relevantes del motor Python (leídas vía `os.getenv` directamente en cada módulo, sin un archivo de configuración centralizado equivalente al `config/trading.php` de Laravel)
| Variable | Usada en | Propósito |
|---|---|---|
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` | Todos los routers y módulos que acceden a PostgreSQL | Construyen el DSN de conexión |
| `INTERNAL_API_KEY` | `main.py`, `real_trading.py`, `broker.py` | Clave compartida que valida cada request entrante |
| `BYBIT_BASE_URL` | `bybit_client.py`, `real_trader.py`, `broker.py`, `ohlcv_collector.py` | Default `https://api.bybit.com` (mainnet) |
| `BYBIT_TESTNET_URL` | `real_trader.py`, `broker.py` | Default `https://api-testnet.bybit.com` |
| `REDIS_URL` | `regime.py` | Default `redis://127.0.0.1:6379` |
| `SYMBOLS` | `ohlcv_collector.py` (fallback), `regime_detector.py` | Default `BTCUSDT,ETHUSDT,SOLUSDT` |
| `INTERVALS` | `ohlcv_collector.py` (fallback) | Default `1,5,15,60,120` |

Todos los módulos llaman `load_dotenv()` individualmente al importarse, leyendo un archivo `.env` ubicado en `python-engine/` (no compartido directamente con el `.env` de Laravel, aunque ambos sistemas deben tener configurada la misma clave `INTERNAL_API_KEY`/`PYTHON_INTERNAL_API_KEY` para poder comunicarse).

### Dependencias declaradas
**Laravel** (`composer.json`): PHP `^8.3`, `laravel/framework ^13.8`, `laravel/horizon ^5.47` (gestión de colas, aunque el sistema de jobs explorado usa el *scheduler* estándar de Laravel más que colas activas de Horizon — no se confirmó si Horizon está siendo usado activamente o quedó instalado sin uso operativo), `phpoffice/phpspreadsheet ^5.8`, `predis/predis ^3.5`, `guzzlehttp/guzzle ^7.11`.

**Python** (`requirements.txt`): `fastapi==0.115.0`, `uvicorn==0.30.6`, `httpx==0.27.0`, `asyncpg==0.29.0`, `psycopg2-binary==2.9.9` (probablemente usado solo por herramientas auxiliares/scripts sueltos, ya que el motor principal usa `asyncpg` de forma asíncrona, no `psycopg2`), `python-dotenv==1.0.1`, `pydantic==2.8.2`, `pandas==2.2.2`, `numpy==2.0.1`, `redis==5.0.8`.

---

## 16. Scripts de análisis sueltos (raíz de `python-engine/`)

Estos 4 archivos **no forman parte del motor en producción** — no son importados por ningún router, job, ni por `main.py`. Son herramientas de investigación que el desarrollador ejecuta manualmente desde la terminal (`python3 nombre_script.py`, con el entorno virtual activado) durante el proceso de diseño y ajuste de estrategias. Se documentan aquí por completitud, no porque participen del flujo operativo del sistema:

- **`analyze_adx.py`** — calcula el ADX histórico H1 de cada símbolo y muestra estadísticas de distribución, para evaluar si el umbral fijo de ADX>25 usado en `classify_regime()` es razonable dado el comportamiento real observado del mercado.
- **`analyze_bad_months.py`** — analiza ADX y ATR de BTCUSDT H1 en meses calendario específicos, usado puntualmente para entender por qué la estrategia VWAP Tendencia (con 4 niveles de TP) tuvo pérdidas en abril, julio y diciembre de 2025.
- **`inspect_bad_trades.py`** — corre un backtest simple (sin walk-forward) de VWAP Tendencia BTC con la configuración ganadora identificada, y muestra el detalle trade-por-trade de meses específicos para diagnosticar por qué perdió en períodos de tendencia alcista aparente.
- **`strategy_matrix.py`** — corre la matriz completa de combinaciones estrategia × símbolo × intervalo llamando directamente al endpoint HTTP `/v1/backtest/run` (apuntando a `http://localhost:8002`, asumiendo que el motor ya está corriendo), y construye una tabla resumen ordenada por retorno total — la herramienta que probablemente se usó para decidir qué combinaciones merecían pasar a producción.

---

## Resumen de archivos por tamaño (referencia rápida)

| Archivo | Líneas | Rol |
|---|---|---|
| `python-engine/trading/real_trader.py` | 1180 | Ejecución de trading real — el más grande y crítico |
| `python-engine/trading/paper_trader.py` | 462 | Ejecución de trading simulado |
| `python-engine/backtesting/strategies/vwap_strategy.py` | 342 | Estrategia VWAP unificada (2 modos) |
| `python-engine/api/v1/real_trading.py` | 380 | Endpoints HTTP de trading real |
| `python-engine/api/v1/backtest.py` | 348 | Endpoint HTTP de backtesting |
| `python-engine/api/v1/broker.py` | 333 (con duplicación) | Validación de credenciales Bybit |
| `python-engine/backtesting/strategies/base_strategy.py` | 286 | Clase base de estrategias |
| `python-engine/backtesting/engine.py` | 257 | Simulador de backtesting |
| `python-engine/trading/risk_manager.py` | 256 | Drawdown/volatilidad (solo paper trading) |
| `python-engine/api/v1/paper_trading.py` | 235 | Endpoints HTTP de paper trading |
| `python-engine/collectors/ohlcv_collector.py` | 240 | Recolección de velas desde Bybit |
| `python-engine/backtesting/walk_forward.py` | 197 | Validación fuera de muestra |
| `app/Http/Controllers/BacktestingController.php` | 443 | Controller más grande de Laravel |
| `app/Http/Controllers/TradingController.php` | 275 | Trading real — vistas Laravel |
| `app/Models/User.php` | ~80 | Roles y permisos |

---

*Fin del Documento 2. El Documento 3 (Contexto para IA) condensa esta referencia en un formato denso pensado para que otro asistente de IA cargue el contexto completo del proyecto de un vistazo, sin necesidad de releer el código fuente.*

# CONTEXT.md — tr-bot V2 (machine-readable project context)

> Documento 3 de 3. Optimizado para que un asistente de IA cargue contexto operativo del proyecto sin re-explorar el código fuente. Prosa mínima, máxima densidad de hechos verificables. Última actualización: exploración completa de 227 archivos del repo `Rcastillo87/tr2`, rama `main`.

---

## IDENTITY

```yaml
project: tr-bot V2
repo: Rcastillo87/tr2 (GitHub)
host: tr2.srv685835.hstgr.cloud (Hostinger VPS, Ubuntu)
domain_purpose: algorithmic crypto trading platform — backtest → paper trade → live trade pipeline
broker: Bybit (REST API v5), testnet AND mainnet supported, currently running testnet only in production
stack:
  web_backend: Laravel 13.8+ (PHP 8.3+)
  trading_engine: Python 3 + FastAPI (uvicorn, single worker)
  database: PostgreSQL + TimescaleDB extension (one hypertable: ohlcv_data)
  cache: Redis (regime cache only, key pattern regime:{symbol})
  frontend: server-rendered Blade + vanilla JS (no SPA framework)
language_of_codebase_comments_and_ui: Spanish (variable/function names are English, comments and user-facing strings are Spanish)
```

## ARCHITECTURE — communication model

```
Browser → Laravel (public, Nginx/PHP-FPM) → HTTP internal → Python engine (127.0.0.1:8002 ONLY, not publicly reachable)
                ↓                                                    ↓
         PostgreSQL (shared) ←──────────────────────────────────────┘
```

- Python engine binds **exclusively** to `127.0.0.1:8002` — unreachable from outside the host. Only Laravel calls it.
- Every Laravel→Python call sends header `X-Internal-API-Key`. Python middleware in `main.py` rejects (401) any request without the matching key, except `GET /health`.
- Laravel and Python share the **same PostgreSQL database** directly — no internal data API, Python runs raw SQL against tables Laravel writes to via Eloquent. The single source of truth for any strategy configuration is always a row in `paper_strategy_configs`.
- Bybit API key/secret encryption: Laravel encrypts (`encrypted` Eloquent cast on `BrokerAccount.api_key/api_secret`, uses Laravel `APP_KEY`). Laravel decrypts before sending credentials to Python in job payloads. **Python never reads `broker_accounts` table directly and has no way to decrypt on its own** — this is intentional, avoids duplicating crypto logic in two languages.
- Config: Laravel side is `config/trading.php` → `PYTHON_ENGINE_URL` (default `http://127.0.0.1:8002`), `PYTHON_INTERNAL_API_KEY`. Python side reads `.env` in `python-engine/` independently via `load_dotenv()` per-module (not centralized) → `DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME`, `INTERNAL_API_KEY` (must match Laravel's `PYTHON_INTERNAL_API_KEY`), `BYBIT_BASE_URL` (default mainnet), `BYBIT_TESTNET_URL`, `REDIS_URL`, `SYMBOLS`, `INTERVALS`.

## USER ROLES (3, defined in `User.role` enum + 5 Gates in `AppServiceProvider::boot()`)

```
admin:          viewPaperTrading=Y viewAnalysisTools=Y viewRealTrading=Y manageUsers=Y createDemoAccounts=Y(always)
consultor:      viewPaperTrading=N viewAnalysisTools=Y viewRealTrading=N manageUsers=N createDemoAccounts=N
inversionista:  viewPaperTrading=Y viewAnalysisTools=N viewRealTrading=Y manageUsers=N createDemoAccounts=N(unless ALLOW_INVESTOR_DEMO_ACCOUNTS=true)
```
Gates map 1:1 to `User::canXxx()` methods, no extra logic in the Gate closures themselves.

Two business-logic middlewares (registration point in `bootstrap/app.php` NOT verified in this exploration — applied somewhere in the auth-protected route group, exact group binding unconfirmed):
- `EnsureUserIsActive` — if `auth()->user()->is_active === false`, force logout + redirect to login.
- `ExpireSessionAtMidnightColombia` — session expires at first midnight `America/Bogota` after login, hard cap 24h regardless.

Side effect on deactivation: `UserManagementController::toggleActive()` when deactivating a user also sets all their `RealStrategySubscription` rows with `status=active` to `status=paused` (stops new real positions, doesn't touch already-open ones).

---

## DATABASE SCHEMA (PostgreSQL, exact column names/types)

### `ohlcv_data` — TimescaleDB hypertable, NO Eloquent model, raw SQL only
```sql
time TIMESTAMPTZ, symbol TEXT, interval TEXT,
open/high/low/close NUMERIC(20,8), volume NUMERIC(30,8)
UNIQUE(symbol, interval, time DESC)
-- partitioned by 'time' via create_hypertable()
```

### `collector_configs`
```
id, symbol(20), interval(10), active(bool,default:true), notes(text,nullable)
UNIQUE(symbol, interval)
```

### `paper_strategy_configs` — SOURCE OF TRUTH for every strategy in the system
```
id, display_name, strategy_class, symbol, interval, params(jsonb), active(bool,default:true)
audited_months(int,null), avg_win_rate(dec5.2,null), avg_monthly_pnl(dec7.4,null),
avg_monthly_trades(dec6.2,null), total_return_pct(dec8.4,null)
star_wr/star_sharpe/star_ret/star_consistency/star_pf(dec3.1,null each — individual 1-5 ratings)
star_rating(dec3.1,null — average of the 5 above)
backtest_range_from/backtest_range_to(string7,null — 'YYYY-MM' format)
sharpe_ratio, consistency_pct, profit_factor(dec, added migration 2026_06_29)
created_at, updated_at
```
⚠️ ORIGINAL MIGRATION has `UNIQUE(strategy_class, symbol, interval)`. ⚠️ APPLICATION CODE (`PaperStrategyConfig::implementFromBacktest()`) was later modified to ALLOW multiple rows with the same triplet, only blocking insert if `params` JSON is byte-identical (JSONB `@>` AND `<@` comparison, key-order-insensitive). **Whether the original unique constraint still physically exists in production was not confirmed** — if it does, app-level duplicate-allowing logic would fail at the DB layer for any second row with identical triplet but different params, contradicting the apparent intent. Check `\d paper_strategy_configs` on the live DB before assuming either behavior.

### `paper_trades`
```
id, strategy(matches display_name), symbol, interval, side(enum:long/short)
entry_price/exit_price(dec20.8, exit nullable), sl/tp(dec20.8), tp2(dec15.8,null)
be_level(dec20.8), be_activated(bool,default:false), size(dec20.8)
pnl/pnl_pct(dec,null), max_profit_pct/max_loss_pct(dec10.4,default:0 — MFE/MAE, updated every monitor tick)
exit_reason(string,null: stop_loss|take_profit|take_profit_1|take_profit_2|time_exit)
regime(string,null), entry_time/exit_time(timestamp, exit nullable)
status(enum:open/closed,default:open)
INDEX(strategy,symbol,status), INDEX(status)
```
⚠️ Schema has `tp2` column but NOT `tp3`/`tp4` — paper trading only supports 2 TP levels in storage, despite backtesting engine supporting 4. See "GOTCHAS" section.

### `risk_controls` (Paper Trading drawdown/volatility pauses ONLY — not used by real trading)
```
id, strategy(string,null=global), symbol(string,null=applies to whole strategy)
reason(enum: daily_drawdown|total_drawdown|volatility_extreme|kill_switch_manual)
value(dec10.4,null), threshold(dec10.4,null), active(bool,default:true)
paused_at(timestamp), auto_resume_at(timestamp,null — daily DD auto-resumes next midnight UTC)
resumed_at(timestamp,null)
INDEX(strategy,symbol,active)
```

### `users` (extends Laravel default)
```
+ role(enum: admin/consultor/inversionista, default:inversionista)
+ is_active(bool, default:true)
```

### `broker_accounts`
```
id, user_id(FK→users cascadeDelete)
broker(string,default:bybit), account_type(enum:real/demo,default:real)
label(string — autogenerated "Bybit Real"/"Bybit Demo")
api_key/api_secret(text,nullable, CAST=encrypted)
status(enum:active/paused,default:active)
UNIQUE(user_id, broker, account_type) — one real + one demo per broker per user, max
INDEX(user_id,status)
```

### `real_strategy_subscriptions`
```
id, user_id(FK), broker_account_id(FK→broker_accounts cascadeDelete)
paper_strategy_config_id(FK→paper_strategy_configs nullOnDelete)
strategy, symbol, interval(string,null)
risk_override_pct(dec5.2,null — overrides config's risk_per_trade_pct for THIS subscription only)
status(enum:active/paused,default:active)
UNIQUE(broker_account_id, paper_strategy_config_id)  -- constraint name: real_subs_unique_v2
```

### `real_trades` — largest table, full execution audit trail
```
id, user_id(FK), subscription_id(FK→real_strategy_subscriptions nullOnDelete)
broker_account_id(FK nullOnDelete), paper_strategy_config_id(FK nullOnDelete)
order_id, close_order_id(string,null — Bybit order IDs)
strategy, symbol, interval, broker(default:bybit), side(enum:long/short)
entry_price/entry_price_signal/exit_price(dec20.8 — signal price vs actual fill price)
sl/tp/tp2/tp3/tp4(dec20.8, tp2-4 nullable — UNLIKE paper_trades, real_trades HAS tp3/tp4 columns)
be_level(dec20.8), be_activated(bool,default:false)
size(dec20.8), leverage(dec10.2,default:1)
pnl/pnl_pct/net_pnl(dec,null — net_pnl = pnl minus commission)
commission(dec20.8,null), slippage_pct(dec10.6,null)
balance_before/balance_after(dec20.8,null)
exit_reason, regime(string,null)
entry_time/exit_time(timestamp, exit nullable)
status(enum — see exact list below)
error_message(text,null)
audit_log(JSONB — array of {action, timestamp(ISO8601), data})
INDEX(user_id,status) INDEX(strategy,symbol,status) INDEX(broker_account_id,status)
```
**Exact status enum values (constraint after migration `2026_06_27_231408`):**
```
pending_open | open | pending_close | closed | error | orphaned | failed | ignored
```
⚠️ `RealTrade` Eloquent model only defines constants for 5 of the 8: `STATUS_PENDING_OPEN/OPEN/PENDING_CLOSE/CLOSED/ERROR`. The other 3 (`orphaned`, `failed`, `ignored`) are used as raw strings throughout Python code, no Laravel-side constant equivalent.

---

*(Continues in next section: full route table, model methods, controller behaviors)*
## ROUTES (Laravel, all under `auth+verified` middleware unless noted)

```
GET  /                                                            → DashboardController@index [dashboard]

# paper-trading (can:viewPaperTrading)
GET  /paper-trading/                                              → PaperTradingController@index
GET  /paper-trading/live                                          → PaperTradingController@live

# paper-trading/configs (can:manageUsers)
PATCH  /paper-trading/configs/{config}/toggle                     → PaperStrategyConfigController@toggleActive
POST   /paper-trading/configs/implement                           → PaperStrategyConfigController@implement
POST   /paper-trading/configs/                                    → PaperStrategyConfigController@store
DELETE /paper-trading/configs/{config}                            → PaperStrategyConfigController@destroy

# collector/configs (can:manageUsers)
GET    /collector/configs/                                        → CollectorConfigController@index
PATCH  /collector/configs/{config}/toggle                         → CollectorConfigController@toggleActive

# backtesting (can:viewAnalysisTools)
GET    /backtesting/                                              → BacktestingController@index
GET    /backtesting/run                                           → BacktestingController@run  [name: backtesting.run]
POST   /backtesting/run                                           → BacktestingController@run  [name: backtesting.execute] (SAME METHOD, dual GET/POST)
POST   /backtesting/run-ajax                                      → BacktestingController@runAjax
GET    /backtesting/data-range/{symbol}/{interval}                → BacktestingController@dataRange
POST   /backtesting/export-excel                                  → BacktestingController@exportExcel
GET    /backtesting/retest/{config}                                → BacktestingController@retest

# users (can:manageUsers)
GET    /users/                                                    → UserManagementController@index
PATCH  /users/{user}/toggle-active                                → UserManagementController@toggleActive

# trading (can:viewRealTrading)
GET    /trading/                                                  → TradingController@index
GET    /trading/live-prices                                       → TradingController@livePrices
GET    /trading/accounts                                          → TradingController@accounts
POST   /trading/accounts                                          → BrokerAccountController@store
PATCH  /trading/accounts/{account}/toggle-status                  → BrokerAccountController@toggleStatus
DELETE /trading/accounts/{account}                                → BrokerAccountController@destroy
POST   /trading/accounts/{account}/subscriptions                  → RealStrategySubscriptionController@store
POST   /trading/accounts/{account}/subscriptions/all              → RealStrategySubscriptionController@storeAll
PATCH  /trading/accounts/{account}/subscriptions/{subscription}/toggle → RealStrategySubscriptionController@toggle
DELETE /trading/accounts/{account}/subscriptions/{subscription}   → RealStrategySubscriptionController@destroy

# profile (no extra middleware beyond auth+verified)
GET    /profile     → ProfileController@edit
PATCH  /profile     → ProfileController@update
DELETE /profile     → ProfileController@destroy

# auth/* — standard Laravel Breeze routes, see routes/auth.php (not explored in detail)
```

## SCHEDULED JOBS (`routes/console.php`, fired via system cron `php artisan schedule:run` every minute)

```
CollectOhlcvDataJob       everyMinute()        → POST /v1/collector/run
DetectMarketRegimeJob     everyFifteenMinutes() → POST /v1/regime/run
PaperTradingTickJob       everyFiveMinutes()   → POST /v1/paper/tick
RealTradingTickJob        everyFiveMinutes()   → POST /v1/real/tick
RealTradingReconcileJob   everyFiveMinutes()   → POST /v1/real/reconcile
```
All jobs: `ShouldQueue`, `tries=1` (no auto-retry, just waits for next cycle), wrapped in try/catch that logs errors and never throws unhandled.

`RealTradingTickJob`/`RealTradingReconcileJob` query identical structure: `BrokerAccount::where('status','active')->whereHas('subscriptions', status=active)->with(subscriptions.paperStrategyConfig)`, then build a nested payload of `{accounts: [{id, broker, account_type, api_key, api_secret, subscriptions: [{subscription_id, user_id, broker_account_id, paper_strategy_config_id, strategy, symbol, interval, strategy_class, config_params, risk_override_pct}]}]}`. If no active accounts/subscriptions found, the tick job skips calling Python entirely (logs debug, returns).

---

## ELOQUENT MODELS — key methods (not exhaustive getters/setters, only business logic)

### `User`
```php
canViewPaperTrading() → role in [admin, inversionista]
canViewAnalysisTools() → role in [admin, consultor]
canViewRealTrading() → role in [admin, inversionista]
canManageUsers() → role === admin
canCreateDemoAccounts() → isAdmin() OR config('trading.allow_investor_demo_accounts')
```

### `PaperStrategyConfig` — central model
```php
pythonModulePath() → maps strategy_class to python import path:
    VwapStrategy → backtesting.strategies.vwap_strategy
    MeanReversionStrategy → backtesting.strategies.mean_reversion
    EmaDonchianStrategy → backtesting.strategies.ema_donchian
  ⚠️ NOTE: appears unused — Python side has its own independent STRATEGY_CLASS_MAP
    duplicated in paper_trading.py AND real_trading.py, not calling back to this method.

strategyNameToClassAndMode($name) [static] → {class, mode}:
    'VWAP Tendencia'         → {VwapStrategy, trend_follow}
    'VWAP Reversión'         → {VwapStrategy, reversion}
    'Reversión a la Media'   → {MeanReversionStrategy, null}
    'Tendencia EMA/Donchian' → {EmaDonchianStrategy, null}

classAndModeToStrategyName($class, $mode) [static] → inverse of above

implementFromBacktest($strategyName, $symbol, $interval, $params, $displayNameOverride=null) [static]
  THE method that creates/updates strategy configs. Flow:
  1. Resolve {class, mode}, inject mode into params if present
  2. Build display_name: "{strategyName} — {symbol} {intervalLabel}"
     intervalLabel map: 1→1m, 5→5m, 15→15m, 60→H1, 120→H2, 240→H4, D→D1
  3. Search existing row matching strategy_class+symbol+interval WHERE params is
     JSONB-identical (params @> ?::jsonb AND params <@ ?::jsonb)
  4. If exact match found → UPDATE that row (display_name, active=true), return it
  5. If no exact match → CREATE new row, NO uniqueness restriction beyond exact-params match
     (multiple configs of same symbol/strategy/interval with different params ARE allowed)
```

### `RealTrade`
```php
isOpen() → status in [open, pending_close]
isClosed() → status === closed
isWinner() → net_pnl > 0, fallback to pnl if net_pnl is null
appendAuditLog($action, $data=[]) → reads audit_log, appends {action, timestamp, data}, saves
  ⚠️ NOTE: equivalent logic exists independently in Python (RealTrader.log_audit()) which is
    what's actually called during the live execution flow — this Eloquent method doesn't
    appear to be invoked from any controller/job in the explored codebase.
```

### `RealStrategySubscription`
```php
pauseIfConfigInactive() → if linked paperStrategyConfig.active===false, set status=paused
  ⚠️ NOTE: not called automatically by any job/controller found — available but disconnected
    from any current trigger.
```

---

## CONTROLLERS — behavior notes worth knowing before modifying

### `BacktestingController` (443 lines, largest)
```php
const STRATEGY_OPTIONS = [
  'VWAP Tendencia'         => [class: VwapStrategy, mode: trend_follow, label: 'VWAP Tendencia (trend follow)'],
  'VWAP Reversión'         => [class: VwapStrategy, mode: reversion, label: 'VWAP Reversión (E-13)'],
  'Reversión a la Media'   => [class: MeanReversionStrategy, mode: null, label: 'Reversión a la Media'],
  'Tendencia EMA/Donchian' => [class: EmaDonchianStrategy, mode: null, label: 'Tendencia EMA/Donchian'],
];

calcularEstrellas($wr, $sharpe, $retMes, $consistencia, $pf) → private, star rating algorithm:
  WinRate:      <35→1 <45→2 <55→3 <65→4 ≥65→5
  Sharpe:        <1→1  <2→2  <3→3  <4→4  ≥4→5
  RetMes%:       <2→1  <5→2 <10→3 <20→4 ≥20→5
  Consistency%: <40→1 <65→2 <85→3 <95→4 ≥95→5
  ProfitFactor:  <1→1<1.5→2  <2→3<2.5→4 ≥2.5→5
  star_rating = round(average(5 stars), 1)

run($request): GET shows empty form (preloads ALL active configs as JSON for JS auto-fill);
  POST builds extensive payload → POST /v1/backtest/run (timeout 180s) → calls calcularEstrellas()
  on the result before rendering.

runAjax($request): AJAX variant, uses buildPayload() helper (separate, parallel implementation
  of the SAME payload-building logic that's also inline inside run() — these two code paths
  CAN DESYNC if one is edited without the other. ⚠️ KNOWN DUPLICATION RISK.

retest($config): JSON endpoint, returns exact params of an existing config for form preload
  (used by "Re-testear" button in the list view).
```

### `PaperStrategyConfigController`
```php
store() and implement() are near-IDENTICAL — same validation block, same create/update logic,
  same metrics-update block. Only difference: different success message text.
  ⚠️ Functionally interchangeable as currently written.

Both: if request has config_id → UPDATE that row directly (bypasses implementFromBacktest's
  duplicate-detection). If no config_id → calls implementFromBacktest().
```

### `TradingController` (275 lines)
```php
getLivePrices($symbols) private:
  1. Try Redis::get("price:{symbol}") for each symbol
  2. If empty, fallback to GET /v1/prices on Python engine
  ⚠️ /v1/prices endpoint NOT FOUND in any explored Python router — likely an incomplete/dead
    fallback path, or implemented in a file not covered by this exploration.

getTestnetPrices($symbols) private: direct call to api-testnet.bybit.com (bypasses Python engine
  entirely), used specifically when open positions belong to demo accounts.

All trading queries scoped first by BrokerAccount::where('user_id', $user->id)->pluck('id') —
  strict per-user isolation, even admin only sees own trades from this controller.
```

### `DashboardController`
```php
index(): builds summary grouped by 4 fixed strategy buckets (VWAP Tendencia, VWAP Reversión,
  Reversión a la Media, Tendencia EMA/Donchian), matching paper_trades.strategy by PREFIX, plus
  a legacy compatibility map that folds the retired "VWAP Intradía" strategy's old trades into
  the "VWAP Tendencia" bucket for historical continuity.
getRegimes()/getCollectorStatus() private: both wrapped try/catch, return [] silently on Python
  engine failure — dashboard never breaks from a backend communication issue.
```

---

*(Continues: Python API surface, strategy math, execution flow state machine, gotchas list)*
## PYTHON ENGINE — entry point

```python
# main.py
FastAPI app, docs_url=None, redoc_url=None (no /docs swagger exposed)
Middleware checks header X-Internal-API-Key on EVERY request except /health
6 routers registered under prefix /v1:
  collector_router, regime_router, backtest_router, paper_router, broker_router, real_trading_router

# start.py
uvicorn.run("main:app", host="127.0.0.1", port=8002, reload=False, workers=1)
```

## API ENDPOINTS — full reference

### `/v1/collector/*`
```
POST /collector/run            → OhlcvCollector.run_all() → {status, results:{sym/int: saved}, total_saved}
POST /collector/initial-load   → loads 730 days history for any config without existing data
GET  /collector/status         → {status, data:{sym/int: {last_candle, has_data}}}
```

### `/v1/regime/*`
```
POST /regime/run               → calculates regime for all SYMBOLS, caches in Redis regime:{symbol}
GET  /regime/status            → reads ALL cached regimes from Redis (no recalculation)
GET  /regime/{symbol}          → single symbol, 404 if not cached
```

### `/v1/backtest/*`
```
POST /backtest/run             → THE main backtest endpoint, see BacktestRequest model below
GET  /backtest/strategies      → static list of 4 strategies with descriptions
GET  /backtest/data-range/{symbol}/{interval} → {first_date, last_date, total_bars}
```

**`BacktestRequest` Pydantic model — exact fields/defaults:**
```python
strategy: str (required)            symbol: str = "BTCUSDT"
interval: str = "60"                initial_balance: float = 10000.0
risk_per_trade_pct: float = 1.0     sl_pct: float = 1.5
tp_pct: float = 3.0                 tp2_pct/tp3_pct/tp4_pct: Optional[float] = None
be_pct: float = 2.0                 max_duration: int = 24
regime_filter: bool = True          walk_forward: bool = True
n_windows: int = 5                  train_pct: float = 0.7
mode: Optional[str] = None          macro_trend_filter: Optional[bool] = None  # None=strategy default
trend_persistence_filter: bool = False    trend_persistence_bars: int = 4
trend_adx_threshold: float = 25     dynamic_sl_filter: bool = False
adx_strong_threshold: float = 30    sl_pct_weak_zone: float = 0.7
start_date/end_date: Optional[str] = None  # YYYY-MM-DD
trailing_mode: Optional[str] = None # None|fixed|stepped
trailing_distance_pct: float = 1.0  trailing_steps: Optional[list] = None  # [[gain%, new_sl%],...]
volatility_protection_mode: Optional[str] = None  # None|close|widen
volatility_atr_multiplier: float = 2.5   volatility_widen_pct: float = 1.0
volume_filter: bool = False         volume_filter_period: int = 20
volume_filter_mult: float = 1.2
hour_filter: bool = False           hour_filter_start: int = 7   hour_filter_end: int = 21  # UTC, legacy
weekend_filter: bool = False
blocked_hours: list[int] = []       # UTC hours 0-23
blocked_days: list[int] = []        # 0=Mon...6=Sun
monthly_breakdown: bool = False
```

**`POST /backtest/run` logic:**
```python
1. load_ohlcv() — raises ValueError(400) if no rows in date range
2. load_strategy() — instantiates correct class, sets allowed_regimes hardcoded per strategy:
     VWAP (both modes) → ["TRENDING"]
     MeanReversionStrategy → ["RANGING"]
     EmaDonchianStrategy → ["TRENDING"]
3. if walk_forward=True:
     run WalkForwardValidator → result with out-of-sample metrics
     if monthly_breakdown=True (almost always from web form):
       ALSO run plain BacktestEngine on FULL range (not walk-forward) to get monthly breakdown
       ⚠️ REPLACES result['aggregate_metrics'] with the FULL backtest's metrics (not walk-forward's)
         so displayed KPIs match the monthly breakdown shown below them — this was a deliberate
         fix to a prior inconsistency where two different metric sources were shown together.
       ⚠️ ALSO recalculates passed/pass_reasons using full-backtest thresholds:
         WinRate≥45% Sharpe≥1 Drawdown≤15%  (slightly different from walk-forward's own 5 criteria below)
4. if walk_forward=False: plain BacktestEngine on full range, no out-of-sample validation at all
```

### `/v1/paper/*`
```python
STRATEGY_CLASS_MAP = {  # independent copy, mirrored in real_trading.py
  'VwapStrategy':          ('backtesting.strategies.vwap_strategy', 'VwapStrategy'),
  'MeanReversionStrategy': ('backtesting.strategies.mean_reversion', 'MeanReversionStrategy'),
  'EmaDonchianStrategy':   ('backtesting.strategies.ema_donchian', 'EmaDonchianStrategy'),
}

POST /paper/tick → the 5-min cycle:
  1. load_active_configs() — SQL: SELECT ... WHERE active=true
  2. instantiate strategies per config (catches individual errors, doesn't abort whole cycle)
  3. RiskManager.evaluate() — may create new pauses / resume expired ones
  4. PaperTrader.monitor_open_trades() then .check_new_signals()
  → {status, configs:N, risk:{...}, monitor:{...}, signals:{display_name: msg}}

GET /paper/open    → open trades enriched with live current_price + floating_pnl_pct
GET /paper/summary → SQL GROUP BY strategy: total/wins/open/total_pnl_pct per display_name
GET /paper/trades/{strategy} → last 200 trades for that strategy
```

### `/v1/real/*`
```python
class SubscriptionPayload(BaseModel):
  subscription_id, user_id, broker_account_id: int
  paper_strategy_config_id: Optional[int]
  strategy, symbol, interval: str
  strategy_class: Optional[str]
  config_params: Optional[dict]

class AccountPayload(BaseModel):
  id: int; broker, account_type, api_key, api_secret: str
  subscriptions: list[SubscriptionPayload]

class RealTickRequest(BaseModel):
  accounts: list[AccountPayload]

POST /real/tick:
  for each account:
    1. CIRCUIT BREAKER CHECK:
       error_count = errors with status='error' in last 2h for this account
       if error_count >= CIRCUIT_BREAKER_THRESHOLD (3):
         classify last 5 error messages: "non-critical" if message contains ANY of:
           ['firma','timestamp','10001','stopLoss','takeProfit','rechazada por bybit','qty','invalid','no confirmada']
         if ANY error does NOT match a non-critical pattern → CRITICAL → pause_account() → skip this account
         if ALL errors are non-critical → clear_non_critical_errors() (mark as 'ignored') → continue processing
    2. BybitClient(api_key, api_secret, account_type)
    3. monitor_open_trades(account.id, client)
    4. for each subscription: instantiate_strategy() → check_new_signals()
  → {status, results: {account_{id}_{broker}: {monitor:{...}, signals:{...}}}}

POST /real/reconcile:
  for each account:
    for each open trade in DB (skip if <10min old):
      if no position in Bybit:
        try get_closed_pnl() — verify avgEntryPrice matches trade.entry_price within 0.1% tolerance
        determine exit_reason from orderType (StopLoss/TakeProfit/PartialTakeProfit) or by comparing
          exit_price against stored sl/tp values if Bybit doesn't specify type
        UPDATE real_trades SET status='closed', ... (reason='reconciled_sl_tp_bybit' if no PnL data found)
    for each trade with status='orphaned':
      if Bybit HAS a position for that symbol → ADOPT: recalc sl/tp from avgPrice, set_trading_stop(),
        UPDATE status='open'
      else → UPDATE status='failed'
    for each unique symbol among subscriptions:
      if Bybit has a position NOT represented by any DB row → INSERT new real_trades row directly
        with status='open', reconstructed from Bybit position data, apply sl/tp from first matching
        subscription's config_params
  → {status, results: {reconciled:[...], orphaned:[...], ok:[...]}}
```

### `/v1/broker/*`
```python
POST /broker/validate-credentials → real call to Bybit wallet-balance endpoint to confirm
  key/secret validity + sufficient permissions. Returns {valid:bool, message, total_equity}
  Handles specific Bybit retCodes: 10003(invalid key) 10004(invalid signature) 10005(insufficient
  perms) 33004(expired key)

POST /broker/account-info → reads API key permissions/expiration via Bybit query-api endpoint
  ⚠️ THIS FUNCTION + ITS MODEL ARE DUPLICATED 3 TIMES VERBATIM in broker.py (lines ~116-187,
    189-260, 262-333). FastAPI silently uses only the LAST definition — first two are dead code.
    Harmless but should be cleaned up.
```

---

## STRATEGY ENGINE — exact formulas

### `BaseStrategy` (all strategies inherit from this)
```python
calculate_sl_tp(entry, side):
  long:  sl = entry*(1-sl_pct/100)   tp = entry*(1+tp_pct/100)
  short: sl = entry*(1+sl_pct/100)   tp = entry*(1-tp_pct/100)
  (rounded to 8 decimals)

calculate_tp_levels(entry, side) → {tp1,tp2,tp3,tp4}, each None if its _pct param is None

calculate_breakeven(entry, side):
  long: entry*(1+be_pct/100)   short: entry*(1-be_pct/100)

calculate_trailing_sl(entry, side, current_price, current_sl):
  if trailing_mode is None → return current_sl unchanged
  gain_pct = (current-entry)/entry*100 [long] or inverse [short]
  if gain_pct <= 0 → no change
  mode="fixed": candidate = current_price ± trailing_distance_pct%, only adopt if it IMPROVES sl (never retreats)
  mode="stepped": find highest trailing_steps threshold already reached, move sl to that step's
    target % FROM ENTRY (not from current price)

check_volatility_protection(current_sl, side, current_atr, avg_atr):
  if mode is None or avg_atr==0 → no action
  if current_atr <= avg_atr * volatility_atr_multiplier → no action (not extreme enough)
  mode="close" → signal immediate close at market
  mode="widen" → widen sl by volatility_widen_pct%

Filters (all no-op if disabled, applied in this exact order in every strategy's generate_signals()):
  apply_volume_filter → nullify signal if volume < rolling_mean(period) * mult
  apply_hour_filter → nullify signal outside [hour_filter_start, hour_filter_end) UTC
  apply_weekend_filter → nullify signal on Sat/Sun
  apply_blocked_hours → nullify signal in any hour listed in blocked_hours
  apply_blocked_days → nullify signal on any weekday listed in blocked_days
  ⚠️ weekend_filter, blocked_hours, blocked_days are initialized TWICE (identical) in
    BaseStrategy.__init__ — harmless copy-paste duplication, second assignment just overwrites
    with the same value.
```

### `classify_regime()` (`indicators/regime_indicators.py`) — used EVERYWHERE regime matters
```python
if atr > atr_avg * 1.8:              return "VOLATILE"   # priority over everything else
if adx > 25:                          return "TRENDING"
if adx < 20 and bb_width < bb_width_avg: return "RANGING"
else:                                  return "RANGING"   # ambiguous zone default
```

### `VwapStrategy` (unified, `mode` param switches behavior)
```python
mode="trend_follow":
  VWAP = cumsum(typical*volume)/cumsum(volume), grouped per calendar day (resets daily)
  bands: vwap ± vwap_std_filter(1.5) * daily_std
  ema_trend = EMA(close, span=ema_trend_period=50)
  LONG signal:  prev.close<=prev.vwap AND curr.close>curr.vwap AND curr.close>curr.ema_trend
  SHORT signal: mirror condition
  allowed_regimes default: ["TRENDING"]
  macro_trend_filter default: False (only active if client explicitly requests)
  trend_persistence_filter: requires ADX>trend_adx_threshold sustained for trend_persistence_bars
    consecutive bars (custom ADX calc, NOT reusing indicators/regime_indicators.py — duplicate impl)
  dynamic_sl_filter: if ADX falls in "gray zone" [trend_adx_threshold, adx_strong_threshold) at
    signal time, uses sl_pct_weak_zone instead of normal sl_pct for that specific trade

mode="reversion":
  std calculated per-day with VOLUME-WEIGHTED rolling accumulation (more expensive, bar-by-bar
    within each day group) — different calc method than trend_follow's simple daily std
  bands: vwap ± vwap_std_entry(2.0) * weighted_std
  LONG signal: price breaks BELOW lower band (bet on reversion back to vwap)
  SHORT signal: price breaks ABOVE upper band
  zone_bars(4): prevents duplicate signals in same direction within N-bar window
  allowed_regimes default: ["TRENDING"]  ⚠️ counterintuitive — "reversion" strategy filtered to
    trending regime, NOT ranging, per empirical backtest results
  macro_trend_filter default: True for this mode (opposite default of trend_follow)
    blocks LONG if macro H4 trend is BEARISH, blocks SHORT if BULLISH
```
Macro trend calculation (shared helper `_calculate_macro_trend`): resamples the H1 dataframe itself
to H4 blocks (`macro_trend_interval_hours=4`), computes EMA50 on the resampled closes, classifies
each H4 block BULLISH/BEARISH, forward-fills that classification onto every H1 bar within the block.
No second dataset needed — replicates a real H4 indicator using only H1 data.

### `MeanReversionStrategy`
```python
allowed_regimes = ["RANGING"]
Bollinger(period=20, std=2.0) + RSI(period=14, EXPONENTIAL smoothing via ewm, not classic Wilder SMA)
LONG:  prev.close<=prev.bb_lower AND curr.close>curr.bb_lower AND curr.rsi < rsi_os(30)+10
SHORT: prev.close>=prev.bb_upper AND curr.close<curr.bb_upper AND curr.rsi > rsi_ob(70)-10
```

### `EmaDonchianStrategy`
```python
allowed_regimes = ["TRENDING"]
ema_fast(9), ema_slow(21), donchian_period(20), trend_window(10)
breakout_up = close >= donchian_high.shift(1)   breakout_down = close <= donchian_low.shift(1)
trend_up_active = breakout_up occurred within last trend_window bars (rolling max)
LONG:  EMA cross up (fast crosses above slow) AND trend_up_active is True
SHORT: mirror with trend_down_active
```

### Dead/legacy strategy files (not imported by any router, confirmed via grep)
```
vwap_intraday.py  → VwapIntradayStrategy   (predecessor of VwapStrategy mode="trend_follow")
vwap_reversion.py → VwapReversionStrategy  (predecessor of VwapStrategy mode="reversion")
```

### Standalone analysis scripts (manual CLI tools, NOT wired into any router/job)
```
analyze_adx.py        — ADX distribution stats per symbol, used to validate the >25 threshold
analyze_bad_months.py — ADX/ATR analysis of specific bad months for BTCUSDT VWAP Tendencia
inspect_bad_trades.py — trade-by-trade detail dump for specific months/strategy combo
strategy_matrix.py    — runs full strategy×symbol×interval matrix via HTTP calls to
                         localhost:8002/v1/backtest/run, prints summary table sorted by return
```

---

*(Continues: execution flow state machines, risk/circuit-breaker constants, env vars table, gotchas summary)*
## REAL TRADING — open_trade() state machine (`trading/real_trader.py`)

This is the most carefully-engineered code path in the project. Exact sequence:

```python
def open_trade(sub, strategy_instance, side, entry_signal_price, regime, client):
    # 1. balance = client.get_balance() — abort (return False) if None or <=0

    # 2. current_price = client.get_market_price(symbol)
    #    entry_price_for_calc = current_price or entry_signal_price (fallback)
    #    if |current - signal| / signal > 0.02 → log warning only, DOES NOT abort yet

    # 3. sl, tp1 = calculate_sl_tp(entry_price_for_calc, side)
    #    be = calculate_breakeven(...)
    #    tp2 = calculate_tp2() if exists; tp3/tp4 manually computed from strategy_instance.tp3_pct/tp4_pct
    #         (NOT using calculate_tp_levels() here — different code path than the backtest engine)

    # 4. risk_pct = sub.risk_override_pct if present and not in ('', 'None', 'null')
    #               else config_params.risk_per_trade_pct (default 1.0)

    # 5. size = (balance * risk_pct/100) / |entry_signal_price - sl|
    #    abort if size <= 0

    # 6. min_qty, qty_step = client.get_min_qty(symbol)
    #    abort if size < min_qty
    #    size = floor(size / qty_step) * qty_step  (rounded to qty_step's implied decimal precision)
    #    abort if size <= 0 after rounding

    # 7. balance = client.get_balance() or balance  (refresh right before insert)

    # 8. INSERT INTO real_trades (..., status='pending_open') — BEFORE touching Bybit
    #    this row exists even if everything below fails completely

    # 9. RECALC sl/tp if price moved >0.5% since step 2-3 (market doesn't wait)
    #    UPDATE real_trades SET sl=.., tp=.., entry_price_signal=.. (reflects recalculated values)

    # 10. result = client.place_market_order(symbol, bybit_side, size, sl=sl, tp=tp1)
    #     place_market_order INTERNALLY computes PROVISIONAL sl/tp (wide margin, see table below)
    #     and retries Bybit submission up to 3x with 2s gaps on rejection
    #     if result is None after 3 tries → status='error', error_message='Orden rechazada por
    #       Bybit tras 3 intentos', log_audit('open_failed'), return False

    # 11. CONFIRMATION SEQUENCE (position may take time to reflect in Bybit's position list):
    #     sleep(1) → check get_open_position()
    #     if not filled: sleep(5) more (6s total) → check again
    #     if STILL not filled: loop up to 3x with sleep(10) each (~38s worst case):
    #       BEFORE each retry: re-generate signal with fresh data, abort with status='failed' if
    #         signal no longer matches expected direction (market already reversed — don't insist)
    #       retry place_market_order() (no explicit sl/tp this time, lets it recompute provisionals)
    #     if NEVER confirmed after all retries → status='orphaned',
    #       error_message='No confirmada tras 3 reintentos (38s)' → reconcile job picks it up later

    # 12. avg_price = filled_price (real execution price from Bybit, may differ from signal due
    #     to slippage)
    #     RECOMPUTE final sl/tp1/tp2/tp3/tp4/be using avg_price (not entry_signal_price)

    # 13. client.set_trading_stop(symbol, sl, tp1) — REPLACES provisional sl/tp with exact values
    #     if this fails, only logs error — position stays protected by wider provisionals, trade
    #     is NOT aborted at this point (it's already live, must be managed going forward)

    # 14. slippage_pct = |filled_price - entry_signal_price| / entry_signal_price * 100

    # 15. UPDATE real_trades SET status='open', order_id=.., entry_price=filled_price,
    #     slippage_pct=.., sl=.., tp=.., tp2=.., tp3=.., tp4=.., be_level=..
    #     retried up to 4x with backoff [2,5,30]s if DB write fails
    #     if all 4 attempts fail → logger.critical() — position is live in Bybit but DB still
    #       shows pending_open, an inconsistency requiring manual fix or reconcile job to catch it

    # 16. log_audit('opened', {order_id, filled_price, signal_price, slippage_pct, balance_before})
    #     return True
```

**Provisional SL/TP margins (inside `BybitClient.place_market_order`):**
```python
is_demo = 'testnet' in base_url
sl_margin = 1.05 if demo else 1.02   # 5% demo / 2% mainnet
tp_margin = 0.90 if demo else 0.96   # 10% demo / 4% mainnet
SHORT: sl_prov = mark*sl_margin (above price)    tp_prov = mark*tp_margin (below price)
LONG:  sl_prov = mark*(2-sl_margin) (below price) tp_prov = mark*(2-tp_margin) (above price)
```

**`close_trade(trade, exit_reason, client, account_id, exit_price_override=None)`:**
```python
# OVERRIDE path (monitor already detected Bybit closed it, just reflect in DB):
#   compute pnl/commission/net_pnl directly with known exit_price_override
#   ⚠️ BUG: this branch's final log line references variable `symbol` which is NEVER DEFINED
#     in this branch (only `trade['symbol']` exists) — would raise NameError if that log
#     statement executes. Confirmed by reading the source, not yet verified against live logs.

# NORMAL path (active close, must send order to Bybit):
#   verify position still exists in Bybit — if not, reconcile directly (status='closed',
#     exit_reason='reconciled', no precise PnL calc in this particular branch)
#   if position exists: status='pending_close' → send opposite-side market order →
#     poll get_order() up to 6x with 5s gaps (~30s max) waiting for status='Filled'
#     if never confirms Filled, use last known market price as exit_price approximation
#       (doesn't block indefinitely)
#   commission = |exit_price * size * BYBIT_TAKER_FEE(0.00055)|
#   net_pnl = pnl - commission
#   status='closed', log_audit('closed', {...})
```

**`monitor_open_trades(account_id, client)` per-trade logic:**
```python
1. position = client.get_open_position(symbol)
   if position doesn't exist anymore (closed by Bybit's native SL/TP, motor wasn't watching live):
     try get_closed_pnl() → determine exit_reason from orderType field, OR infer by comparing
       exit_price against stored sl/tp if Bybit doesn't specify type
     call close_trade() with override path using reconstructed exit_price
   if position still exists:
     2. CHECK FOR STALE PROVISIONAL SL: if |sl-entry|/entry > 2.5%, query real sl_pct via
        JOIN real_trades→real_strategy_subscriptions→paper_strategy_configs (fallback 0.8% if
        not found), recompute correct sl, call set_trading_stop() to fix it
        ⚠️ This is a SAFETY NET catching cases where step 13 of open_trade() silently failed
     3. get current market price (cached per symbol within this monitor cycle)
     4. BREAK-EVEN CHECK: if reached and not yet activated → set_trading_stop(symbol, entry, tp)
        DIRECTLY IN BYBIT (not just DB) → mark be_activated=true
     5. MAX DURATION CHECK: query real max_duration via same JOIN pattern (fallback 24) →
        close_trade(reason='time_exit') if exceeded
   ⚠️ NOTE: this monitor does NOT actively compare current_price against stored sl/tp to decide
     closure (unlike paper_trader's monitor) — it relies on BYBIT'S OWN NATIVE SL/TP EXECUTION
     (configured server-side via place_market_order/set_trading_stop) and only discovers those
     closures after the fact in step 1 (position no longer exists). This is intentional: real
     money SL/TP execution shouldn't depend on the 5-min tick cycle reaching the exchange in time.
   any exception per-trade is caught, logged with traceback, counted in results["errors"],
     does NOT abort processing of remaining trades in the account
```

---

## RISK MANAGEMENT — two SEPARATE, UNRELATED systems

```
┌─────────────────────────────┬──────────────────────────────┐
│ RiskManager                  │ Circuit Breaker               │
│ (trading/risk_manager.py)    │ (inline in real_trading.py)   │
├─────────────────────────────┼──────────────────────────────┤
│ ONLY used by Paper Trading   │ ONLY used by Real Trading      │
│ Protects against STRATEGY    │ Protects against TECHNICAL     │
│   drawdown/volatility        │   API failures                │
│ Pauses stored in risk_controls│ Pause = broker_accounts.status │
│   table                      │   = 'paused'                   │
│ Daily DD ≥3% → auto-resume   │ 3+ 'error' status trades in    │
│   next midnight UTC          │   2h → classify → pause if     │
│ Total DD ≥10% → MANUAL resume│   critical, else auto-clear    │
│ Volatility ATR>2x avg →      │ Manual reactivation required   │
│   pause per-strategy-per-    │   for paused account           │
│   symbol                     │                                │
│ Global kill switch exists in │ No kill switch equivalent      │
│   schema/logic but NO UI/    │                                │
│   endpoint found to activate │                                │
│   it (manual SQL only?)      │                                │
└─────────────────────────────┴──────────────────────────────┘
```
⚠️ **Real Trading has NO automatic drawdown protection.** Only the circuit breaker (API-failure-based) exists for it. If asked to add drawdown protection to real trading, this is a genuine feature gap, not a misunderstanding of existing code.

```python
# RiskManager constants
INITIAL_BALANCE = 10000.0   # separate constant from paper_trader.py's VIRTUAL_BALANCE=10000.0
                             # same value, two independent definitions, not shared
DAILY_DRAWDOWN_PCT = 3.0
TOTAL_DRAWDOWN_PCT = 10.0
VOLATILITY_MULTIPLIER = 2.0

# Circuit breaker constants (real_trader.py)
CIRCUIT_BREAKER_THRESHOLD = 3
BYBIT_TAKER_FEE = 0.00055   # 0.055%, used to ESTIMATE commission on close (not queried from
                              # Bybit's actual fee for that specific trade)
non_critical_error_patterns = ['firma','timestamp','10001','stopLoss','takeProfit',
  'rechazada por bybit','qty','invalid','no confirmada']
```

---

## ENVIRONMENT VARIABLES — complete reference

```bash
# Laravel (.env)
PYTHON_ENGINE_URL=http://127.0.0.1:8002
PYTHON_INTERNAL_API_KEY=<must match Python's INTERNAL_API_KEY>
ALLOW_INVESTOR_DEMO_ACCOUNTS=false

# Python (python-engine/.env, loaded independently per-module via load_dotenv())
DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
INTERNAL_API_KEY=<must match Laravel's PYTHON_INTERNAL_API_KEY>
BYBIT_BASE_URL=https://api.bybit.com           # default mainnet
BYBIT_TESTNET_URL=https://api-testnet.bybit.com
REDIS_URL=redis://127.0.0.1:6379
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT                # fallback for collector + regime_detector default
INTERVALS=1,5,15,60,120                        # collector fallback only
```

---

## DEPENDENCIES (pinned versions)

```
# Laravel composer.json
php: ^8.3
laravel/framework: ^13.8
laravel/horizon: ^5.47        # installed, NOT confirmed actively used (scheduler used, not clear if queue workers run via Horizon)
phpoffice/phpspreadsheet: ^5.8
predis/predis: ^3.5
guzzlehttp/guzzle: ^7.11

# Python requirements.txt
fastapi==0.115.0   uvicorn==0.30.6   httpx==0.27.0
asyncpg==0.29.0    psycopg2-binary==2.9.9  (likely unused by main engine, asyncpg is what's used async)
python-dotenv==1.0.1   pydantic==2.8.2
pandas==2.2.2   numpy==2.0.1   redis==5.0.8
```

---

## GOTCHAS — consolidated list (things that look like bugs or surprising design choices)

1. **`broker.py`**: `account_info()` function + `AccountInfoRequest` model defined 3 times verbatim. FastAPI silently keeps only the last. Dead code, harmless, should be cleaned.
2. **`base_strategy.py`**: `weekend_filter`/`blocked_hours`/`blocked_days` initialized twice identically in `__init__`. Harmless.
3. **`paper_strategy_configs` uniqueness**: original migration has hard `UNIQUE(strategy_class,symbol,interval)`, application code (`implementFromBacktest`) was changed to allow duplicates with different params. Unclear if original constraint was later dropped in a migration not yet found — verify on live schema before assuming duplicate-creation will succeed.
4. **`vwap_intraday.py`/`vwap_reversion.py`**: legacy predecessor strategy classes, confirmed unused by any router via grep. Candidates for removal/archival.
5. **`TradingController::getLivePrices()`**: falls back to `GET /v1/prices` on the Python engine — this endpoint was not found in ANY explored router. Likely dead/incomplete code path.
6. **`BacktestingController`**: `run()` (inline payload building) and `buildPayload()` (used only by `runAjax()`) are two independent implementations of the same logic — risk of drift if one is edited without the other.
7. **`PaperStrategyConfigController::store()` vs `::implement()`**: near-identical, functionally interchangeable, differ only in success message text.
8. **`paper_trades` schema**: has `tp2` column but no `tp3`/`tp4`, despite the backtest engine fully supporting 4 TP levels and `real_trades` having all 4 columns. Paper trading's `monitor_open_trades()` only actively evaluates TP1/TP2 priority in its close logic — TP3/TP4 levels calculated during backtest don't have an evident persistence/evaluation path in live paper trading.
9. **`real_trader.py::close_trade()` override branch**: references undefined local variable `symbol` in its final log statement (only `trade['symbol']` exists in scope) — would raise `NameError` if that specific log line executes. Verify against production logs whether this path has actually fired.
10. **`get_last_error_messages()` / `clear_non_critical_errors()`**: both defined twice, identically, in `RealTrader` class (`real_trader.py` lines ~459-484 and ~486-511). Harmless (Python just keeps the later definition), but indicates copy-paste residue.
11. **`get_current_price()` (paper trading price source) vs `BybitClient.get_market_price()` (real trading price source)**: the former ALWAYS hits mainnet regardless of context; the latter respects testnet/mainnet per the specific account's `account_type`. This is consistent by design (paper trading should reflect real market conditions regardless of which Bybit environment any connected real account uses) but isn't obvious without reading both implementations side by side.
12. **Walk-forward approval criteria vs full-backtest approval criteria**: `WalkForwardValidator._evaluate()` uses 5 criteria (trades≥10, Sharpe>0.5, WinRate>45%, Drawdown<15%, ProfitFactor>1.2). The `/backtest/run` endpoint, when `monthly_breakdown=True`, RECALCULATES `passed`/`pass_reasons` using only 3 criteria against the full (non-walk-forward) backtest (WinRate≥45%, Sharpe≥1, Drawdown≤15%) — slightly different thresholds and a different (smaller) criteria set, and crucially evaluated against a DIFFERENT dataset (full vs out-of-sample). The walk-forward's own `passed` value gets silently overwritten in this code path.
13. **`PaperStrategyConfig::pythonModulePath()`**: defined but appears unused — Python side maintains its own independent `STRATEGY_CLASS_MAP`, duplicated between `paper_trading.py` and `real_trading.py`, not calling back to this Laravel method (which wouldn't even be directly callable from Python anyway, given the two are separate language runtimes — this method seems to be a vestige or intended for some other use within Laravel itself).
14. **`RealStrategySubscription::pauseIfConfigInactive()`** and **`RealTrade::appendAuditLog()`**: both defined with clear intent but not found wired to any active trigger/job/controller in the explored codebase — likely available utilities, possibly meant for future use or manual invocation.
15. **No automatic drawdown protection on Real Trading** — only the API-failure circuit breaker exists for live money; the strategy-performance-based `RiskManager` is paper-trading-only. Relevant before connecting real capital at scale.
16. **No mainnet capital in production yet** — as of the last working session referenced in this exploration, real trading runs exclusively on Bybit testnet (demo account), used as the live-validation phase before committing real funds.

---

## QUICK ANSWERS TO LIKELY QUESTIONS

```
Q: Where do I add a new strategy?
A: 1) Create class in backtesting/strategies/, inherit BaseStrategy, implement generate_signals()
   2) Add to STRATEGY_CLASS_MAP in BOTH paper_trading.py AND real_trading.py (kept in sync manually)
   3) Add to BacktestingController::STRATEGY_OPTIONS (Laravel) for it to appear in the UI form
   4) Add to PaperStrategyConfig::strategyNameToClassAndMode() / classAndModeToStrategyName() (Laravel)
   5) Add regime default in api/v1/backtest.py::load_strategy()

Q: Where is SL/TP actually enforced for paper trading?
A: PaperTrader.monitor_open_trades() — compares current_price against stored sl/tp every 5-min tick,
   closes in-process if breached. No exchange involved, pure simulation.

Q: Where is SL/TP actually enforced for real trading?
A: Set NATIVELY on Bybit's side via place_market_order() (provisional) then set_trading_stop()
   (exact values, after fill confirmation). The 5-min monitor only discovers closures AFTER they
   already happened on Bybit's side — it does not decide them.

Q: How do I change the star-rating formula?
A: BacktestingController::calcularEstrellas() (Laravel) — the ONLY place this logic lives.

Q: Why does a backtest show different numbers in KPIs vs the monthly breakdown table?
A: It shouldn't, post-fix (see GOTCHA #12) — if it does, check whether walk_forward result's
   aggregate_metrics is being read instead of the full-backtest's recalculated version.

Q: Can two paper_strategy_configs exist for the same symbol+strategy+interval?
A: Yes, as long as their `params` JSON differ in at least one value. See GOTCHA #3 for the
   unconfirmed DB constraint caveat.
```

---

*End of CONTEXT.md. This document, together with 01_GENERAL.md (narrative overview) and 02_TECHNICAL.md (exhaustive function-by-function reference), constitutes the complete documentation set for tr-bot V2 as of this exploration.*

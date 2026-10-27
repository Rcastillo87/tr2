<?php
/**
 * Crea backtests en el historial a partir de las configuraciones de cli/param_search.py (robustas.json),
 * por el MISMO camino que la pantalla de Backtesting:
 *   1) arma los campos del formulario (los mismos nombres y formatos que envía run.blade.php),
 *   2) llama a BacktestingController::executeAjax (mismo payload a Python, mismas métricas y firma),
 *   3) toma el save_data del HTML de resultados (exactamente lo que el navegador enviaría al pulsar Guardar)
 *   4) y llama a BacktestingController::saveBacktest (firma HMAC, hash anti-duplicado, transacción).
 * No escribe en la base por ningún otro lado. No implementa en Paper (eso sigue siendo decisión en la UI).
 *
 * Uso (desde la raíz del proyecto):
 *   php ops/backtest_from_search.php /tmp/x_robustas.json --symbols BTCUSDT,ETHUSDT [--months 24] [--solo 1] [--simular]
 *     --solo N    solo la configuración N (1 = la primera del JSON)
 *     --simular   ejecuta y muestra resultados, pero NO guarda
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BacktestingController;
use App\Models\Strategy;
use App\Models\User;
use App\Services\StrategyConfigSync;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

$args = $argv;
array_shift($args);
$opt = static function (string $name, ?string $default = null) use (&$args): ?string {
    $i = array_search($name, $args, true);
    if ($i === false) {
        return $default;
    }
    $val = $args[$i + 1] ?? null;
    array_splice($args, $i, 2);

    return $val;
};
$flag = static function (string $name) use (&$args): bool {
    $i = array_search($name, $args, true);
    if ($i === false) {
        return false;
    }
    array_splice($args, $i, 1);

    return true;
};

$symbolsArg = $opt('--symbols');
$months = (int) $opt('--months', '24');
$only = $opt('--solo');
$simulate = $flag('--simular');
$jsonPath = $args[0] ?? '';

if (! is_file($jsonPath) || ! $symbolsArg) {
    fwrite(STDERR, "Uso: php ops/backtest_from_search.php <robustas.json> --symbols A,B,C [--months 24] [--solo N] [--simular]\n");
    exit(2);
}
$symbols = array_values(array_filter(array_map('trim', explode(',', $symbolsArg))));
$picks = json_decode((string) file_get_contents($jsonPath), true);
if (! is_array($picks) || $picks === []) {
    fwrite(STDERR, "El JSON no tiene configuraciones.\n");
    exit(2);
}

// Usuario con permiso de Backtesting (el Gate del controlador se evalúa igual que en la web)
$user = User::query()->orderBy('id')->get()->first(fn (User $u) => $u->canViewAnalysisTools());
if (! $user) {
    fwrite(STDERR, "No hay ningún usuario con permiso de Backtesting.\n");
    exit(2);
}
Auth::setUser($user);
$session = app('session')->driver();
$session->start();

/** Campos del formulario tal como los envía run.blade.php (checkbox marcado = campo presente). */
function formFields(array $p, int $strategyId, array $symbols, int $months): array
{
    $ambiguous = match (strtoupper((string) ($p['regime_ambiguous_as'] ?? 'RANGING'))) {
        'TRENDING' => 'tendencia',
        'NO_OPERAR' => 'ignorar',
        default => 'lateral',
    };
    $f = [
        'strategy_id' => $strategyId,
        'symbols' => $symbols,
        'interval' => (string) $p['intervalo'],
        'months' => $months,
        'initial_balance' => '10000',          // el valor oculto por defecto del formulario
        'risk_per_trade_pct' => '1.0',          // el mismo de la búsqueda
        'commission_pct' => '0.055',
        'slippage_pct' => '0.05',
        'sl_pct' => (string) $p['sl_pct'],
        'tp_pct' => (string) $p['tp_pct'],
        'be_pct' => (string) $p['be_pct'],
        'max_duration' => (string) $p['max_duration'],
        'trailing_mode' => $p['trailing_mode'] ?: 'none',
        'trailing_distance_pct' => (string) $p['trailing_distance_pct'],
        'trailing_activation_buffer_pct' => (string) $p['trailing_activation_buffer_pct'],
        'trailing_atr_mult' => (string) $p['trailing_atr_mult'],
        'regime_adx_trending' => (string) $p['regime_adx_trending'],
        'regime_adx_ranging' => (string) $p['regime_adx_ranging'],
        'regime_ambiguous_as' => $ambiguous,
        'volume_filter_period' => (string) $p['volume_filter_period'],
        'volume_filter_mult' => (string) $p['volume_filter_mult'],
        'volatility_protection_mode' => 'none',
    ];
    foreach (['max_duration_profit', 'close_on_opposite', 'regime_filter', 'macro_trend_filter', 'volume_filter'] as $cb) {
        if (! empty($p[$cb])) {
            $f[$cb] = 'on';
        }
    }

    return $f;
}

function saveDataFromHtml(string $html): ?string
{
    $doc = new DOMDocument();
    libxml_use_internal_errors(true);
    $doc->loadHTML('<?xml encoding="utf-8"?>' . $html);
    libxml_clear_errors();
    $node = (new DOMXPath($doc))->query('//form[@id="saveBacktestForm"]//input[@name="save_data"]')->item(0);

    return $node?->getAttribute('value');
}

function bind(Request $req): Request
{
    $req->setLaravelSession(app('session')->driver());
    $req->setUserResolver(fn () => Auth::user());
    app()->instance('request', $req);

    return $req;
}

$controller = app(BacktestingController::class);
$sync = app(StrategyConfigSync::class);
$exit = 0;

foreach ($picks as $k => $p) {
    $n = $k + 1;
    if ($only !== null && (int) $only !== $n) {
        continue;
    }
    $strategy = Strategy::where('name', $p['estrategia'])->first();
    if (! $strategy) {
        fwrite(STDERR, "Config {$n}: no existe la estrategia '{$p['estrategia']}'.\n");
        $exit = 1;
        continue;
    }
    $fields = formFields($p, (int) $strategy->id, $symbols, $months);
    echo "\n═══ Config {$n}: {$strategy->name} · {$fields['interval']} · {$months} meses · " . count($symbols) . " monedas\n";
    $t0 = microtime(true);

    $res = $controller->executeAjax(bind(Request::create('/backtesting/execute-ajax', 'POST', $fields)));
    $body = $res->getData(true);
    if (empty($body['success'])) {
        fwrite(STDERR, '  ERROR al ejecutar: ' . ($body['error'] ?? 'desconocido') . "\n");
        $exit = 1;
        continue;
    }
    $saveData = saveDataFromHtml($body['html'] ?? '');
    $payload = $saveData ? json_decode((string) base64_decode($saveData, true), true) : null;
    if (! is_array($payload)) {
        fwrite(STDERR, "  ERROR: el HTML de resultados no trae save_data.\n");
        $exit = 1;
        continue;
    }

    printf("  %-10s %6s │ %6s %8s %6s\n", 'Moneda', 'Trades', 'PF', 'Ret', 'DD');
    foreach ($payload['metrics']['individual_results'] ?? [] as $ind) {
        $a = $ind['aggregate_metrics'] ?? [];
        printf("  %-10s %6d │ %6s %7s%% %5s%%\n", $ind['symbol'], $a['total_trades'] ?? 0,
            $a['profit_factor'] ?? '-', $a['total_return_pct'] ?? '-', $a['max_drawdown_pct'] ?? '-');
    }
    $m = $payload['metrics'];
    printf("  → TOTAL %d operaciones · PF %s · retorno %s%% · win %s%% · %.0f s\n",
        $m['total_trades'] ?? 0, $m['profit_factor'] ?? '-', $m['total_return_pct'] ?? '-', $m['win_rate'] ?? '-', microtime(true) - $t0);
    foreach (array_unique($body['warnings'] ?? []) as $w) {
        echo '  aviso: ' . mb_strimwidth((string) $w, 0, 160, '…') . "\n";
    }

    if ($simulate) {
        echo "  (simulación: no se guardó)\n";
        continue;
    }
    $req = Request::create('/backtesting/save', 'POST', ['save_data' => $saveData]);
    $req->headers->set('Accept', 'application/json');
    $saved = $controller->saveBacktest(bind($req), $sync)->getData(true);
    echo '  ' . (! empty($saved['success']) ? "GUARDADO backtest #{$saved['backtest_id']}" : 'NO GUARDADO') . ': ' . ($saved['message'] ?? '') . "\n";
    if (empty($saved['success'])) {
        $exit = 1;
    }
}

exit($exit);

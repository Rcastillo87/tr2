<?php
/**
 * Corre (y opcionalmente guarda) backtests a partir de configuraciones de cli/param_search.py (robustas.json),
 * por el MISMO camino que la pantalla (servicio App\Services\BacktestFromSearch, el que usa "Crear en historial").
 *
 * Uso (desde la raíz del proyecto):
 *   php ops/backtest_from_search.php /tmp/x_robustas.json --symbols BTCUSDT,ETHUSDT [--months 24] [--solo 1] [--simular]
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Strategy;
use App\Models\User;
use App\Services\BacktestFromSearch;

$args = array_slice($argv, 1);
$take = static function (string $name, ?string $default = null) use (&$args): ?string {
    $i = array_search($name, $args, true);
    if ($i === false) {
        return $default;
    }
    $val = $args[$i + 1] ?? null;
    array_splice($args, $i, 2);

    return $val;
};
$symbolsArg = $take('--symbols');
$months = (int) $take('--months', '24');
$only = $take('--solo');
$simulate = in_array('--simular', $args, true);
$args = array_values(array_diff($args, ['--simular']));
$jsonPath = $args[0] ?? '';

if (! is_file($jsonPath) || ! $symbolsArg) {
    fwrite(STDERR, "Uso: php ops/backtest_from_search.php <robustas.json> --symbols A,B,C [--months 24] [--solo N] [--simular]\n");
    exit(2);
}
$symbols = array_values(array_filter(array_map('trim', explode(',', $symbolsArg))));
$picks = json_decode((string) file_get_contents($jsonPath), true) ?: [];
$user = User::query()->orderBy('id')->get()->first(fn (User $u) => $u->canViewAnalysisTools());
if (! $user || $picks === []) {
    fwrite(STDERR, "Sin usuario con permiso de Backtesting o JSON vacío.\n");
    exit(2);
}
$creator = app(BacktestFromSearch::class);
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
    echo "\n═══ Config {$n}: {$strategy->name} · {$p['intervalo']} · {$months} meses · " . count($symbols) . " monedas\n";
    $t0 = microtime(true);
    try {
        $out = $creator->run($user, $strategy, $p, (string) $p['intervalo'], $symbols, $months, ! $simulate);
    } catch (Throwable $e) {
        fwrite(STDERR, '  ERROR: ' . $e->getMessage() . "\n");
        $exit = 1;
        continue;
    }
    $m = $out['payload']['metrics'];
    printf("  %-10s %6s │ %6s %8s %6s\n", 'Moneda', 'Trades', 'PF', 'Ret', 'DD');
    foreach ($m['individual_results'] ?? [] as $ind) {
        $a = $ind['aggregate_metrics'] ?? [];
        printf("  %-10s %6d │ %6s %7s%% %5s%%\n", $ind['symbol'], $a['total_trades'] ?? 0,
            $a['profit_factor'] ?? '-', $a['total_return_pct'] ?? '-', $a['max_drawdown_pct'] ?? '-');
    }
    printf("  → TOTAL %d operaciones · PF %s · retorno %s%% · ★ %s · consistencia %s%% · %.0f s\n", $m['total_trades'] ?? 0,
        $m['profit_factor'] ?? '-', $m['total_return_pct'] ?? '-', $m['rating'] ?? '-', $m['consist_pct'] ?? '-', microtime(true) - $t0);
    foreach ($out['warnings'] as $w) {
        echo '  aviso: ' . mb_strimwidth((string) $w, 0, 160, '…') . "\n";
    }
    echo $simulate ? "  (simulación: no se guardó)\n" : "  GUARDADO backtest #{$out['saved']['backtest_id']}: {$out['saved']['message']}\n";
}
exit($exit);

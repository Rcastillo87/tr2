<?php
/**
 * Prueba forense: las métricas que muestra la búsqueda (ParamSearchService::summarize) son IDÉNTICAS a las que
 * guarda el historial para el mismo backtest. Compara una fila de una búsqueda terminada contra un backtest guardado
 * con la misma configuración, intervalo y monedas: estrellas, retorno total, consistencia, PF, trades, win rate,
 * Sharpe y promedio mensual. Solo lectura.
 *
 * Uso: php tests/Forensic/param_search_summary_test.php <id_busqueda> <id_fila> <id_backtest>
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Backtest;
use App\Models\ParamSearchRun;
use App\Services\ParamSearchService;

[$runId, $rowId, $btId] = [(int) ($argv[1] ?? 0), (string) ($argv[2] ?? ''), (int) ($argv[3] ?? 0)];
$run = ParamSearchRun::find($runId);
$bt = Backtest::find($btId);
$row = collect($run?->results['rows'] ?? [])->firstWhere('id', $rowId);
if (! $run || ! $bt || ! $row) {
    fwrite(STDERR, "No encontré la búsqueda #{$runId}, la fila {$rowId} o el backtest #{$btId}.\n");
    exit(2);
}
$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails) {
    $fails += $ok ? 0 : 1;
    echo ($ok ? 'PASS' : 'FAIL') . "  {$name}" . ($detail !== '' ? "  -> {$detail}" : '') . "\n";
};

$symbols = array_values((array) $bt->symbols);
$s = app(ParamSearchService::class)->summarize($row, $symbols);
$m = (array) $bt->metrics;
$cp = (array) $bt->config_params;

$check('mismas monedas', count($s['symbols']) === count($symbols), implode(',', $s['symbols']));
$check('mismo intervalo', (string) $row['interval'] === (string) $bt->interval, "{$row['interval']} vs {$bt->interval}");
foreach (['sl_pct', 'tp_pct', 'be_pct', 'max_duration', 'trailing_distance_pct', 'trailing_atr_mult'] as $k) {
    $check("misma config: {$k}", (float) $row['cfg'][$k] === (float) ($cp[$k] ?? -1), "{$row['cfg'][$k]} vs " . ($cp[$k] ?? 'null'));
}
$pairs = [
    'estrellas'         => ['rating', 'rating', 0.0],
    'retorno total %'   => ['total_return_pct', 'total_return_pct', 0.011],
    'consistencia %'    => ['consist_pct', 'consist_pct', 0.0],
    'promedio mensual'  => ['avg_monthly_pnl', 'avg_monthly_pnl', 0.011],
    'profit factor'     => ['profit_factor', 'profit_factor', 0.0],
    'operaciones'       => ['total_trades', 'total_trades', 0.0],
    'win rate %'        => ['win_rate', 'win_rate', 0.0],
    'sharpe'            => ['sharpe_ratio', 'sharpe_ratio', 0.0],
];
foreach ($pairs as $label => [$a, $b, $tol]) {
    $va = (float) $s[$a];
    $vb = (float) ($m[$b] ?? NAN);
    $check("{$label}: búsqueda = historial", abs($va - $vb) <= $tol + 1e-9, "{$va} vs {$vb}");
}
echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails ? 1 : 0);

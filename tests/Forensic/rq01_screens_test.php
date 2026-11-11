<?php
/**
 * RQ-01 pantallas (integración, Laravel + base real): renderiza las vistas reales con datos reales y de prueba.
 * - Estrategias: cada backtest en Paper muestra Trades/mes, abiertos/cerrados de Paper y el enlace a history#bt-<id>.
 * - Historial: cada tarjeta tiene id="bt-<id>", línea de Origen (búsqueda con enlace, manual, no registrado) y Trades/mes.
 * - Búsqueda: la página compila y trae las insignias nuevas (borrado · disponible, enlace al historial).
 * Todo en una transacción que se revierte. No llama al motor.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/rq01_screens_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BacktestingController;
use App\Http\Controllers\ParamSearchController;
use App\Http\Controllers\StrategyController;
use App\Models\Backtest;
use App\Models\ParamSearchRun;
use App\Models\Strategy;
use App\Models\User;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails) {
    $fails += $ok ? 0 : 1;
    echo ($ok ? 'PASS ' : 'FAIL ') . $name . ($detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '') . "\n";
};
$render = function (callable $fn): string {
    try {
        $out = $fn();

        return is_object($out) && method_exists($out, 'render') ? (string) $out->render() : '';
    } catch (Throwable $e) {
        return 'EXCEPCION: ' . $e->getMessage() . ' @ ' . basename($e->getFile()) . ':' . $e->getLine();
    }
};

DB::beginTransaction();
try {
    $admin = User::where('role', 'admin')->orderBy('id')->first();
    $strategy = Strategy::orderBy('id')->first();
    if (! $admin || ! $strategy) {
        echo "SKIP  hace falta un usuario admin y una estrategia\n";
        DB::rollBack();
        exit(2);
    }
    Auth::login($admin);
    app('request')->setUserResolver(fn () => Auth::user());
    // En la web, ShareErrorsFromSession comparte $errors con todas las vistas; en CLI hay que hacerlo a mano
    view()->share('errors', new Illuminate\Support\ViewErrorBag());

    // Datos de prueba: un backtest por origen, en la misma estrategia
    $base = ['strategy_id' => $strategy->id, 'interval' => '240', 'months' => 6, 'strategy_snapshot' => [], 'approved' => false];
    $run = ParamSearchRun::create(['strategy_id' => $strategy->id, 'user_id' => $admin->id, 'intervals' => ['240'],
        'search_symbols' => ['ENAUSDT'], 'validation_symbols' => [], 'months' => 24, 'samples' => 40, 'seed' => 1,
        'status' => 'done', 'focus' => 'gain', 'mode' => 'symbol']);
    $mk = fn (array $o) => Backtest::create($base + $o);
    $bS = $mk(['symbols' => ['ENAUSDT'], 'config_params' => ['t' => 'rq01-s', 'start_date' => '2025-01-01', 'end_date' => '2025-07-01'],
               'metrics' => ['total_trades' => 61, 'closed_at_end' => 1, 'trades_by_symbol' => ['ENAUSDT' => 60]],
               'origin' => 'search', 'origin_meta' => ['run_id' => $run->id, 'row_id' => 'ENAUSDT-240-3', 'focus' => 'gain',
                                                         'mode' => 'symbol', 'search_at' => '2026-11-07T14:00:00+00:00']]);
    $bM = $mk(['symbols' => ['SOLUSDT'], 'config_params' => ['t' => 'rq01-m'], 'metrics' => ['total_trades' => 5], 'origin' => 'manual']);
    $bN = $mk(['symbols' => ['BTCUSDT', 'ETHUSDT'], 'config_params' => ['t' => 'rq01-n'], 'metrics' => ['total_trades' => 9]]);
    $bGone = $mk(['symbols' => ['XRPUSDT'], 'config_params' => ['t' => 'rq01-g'], 'metrics' => ['total_trades' => 3], 'origin' => 'search',
                  'origin_meta' => ['run_id' => 999999999, 'row_id' => 'r1']]);

    // Historial
    $h = $render(fn () => app(BacktestingController::class)->history($strategy));
    $card = function (int $id) use ($h): string {
        $p = strpos($h, 'id="bt-' . $id . '"');
        if ($p === false) {
            return '';
        }
        $n = strpos($h, 'id="bt-', $p + 10);   // la tarjeta termina donde empieza la siguiente

        return substr($h, $p, $n === false ? 6000 : $n - $p);
    };
    $check('H0: el historial renderiza', $h !== '' && ! str_starts_with($h, 'EXCEPCION'), substr($h, 0, 200));
    $cS = $card($bS->id);
    $check('H1: tarjeta con ancla bt-<id> y número de backtest', $cS !== '' && str_contains($cS, "Backtest #{$bS->id}"));
    $check('H2: origen búsqueda con enlace a la búsqueda', str_contains($cS, route('strategies.search.show', $run->id))
        && str_contains($cS, "Búsqueda #{$run->id} · fila ENAUSDT-240-3"), substr(strip_tags($cS), 0, 300));
    $check('H3: Trades/mes de la tarjeta = 60 trades / 181 días × 30,4375 = 10.09', str_contains($cS, '10.09'));
    $cM = $card($bM->id);
    $check('H4: origen manual', str_contains($cM, 'Manual (pantalla de backtesting)'));
    $cN = $card($bN->id);
    $check('H5: sin origen -> «Origen no registrado»; multimoneda sin conteos -> N/D por moneda',
        str_contains($cN, 'Origen no registrado') && str_contains($cN, 'BTCUSDT N/D') && str_contains($cN, 'ETHUSDT N/D'));
    $cG = $card($bGone->id);
    $check('H6: búsqueda borrada -> texto sin enlace', str_contains($cG, 'Búsqueda #999999999') && ! str_contains($cG, '/busquedas/999999999'));

    // Estrategias (configs Paper activas reales)
    $s = $render(fn () => app(StrategyController::class)->index());
    $check('S0: Estrategias renderiza', $s !== '' && ! str_starts_with($s, 'EXCEPCION'), substr($s, 0, 200));
    $active = DB::table('paper_strategy_configs')->where('active', true)->whereNotNull('backtest_id')->get(['id', 'backtest_id', 'avg_monthly_trades']);
    if ($active->isEmpty()) {
        echo "     (sin configs Paper activas: S1-S3 no aplican)\n";
    } else {
        $missing = $active->filter(fn ($c) => ! str_contains($s, '#bt-' . $c->backtest_id . '"'))->pluck('backtest_id')->unique()->values()->all();
        $check('S1: cada backtest en Paper enlaza a su tarjeta del historial (#bt-<id>)', $missing === [], $missing);
        $c = $active->firstWhere('avg_monthly_trades', '!=', null);
        $check('S2: muestra Trades/mes de las configs', str_contains($s, 'Trades/mes:')
            && ($c === null || str_contains($s, number_format((float) $c->avg_monthly_trades, 2))), $c?->avg_monthly_trades);
        $check('S3: muestra abiertos/cerrados de Paper', str_contains($s, 'abiertos ·') && str_contains($s, 'cerrados'));
    }

    // Búsqueda
    $p = $render(fn () => app(ParamSearchController::class)->show($run));
    $check('B1: la página de la búsqueda renderiza con las insignias nuevas', ! str_starts_with($p, 'EXCEPCION')
        && str_contains($p, 'borrado · disponible') && str_contains($p, '#bt-${id}'), substr($p, 0, 200));
} finally {
    DB::rollBack();
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

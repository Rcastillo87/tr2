<?php
/**
 * Búsqueda v3 en Laravel: orden por enfoque, monedas por modo (resumen y creación), eliminar (activa no, terminada sí),
 * ruta DELETE y la página de resultados con búsquedas v3 y anteriores. Todo en una transacción que se revierte.
 * Uso: php tests/Forensic/param_search_v3_laravel_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\ParamSearchController;
use App\Models\ParamSearchRun;
use App\Models\Strategy;
use App\Models\User;
use App\Services\ParamSearchService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails) {
    $fails += $ok ? 0 : 1;
    echo ($ok ? 'PASS ' : 'FAIL ') . $name . ($detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '') . "\n";
};

$sym = fn (float $ret, float $wr, array $m) => ['role' => 'win', 'why' => null, 'n' => 60, 'wins' => (int) round(60 * $wr / 100), 'wr' => $wr,
    'sharpe' => 1.0, 'pf' => 1.4, 'ret' => $ret, 'dd' => 5.0, 'gp' => 100.0, 'gl' => 70.0, 'm' => $m, 'm1' => true];
$cfg = ['sl_pct' => 1.5, 'tp_pct' => 3.0, 'be_pct' => 99.0, 'trailing_mode' => null, 'trailing_atr_mult' => 2.0, 'trailing_distance_pct' => 1.0,
    'trailing_activation_buffer_pct' => 0.0, 'regime_filter' => false, 'macro_trend_filter' => false, 'volume_filter' => false,
    'volume_filter_period' => 20, 'volume_filter_mult' => 1.2, 'max_duration' => 0, 'max_duration_profit' => false, 'close_on_opposite' => false,
    'regime_adx_trending' => 25.0, 'regime_adx_ranging' => 20.0, 'regime_ambiguous_as' => 'RANGING'];
$seg = ['n' => 40, 'pf' => 1.3, 'ret' => 2.5, 'pos' => 1];
$months = array_map(fn ($i) => sprintf('2025-%02d', $i % 12 + 1), range(0, 23));
$up = array_fill(0, 24, 0.5);
$mixed = array_merge(array_fill(0, 12, 2.0), array_fill(0, 12, -0.2));   // retorno alto, consistencia 50 %

DB::beginTransaction();
try {
    $strategy = Strategy::orderBy('id')->first();
    $admin = User::where('role', 'admin')->orderBy('id')->first() ?? User::orderBy('id')->first();
    Auth::login($admin);
    $base = ['strategy_id' => $strategy->id, 'user_id' => $admin->id, 'intervals' => ['60'], 'search_symbols' => ['SOLUSDT', 'ENAUSDT'],
             'validation_symbols' => [], 'months' => 24, 'samples' => 40, 'seed' => 1];

    // 1. Por moneda, enfoque consistencia
    $rowsSym = [
        ['id' => 'SOLUSDT-60-0', 'symbol' => 'SOLUSDT', 'interval' => '60', 'cfg' => $cfg, 'symbols' => ['SOLUSDT' => $sym(24.0, 45, $mixed)],
         'survivors' => ['SOLUSDT'], 'discarded' => [], 'is' => $seg, 'oos' => $seg, 'oos_ok' => true, 'ret_total' => 21.6, 'consist' => 50.0],
        ['id' => 'SOLUSDT-60-1', 'symbol' => 'SOLUSDT', 'interval' => '60', 'cfg' => $cfg, 'symbols' => ['SOLUSDT' => $sym(12.0, 60, $up)],
         'survivors' => ['SOLUSDT'], 'discarded' => [], 'is' => $seg, 'oos' => $seg, 'oos_ok' => true, 'ret_total' => 12.0, 'consist' => 100.0],
        ['id' => 'ENAUSDT-60-0', 'symbol' => 'ENAUSDT', 'interval' => '60', 'cfg' => $cfg, 'symbols' => ['ENAUSDT' => $sym(8.0, 52, $up)],
         'survivors' => ['ENAUSDT'], 'discarded' => [], 'is' => $seg, 'oos' => $seg, 'oos_ok' => true, 'ret_total' => 12.0, 'consist' => 100.0],
    ];
    $results = ['version' => 3, 'focus' => 'cons', 'mode' => 'symbol', 'months' => $months, 'tested' => 40, 'survivors' => 3, 'min_trades' => 30,
                'rows' => $rowsSym, 'near' => ['SOLUSDT' => [], 'ENAUSDT' => []], 'period' => ['start' => '2024-10-01', 'split' => '2026-02-01', 'end' => '2026-10-01']];
    $run = ParamSearchRun::create($base + ['status' => 'done', 'focus' => 'cons', 'mode' => 'symbol']);
    DB::table('param_search_runs')->where('id', $run->id)->update(['results' => json_encode($results)]);
    $run->refresh();
    $check('focus y mode se guardan (fillable)', $run->focus === 'cons' && $run->mode === 'symbol', [$run->focus, $run->mode]);

    $ctrl = app(ParamSearchController::class);
    $out = $ctrl->results(Request::create('/', 'GET'), $run)->getData(true);
    $ids = array_column($out['rows'], 'id');
    $check('v3: devuelve focus, mode y la moneda de cada fila', $out['focus'] === 'cons' && $out['mode'] === 'symbol'
        && array_column($out['rows'], 'symbol') !== [] && ! in_array(null, array_column($out['rows'], 'symbol'), true));
    $check('enfoque consistencia: 100 % de meses antes que 50 % aunque gane menos', array_search('SOLUSDT-60-1', $ids) < array_search('SOLUSDT-60-0', $ids), $ids);
    $r0 = collect($out['rows'])->firstWhere('id', 'SOLUSDT-60-0');
    $check('por moneda: el resumen usa solo su moneda', $r0['summary']['symbols'] === ['SOLUSDT'] || in_array('SOLUSDT', $r0['summary']['symbols'], true), $r0['summary']['symbols']);
    $svc = app(ParamSearchService::class);
    $check('por moneda: se crea con su moneda', $svc->symbolsFor($run, $rowsSym[0], 'survivors') === ['SOLUSDT']);

    // Mismo run con enfoque ganancia: orden por retorno
    $results['focus'] = 'gain';
    DB::table('param_search_runs')->where('id', $run->id)->update(['results' => json_encode($results)]);
    $ids = array_column($ctrl->results(Request::create('/', 'GET'), $run->fresh())->getData(true)['rows'], 'id');
    $check('enfoque ganancia: mayor retorno primero', $ids[0] === 'SOLUSDT-60-0', $ids);

    // 2. Por temporalidad: métricas de TODAS las monedas (también las que pierden)
    $lose = $sym(-6.0, 40, array_fill(0, 24, -0.25));
    $lose['role'] = 'lose';
    $lose['why'] = 'pierde';
    $rowInt = ['id' => '60-0', 'interval' => '60', 'cfg' => $cfg, 'symbols' => ['BTCUSDT' => $sym(10.0, 55, $up), 'ETHUSDT' => $sym(9.0, 55, $up),
               'SOLUSDT' => $sym(8.0, 55, $up), 'XRPUSDT' => $lose], 'survivors' => ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'], 'discarded' => ['XRPUSDT'],
               'is' => $seg, 'oos' => $seg, 'oos_ok' => true, 'ret_total' => 0, 'consist' => 0];
    $runI = ParamSearchRun::create(array_merge($base, ['status' => 'done', 'focus' => 'gain', 'mode' => 'interval', 'search_symbols' => ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']]));
    DB::table('param_search_runs')->where('id', $runI->id)->update(['results' => json_encode(['version' => 3, 'focus' => 'gain', 'mode' => 'interval',
        'need' => 3, 'months' => $months, 'rows' => [$rowInt], 'near' => [], 'survivors' => 1])]);
    $runI->refresh();
    $s = collect($ctrl->results(Request::create('/', 'GET'), $runI)->getData(true)['rows'])->first()['summary'];
    $check('por temporalidad: el resumen incluye la moneda que pierde', count($s['symbols']) === 4 && in_array('XRPUSDT', $s['symbols'], true), $s['symbols']);
    $check('por temporalidad: se crea con todas las monedas probadas', count($svc->symbolsFor($runI, $rowInt, 'survivors')) === 4);
    $check('por temporalidad: el retorno total descuenta la perdedora', abs($s['total_return_pct'] - (12 + 12 + 12 - 6)) < 1e-6, $s['total_return_pct']);

    // 3. Compatibilidad v2: sigue usando las sobrevivientes
    $runOld = ParamSearchRun::create($base + ['status' => 'done']);
    DB::table('param_search_runs')->where('id', $runOld->id)->update(['results' => json_encode(['version' => 2, 'months' => $months, 'rows' => [$rowInt]])]);
    $check('v2: sigue creando con las sobrevivientes', $svc->symbolsFor($runOld->fresh(), $rowInt, 'survivors') === ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']);

    // 4. Eliminar
    $active = ParamSearchRun::whereIn('status', ParamSearchRun::ACTIVE)->exists();
    if (! $active) {
        $q = ParamSearchRun::create($base + ['status' => 'queued']);
        $res = $ctrl->destroy($q);
        $check('eliminar una búsqueda en cola -> rechazada (422)', $res->getStatusCode() === 422 && ParamSearchRun::whereKey($q->id)->exists());
        $q->update(['status' => 'cancelled']);
    } else {
        echo "SKIP eliminar en cola: hay una búsqueda real activa\n";
    }
    $res = $ctrl->destroy($runOld);
    $check('eliminar una terminada -> borrada', $res->getStatusCode() === 200 && ! ParamSearchRun::whereKey($runOld->id)->exists());
    $route = app('router')->getRoutes()->getByName('strategies.search.destroy');
    $check('ruta DELETE (solo administración: grupo can:manageUsers)', $route && in_array('DELETE', $route->methods(), true)
        && in_array('can:manageUsers', $route->gatherMiddleware(), true), $route?->gatherMiddleware());

    // 5. Validación del inicio
    try {
        $svc->start($strategy, 'symbol', [], ['SOLUSDT'], $admin->id, 'otro');
        $check('enfoque inválido -> rechazado', false);
    } catch (DomainException $e) {
        $check('enfoque inválido -> rechazado', str_contains($e->getMessage(), 'Enfoque'));
    }
    try {
        $svc->start($strategy, 'symbol', [], ['A', 'B', 'C', 'D', 'E', 'F'], $admin->id, 'gain');
        $check('6 monedas en modo por moneda -> rechazado', false);
    } catch (DomainException $e) {
        $check('6 monedas en modo por moneda -> rechazado', str_contains($e->getMessage(), '5'), $e->getMessage());
    }
    $opts = $ctrl->options($strategy)->getData(true);
    $check('opciones: 3 enfoques y hasta 5 monedas', count($opts['focuses']) === 3 && $opts['limits']['max_symbols_symbol_mode'] === 5);

    // 6. Página de resultados con búsquedas v3 y anteriores
    try {
        $html = $ctrl->show($run->fresh())->render();
        $check('página de resultados: se dibuja (historial con enfoque, modo y eliminar)', str_contains($html, 'Eliminar')
            && str_contains($html, 'Consistencia alta') && str_contains($html, 'Por moneda') && str_contains($html, 'sbResults3'));
    } catch (Throwable $e) {
        $check('página de resultados: se dibuja', false, get_class($e) . ': ' . $e->getMessage());
    }
} finally {
    DB::rollBack();
}
echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);

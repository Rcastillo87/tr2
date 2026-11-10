<?php
/**
 * RQ-01.3 (integración, Laravel + base real): el guardado real (BacktestingController::saveBacktest) fija el origen.
 * - Guardar desde la pantalla -> manual; un campo «origin» enviado por el navegador no cambia nada.
 * - Con la foto de búsqueda como atributo interno (lo que hace BacktestFromSearch) -> search con su foto.
 * - Un re-test (mismo backtest_id) no cambia el origen.
 * - La columna rechaza valores fuera de manual|search; los recuperados apuntan a un results.created real.
 * TODO corre dentro de una transacción que se revierte. No llama al motor.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/backtest_origin_save_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BacktestingController;
use App\Models\Backtest;
use App\Models\Strategy;
use App\Models\User;
use App\Services\StrategyConfigSync;
use App\Support\BacktestOrigin;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

$user = User::query()->where('role', 'admin')->orderBy('id')->first();
$strategy = Strategy::query()->orderBy('id')->first();
if (! $user || ! $strategy) {
    echo "SKIP  hace falta un usuario admin y una estrategia\n";
    exit(2);
}
Auth::setUser($user);
$session = app('session')->driver();
$session->start();

/** Guarda por el camino real: payload firmado como lo deja executeAjax, petición JSON como la del navegador. */
$save = function (string $marker, array $body = [], ?array $attribute = null, ?int $backtestId = null) use ($strategy, $session): array {
    $configParams = ['sl_pct' => 1.5, 'tp_pct' => 3.0, 'test_marker' => $marker];
    $signed = ['strategy_id' => (int) $strategy->id, 'symbols' => ['BTCUSDT'], 'interval' => '60', 'months' => 6,
               'config_params' => $configParams, 'total_trades' => 4];
    $payload = $signed + ['signed_total_trades' => 4, 'signature' => StrategyConfigSync::sign($signed),
                          'metrics' => ['total_trades' => 4, 'win_rate' => 50.0], 'strategy_snapshot' => [],
                          'backtest_id' => $backtestId, 'origin' => 'search', 'origin_meta' => ['run_id' => 999, 'row_id' => 'x']];
    $req = Request::create('/backtesting/save', 'POST', ['save_data' => base64_encode(json_encode($payload))] + $body);
    $req->headers->set('Accept', 'application/json');
    $req->setLaravelSession($session);
    $req->setUserResolver(fn () => Auth::user());
    if ($attribute !== null) {
        $req->attributes->set(BacktestOrigin::REQUEST_ATTRIBUTE, $attribute);
    }
    app()->instance('request', $req);

    return app(BacktestingController::class)->saveBacktest($req, app(StrategyConfigSync::class))->getData(true);
};

DB::beginTransaction();
try {
    $tag = 'rq013-' . bin2hex(random_bytes(4));
    $dist = DB::select("SELECT coalesce(origin, 'no registrado') AS o, count(*) AS n FROM backtests GROUP BY 1 ORDER BY 1");
    echo '     origen en la base (antes de la prueba): ' . implode(', ', array_map(fn ($x) => "{$x->o} {$x->n}", $dist)) . "\n";

    // I1. Pantalla de backtesting; el navegador intenta declararse «search» (en el formulario y en el payload)
    $r = $save("{$tag}-a", ['origin' => 'search', 'origin_meta' => json_encode(['run_id' => 1, 'row_id' => 'r1'])]);
    $a = Backtest::find($r['backtest_id'] ?? 0);
    $check('I1: guardado desde la pantalla -> manual sin foto, aunque el navegador mande origin=search',
        $a !== null && $a->origin === 'manual' && $a->origin_meta === null, json_encode([$r['message'] ?? null, $a?->origin]));

    // I2. Desde la búsqueda (atributo interno)
    $foto = BacktestOrigin::fromSearch(77, 'r12', 'gain', 'robust', 'survivors', '2026-11-08T14:00:00+00:00');
    $r = $save("{$tag}-b", [], $foto);
    $b = Backtest::find($r['backtest_id'] ?? 0);
    $check('I2: desde la búsqueda -> search con run, fila, foco, modo y fecha', $b !== null && $b->origin === 'search'
        && ($b->origin_meta['run_id'] ?? null) === 77 && ($b->origin_meta['row_id'] ?? null) === 'r12'
        && ($b->origin_meta['focus'] ?? null) === 'gain' && ! empty($b->origin_meta['created_at']),
        json_encode([$b?->origin, $b?->origin_meta]));
    $check('I2: describe() de lo guardado', $b !== null
        && BacktestOrigin::describe($b->origin, $b->origin_meta) === 'Búsqueda #77 · fila r12 · foco gain · modo robust · 2026-11-08');

    // I3. Re-test: no cambia el origen en ninguno de los dos sentidos
    $r = $save("{$tag}-b", [], null, $b?->id);
    $b2 = Backtest::find($b?->id ?? 0);
    $check('I3: re-test del creado por búsqueda sin atributo -> sigue search con la misma foto', ! empty($r['success'])
        && $b2?->origin === 'search' && ($b2->origin_meta['run_id'] ?? null) === 77, json_encode([$r['message'] ?? null, $b2?->origin]));
    $r = $save("{$tag}-a", [], $foto, $a?->id);
    $a2 = Backtest::find($a?->id ?? 0);
    $check('I3: re-test del manual con atributo de búsqueda -> sigue manual', ! empty($r['success'])
        && $a2?->origin === 'manual' && $a2->origin_meta === null, json_encode([$r['message'] ?? null, $a2?->origin]));

    // I4. Restricción de la columna
    DB::statement('SAVEPOINT bad_origin');
    try {
        DB::table('backtests')->where('id', $a?->id ?? 0)->update(['origin' => 'browser']);
        $rejected = false;
    } catch (Throwable $e) {
        $rejected = str_contains($e->getMessage(), 'backtests_origin_check');
    }
    DB::statement('ROLLBACK TO SAVEPOINT bad_origin');
    $check('I4: la base rechaza un origen fuera de manual|search', $rejected);

    // I5. Los recuperados por la migración apuntan a una creación real de su búsqueda
    $bad = DB::select("SELECT b.id FROM backtests b
                        WHERE (b.origin_meta->>'recovered')::boolean IS TRUE
                          AND NOT EXISTS (SELECT 1 FROM param_search_runs r
                                           WHERE r.id = (b.origin_meta->>'run_id')::bigint
                                             AND r.results::jsonb->'created'->(b.origin_meta->>'row_id')->>'backtest_id' = b.id::text)");
    $rec = (int) DB::scalar("SELECT count(*) FROM backtests WHERE (origin_meta->>'recovered')::boolean IS TRUE");
    $check("I5: los {$rec} backtests recuperados coinciden con results.created de su búsqueda", $bad === [],
        json_encode(array_column($bad, 'id')));
} finally {
    DB::rollBack();
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

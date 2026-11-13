<?php
/**
 * Prueba forense p01 (REAL-04): una config Paper desactivada/borrada NO puede seguir abriendo posiciones Real.
 * TODO corre dentro de una transacción que se revierte al final: no deja cambios en la base.
 * No llama al motor Python ni a Bybit (Http::fake) y no encola nada (Queue::fake).
 *
 * Uso: cd <raíz del proyecto> && php tests/Forensic/real_config_gate_test.php
 * Antes del parche debe FALLAR en los casos A2/A4/C/D (reproduce el bug); después, todo PASS.
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
config(['session.driver' => 'array']);

use App\Http\Controllers\BacktestingController;
use App\Jobs\RealTradingAccountTickJob;
use App\Jobs\RealTradingTickJob;
use App\Models\Backtest;
use App\Models\RealStrategySubscription;
use App\Models\RealTrade;
use App\Services\StrategyConfigSync;
use Illuminate\Http\Client\Factory as HttpFactory;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    if (! $ok) {
        $fails++;
    }
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

$counts = fn () => [
    'subs'     => DB::table('real_strategy_subscriptions')->count(),
    'configs'  => DB::table('paper_strategy_configs')->count(),
    'backtest' => DB::table('backtests')->count(),
    'active_c' => DB::table('paper_strategy_configs')->where('active', true)->count(),
    'paused_s' => DB::table('real_strategy_subscriptions')->where('status', 'paused')->count(),
];
$before = $counts();

/** Ids de suscripción que el job de la cuenta enviaría al motor (null = no hubo pedido). */
$sentSubIds = function (int $accountId): ?array {
    Http::swap(new HttpFactory());
    Http::fake(['*' => Http::response(['status' => 'ok', 'results' => []], 200)]);
    (new RealTradingAccountTickJob($accountId))->handle();
    $recorded = Http::recorded();
    if ($recorded->isEmpty()) {
        return null;
    }
    [$request] = $recorded->last();
    $accounts = $request->data()['accounts'] ?? [];

    return collect($accounts[0]['subscriptions'] ?? [])->pluck('subscription_id')->map(fn ($v) => (int) $v)->all();
};
$cfgActive = fn (int $id, bool $v) => DB::table('paper_strategy_configs')->where('id', $id)->update(['active' => $v]);

DB::beginTransaction();
try {
    echo "=== 0. Estado REAL (antes de tocar nada): suscripciones activas con la config Paper apagada\n";
    $exposed = DB::table('real_strategy_subscriptions as s')
        ->join('paper_strategy_configs as c', 'c.id', '=', 's.paper_strategy_config_id')
        ->join('broker_accounts as a', 'a.id', '=', 's.broker_account_id')
        ->where('s.status', 'active')->where('c.active', false)->where('a.status', 'active')
        ->get(['s.id as sub', 's.broker_account_id as acc', 's.symbol as sym']);
    if ($exposed->isEmpty()) {
        echo "INFO  A0: no hay suscripción activa con config apagada en cuenta ACTIVA (nada que comprobar con el estado real)\n";
    }
    foreach ($exposed as $e) {
        $ids = $sentSubIds((int) $e->acc);
        $check("A0 estado real: sub #{$e->sub} ({$e->sym}, config APAGADA) NO viaja al motor",
            $ids === null || ! in_array((int) $e->sub, $ids, true), json_encode($ids));
    }

    echo "=== 0b. Fixture controlado (se fuerza dentro de la transacción: cuenta, suscripción y config activas)\n";
    $sub = RealStrategySubscription::query()
        ->whereNotNull('paper_strategy_config_id')
        ->whereHas('paperStrategyConfig')
        ->whereHas('brokerAccount')
        ->orderBy('id')
        ->first();
    if (! $sub) {
        echo "SKIP  no existe ninguna suscripción con config y cuenta para armar el fixture\n";
        DB::rollBack();
        exit(2);
    }
    $accountId = (int) $sub->broker_account_id;
    $subId     = (int) $sub->id;
    $cfgId     = (int) $sub->paper_strategy_config_id;
    DB::table('broker_accounts')->where('id', $accountId)->update(['status' => 'active']);
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'active']);
    DB::table('paper_strategy_configs')->where('id', $cfgId)->update(['active' => true]);
    echo "     suscripción #{$subId}, config #{$cfgId}, cuenta #{$accountId} (forzadas a activas SOLO dentro de la transacción)\n";

    echo "=== A. Payload que el job envía al motor\n";
    $ids = $sentSubIds($accountId);
    $check('A1 config activa -> la suscripción SÍ viaja', in_array($subId, $ids ?? [], true), json_encode($ids));

    $cfgActive($cfgId, false);
    $ids = $sentSubIds($accountId);
    $check('A2 config DESACTIVADA (stop-paper) -> la suscripción NO viaja',
        $ids === null || ! in_array($subId, $ids, true), json_encode($ids));

    // Control: con el filtro VIEJO (solo status de la suscripción) esa misma suscripción SÍ habría viajado
    $old = RealStrategySubscription::where('broker_account_id', $accountId)->where('status', 'active')
        ->pluck('id')->map(fn ($v) => (int) $v)->all();
    $check('A2-control: con el filtro VIEJO la suscripción SÍ habría viajado (el escenario reproduce el bug)', in_array($subId, $old, true));

    $cfgActive($cfgId, true);
    $ids = $sentSubIds($accountId);
    $check('A3 config reactivada -> vuelve a viajar', in_array($subId, $ids ?? [], true), json_encode($ids));

    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['paper_strategy_config_id' => null]);
    $ids = $sentSubIds($accountId);
    $check('A4 suscripción HUÉRFANA (config NULL) -> NO viaja', $ids === null || ! in_array($subId, $ids, true), json_encode($ids));
    $old = RealStrategySubscription::where('broker_account_id', $accountId)->where('status', 'active')
        ->pluck('id')->map(fn ($v) => (int) $v)->all();
    $check('A4-control: con el filtro VIEJO la suscripción huérfana SÍ habría viajado', in_array($subId, $old, true));
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['paper_strategy_config_id' => $cfgId]);

    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'paused']);
    $ids = $sentSubIds($accountId);
    $check('A5 suscripción pausada -> NO viaja (comportamiento previo intacto)', $ids === null || ! in_array($subId, $ids, true), json_encode($ids));
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'active']);

    echo "=== B. El scope coincide con la consulta cruda\n";
    $viaScope = RealStrategySubscription::runnable()->count();
    $viaSql = DB::table('real_strategy_subscriptions as s')
        ->join('paper_strategy_configs as c', 'c.id', '=', 's.paper_strategy_config_id')
        ->where('s.status', 'active')->where('c.active', true)->count();
    $check('B1 runnable() == SQL crudo', $viaScope === $viaSql, "scope={$viaScope} sql={$viaSql}");

    echo "=== C. El despachador no encola cuentas sin suscripciones operables\n";
    $accSubCfgs = DB::table('real_strategy_subscriptions')->where('broker_account_id', $accountId)
        ->whereNotNull('paper_strategy_config_id')->pluck('paper_strategy_config_id')->all();
    DB::table('paper_strategy_configs')->whereIn('id', $accSubCfgs)->update(['active' => false]);
    $hasOpen = RealTrade::where('broker_account_id', $accountId)->whereIn('status', ['open', 'pending_close'])->exists();
    if ($hasOpen) {
        echo "SKIP  C1: la cuenta tiene posiciones abiertas (se despacha igual para gestionarlas)\n";
    } else {
        Queue::fake();
        (new RealTradingTickJob())->handle();
        $pushed = Queue::pushed(RealTradingAccountTickJob::class, fn ($job) => $job->accountId === $accountId)->count();
        $check('C1 todas sus configs inactivas y sin posiciones -> la cuenta NO se despacha', $pushed === 0, "despachos={$pushed}");
    }
    DB::table('paper_strategy_configs')->whereIn('id', $accSubCfgs)->update(['active' => true]);

    echo "=== D. Borrar un backtest\n";
    $btId = DB::table('paper_strategy_configs')->where('id', $cfgId)->value('backtest_id');
    if (! $btId) {
        echo "SKIP  D: la config #{$cfgId} no tiene backtest asociado\n";
    } else {
        $btId = (int) $btId;
        $cfgIds = DB::table('paper_strategy_configs')->where('backtest_id', $btId)->pluck('id')->all();
        DB::table('paper_strategy_configs')->whereIn('id', $cfgIds)->update(['active' => false]); // que no esté "operando"
        // Reglas de borrado vigentes (p40b, CFG-05): bloquean los trades Real por reconciliar y los Paper abiertos
        $openReal = RealTrade::whereIn('paper_strategy_config_id', $cfgIds)
            ->whereIn('status', RealTrade::RECONCILE_STATUSES)->count();
        $openPaper = DB::table('paper_trades')->whereIn('paper_strategy_config_id', $cfgIds)->where('status', 'open')->count();
        $subsOfBt = DB::table('real_strategy_subscriptions')->whereIn('paper_strategy_config_id', $cfgIds)->pluck('id')->all();
        $statusBefore = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->pluck('status', 'id')->all();

        Gate::before(fn ($user = null) => true);
        $req = Request::create('/backtest/' . $btId, 'DELETE');
        $req->setLaravelSession(app('session.store'));
        app()->instance('request', $req);
        try {
            app(BacktestingController::class)->destroyBacktest(Backtest::findOrFail($btId), app(StrategyConfigSync::class));
            if ($openReal > 0 || $openPaper > 0) {
                $check('D1 con posición Real por reconciliar o Paper abierta NO se borra', Backtest::find($btId) !== null,
                       "real={$openReal} paper={$openPaper}");
                $statusAfter = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->pluck('status', 'id')->all();
                $check('D2 sus suscripciones siguen como estaban (no se tocó nada)', $statusAfter === $statusBefore);
            } else {
                $check('D1 sin posiciones abiertas -> el backtest se borra', Backtest::find($btId) === null);
                $left = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->where('status', 'active')->count();
                $check('D2 NINGUNA suscripción queda activa tras borrar (antes quedaban huérfanas activas)', $left === 0, "activas={$left}");
                $orph = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->whereNull('paper_strategy_config_id')->count();
                $check('D3 las suscripciones quedaron huérfanas pero PAUSADAS', $orph === count($subsOfBt), "huérfanas={$orph}/" . count($subsOfBt));
                $ids = $sentSubIds($accountId);
                $check('D4 el motor ya no recibe esas suscripciones', $ids === null || array_intersect($subsOfBt, $ids) === [], json_encode($ids));
            }
        } catch (\Throwable $e) {
            $check('D destroyBacktest sin excepción', false, get_class($e) . ': ' . substr($e->getMessage(), 0, 200));
        }
    }
} catch (\Throwable $e) {
    $fails++;
    echo 'FAIL  excepción inesperada: ' . get_class($e) . ': ' . $e->getMessage() . "\n";
} finally {
    DB::rollBack();
}

echo "=== Z. La base quedó intacta\n";
$after = $counts();
$check('Z1 conteos idénticos antes/después (rollback)', $before === $after, json_encode(['antes' => $before, 'despues' => $after]));

echo "\n" . ($fails === 0 ? 'TODO OK' : "FALLOS: {$fails}") . "\n";
exit($fails === 0 ? 0 : 1);

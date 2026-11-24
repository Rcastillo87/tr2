<?php
/**
 * D-63 (C5-13, integración: Laravel + base real): StrategyConfigSync::deleteStrategy.
 * - Control: el borrado anterior ($strategy->delete()) con configs falla por la FK RESTRICT (el error 500).
 * - Con una config activa en Paper no borra nada.
 * - Con las configs detenidas borra estrategia, backtests, búsquedas, configs, lo de Paper (también abiertas) y las
 *   suscripciones; deja la auditoría 'deleted' por config; no toca ninguna operación Real.
 * - Una suscripción con una operación Real viva no se borra: queda pausada y retire_on_close (se borra al cerrar).
 * TODO corre dentro de una transacción que se revierte: no deja cambios. No llama al motor ni a Bybit.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/strategy_delete_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\RealTrade;
use App\Models\Strategy;
use App\Services\StrategyConfigSync;
use App\Support\StrategyDeletionPlan;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

// La estrategia con menos configs que tenga al menos una config y una suscripción Real
$sid = DB::table('strategies as s')->join('backtests as b', 'b.strategy_id', '=', 's.id')
    ->join('paper_strategy_configs as c', 'c.backtest_id', '=', 'b.id')
    ->join('real_strategy_subscriptions as r', 'r.paper_strategy_config_id', '=', 'c.id')
    ->groupBy('s.id')->orderByRaw('count(DISTINCT c.id)')->orderBy('s.id')->value('s.id');
if (! $sid) {
    echo "SKIP  hace falta una estrategia con config y suscripción Real\n";
    exit(2);
}
$sync = app(StrategyConfigSync::class);
$bt = fn () => DB::table('backtests')->where('strategy_id', $sid)->pluck('id')->all();
$cfgIds = fn (array $b) => DB::table('paper_strategy_configs')->whereIn('backtest_id', $b)->pluck('id')->map(fn ($v) => (int) $v)->all();
$realBefore = DB::table('real_trades')->count();
$realSnapshot = DB::table('real_trades')->orderBy('id')->get(['id', 'status', 'net_pnl', 'size'])->toJson();

DB::beginTransaction();
try {
    $b = $bt();
    $ids = $cfgIds($b);
    $subs = DB::table('real_strategy_subscriptions')->whereIn('paper_strategy_config_id', $ids)->pluck('id')->map(fn ($v) => (int) $v)->all();
    printf("estrategia #%d: %d backtests, %d configs, %d suscripciones\n", $sid, count($b), count($ids), count($subs));
    // Fixture (solo en la transacción): ninguna operación Real viva en esas configs
    RealTrade::whereIn('paper_strategy_config_id', $ids)->whereIn('status', RealTrade::RECONCILE_STATUSES)->update(['status' => 'closed']);
    DB::table('paper_strategy_configs')->whereIn('id', [$ids[0]])->update(['active' => true]);

    // Control: el borrado anterior (directo) con configs choca con la FK RESTRICT → error 500
    DB::beginTransaction();
    $old = 'sin error';
    try { Strategy::whereKey($sid)->first()->delete(); } catch (Illuminate\Database\QueryException $e) { $old = 'QueryException'; }
    DB::rollBack();
    $check('I0 (control): el borrado anterior con configs falla en la base (lo que daba el error 500)', $old === 'QueryException', $old);

    $r = $sync->deleteStrategy(Strategy::find($sid), null);
    $check('I1: con una config activa en Paper no borra nada', $r['error'] === StrategyDeletionPlan::ACTIVE_PAPER
        && Strategy::whereKey($sid)->exists() && count($cfgIds($bt())) === count($ids), $r);

    DB::table('paper_strategy_configs')->whereIn('id', $ids)->update(['active' => false]);

    // I3 primero, en un punto de guardado: una suscripción con operación Real viva
    DB::beginTransaction();
    $tradeId = DB::table('real_trades')->orderBy('id')->value('id');
    if ($tradeId) {
        DB::table('real_trades')->where('id', $tradeId)->update(['subscription_id' => $subs[0], 'paper_strategy_config_id' => $ids[0], 'status' => 'open']);
        $r3 = $sync->deleteStrategy(Strategy::find($sid), null);
        $s3 = DB::table('real_strategy_subscriptions')->where('id', $subs[0])->first();
        $check('I3: suscripción con operación Real viva: no se borra, queda pausada y se borrará al cerrar',
            $r3['error'] === null && $s3 && $s3->status === 'paused' && (bool) $s3->retire_on_close
            && DB::table('real_trades')->where('id', $tradeId)->value('status') === 'open'
            && (str_contains((string) $r3['message'], 'se eliminará sola al cerrar')
                || str_contains((string) $r3['message'], 'se eliminarán solas al cerrar')),
            [$r3, $s3]);
    } else {
        echo "SKIP  I3: no hay operaciones Real para la prueba\n";
    }
    DB::rollBack();

    $paperOpen = DB::table('paper_trades')->whereIn('paper_strategy_config_id', $ids)->where('status', 'open')->count();
    $paperAll = DB::table('paper_trades')->whereIn('paper_strategy_config_id', $ids)->count();
    $searches = DB::table('param_search_runs')->where('strategy_id', $sid)->count();
    $active = DB::table('param_search_runs')->where('strategy_id', $sid)->whereIn('status', ['queued', 'running'])->count();
    $r = $sync->deleteStrategy(Strategy::find($sid), null);
    if ($active > 0) {
        $check('I2: con una búsqueda en curso no borra', $r['error'] !== null && Strategy::whereKey($sid)->exists(), $r);
    } else {
        $check('I2: con las configs detenidas borra la estrategia, sus backtests, búsquedas y configs',
            $r['error'] === null && ! Strategy::whereKey($sid)->exists() && DB::table('backtests')->whereIn('id', $b)->count() === 0
            && DB::table('paper_strategy_configs')->whereIn('id', $ids)->count() === 0
            && DB::table('param_search_runs')->where('strategy_id', $sid)->count() === 0, $r);
        $check("I2b: lo de Paper de esas configs se borra (también las abiertas: {$paperOpen} de {$paperAll})",
            DB::table('paper_trades')->whereIn('paper_strategy_config_id', $ids)->count() === 0
            && DB::table('paper_eval_state')->whereIn('paper_strategy_config_id', $ids)->count() === 0);
        $check('I2c: las suscripciones de esas configs se borran', DB::table('real_strategy_subscriptions')->whereIn('id', $subs)->count() === 0);
        $audit = DB::table('strategy_config_changes')->where('source', StrategyConfigSync::SOURCE_STRATEGY_DELETE)
            ->where('action', 'deleted')->whereRaw("(new_params->'deleted'->>'strategy_id')::bigint = ?", [$sid])->count();
        $check("I2d: auditoría 'deleted' por config", $audit === count($ids), [$audit, count($ids)]);
        $check('I2e: el mensaje dice lo borrado', str_starts_with((string) $r['message'], 'Estrategia ')
            && str_contains((string) $r['message'], count($ids) === 1 ? '1 configuración' : count($ids) . ' configuraciones'), $r['message']);
    }
    $check('I4: ninguna operación Real se borró', DB::table('real_trades')->count() === $realBefore);
} finally {
    DB::rollBack();
}
$check('I5: tras revertir, la base queda igual (estrategia y operaciones Real)', Strategy::whereKey($sid)->exists()
    && DB::table('real_trades')->orderBy('id')->get(['id', 'status', 'net_pnl', 'size'])->toJson() === $realSnapshot);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

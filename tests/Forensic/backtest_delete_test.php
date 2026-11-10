<?php
/**
 * CFG-05 (integración, Laravel + base real): StrategyConfigSync::deleteBacktest.
 * - Bloquea con un trade Paper abierto y con un trade Real 'orphaned' (el criterio anterior no lo hacía).
 * - Sin nada vivo: borra configs y backtest, pausa las suscripciones Real y deja auditoría 'deleted' por config.
 * TODO corre dentro de una transacción que se revierte: no deja cambios. No llama al motor ni a Bybit.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/backtest_delete_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Backtest;
use App\Models\BrokerAccount;
use App\Models\RealTrade;
use App\Services\StrategyConfigSync;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

$backtestId = DB::table('paper_strategy_configs')->whereNotNull('backtest_id')->orderBy('backtest_id')->value('backtest_id');
$acc = BrokerAccount::orderBy('id')->first();
if (! $backtestId || ! $acc) {
    echo "SKIP  hace falta un backtest con configs Paper y una cuenta broker\n";
    exit(2);
}
$sync = app(StrategyConfigSync::class);
$exists = fn () => Backtest::whereKey($backtestId)->exists();

/** El criterio anterior a p40 (solo config activa y Real open/pending_*), para el control. */
$oldAllows = function (array $ids): bool {
    return ! DB::table('paper_strategy_configs')->whereIn('id', $ids)->where('active', true)->exists()
        && ! RealTrade::whereIn('paper_strategy_config_id', $ids)->whereIn('status', ['open', 'pending_open', 'pending_close'])->exists();
};

DB::beginTransaction();
try {
    $ids = DB::table('paper_strategy_configs')->where('backtest_id', $backtestId)->pluck('id')->map(fn ($v) => (int) $v)->all();
    $cfg = $ids[0];
    // Fixture (solo dentro de la transacción): configs detenidas y sin nada vivo
    DB::table('paper_strategy_configs')->whereIn('id', $ids)->update(['active' => false]);
    DB::table('paper_trades')->whereIn('paper_strategy_config_id', $ids)->where('status', 'open')->update(['status' => 'closed']);
    RealTrade::whereIn('paper_strategy_config_id', $ids)->whereIn('status', RealTrade::RECONCILE_STATUSES)->update(['status' => 'closed']);
    echo "     backtest #{$backtestId} con configs " . implode(',', $ids) . " detenidas (solo dentro de la transacción)\n";

    // S1. Trade Paper abierto
    $p = DB::table('paper_trades')->insertGetId([
        'strategy' => 'TEST CFG-05', 'paper_strategy_config_id' => $cfg, 'symbol' => 'BTCUSDT', 'interval' => '60',
        'side' => 'long', 'entry_price' => 1, 'sl' => 1, 'tp' => 1, 'be_level' => 1, 'size' => 1,
        'entry_time' => now(), 'status' => 'open', 'created_at' => now(), 'updated_at' => now(),
    ]);
    $check('S1-control: el criterio anterior lo dejaba borrar con un trade Paper abierto', $oldAllows($ids));
    $msg = $sync->deleteBacktest(Backtest::find($backtestId), null);
    $check('S1: trade Paper abierto -> bloquea y no borra nada', is_string($msg) && str_contains($msg, 'Paper') && $exists(), (string) $msg);
    DB::table('paper_trades')->where('id', $p)->update(['status' => 'closed']);

    // S2. Trade Real orphaned
    $r = DB::table('real_trades')->insertGetId([
        'user_id' => $acc->user_id, 'broker_account_id' => $acc->id, 'paper_strategy_config_id' => $cfg,
        'strategy' => 'TEST CFG-05', 'symbol' => 'BTCUSDT', 'broker' => 'bybit', 'interval' => '60', 'side' => 'long',
        'entry_price' => 1, 'sl' => 1, 'tp' => 1, 'be_level' => 1, 'size' => 0.001, 'entry_time' => now(),
        'status' => 'orphaned', 'created_at' => now(), 'updated_at' => now(),
    ]);
    $check('S2-control: el criterio anterior lo dejaba borrar con un trade Real orphaned', $oldAllows($ids));
    $msg = $sync->deleteBacktest(Backtest::find($backtestId), null);
    $check('S2: trade Real orphaned -> bloquea y no borra nada', is_string($msg) && str_contains($msg, 'Real') && $exists(), (string) $msg);
    DB::table('real_trades')->where('id', $r)->update(['status' => 'closed']);

    // S3. Config activa (comportamiento previo)
    DB::table('paper_strategy_configs')->where('id', $cfg)->update(['active' => true]);
    $msg = $sync->deleteBacktest(Backtest::find($backtestId), null);
    $check('S3: config activa -> bloquea (como antes)', is_string($msg) && str_contains($msg, 'OPERANDO') && $exists(), (string) $msg);
    DB::table('paper_strategy_configs')->where('id', $cfg)->update(['active' => false]);

    // S4. Nada vivo: borra, pausa suscripciones y audita
    $subs = DB::table('real_strategy_subscriptions')->whereIn('paper_strategy_config_id', $ids)->pluck('id')->all();
    DB::table('real_strategy_subscriptions')->whereIn('id', $subs)->update(['status' => 'active']);
    // Las FK de strategy_config_changes son ON DELETE SET NULL: tras el borrado la fila se encuentra por su lápida
    $tomb = fn () => DB::table('strategy_config_changes')->where('action', 'deleted')
        ->where('source', StrategyConfigSync::SOURCE_DELETE)
        ->whereRaw("(new_params->'deleted'->>'backtest_id')::bigint = ?", [$backtestId])
        ->whereIn(DB::raw("(new_params->'deleted'->>'config_id')::bigint"), $ids);
    $before = $tomb()->count();
    $msg = $sync->deleteBacktest(Backtest::find($backtestId), null);
    $after = $tomb()->count();
    $check('S4: sin nada vivo -> borra el backtest y sus configs', $msg === null && ! $exists()
        && ! DB::table('paper_strategy_configs')->whereIn('id', $ids)->exists(), (string) $msg);
    $check("S4: una fila 'deleted' por config, con config_id y backtest_id en new_params", $after - $before === count($ids), ($after - $before) . '/' . count($ids));
    $kept = DB::table('strategy_config_changes')->where('action', 'deleted')->where('source', StrategyConfigSync::SOURCE_DELETE)
        ->whereRaw("(new_params->'deleted'->>'backtest_id')::bigint = ?", [$backtestId])->whereNotNull('old_params')->count();
    $check("S4: la fila 'deleted' conserva los parámetros de la config (old_params)", $kept === count($ids), (string) $kept);
    $active = DB::table('real_strategy_subscriptions')->whereIn('id', $subs)->where('status', 'active')->count();
    $check('S4: suscripciones Real de esas configs pausadas (' . count($subs) . ')', $active === 0, (string) $active);
} finally {
    DB::rollBack();
}

$check('S5: la transacción se revirtió (el backtest sigue y no quedan trades de prueba)',
    $exists() && DB::table('paper_trades')->where('strategy', 'TEST CFG-05')->count() === 0
    && DB::table('real_trades')->where('strategy', 'TEST CFG-05')->count() === 0);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

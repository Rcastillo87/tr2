<?php
/**
 * N-01 (integración, Laravel + base real): RealTradingReconcileJob envía al motor una cuenta PAUSADA y sin
 * suscripciones activas cuyo único trade está en 'pending_open'. Es el único camino que recupera una apertura
 * interrumpida (/v1/real/reconcile → _recover_pending_opens).
 * TODO corre dentro de una transacción que se revierte: no deja cambios. No llama al motor (Http::fake) ni a Bybit.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/real_reconcile_selector_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Jobs\RealTradingReconcileJob;
use App\Models\BrokerAccount;
use Illuminate\Http\Client\Factory as HttpFactory;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

/** Ids de cuenta que el job envía al motor ([] si no hubo pedido). Solo ids: nunca se imprimen credenciales. */
$sentAccounts = function (): array {
    Http::swap(new HttpFactory());
    Http::fake(['*' => Http::response(['status' => 'ok', 'results' => ['reconciled' => [], 'orphaned' => [], 'ok' => []]], 200)]);
    (new RealTradingReconcileJob())->handle();
    $recorded = Http::recorded();
    if ($recorded->isEmpty()) {
        return [];
    }
    [$request] = $recorded->last();

    return collect($request->data()['accounts'] ?? [])->pluck('id')->map(fn ($v) => (int) $v)->all();
};

/** El selector anterior a p34 (sin 'pending_open'), para el control. */
$oldSelector = fn (): array => BrokerAccount::query()
    ->where(fn ($q) => $q
        ->where(fn ($a) => $a->where('status', 'active')
            ->whereHas('subscriptions', fn ($s) => $s->where('status', 'active')))
        ->orWhereExists(fn ($e) => $e->selectRaw('1')->from('real_trades')
            ->whereColumn('real_trades.broker_account_id', 'broker_accounts.id')
            ->whereIn('real_trades.status', ['open', 'pending_close', 'orphaned'])))
    ->pluck('id')->map(fn ($v) => (int) $v)->all();

$acc = BrokerAccount::orderBy('id')->first();
if (! $acc) {
    echo "SKIP  no hay cuentas broker para armar el fixture\n";
    exit(2);
}
$accId = (int) $acc->id;

DB::beginTransaction();
try {
    // Fixture (solo dentro de la transacción): cuenta pausada, sin suscripciones activas y sin trades por reconciliar
    DB::table('broker_accounts')->where('id', $accId)->update(['status' => 'paused']);
    DB::table('real_strategy_subscriptions')->where('broker_account_id', $accId)->update(['status' => 'paused']);
    DB::table('real_trades')->where('broker_account_id', $accId)
        ->whereNotIn('status', ['closed', 'failed', 'ignored', 'error'])->update(['status' => 'closed']);
    echo "     cuenta #{$accId} pausada, sin suscripciones activas ni trades abiertos (solo dentro de la transacción)\n";

    $check('S1: pausada y sin nada que reconciliar -> no viaja', ! in_array($accId, $sentAccounts(), true));

    $tid = DB::table('real_trades')->insertGetId([
        'user_id' => $acc->user_id, 'broker_account_id' => $accId, 'strategy' => 'TEST N-01', 'symbol' => 'BTCUSDT',
        'broker' => 'bybit', 'interval' => '60', 'side' => 'long', 'entry_price' => 1, 'sl' => 1, 'tp' => 1,
        'be_level' => 1, 'size' => 0.001, 'entry_time' => now(), 'status' => 'pending_open',
        'created_at' => now()->subMinutes(30), 'updated_at' => now(),
    ]);
    echo "     trade de prueba #{$tid} en pending_open (se revierte)\n";

    $check('S2: pausada con un pending_open -> SÍ viaja a la reconciliación', in_array($accId, $sentAccounts(), true));
    $check('S2-control: el selector anterior NO la enviaba (reproduce N-01)', ! in_array($accId, $oldSelector(), true));

    DB::table('real_trades')->where('id', $tid)->update(['status' => 'orphaned']);
    $check('S3: con un orphaned -> viaja (comportamiento previo intacto)', in_array($accId, $sentAccounts(), true));

    DB::table('real_trades')->where('id', $tid)->update(['status' => 'failed']);
    $check('S4: con solo un trade final (failed) -> no viaja', ! in_array($accId, $sentAccounts(), true));
} finally {
    DB::rollBack();
}

$left = DB::table('real_trades')->where('strategy', 'TEST N-01')->count();
$check('S5: la transacción se revirtió (sin trades de prueba en la base)', $left === 0, (string) $left);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

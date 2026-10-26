<?php
/**
 * Prueba forense del paso 6b. TODO corre dentro de una transacción que se
 * revierte al final: no deja ningún cambio en la base de datos.
 * Uso: cd <raíz del proyecto> && php /root/patches/forensic_6b.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BacktestingController;
use App\Models\Backtest;
use App\Models\PaperStrategyConfig;
use App\Services\StrategyConfigSync;
use Illuminate\Support\Facades\DB;

const BT_LIVE  = 75;   // 4 monedas, 24 meses, activo
const BT_SHORT = 39;   // 12 meses

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    if (! $ok) {
        $fails++;
    }
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};
$snapshot = fn () => [
    'configs' => DB::table('paper_strategy_configs')->orderBy('id')->get(['id', 'symbol', 'active', 'params', 'display_name'])->toJson(),
    'audit'   => DB::table('strategy_config_changes')->count(),
    'subs'    => DB::table('real_strategy_subscriptions')->count(),
];

$before = $snapshot();
$sync = app(StrategyConfigSync::class);
$sign = (new ReflectionClass(BacktestingController::class))->getMethod('saveSignatureFields');
$block = (new ReflectionClass(BacktestingController::class))->getMethod('liveBlockReason');
$ctrl = app(BacktestingController::class);

echo "=== 1. Firma HMAC (viaje por el navegador)\n";
$bt = Backtest::findOrFail(BT_LIVE);
$payload = [
    'strategy_id' => (string) $bt->strategy_id, 'symbols' => $bt->symbols, 'interval' => $bt->interval,
    'months' => $bt->months, 'config_params' => $bt->config_params,
];
$payload['signed_total_trades'] = 111;
$payload['signature'] = StrategyConfigSync::sign($sign->invoke(null, $payload, 111));
$payload['backtest_id'] = (string) BT_LIVE;          // lo agrega el blade
$payload['metrics'] = ['total_trades' => 999];       // el blade las recalcula
$roundTrip = json_decode(base64_decode(base64_encode(json_encode($payload))), true);
$check('firma válida tras round-trip', StrategyConfigSync::verify(
    $sign->invoke(null, $roundTrip, (int) $roundTrip['signed_total_trades']), $roundTrip['signature']));
$tampered = $roundTrip;
$tampered['config_params']['sl_pct'] = 0.1;
$check('detecta parámetro alterado', ! StrategyConfigSync::verify(
    $sign->invoke(null, $tampered, (int) $tampered['signed_total_trades']), $tampered['signature']));
$check('detecta total_trades alterado', ! StrategyConfigSync::verify(
    $sign->invoke(null, $roundTrip, 5000), $roundTrip['signature']));

echo "=== 2. Reglas de aptitud para vivo\n";
$check('bt ' . BT_SHORT . ' (12 meses) apto: el usuario decide', $block->invoke($ctrl, Backtest::findOrFail(BT_SHORT), 59) === null);
$check('bt ' . BT_LIVE . ' con 0 trades bloqueado', $block->invoke($ctrl, $bt, 0) !== null);
$check('bt ' . BT_LIVE . ' apto', $block->invoke($ctrl, $bt, 111) === null);

DB::beginTransaction();
try {
    echo "=== 3. Sync sin cambios (debe ser no-op)\n";
    $activeBefore = PaperStrategyConfig::where('backtest_id', BT_LIVE)->pluck('active', 'symbol')->all();
    $r = $sync->syncFromBacktest(Backtest::findOrFail(BT_LIVE), 'forensic', null);
    $check('4 monedas sin cambios de parámetros', count($r['unchanged']) === 4 && $r['updated'] === [] && $r['created'] === [],
        json_encode($r));
    $check('estado activo preservado', PaperStrategyConfig::where('backtest_id', BT_LIVE)->pluck('active', 'symbol')->all() === $activeBefore);
    $check('params limpios (sin symbol/start_date)', PaperStrategyConfig::where('backtest_id', BT_LIVE)->get()
        ->every(fn ($c) => ! array_key_exists('symbol', $c->params) && ! array_key_exists('start_date', $c->params)));
    $check('strategy_code conservado', PaperStrategyConfig::where('backtest_id', BT_LIVE)->get()
        ->every(fn ($c) => ! empty($c->params['strategy_code'])));

    echo "=== 4. Cambio de parámetro (sl_pct) se propaga a las 4\n";
    $bt = Backtest::findOrFail(BT_LIVE);
    $params = $bt->config_params;
    $params['sl_pct'] = (float) $params['sl_pct'] + 0.7;
    $bt->config_params = $params;
    $auditBefore = DB::table('strategy_config_changes')->count();
    $r = $sync->syncFromBacktest($bt, 'forensic', null);
    $check('4 actualizadas solo en sl_pct', count($r['updated']) === 4
        && collect($r['updated'])->every(fn ($k) => $k === ['sl_pct']), json_encode($r['updated']));
    $check('4 filas de auditoría', DB::table('strategy_config_changes')->count() - $auditBefore === 4);
    $check('Paper/Real leen el nuevo sl_pct', PaperStrategyConfig::where('backtest_id', BT_LIVE)->get()
        ->every(fn ($c) => (float) $c->params['sl_pct'] === (float) $params['sl_pct']));

    echo "=== 5. Re-test sin SUI y con ETH\n";
    $bt->symbols = ['BTCUSDT', 'LINKUSDT', 'SOLUSDT', 'ETHUSDT'];
    $r = $sync->syncFromBacktest($bt, 'forensic', null);
    $check('SUI desactivada (no borrada)', $r['deactivated'] === ['SUIUSDT']
        && PaperStrategyConfig::where('backtest_id', BT_LIVE)->where('symbol', 'SUIUSDT')->where('active', false)->exists());
    $eth = PaperStrategyConfig::where('backtest_id', BT_LIVE)->where('symbol', 'ETHUSDT')->first();
    $check('ETH creada activa en Paper', $r['created'] === ['ETHUSDT'] && $eth?->active === true, $eth?->display_name ?? 'no creada');
    $check('ETH con suscripción por cuenta broker activa', DB::table('real_strategy_subscriptions')->where('paper_strategy_config_id', $eth?->id)->count()
        === DB::table('broker_accounts')->where('status', 'active')->count());

    echo "=== 6. Repetir el mismo sync (idempotente)\n";
    $r = $sync->syncFromBacktest($bt, 'forensic', null);
    $check('sin cambios ni duplicados', $r['created'] === [] && $r['updated'] === [] && count($r['unchanged']) === 4, json_encode($r));
    $check('UNIQUE (backtest_id, symbol) intacto', DB::table('paper_strategy_configs')->select('backtest_id', 'symbol')
        ->groupBy('backtest_id', 'symbol')->havingRaw('count(*) > 1')->count() === 0);

    echo "=== 7. Detener estrategia\n";
    $n = $sync->deactivateBacktest($bt);
    $check('todas las configs del bt desactivadas', $n === 4
        && ! PaperStrategyConfig::where('backtest_id', BT_LIVE)->where('active', true)->exists(), "desactivadas={$n}");
} catch (Throwable $e) {
    $check('excepción inesperada', false, get_class($e) . ': ' . $e->getMessage());
} finally {
    DB::rollBack();
}

echo "=== 8. Rollback: la base quedó exactamente igual\n";
$check('sin cambios persistidos', $snapshot() === $before);

echo $fails === 0 ? "\nRESULTADO: TODO OK\n" : "\nRESULTADO: {$fails} FALLO(S)\n";
exit($fails === 0 ? 0 : 1);

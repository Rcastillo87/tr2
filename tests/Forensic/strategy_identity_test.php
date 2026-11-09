<?php
/**
 * N-09 (integración, Laravel + base real): la identidad de una config es su id, no su etiqueta.
 * - Dos configs con la MISMA etiqueta: renombrar una NO le pasa el trade abierto de la otra; el de legado (sin
 *   config_id) sí se reasigna por nombre, como antes.
 * - Strategy::hasActivePaper(): por el strategy_id del backtest; una estrategia cuyo nombre es prefijo de otra no
 *   hereda sus configs activas.
 * TODO corre dentro de una transacción que se revierte: no deja cambios. No llama al motor ni a Bybit.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/strategy_identity_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\PaperStrategyConfig;
use App\Models\Strategy;
use App\Services\StrategyConfigSync;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

$configs = PaperStrategyConfig::orderBy('id')->limit(2)->get();
if ($configs->count() < 2) {
    echo "SKIP  hacen falta 2 configs Paper para armar el fixture\n";
    exit(2);
}
[$a, $b] = [$configs[0], $configs[1]];
$label = 'TEST N-09 — ETHUSDT H4';

$trade = fn (?int $configId, string $strategy) => DB::table('paper_trades')->insertGetId([
    'strategy' => $strategy, 'paper_strategy_config_id' => $configId, 'symbol' => 'ETHUSDT', 'interval' => '240',
    'side' => 'long', 'entry_price' => 1, 'sl' => 1, 'tp' => 1, 'be_level' => 1, 'size' => 1,
    'entry_time' => now(), 'status' => 'open', 'created_at' => now(), 'updated_at' => now(),
]);

DB::beginTransaction();
try {
    // ── Renombrar con etiqueta compartida ──
    DB::table('paper_strategy_configs')->whereIn('id', [$a->id, $b->id])->update(['display_name' => $label]);
    $tB = $trade($b->id, $label);
    $tL = $trade(null, $label);
    echo "     configs #{$a->id} y #{$b->id} con la misma etiqueta; trade #{$tB} de #{$b->id} y #{$tL} de legado (se revierte)\n";

    // Control: el criterio anterior tomaba el trade de la otra config
    $oldHits = DB::table('paper_trades')->where('status', 'open')
        ->where(fn ($q) => $q->where('paper_strategy_config_id', $a->id)->orWhere('strategy', $label))
        ->whereIn('id', [$tB])->count();
    $check('S1-control: el criterio anterior tomaba el trade de la otra config (reproduce N-09)', $oldHits === 1);

    $cfgA = PaperStrategyConfig::find($a->id);
    $cfgA->display_name = 'TEST N-09 renombrada — ETHUSDT H4';
    $m = new ReflectionMethod(StrategyConfigSync::class, 'renameReferences');
    $m->invoke(app(StrategyConfigSync::class), $cfgA, $label);

    $rowB = DB::table('paper_trades')->where('id', $tB)->first();
    $rowL = DB::table('paper_trades')->where('id', $tL)->first();
    $check("S1: el trade de #{$b->id} sigue siendo de #{$b->id} con su etiqueta",
        (int) $rowB->paper_strategy_config_id === (int) $b->id && $rowB->strategy === $label,
        "config={$rowB->paper_strategy_config_id} strategy={$rowB->strategy}");
    $check("S2: el trade de legado (sin config_id) pasa a #{$a->id} con la etiqueta nueva",
        (int) $rowL->paper_strategy_config_id === (int) $a->id && $rowL->strategy === $cfgA->display_name,
        "config={$rowL->paper_strategy_config_id} strategy={$rowL->strategy}");

    // ── hasActivePaper por id ──
    $active = PaperStrategyConfig::where('active', true)->whereNotNull('backtest_id')->with('backtest.strategy')->get()
        ->first(fn ($c) => $c->backtest?->strategy && mb_strlen($c->backtest->strategy->name) > 1);
    if (! $active) {
        echo "SKIP  S3-S4: no hay una config activa con backtest y estrategia\n";
    } else {
        $owner = $active->backtest->strategy;
        $check("S3: «{$owner->name}» tiene una config activa (#{$active->id})", $owner->hasActivePaper());
        $prefix = Strategy::create(['name' => mb_substr($owner->name, 0, -1), 'code' => '', 'active' => false]);
        $oldBlocks = PaperStrategyConfig::where('active', true)->where('display_name', 'like', $prefix->name . '%')->exists();
        $check("S4-control: el criterio anterior bloqueaba borrar «{$prefix->name}» (reproduce N-09)", $oldBlocks);
        $check("S4: «{$prefix->name}» (sin backtests) no hereda configs activas de «{$owner->name}»", ! $prefix->hasActivePaper());
    }
} finally {
    DB::rollBack();
}

$left = DB::table('paper_trades')->where('strategy', 'like', 'TEST N-09%')->count()
    + DB::table('paper_strategy_configs')->where('display_name', 'like', 'TEST N-09%')->count();
$check('S5: la transacción se revirtió (sin restos de prueba)', $left === 0, (string) $left);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

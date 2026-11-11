<?php
/**
 * RQ-01.5 (integración, Laravel + base real): sección «Diagnóstico» de Paper Trading.
 * - Una fila por config activa, con el motivo real de paper_eval_state.
 * - Con datos de prueba (transacción revertida): una señal anulada muestra qué filtro la anuló; una config sin
 *   evaluar hace más de 15 min sale como problema y primero; el historial de 24 h se suma por motivo.
 * - La pantalla de Paper renderiza con la sección.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/paper_diagnostics_screen_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\PaperTradingController;
use App\Models\User;
use App\Services\PaperDiagnostics;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails) {
    $fails += $ok ? 0 : 1;
    echo ($ok ? 'PASS ' : 'FAIL ') . $name . ($detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '') . "\n";
};

DB::beginTransaction();
try {
    $svc = app(PaperDiagnostics::class);
    $active = DB::table('paper_strategy_configs')->where('active', true)->orderBy('id')->pluck('id')->map(fn ($v) => (int) $v)->all();
    $o = $svc->overview();
    $ids = array_column($o['rows'], 'id');
    sort($ids);
    $check('R1: una fila por config activa (' . count($active) . ')', $ids === $active, [$ids, $active]);
    $state = DB::table('paper_eval_state')->pluck('code', 'paper_strategy_config_id');
    $bad = array_values(array_filter($o['rows'], fn ($r) => $r['group'] !== 'stale' && $r['code'] !== ($state[$r['id']] ?? null)));
    $check('R2: el motivo de cada fila es el de paper_eval_state', $bad === [], array_slice($bad, 0, 2));
    echo '     hoy: ' . json_encode($o['counts'], JSON_UNESCAPED_UNICODE) . "\n";

    if (count($active) < 2) {
        echo "     (menos de 2 configs activas: R3-R5 no aplican)\n";
    } else {
        [$a, $b] = $active;
        $now = DB::scalar("SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')");
        $upsert = fn (int $id, string $at, string $code, ?array $filters) => DB::statement(
            "INSERT INTO paper_eval_state (paper_strategy_config_id, evaluated_at, code, detail, regime, signal, filters, candle_time, last_bar_time, bars)
             VALUES (?, ?::timestamp, ?, 'prueba', 'TRENDING', 0, ?::jsonb, ?::timestamp, ?::timestamp, 120)
             ON CONFLICT (paper_strategy_config_id) DO UPDATE SET evaluated_at = EXCLUDED.evaluated_at, code = EXCLUDED.code,
                 detail = EXCLUDED.detail, filters = EXCLUDED.filters", [$id, $at, $code, $filters === null ? null : json_encode($filters), $at, $at]);
        $upsert($a, $now, 'filter_blocked', [['step' => 'estrategia', 'signal' => 1], ['step' => 'volume_filter', 'signal' => 1],
                                             ['step' => 'weekend_filter', 'signal' => 0], ['step' => 'btc_trend_filter', 'signal' => 0]]);
        $upsert($b, DB::scalar("SELECT to_char((now() AT TIME ZONE 'UTC') - interval '2 hours', 'YYYY-MM-DD HH24:MI:SS')"), 'no_signal', null);
        foreach ([['no_signal', 7], ['regime_blocked', 3]] as $i => [$code, $n]) {
            DB::statement("INSERT INTO paper_eval_log (paper_strategy_config_id, bucket_time, code, detail, first_at, last_at, evaluations)
                           VALUES (?, ?::timestamp - interval '1 hour' * ?, ?, 'prueba', ?::timestamp, ?::timestamp, ?)
                           ON CONFLICT (paper_strategy_config_id, bucket_time, code) DO UPDATE SET evaluations = paper_eval_log.evaluations + EXCLUDED.evaluations",
                [$a, $now, 100 + $i, $code, $now, $now, $n]);
        }
        $o = $svc->overview();
        $rows = collect($o['rows'])->keyBy('id');
        $ra = $rows[$a];
        $check('R3: señal anulada -> grupo «Señal anulada» y la traza marca weekend como el que anuló',
            $ra['group'] === 'filtered' && collect($ra['trace'])->where('kills', true)->pluck('step')->all() === ['weekend'], $ra['trace']);
        $check('R4: sin evaluar hace 2 h -> problema «Sin evaluar desde …», entre las primeras filas', $rows[$b]['group'] === 'stale'
            && str_starts_with($rows[$b]['label'], 'Sin evaluar desde') && in_array($o['rows'][0]['group'], ['stale', 'missing'], true) && $o['counts']['problem'] >= 1,
            [$rows[$b]['label'], $o['rows'][0]['id']]);
        $day = collect($ra['day'])->mapWithKeys(fn ($x) => [$x[0] => $x[1]]);
        $check('R5: últimas 24 h suma el historial por motivo (incluye los de prueba)', ($day['Sin señal'] ?? 0) >= 7
            && ($day['Bloqueada por régimen'] ?? 0) >= 3, $ra['day']);
    }

    $admin = User::where('role', 'admin')->orderBy('id')->first();
    Auth::login($admin);
    view()->share('errors', new Illuminate\Support\ViewErrorBag());
    $req = Request::create('/paper-trading', 'GET');
    $req->setUserResolver(fn () => Auth::user());
    app()->instance('request', $req);
    try {
        $html = (string) app(PaperTradingController::class)->index($req)->render();
    } catch (Throwable $e) {
        $html = 'EXCEPCION: ' . $e->getMessage() . ' @ ' . basename($e->getFile()) . ':' . $e->getLine();
    }
    $check('P1: Paper Trading renderiza con la sección de diagnóstico, la traza y el aviso de problema', ! str_starts_with($html, 'EXCEPCION')
        && str_contains($html, 'Diagnóstico (') && (count($active) < 2 || (str_contains($html, 'weekend · 0 · anuló') && str_contains($html, 'Sin evaluar desde'))),
        substr($html, 0, 200));
} finally {
    DB::rollBack();
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * Fase 2 · tramo Laravel → Python. Llama al controlador real (BacktestingController::executeAjax) con
 * valores "raros" en todos los campos del formulario, intercepta el POST a Python con Http::fake
 * (Python NO se ejecuta) y verifica, campo por campo, que el payload enviado al motor es exactamente
 * lo que el usuario escribió. También verifica que lo que se guardaría (save_payload.config_params) es
 * ese mismo payload. Guarda el payload capturado para la segunda parte (Python).
 * Solo lectura: no escribe en la base de datos.
 *
 * Uso (desde la raíz del proyecto): php tests/Forensic/backtest_payload_chain_test.php [salida.json]
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BacktestingController;
use App\Models\Strategy;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Http;

$out = $argv[1] ?? '/tmp/tr2_bt_payload.json';
$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

$user = User::query()->where('role', 'admin')->orderBy('id')->first();
$strategy = Strategy::query()->orderBy('id')->first();
if (! $user || ! $strategy) {
    fwrite(STDERR, "Se necesita un usuario admin y al menos una estrategia.\n");
    exit(2);
}
Auth::setUser($user);
$session = app('session')->driver();
$session->start();

// Respuesta falsa de Python: solo para que el controlador termine; lo que se prueba es lo ENVIADO.
Http::fake([
    '*/v1/backtest/run' => Http::response(['status' => 'ok', 'warnings' => [], 'result' => [
        'aggregate_metrics' => ['total_trades' => 3, 'winning_trades' => 2, 'win_rate' => 66.67, 'total_return_pct' => 1.2,
            'sharpe_ratio' => 1.1, 'profit_factor' => 1.5, 'max_drawdown_pct' => 2.0, 'gross_profit' => 30.0, 'gross_loss' => 20.0,
            'total_pnl' => 10.0],
        'monthly_breakdown' => [], 'passed' => false, 'trades' => [],
    ]], 200),
]);

$config = ['fast_period' => 7, 'zone_bars' => 3, 'sl_pct' => 9.9];
$form = [
    'strategy_id' => (string) $strategy->id, 'backtest_id' => '',
    'symbols' => ['ETHUSDT', 'SOLUSDT'], 'interval' => '15', 'months' => '18',
    'initial_balance' => '4321', 'sl_pct' => '1.37', 'tp_pct' => '2.91', 'risk_per_trade_pct' => '0.73',
    'commission_pct' => '0.061', 'slippage_pct' => '0.07',
    'strategy_config_override' => json_encode($config),
    'regime_filter' => '1', 'regime_adx_trending' => '27', 'regime_adx_ranging' => '17', 'regime_ambiguous_as' => 'ignorar',
    'volume_filter' => '1', 'volume_filter_period' => '33', 'volume_filter_mult' => '1.7', 'macro_trend_filter' => '1',
    'btc_trend_filter' => '1', 'allowed_regimes_present' => '1', 'allowed_regimes' => ['VOLATILE', 'RANGING'],
    'max_duration' => '41', 'be_pct' => '0.9', 'trailing_mode' => 'atr', 'trailing_distance_pct' => '1.3',
    'trailing_atr_mult' => '2.6', 'trailing_activation_buffer_pct' => '0.45',
    'max_duration_profit' => '1', 'close_on_opposite' => '1',
];

function runAjax(array $form): array
{
    $req = Request::create('/backtesting/execute-ajax', 'POST', $form);
    $req->setLaravelSession(app('session')->driver());
    $req->setUserResolver(fn () => Auth::user());
    app()->instance('request', $req);
    try {
        $resp = app(BacktestingController::class)->executeAjax($req);
    } catch (Throwable $e) {
        return ['success' => false, 'error' => 'excepción: ' . $e->getMessage()];
    }
    return json_decode($resp->getContent(), true) ?? [];
}

function pythonCalls(): array
{
    $calls = [];
    foreach (Http::recorded() as [$request]) {
        if (str_contains($request->url(), '/v1/backtest/run')) {
            $calls[] = $request->data();
        }
    }
    return $calls;
}

// ── 1) Todo activado ─────────────────────────────────────────────────────────
$resp = runAjax($form);
$sent = pythonCalls();
$check('el controlador respondió sin error', ($resp['success'] ?? false) === true, $resp['error'] ?? '');
$check('un POST a Python por moneda (2)', count($sent) === 2, (string) count($sent));
$p = $sent[0] ?? [];

$expected = [
    'symbol' => 'ETHUSDT', 'interval' => '15', 'initial_balance' => 4321.0, 'sl_pct' => 1.37, 'tp_pct' => 2.91,
    'risk_per_trade_pct' => 0.73, 'commission_pct' => 0.061, 'slippage_pct' => 0.07, 'regime_filter' => true,
    'regime_adx_trending' => 27.0, 'regime_adx_ranging' => 17.0, 'regime_ambiguous_as' => 'NO_OPERAR',
    'volume_filter' => true, 'volume_filter_period' => 33, 'volume_filter_mult' => 1.7, 'macro_trend_filter' => true,
    'btc_trend_filter' => true, 'allowed_regimes' => ['RANGING', 'VOLATILE'],
    'max_duration' => 41, 'be_pct' => 0.9, 'trailing_mode' => 'atr', 'trailing_distance_pct' => 1.3,
    'trailing_atr_mult' => 2.6, 'trailing_activation_buffer_pct' => 0.45, 'max_duration_profit' => true,
    'close_on_opposite' => true, 'strategy_config' => $config, 'strategy_code' => $strategy->code,
    'strategy' => $strategy->name,
];
foreach ($expected as $k => $v) {
    $got = $p[$k] ?? '<<ausente>>';
    $same = is_float($v) ? (is_numeric($got) && abs((float) $got - $v) < 1e-12) : $got === $v;
    $check("payload.$k", $same, $same ? '' : 'enviado=' . json_encode($got) . ' esperado=' . json_encode($v));
}
$check('payload segunda moneda = SOLUSDT con los mismos parámetros',
    ($sent[1]['symbol'] ?? '') === 'SOLUSDT' && array_diff_key($sent[1] ?? [], ['symbol' => 1]) == array_diff_key($p, ['symbol' => 1]));

// Fechas: 18 meses completos que terminan el último día del mes anterior
$end = now()->subMonthNoOverflow()->endOfMonth();
$start = $end->copy()->subMonths(17)->startOfMonth();
$check('rango de fechas = 18 meses completos', ($p['start_date'] ?? '') === $start->format('Y-m-d') && ($p['end_date'] ?? '') === $end->format('Y-m-d'),
    ($p['start_date'] ?? '?') . ' → ' . ($p['end_date'] ?? '?'));

// Campos que viajan y NO vienen del formulario (valores fijos del controlador)
$extra = array_diff(array_keys($p), array_keys($expected), ['start_date', 'end_date']);
echo "INFO  campos fijados por el controlador (no están en la UI): " . implode(', ', array_map(fn ($k) => "$k=" . json_encode($p[$k]), $extra)) . "\n";

// Lo que se guardaría en el historial (y luego usa paper/real) es exactamente lo ejecutado
$saved = null;
if (preg_match('/name="save_data" value="([^"]*)"/', $resp['html'] ?? '', $m)) {
    $saved = json_decode(base64_decode(html_entity_decode($m[1], ENT_QUOTES)), true)['config_params'] ?? null;
}
$check('config_params que se guardaría == payload ejecutado', $saved !== null && $saved == $p,
    $saved === null ? 'save_data no encontrado en el HTML de resultados' : '');

file_put_contents($out, json_encode($p, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
echo "INFO  payload capturado en $out (para la parte Python)\n";

// ── 2) Todo apagado: checkboxes sin marcar deben viajar como false, trailing 'none' como null ─────
Http::fake(['*/v1/backtest/run' => Http::response(['status' => 'ok', 'warnings' => [], 'result' => [
    'aggregate_metrics' => ['total_trades' => 1, 'winning_trades' => 1], 'monthly_breakdown' => []]], 200)]);
$off = $form;
foreach (['regime_filter', 'volume_filter', 'macro_trend_filter', 'btc_trend_filter', 'max_duration_profit', 'close_on_opposite'] as $k) {
    unset($off[$k]);
}
$off['trailing_mode'] = 'none';
$off['regime_ambiguous_as'] = 'TRENDING';
$off['symbols'] = ['ETHUSDT'];
$before = count(pythonCalls());
runAjax($off);
$q = array_slice(pythonCalls(), $before)[0] ?? [];
foreach (['regime_filter', 'volume_filter', 'macro_trend_filter', 'btc_trend_filter', 'max_duration_profit', 'close_on_opposite'] as $k) {
    $check("apagado: $k = false", ($q[$k] ?? null) === false, json_encode($q[$k] ?? '<<ausente>>'));
}
$check('apagado: trailing_mode none → null', array_key_exists('trailing_mode', $q) && $q['trailing_mode'] === null, json_encode($q['trailing_mode'] ?? '<<ausente>>'));
$check('ambiguo TRENDING → TRENDING', ($q['regime_ambiguous_as'] ?? '') === 'TRENDING', json_encode($q['regime_ambiguous_as'] ?? ''));

// ── 2b) Regímenes permitidos: ninguno con el filtro activo -> error; sin el bloque (búsqueda) -> los de la estrategia ─
Http::fake(['*/v1/backtest/run' => Http::response(['status' => 'ok', 'warnings' => [], 'result' => [
    'aggregate_metrics' => ['total_trades' => 1, 'winning_trades' => 1], 'monthly_breakdown' => []]], 200)]);
$none = $form;
$none['symbols'] = ['ETHUSDT'];
unset($none['allowed_regimes']);
$before = count(pythonCalls());
$r = runAjax($none);
$check('régimen activo sin ningún régimen elegido -> error y no llama a Python',
    ($r['success'] ?? true) === false && count(pythonCalls()) === $before, $r['error'] ?? 'se ejecutó');
$noBlock = $form;
$noBlock['symbols'] = ['ETHUSDT'];
unset($noBlock['allowed_regimes'], $noBlock['allowed_regimes_present']);
$before = count(pythonCalls());
runAjax($noBlock);
$q2 = array_slice(pythonCalls(), $before)[0] ?? [];
$check('sin el bloque de regímenes: allowed_regimes no viaja (= los de la estrategia)', $q2 !== [] && ! array_key_exists('allowed_regimes', $q2),
    json_encode($q2['allowed_regimes'] ?? '<<ausente>>'));
$none['regime_filter'] = null;
unset($none['regime_filter']);
$before = count(pythonCalls());
runAjax($none);
$q3 = array_slice(pythonCalls(), $before)[0] ?? [];
$check('régimen apagado y ninguno elegido: corre y envía lista vacía', ($q3['allowed_regimes'] ?? null) === [],
    json_encode($q3['allowed_regimes'] ?? '<<ausente>>'));

// ── 3) JSON de parámetros inválido: no debe ejecutarse en silencio con otra configuración ─────
Http::fake(['*/v1/backtest/run' => Http::response(['status' => 'ok', 'warnings' => [], 'result' => [
    'aggregate_metrics' => ['total_trades' => 1, 'winning_trades' => 1], 'monthly_breakdown' => []]], 200)]);
$bad = $form;
$bad['symbols'] = ['ETHUSDT'];
$bad['strategy_config_override'] = '{"fast_period": 7,}';
$before = count(pythonCalls());
$r = runAjax($bad);
$calls = count(pythonCalls()) - $before;
$check('JSON inválido → error al usuario (no corre con la config por defecto)', ($r['success'] ?? true) === false && $calls === 0,
    ($r['success'] ?? false) ? "se ejecutó igual ($calls llamada/s a Python) con la config guardada de la estrategia" : '');

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "$fails FALLO(S)") . "\n";
exit($fails ? 1 : 0);

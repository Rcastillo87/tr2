<?php
/**
 * Prueba forense: el formulario de "Configurar Backtest" envía EXACTAMENTE los mismos campos y valores
 * antes y después de un cambio de diseño. Renderiza con Laravel la vista actual (backtesting.run) y la
 * candidata en varios escenarios y compara, campo por campo, lo que el navegador enviaría al motor:
 * inputs (incluidos ocultos y checkboxes marcados), selects (opción seleccionada), textareas, y los datos
 * de símbolos que el JS convierte en symbols[].
 * Solo lectura: no toca la base de datos. La vista candidata se copia a un nombre temporal y se borra.
 *
 * Uso (desde la raíz del proyecto): php tests/Forensic/backtest_form_payload_test.php /ruta/candidata.blade.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Backtest;
use App\Models\Strategy;
use App\Models\User;
use Illuminate\Support\Facades\Auth;

$candidate = $argv[1] ?? '';
// Campos NUEVOS que la candidata agrega a propósito (coma-separados): se informan, no fallan. Lo demás debe ser idéntico.
$allowNew = array_filter(explode(',', $argv[2] ?? ''));
if (! is_file($candidate)) {
    fwrite(STDERR, "Uso: php tests/Forensic/backtest_form_payload_test.php /ruta/candidata.blade.php\n");
    exit(2);
}
$tmpView = resource_path('views/backtesting/__candidate_run.blade.php');
copy($candidate, $tmpView);
register_shutdown_function(fn () => @unlink($tmpView));

// old() y csrf_token() necesitan una sesión en el request (en CLI no hay)
$session = app('session')->driver();
$session->start();
app('request')->setLaravelSession($session);

$user = User::query()->orderBy('id')->first();
if ($user) {
    Auth::setUser($user);
}
$strategy = Strategy::query()->orderBy('id')->first();

/** Campos que enviaría el form #backtestForm (FormData), en orden de documento. */
function formPayload(string $html): array
{
    $doc = new DOMDocument();
    libxml_use_internal_errors(true);
    $doc->loadHTML('<?xml encoding="utf-8"?>' . $html);
    libxml_clear_errors();
    $xp = new DOMXPath($doc);
    $form = $xp->query('//form[@id="backtestForm"]')->item(0);
    if (! $form) {
        return ['__error__' => 'no se encontró form#backtestForm'];
    }
    $out = [];
    foreach ($xp->query('.//input|.//select|.//textarea', $form) as $el) {
        $name = $el->getAttribute('name');
        if ($name === '' || $el->hasAttribute('disabled')) {
            continue;
        }
        $tag = strtolower($el->nodeName);
        if ($tag === 'input') {
            $type = strtolower($el->getAttribute('type') ?: 'text');
            if (in_array($type, ['checkbox', 'radio'], true) && ! $el->hasAttribute('checked')) {
                continue;
            }
            if (in_array($type, ['submit', 'button', 'file'], true)) {
                continue;
            }
            $value = $el->hasAttribute('value') ? $el->getAttribute('value') : (in_array($type, ['checkbox', 'radio'], true) ? 'on' : '');
        } elseif ($tag === 'select') {
            $opts = $xp->query('.//option', $el);
            $value = null;
            foreach ($opts as $o) {
                if ($o->hasAttribute('selected')) {
                    $value = $o->getAttribute('value');
                }
            }
            if ($value === null && $opts->length) {
                $value = $opts->item(0)->getAttribute('value');
            }
        } else {
            $value = $el->textContent;
        }
        $out[] = [$name, (string) $value];
    }
    // Datos con los que el JS arma symbols[] (lista disponible + seleccionados)
    foreach (['rawSymbols', 'rawSelected'] as $var) {
        $out[] = ["js:$var", preg_match('/let ' . $var . ' = (.*?);\n/', $html, $m) ? $m[1] : '<<no encontrado>>'];
    }
    return $out;
}

function render(string $view, array $data): string
{
    view()->flushFinderCache();
    return view($view, $data)->render();
}

$base = [
    'strategies' => collect(), 'symbols' => ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'], 'intervals' => ['1', '5', '15', '60', '240', 'D'],
    'symbolBrokerMap' => [], 'result' => null, 'implementParams' => null, 'error' => null,
];

// Backtest cargado con valores "raros" y TODO activado, para detectar cualquier campo que no viaje intacto
$bt = new Backtest();
$bt->forceFill([
    'id' => 987654, 'strategy_id' => $strategy?->id ?? 1, 'interval' => '15', 'months' => 18, 'symbols' => ['ETHUSDT', 'SOLUSDT'],
    'config_params' => [
        'sl_pct' => 1.37, 'tp_pct' => 2.91, 'initial_balance' => 4321, 'risk_per_trade_pct' => 0.73,
        'commission_pct' => 0.061, 'slippage_pct' => 0.07, 'regime_filter' => true, 'regime_adx_trending' => 27,
        'regime_adx_ranging' => 17, 'regime_ambiguous_as' => 'ignorar', 'volume_filter' => true,
        'volume_filter_period' => 33, 'volume_filter_mult' => 1.7, 'macro_trend_filter' => true, 'max_duration' => 41,
        'be_pct' => 0.9, 'trailing_mode' => 'atr', 'trailing_distance_pct' => 1.3, 'trailing_atr_mult' => 2.6,
        'trailing_activation_buffer_pct' => 0.45, 'max_duration_profit' => true, 'close_on_opposite' => true,
    ],
    'strategy_snapshot' => ['config' => ['fast_period' => 7, 'sl_pct' => 9, 'zone_bars' => 3]],
]);
if ($strategy) {
    $bt->setRelation('strategy', $strategy);
}
// Variante con todo apagado y trailing fijo
$bt2 = clone $bt;
$bt2->forceFill(['config_params' => array_merge($bt->config_params, [
    'regime_filter' => false, 'volume_filter' => false, 'macro_trend_filter' => false, 'max_duration_profit' => false,
    'close_on_opposite' => false, 'trailing_mode' => 'fixed', 'regime_ambiguous_as' => 'TRENDING',
])]);

$scenarios = [
    'nuevo desde estrategia'          => $base + ['backtestToLoad' => null, 'strategyToLoad' => $strategy, 'selectedSymbols' => ['BTCUSDT']],
    'backtest cargado (todo activo)'  => $base + ['backtestToLoad' => $bt, 'strategyToLoad' => null, 'selectedSymbols' => $bt->symbols],
    'backtest cargado (todo apagado)' => $base + ['backtestToLoad' => $bt2, 'strategyToLoad' => null, 'selectedSymbols' => $bt2->symbols],
    'con mensaje de error'            => array_merge($base, ['error' => 'Error de prueba', 'backtestToLoad' => null, 'strategyToLoad' => $strategy, 'selectedSymbols' => []]),
];

$fails = 0;
foreach ($scenarios as $label => $data) {
    try {
        $old = formPayload(render('backtesting.run', $data));
        $newHtml = render('backtesting.__candidate_run', $data);
        $new = formPayload($newHtml);
    } catch (Throwable $e) {
        $fails++;
        printf("FAIL  %-32s excepción al renderizar: %s\n", $label, $e->getMessage());
        continue;
    }
    $oldMap = array_map(fn ($p) => $p[0] . '=' . $p[1], $old);
    $newMap = array_map(fn ($p) => $p[0] . '=' . $p[1], $new);
    sort($oldMap);
    sort($newMap);
    $missing = array_values(array_diff($oldMap, $newMap));
    $extra   = array_values(array_diff($newMap, $oldMap));
    $expectedNew = array_values(array_filter($extra, fn ($e) => in_array(explode('=', $e, 2)[0], $allowNew, true)));
    $extra = array_values(array_diff($extra, $expectedNew));
    $ok = $missing === [] && $extra === [];
    foreach ($expectedNew as $e) {
        echo "        nuevo (esperado):     $e\n";
    }
    $fails += $ok ? 0 : 1;
    printf("%s  %-32s %d campos%s\n", $ok ? 'PASS' : 'FAIL', $label, count($new), $ok ? '' : '');
    foreach ($missing as $m) {
        echo "        solo en la ACTUAL:    $m\n";
    }
    foreach ($extra as $m) {
        echo "        solo en la CANDIDATA: $m\n";
    }
    if ($label === 'backtest cargado (todo activo)') {
        foreach ($new as [$n, $v]) {
            if (! str_starts_with($n, 'js:') && $n !== '_token' && $n !== 'strategy_config_override') {
                printf("        %-32s = %s\n", $n, $v);
            }
        }
    }
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK (el formulario envía exactamente lo mismo)' : "$fails FALLO(S)") . "\n";
exit($fails ? 1 : 0);

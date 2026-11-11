<?php
/**
 * RQ-01.5 (PHP puro): diagnóstico de Paper en pantalla.
 * - trace(): el paso que anuló la señal es el primero, después de la estrategia, que deja en 0 una señal distinta
 *   de 0 (misma regla que paper_trader.blocking_filter); estrategia sin señal = nadie anuló.
 * - CODES cubre todos los motivos que escribe el motor (se leen de paper_trader.py).
 * - Cableado (estático): 2 consultas, sección que no rompe la pantalla de Paper si falla.
 * La prueba con la base real es paper_diagnostics_screen_test.php (corre al instalar).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/paper_diagnostics_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$file = "{$root}/app/Services/PaperDiagnostics.php";
$check('D0: existe App\Services\PaperDiagnostics', is_file($file));
if (is_file($file)) {
    require $file;
    $P = 'App\Services\PaperDiagnostics';
    $T = fn (...$xs) => array_map(fn ($x) => ['step' => $x[0], 'signal' => $x[1]], $xs);
    $kills = fn (array $t) => array_values(array_map(fn ($s) => $s['step'], array_filter($t, fn ($s) => $s['kills'])));

    $t = $P::trace($T(['estrategia', 1], ['volume_filter', 1], ['weekend_filter', 0], ['btc_trend_filter', 0]));
    $check('D1: señal 1 anulada por weekend -> solo weekend marca «anuló»; nombres sin _filter',
        $kills($t) === ['weekend'] && array_column($t, 'step') === ['estrategia', 'volume', 'weekend', 'btc_trend'], $t);
    $check('D2: estrategia sin señal -> ningún paso anuló', $kills($P::trace($T(['estrategia', 0], ['volume_filter', 0]))) === []);
    $check('D3: señal que pasa todos los filtros -> nadie anuló', $kills($P::trace($T(['estrategia', -1], ['hour_filter', -1]))) === []);
    $check('D4: traza vacía, nula o con basura -> sin pasos', $P::trace(null) === [] && $P::trace([]) === []
        && $P::trace(['x', ['signal' => 1]]) === []);

    $py = (string) @file_get_contents("{$root}/python-engine/trading/paper_trader.py");
    preg_match_all("/decide\\(\\s*'([a-z_]+)'/", $py, $m1);
    preg_match_all("/decide\\('([a-z_]+)' if \\w+ else '([a-z_]+)'/", $py, $m2);
    $engine = array_values(array_unique(array_merge($m1[1], $m2[1], $m2[2])));
    sort($engine);
    $missing = array_values(array_diff($engine, array_keys($P::CODES)));
    $check('D5: todos los motivos del motor tienen texto y grupo en la pantalla (' . count($engine) . ')',
        count($engine) >= 12 && $missing === [], $missing);
    $check('D6: cada motivo cae en un grupo conocido', array_diff(array_unique(array_column($P::CODES, 0)), array_keys($P::GROUPS)) === []);
}

$svc = (string) @file_get_contents($file);
$check('W1: 2 consultas (estado por config activa + historial 24 h agregado por motivo), con parámetro enlazado',
    substr_count($svc, 'DB::select(') === 2 && str_contains($svc, "LEFT JOIN paper_eval_state") && str_contains($svc, 'GROUP BY 1, 2')
    && str_contains($svc, "= ANY(?::bigint[])"));
$ctl = (string) @file_get_contents("{$root}/app/Http/Controllers/PaperTradingController.php");
$view = (string) @file_get_contents("{$root}/resources/views/paper-trading/index.blade.php");
$check('W2: si el diagnóstico falla, Paper se muestra sin la sección (try/catch + includeWhen)',
    (bool) preg_match('/try \{\s*\$diagnostics = app\(\\\\App\\\\Services\\\\PaperDiagnostics::class\)->overview\(\);\s*\} catch \(\\\\Throwable/', $ctl)
    && str_contains($view, "@includeWhen(\$diagnostics !== null, 'paper-trading._diagnostics'"));
$check('W3: sin evaluar en 15 min = problema', str_contains($svc, 'STALE_AFTER_MIN = 15') && str_contains($svc, "['stale',"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * C6-04: la pantalla de la búsqueda muestra las fechas reales del período y de cada tramo, desde los cortes que guarda
 * cada búsqueda (App\Support\SearchPeriodLabels). D-58 no cambia: el total ordena y filtra; los tramos solo se rotulan.
 * A: fechas (fin exclusivo → último día que cuenta; tramos sin solaparse; año en las dos puntas si cambia).
 * B: búsquedas viejas (dos tramos) y datos raros: sin tramos o sin rótulos, la pantalla queda como antes.
 * C: el controlador lo entrega y la vista lo muestra (encabezado y barra), escapado.
 * PHP puro. Uso: cd <raíz del proyecto> && php tests/Forensic/search_period_labels_test.php
 */
declare(strict_types=1);

$root = getenv('TR2_TEST_ROOT') ?: getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$file = "{$root}/app/Support/SearchPeriodLabels.php";
$check('A0: existe App\Support\SearchPeriodLabels', is_file($file));
if (is_file($file)) {
    require_once $file;
    $L = App\Support\SearchPeriodLabels::class;
    // cortes reales de una búsqueda del 24-nov (cli/param_search: ui_period(24) + segment_cuts 60/20/20)
    $r = $L::build(['start' => '2024-11-01', 'split' => '2026-01-13', 'test' => '2026-06-08', 'end' => '2026-11-01']);
    $check('A1: total hasta el último día que cuenta (31 oct, no 1 nov)', $r['total'] === '1 nov 2024 → 31 oct 2026', $r);
    $check('A2: las tres fechas de los tramos, contiguas y sin solaparse', $r['segments'] === [
        '1 nov 2024 – 12 ene 2026', '13 ene – 7 jun 2026', '8 jun – 31 oct 2026'], $r['segments']);
    $r2 = $L::build(['start' => '2024-01-01', 'split' => '2025-03-01', 'test' => '2025-08-01', 'end' => '2026-01-01']);
    $check('A3: otro período (los rótulos salen de los cortes de CADA búsqueda)', $r2['segments'] === [
        '1 ene 2024 – 28 feb 2025', '1 mar – 31 jul 2025', '1 ago – 31 dic 2025'] && $r2['total'] === '1 ene 2024 → 31 dic 2025', $r2);
    $v3 = $L::build(['start' => '2024-11-01', 'split' => '2026-03-01', 'end' => '2026-11-01']);
    $check('B1: búsqueda vieja de dos tramos: total corregido, sin tramos', $v3['total'] === '1 nov 2024 → 31 oct 2026' && $v3['segments'] === null, $v3);
    $check('B2: sin período o con fechas inválidas: nada (la pantalla queda como antes)', $L::build(null) === null
        && $L::build(['start' => '2024-13-01', 'end' => '2026-11-01']) === null && $L::build(['start' => 'x', 'end' => 'y']) === null
        && $L::build(['start' => '2026-11-01', 'end' => '2024-11-01']) === null);
    $bad = $L::build(['start' => '2024-11-01', 'split' => '2026-07-01', 'test' => '2026-03-01', 'end' => '2026-11-01']);
    $check('B3: cortes desordenados: total sí, tramos no', $bad['segments'] === null && $bad['total'] !== '', $bad);
}
$c = (string) @file_get_contents("{$root}/app/Http/Controllers/ParamSearchController.php");
$v = (string) @file_get_contents("{$root}/resources/views/param-search/show.blade.php");
$check('C1: el controlador entrega period_labels desde el período guardado',
    str_contains($c, "'period_labels'  => \\App\\Support\\SearchPeriodLabels::build(\$r['period'] ?? null),"));
$check('C2: el encabezado usa el total con el último día que cuenta (y el texto de antes si no hay rótulos)',
    str_contains($v, 'if (s.period_labels) meta += ` · 24 meses: ${s.period_labels.total}`;')
    && str_contains($v, 'else if (p) meta += ` · 24 meses (${p.start} → ${p.end})`;'));
$check('C3: cada tramo de la barra lleva su fecha, escapada', str_contains($v, 'const dates = state?.period_labels?.segments || [\'\', \'\', \'\'];')
    && str_contains($v, '${SB.esc(dates)}') && substr_count($v, ', g.dates[') === 3);
$check('C4: la barra sigue diciendo qué cuenta (D-58: total ordena y filtra; prueba final solo se muestra)',
    str_contains($v, 'con esto se ordena, ') && str_contains($v, 'no se le exige ganar: solo se muestra'));

echo $fails === 0 ? "TODO OK\n" : "{$fails} FALLOS\n";
exit($fails === 0 ? 0 : 1);

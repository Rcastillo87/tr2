<?php
/**
 * D-58 (p103, C5-03): resultados de la búsqueda de configuraciones.
 * A. Puro: solo se muestran (y se pueden crear) las configuraciones con retorno total ≥ +5 % en los 24 meses, medido
 *    con summarize() igual que el historial (suma mensual de las monedas; por moneda en el modo por moneda).
 * B. Cableado (estático): results() filtra todas las búsquedas (también las ya hechas) sin aviso; creatable() rechaza
 *    lo que no se muestra; en la tabla con tramos «Retorno 24 m» va justo antes de «Elegir»; el texto dice lo cierto
 *    (la prueba final cuenta en el total y no se le exige ganar) y ya no dice que «no eligió ni aceptó».
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/search_min_return_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

require "{$root}/app/Helpers/RatingHelper.php";
require "{$root}/app/Services/ParamSearchService.php";
$S = 'App\Services\ParamSearchService';
$ok = defined("{$S}::MIN_TOTAL_RETURN_PCT") && method_exists($S, 'passesMinReturn') && method_exists($S, 'meetsMinReturn');
$check('A0: existen MIN_TOTAL_RETURN_PCT, passesMinReturn y meetsMinReturn', $ok);
if ($ok) {
    $check('A1: el mínimo es +5 % (D-58)', $S::MIN_TOTAL_RETURN_PCT === 5.0, $S::MIN_TOTAL_RETURN_PCT);
    foreach ([[5.0, true], [5.01, true], [38.2, true], [4.99, false], [0.0, false], [-12.0, false]] as [$ret, $want]) {
        $check("A2: retorno 24 m {$ret} % -> " . ($want ? 'se muestra' : 'no se muestra'),
            $S::passesMinReturn(['total_return_pct' => $ret]) === $want);
    }
    $check('A3: sin dato de retorno: no se muestra', $S::passesMinReturn([]) === false);
    // con summarize(): la suma mensual de las monedas sobrevivientes, como el historial
    $svc = (new ReflectionClass($S))->newInstanceWithoutConstructor();
    $row = ['survivors' => ['BTCUSDT', 'ETHUSDT'], 'symbols' => [
        'BTCUSDT' => ['m' => [1.0, 1.5, 0.5], 'n' => 40, 'wins' => 20, 'gp' => 10, 'gl' => 5, 'wr' => 50, 'sharpe' => 1, 'pf' => 2, 'dd' => 4],
        'ETHUSDT' => ['m' => [0.5, 0.5, 0.9], 'n' => 35, 'wins' => 15, 'gp' => 8, 'gl' => 6, 'wr' => 43, 'sharpe' => 1, 'pf' => 1.3, 'dd' => 6],
        'SOLUSDT' => ['m' => [-9.0, -9.0, -9.0], 'n' => 30, 'wins' => 5, 'gp' => 1, 'gl' => 9, 'wr' => 17, 'sharpe' => -1, 'pf' => 0.1, 'dd' => 20],
    ]];
    $sum = $svc->summarize($row, ['BTCUSDT', 'ETHUSDT']);
    $check('A4: summarize suma los meses de las monedas que quedan (+4,9 %): no llega a +5 %',
        abs($sum['total_return_pct'] - 4.9) < 1e-9 && $S::passesMinReturn($sum) === false, $sum['total_return_pct']);
    $row['symbols']['ETHUSDT']['m'][2] = 1.0;
    $check('A5: con +5,0 % justo sí se muestra', $S::passesMinReturn($svc->summarize($row, ['BTCUSDT', 'ETHUSDT'])));
}

// B. Cableado
$svcSrc = (string) file_get_contents("{$root}/app/Services/ParamSearchService.php");
$ctl = (string) file_get_contents("{$root}/app/Http/Controllers/ParamSearchController.php");
$view = (string) file_get_contents("{$root}/resources/views/param-search/show.blade.php");
$check('B1: results() salta las filas por debajo del mínimo (todas las búsquedas, sin aviso)',
    (bool) preg_match('/foreach \(\$run->results\[\'rows\'\] \?\? \[\] as \$row\) \{\s*if \(! \$this->service->meetsMinReturn\(\$run, \$row\)\) \{[^}]*continue;/s', $ctl));
$check('B2: creatable() rechaza lo que no se muestra (no se crea por un id directo)',
    (bool) preg_match('/public function creatable\(ParamSearchRun \$run, array \$row\): bool\s*\{\s*if \(! \$this->meetsMinReturn\(\$run, \$row\)\) \{[^\n]*\n\s*return false;/s', $svcSrc));
$check('B3: meetsMinReturn usa las monedas de la vista por defecto (survivors) y summarize()',
    str_contains($svcSrc, "self::passesMinReturn(\$this->summarize(\$row, \$this->symbolsFor(\$run, \$row, 'survivors')))"));
preg_match('/\$\(\'sbHead3\'\)\.innerHTML = `(.*?)`;\n/s', $view, $h);
$head = $h[1] ?? '';
$pRet = strpos($head, "H('Retorno ' + months + ' m', 'total_return_pct')");
$pDd = strpos($head, 'DD máx');
$pElegir = strpos($head, 'Elegir ${g.choose} m');
$check('B4: cabecera: «Retorno 24 m» justo después de «DD máx» y antes de «Elegir»',
    $pRet !== false && $pDd !== false && $pElegir !== false && $pDd < $pRet && $pRet < $pElegir
    && ! str_contains(substr($head, 0, (int) $pDd), "'total_return_pct'"), [$pDd, $pRet, $pElegir]);
preg_match('/\$\(\'sbRows3\'\)\.innerHTML = list\.map\(r => \{(.*?)\}\)\.join/s', $view, $b);
$body = $b[1] ?? '';
$pDdc = strpos($body, 'm.max_drawdown_pct');
$pRetc = strpos($body, 'SB.pct(m.total_return_pct)');
$pIs = strpos($body, 'r.is.ret');
$check('B5: filas: la celda del retorno va entre DD máx y Elegir', $pDdc !== false && $pDdc < $pRetc && $pRetc < $pIs,
    [$pDdc, $pRetc, $pIs]);
$check('B6: el texto ya no dice que la prueba final «no eligió ni aceptó»',
    ! str_contains($view, 'no eligió ni aceptó') && ! str_contains($view, 'que no eligieron ni aceptaron')
    && ! str_contains($view, 'la prueba final solo se muestra.'));
$check('B7: el texto dice qué se evalúa: total para ordenar, ganar en elegir y validación, prueba final sin exigirle ganar',
    str_contains($view, 'con esto se ordena') && str_contains($view, 'debe ganar aquí también')
    && str_contains($view, 'no se le exige ganar: solo se muestra') && str_contains($view, 'cuenta dentro del total'));
$check('B8: el mínimo de la pantalla sale de la misma constante del servidor',
    str_contains($view, 'const MIN_RET = {{ \App\Services\ParamSearchService::MIN_TOTAL_RETURN_PCT }};'));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

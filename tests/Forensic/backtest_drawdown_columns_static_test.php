<?php
/**
 * Fase 12 · 4A (D-38): la tabla «Resumen por moneda» del backtest muestra DD cerrado y DD flotante.
 * - El encabezado tiene las dos columnas justo después de «Retorno» y cada fila (moneda, CONSOLIDADO, GUARDADO,
 *   COMPARATIVO) tiene tantas celdas como columnas: una fila corta descuadra toda la tabla.
 * - CONSOLIDADO = el peor drawdown entre las monedas; se guarda con el backtest para la fila GUARDADO.
 * - Backtests guardados antes de p75 no traen el dato: se muestra «—», nunca 0.
 * - El Excel exportado trae la fila «Max drawdown flotante (%)».
 * - C5-12 (D-62): con más de una moneda, el DD del CONSOLIDADO dice «peor moneda», lleva la explicación al pasar el
 *   mouse y una nota bajo la tabla (no es el DD de una cartera conjunta, D-41). Con una sola moneda, sin rótulo.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/backtest_drawdown_columns_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$v = file_get_contents($root . '/resources/views/backtesting/partials/results.blade.php');
$a = strpos($v, 'TABLA 1: Resumen por moneda');
$b = strpos($v, 'TABLA 2:');
$t1 = ($a !== false && $b !== false) ? substr($v, $a, $b - $a) : '';
$check('existe la sección TABLA 1', $t1 !== '');

// Encabezado
preg_match('/<thead>(.*?)<\/thead>/s', $t1, $m);
preg_match_all('/<th\b[^>]*>(.*?)<\/th>/s', $m[1] ?? '', $th);
$heads = array_map('trim', $th[1]);
$cols = count($heads);
$iRet = array_search('Retorno', $heads, true);
$check('encabezado: 13 columnas', $cols === 13, $heads);
$check('encabezado: «DD cerrado» y «DD flotante» justo después de «Retorno»',
    $iRet !== false && ($heads[$iRet + 1] ?? '') === 'DD cerrado' && ($heads[$iRet + 2] ?? '') === 'DD flotante', $heads);

// Cada fila: tantas celdas de primer nivel como columnas (se cuentan las <td de apertura del <tr>)
preg_match('/<tbody\b[^>]*>(.*)<\/tbody>/s', $t1, $tb);
preg_match_all('/<tr\b.*?<\/tr>/s', $tb[1] ?? '', $rows);
$counts = array_map(fn ($r) => preg_match_all('/<td\b/', $r), $rows[0]);
$check('cuatro filas de plantilla (moneda, CONSOLIDADO, GUARDADO, COMPARATIVO)', count($counts) === 4, $counts);
$check('todas las filas tienen 13 celdas', $counts !== [] && count(array_unique($counts)) === 1 && $counts[0] === $cols, $counts);

// Qué muestra cada fila en las columnas nuevas
$check('moneda: usa max_drawdown_pct y max_drawdown_floating_pct del resultado de esa moneda',
    str_contains($rows[0][0] ?? '', "\$fmtDd(\$d['agg']['max_drawdown_pct'] ?? null)")
    && str_contains($rows[0][0] ?? '', "\$fmtDd(\$d['agg']['max_drawdown_floating_pct'] ?? null)"));
$check('CONSOLIDADO: usa los valores consolidados del controlador',
    str_contains($rows[0][1] ?? '', "\$fmtDd(\$aggGlobal['max_drawdown_pct'] ?? null)")
    && str_contains($rows[0][1] ?? '', "\$fmtDd(\$aggGlobal['max_drawdown_floating_pct'] ?? null)"));
$check('GUARDADO: dato ausente = null (se muestra «—», no 0)',
    str_contains($t1, "\$prevDd = isset(\$prevM['max_drawdown_pct']) ? (float) \$prevM['max_drawdown_pct'] : null;")
    && str_contains($t1, "\$prevDdFloat = isset(\$prevM['max_drawdown_floating_pct']) ? (float) \$prevM['max_drawdown_floating_pct'] : null;")
    && str_contains($rows[0][2] ?? '', '$fmtDd($prevDd)') && str_contains($rows[0][2] ?? '', '$fmtDd($prevDdFloat)'));
$check('COMPARATIVO: en drawdown bajar es mejorar (verde si la diferencia es negativa) y «—» sin dato previo',
    substr_count($rows[0][3] ?? '', "\$diff < 0 ? 'var(--color-profit)'") === 2
    && str_contains($rows[0][3] ?? '', '$prevDd !== null') && str_contains($rows[0][3] ?? '', '$prevDdFloat !== null'));

// Formato: se ejecuta la misma expresión de la vista
preg_match('/\$fmtDd = (fn \(\$v\) => [^;]+);/', $t1, $fm);
$fmt = isset($fm[1]) ? eval('return ' . $fm[1] . ';') : null;
$check('formato: null → «—»; 0 → «0.00%»; 12.345 → «12.35%»',
    $fmt !== null && $fmt(null) === '—' && $fmt(0) === '0.00%' && $fmt(12.345) === '12.35%');

// Controlador
$c = file_get_contents($root . '/app/Http/Controllers/BacktestingController.php');
$check('controlador: arranca sin dato (null) y toma el peor drawdown de las monedas',
    str_contains($c, '$maxDd = null;') && str_contains($c, '$maxDdFloat = null;')
    && str_contains($c, "\$maxDd = max(\$maxDd ?? 0.0, (float) \$agg['max_drawdown_pct']);")
    && str_contains($c, "\$maxDdFloat = max(\$maxDdFloat ?? 0.0, (float) \$agg['max_drawdown_floating_pct']);"));
$check('controlador: los dos valores van en aggregate_metrics (pantalla) y en metrics (lo que se guarda)',
    substr_count($c, "'max_drawdown_pct' => \$maxDd,") === 2 && substr_count($c, "'max_drawdown_floating_pct' => \$maxDdFloat,") === 2);
// Ejecución de la regla de consolidación con datos de ejemplo
$maxDd = null; $maxDdFloat = null;
foreach ([['max_drawdown_pct' => 8.4, 'max_drawdown_floating_pct' => 11.9], ['max_drawdown_pct' => 10.2, 'max_drawdown_floating_pct' => 14.6]] as $agg) {
    if (isset($agg['max_drawdown_pct'])) { $maxDd = max($maxDd ?? 0.0, (float) $agg['max_drawdown_pct']); }
    if (isset($agg['max_drawdown_floating_pct'])) { $maxDdFloat = max($maxDdFloat ?? 0.0, (float) $agg['max_drawdown_floating_pct']); }
}
$check('consolidación: BTC 8.4/11.9 y ETH 10.2/14.6 → 10.2 / 14.6', $maxDd === 10.2 && $maxDdFloat === 14.6, [$maxDd, $maxDdFloat]);

// Excel
$x = file_get_contents($root . '/app/Exports/BacktestMonthlyExport.php');
$check('Excel: fila «Max drawdown flotante (%)» después de «Max drawdown (%)» y «—» sin dato',
    preg_match("/\['Max drawdown \(%\)',\s+\\\$agg\['max_drawdown_pct'\] \?\? 0\],\s*\n\s*\['Max drawdown flotante \(%\)', \\\$agg\['max_drawdown_floating_pct'\] \?\? '—'\],/", $x) === 1);

// Motor: el dato existe en las métricas que el controlador recibe
$e = file_get_contents($root . '/python-engine/backtesting/engine.py');
$check("motor: metrics['max_drawdown_floating_pct'] se calcula (llega como aggregate_metrics)",
    str_contains($e, "metrics['max_drawdown_floating_pct'] = "));

// ── C5-12 (D-62): rótulo del DD consolidado ──
$note = 'DD del consolidado = el peor DD entre las monedas. Cada moneda se simula sola, así que no es la caída de una cartera con todas a la vez.';
$check('C5-12: la explicación está definida una vez con el texto aprobado',
    substr_count($v, "\$ddConsolidatedNote = '" . $note . "';") === 1);
preg_match('/CONSOLIDADO<\/td>(.*?)<\/tr>/s', $t1, $cr);
$cons = $cr[1] ?? '';
$cell = fn (string $k) => '@if($isMulti) title="{{ $ddConsolidatedNote }}"@endif>{{ $fmtDd($aggGlobal[\'' . $k . '\'] ?? null) }}'
    . '@if($isMulti)<div class="font-sans font-normal text-[10px]" style="color:var(--color-neutral);">peor moneda</div>@endif</td>';
$check('C5-12: CONSOLIDADO: DD cerrado y flotante con «peor moneda» y la explicación al pasar el mouse, solo con varias monedas',
    str_contains($cons, $cell('max_drawdown_pct')) && str_contains($cons, $cell('max_drawdown_floating_pct')));
$check('C5-12: «peor moneda» solo en esas dos celdas (no en moneda, GUARDADO ni COMPARATIVO)',
    substr_count($t1, 'peor moneda') === 2 && substr_count($cons, 'peor moneda') === 2);
$tail = strrpos($t1, '</table>') !== false ? substr($t1, strrpos($t1, '</table>')) : '';
$check('C5-12: nota bajo la tabla de resumen, solo con varias monedas',
    preg_match('/<\/table>\s*@if\(\$isMulti\)\s*<p\b[^>]*>.*?DD del consolidado:<\/span> \{\{ \\\\Illuminate\\\\Support\\\\Str::after\(\$ddConsolidatedNote, \'DD del consolidado = \'\) \}\}<\/p>\s*@endif/s', $tail) === 1, $tail);
$after = substr($note, strpos($note, 'DD del consolidado = ') + strlen('DD del consolidado = '));
$check('C5-12: la nota dice «el peor DD entre las monedas» y que no es una cartera conjunta',
    str_starts_with($after, 'el peor DD entre las monedas.') && str_contains($after, 'no es la caída de una cartera'), $after);
// Directivas como las reconoce Blade (\B@): todas las @if($isMulti) nuevas se compilan y quedan balanceadas
preg_match_all('/\B@(if|endif)\b/', $t1, $dm);
$check('C5-12: TABLA 1 con @if / @endif balanceados',
    count(array_keys($dm[1], 'if')) === count(array_keys($dm[1], 'endif')), array_count_values($dm[1]));
$check('C5-12: el número no cambia: CONSOLIDADO sigue con los valores del controlador (peor de las monedas)',
    substr_count($cons, "\$fmtDd(\$aggGlobal['max_drawdown_pct'] ?? null)") === 1
    && substr_count($cons, "\$fmtDd(\$aggGlobal['max_drawdown_floating_pct'] ?? null)") === 1);

echo $fails === 0 ? "TODO OK\n" : "FALLAS: $fails\n";
exit($fails === 0 ? 0 : 1);

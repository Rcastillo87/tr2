<?php
/**
 * Fase 12 · 1A (D-38): pantalla de resultados de la búsqueda con tres tramos (maqueta aprobada el 19-nov).
 * - Barra «Elegir · Validar · Prueba final» con los meses de cada tramo, solo en búsquedas v4.
 * - Columnas «Elegir N m», «Validación N m», «Prueba final N m» (tabla y tarjetas); la prueba final en verde/rojo y
 *   «—» si la fila no la trae. KPI «También ganan en la prueba final».
 * - Búsquedas anteriores (v3, dos tramos): se ven como siempre («Primeros 16 m / Últimos 8 m», sin barra).
 * - El controlador entrega la prueba final de cada fila.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/search_three_segments_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$v = (string) file_get_contents($root . '/resources/views/param-search/show.blade.php');
$c = (string) file_get_contents($root . '/app/Http/Controllers/ParamSearchController.php');

$check('controlador: cada fila lleva la prueba final (null en búsquedas anteriores)', str_contains($c, "'test'       => \$row['test'] ?? null,"));
$check('vista: contenedor de la barra de tramos, oculto por defecto', str_contains($v, '<div id="sbBar3" class="mb-3" style="display:none"></div>'));
$check('vista: los tres tramos solo con resultado v4 y corte de la prueba final guardado',
    str_contains($v, "if (!(data.version >= 4) || !p || !p.test) return null;"));
$check('vista: meses de cada tramo desde el período guardado (inicio, corte, prueba final, fin)',
    str_contains($v, 'const choose = monthsBetween(p.start, p.split), val = monthsBetween(p.split, p.test), test = monthsBetween(p.test, p.end);'));
$check('vista: barra con los tres rótulos de la maqueta',
    str_contains($v, '`Elegir · meses ${g.from[0]}–${g.to[0]}`') && str_contains($v, '`Validar · ${g.from[1]}–${g.to[1]}`')
    && str_contains($v, '`Prueba final · ${g.from[2]}–${g.to[2]}`'));
$check('vista: encabezado con las tres columnas en v4 y las dos de siempre en v3',
    str_contains($v, '<th class="r">Elegir ${g.choose} m</th><th class="r">Validación ${g.val} m</th><th class="r">Prueba final ${g.test} m</th>')
    && str_contains($v, '<th class="r">Primeros ${first} m</th><th class="r">Últimos ${late} m</th>'));
$check('vista: celda de la prueba final en verde/rojo según el retorno y «—» sin dato',
    str_contains($v, "const testCell = r => r.test ? `<span class=\"\${SB.cls(r.test.ret)}\">\${SB.pct(r.test.ret)}</span>` : '—';"));
$check('vista: la celda de la prueba final está en la tabla y en las tarjetas (móvil)',
    str_contains($v, '${g ? `<td class="r">${testCell(r)}</td>` : \'\'}') && str_contains($v, '<div><span>Prueba final ${g.test} m</span><b>${testCell(r)}</b></div>'));
$check('vista: KPI «También ganan en la prueba final» (cuántas de la lista)',
    str_contains($v, "['También ganan en la prueba final', `\${testWins} de \${list.length}`"));
$check('vista: la prueba final no filtra la lista (la lista es la misma; solo se cuenta)',
    str_contains($v, 'const testWins = list.filter(r => r.test && r.test.ret > 0).length;')
    && ! preg_match('/list\s*=\s*[^;]*\.test\b/', $v));

echo $fails === 0 ? "TODO OK\n" : "FALLAS: $fails\n";
exit($fails === 0 ? 0 : 1);

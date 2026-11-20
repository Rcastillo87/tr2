<?php
/**
 * Limpieza (p88): ningún `use` de clase sin usar en app/ y routes/ (confunde al que lee y al auditor).
 * Un `use A\B\C;` (o `as X`) cuyo nombre corto no vuelve a aparecer como palabra en el archivo es un import sin usar.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/unused_uses_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$bad = [];
$n = 0;
$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/app', FilesystemIterator::SKIP_DOTS));
$files = array_merge(iterator_to_array($it), array_map(fn ($f) => new SplFileInfo($f), glob($root . '/routes/*.php')));
foreach ($files as $f) {
    if ($f->getExtension() !== 'php') {
        continue;
    }
    $n++;
    $src = (string) file_get_contents($f->getPathname());
    preg_match_all('/^use ([A-Za-z0-9_\\\\]+)(?: as ([A-Za-z0-9_]+))?;/m', $src, $m, PREG_SET_ORDER);
    $body = (string) preg_replace('/^use [^;]+;$/m', '', $src);   // se cuenta fuera de las líneas `use`
    foreach ($m as $u) {
        $short = $u[2] ?? '';
        if ($short === '') {
            $parts = explode('\\', $u[1]);
            $short = end($parts);
        }
        if (preg_match_all('/(?<![\w\\\\$])' . preg_quote($short, '/') . '\b/', $body) === 0) {
            $bad[] = str_replace($root . '/', '', $f->getPathname()) . ': ' . $u[1];
        }
    }
}
echo "{$n} archivos revisados\n";
foreach ($bad as $b) {
    echo "FAIL  use sin usar: {$b}\n";
}
echo $bad === [] ? "PASS  ningún use sin usar\n" : '';
echo "\nRESULTADO: " . ($bad === [] ? 'TODO OK' : count($bad) . ' FALLO(S)') . "\n";
exit($bad === [] ? 0 : 1);

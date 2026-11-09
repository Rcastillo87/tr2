<?php
/**
 * Vistas Blade sin llamadas imposibles. `[]->metodo()` (método sobre un array literal) es un error fatal en PHP 8 que
 * `php -l` no detecta dentro de @php y que solo explota cuando esa línea se ejecuta (p. ej. dentro de un @foreach
 * vacío hasta que hay datos): así cayó /trading el 09-nov al aparecer el primer trade de Real.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/blade_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$bad = [];
$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/resources/views', FilesystemIterator::SKIP_DOTS));
$n = 0;
foreach ($it as $f) {
    if (! str_ends_with($f->getFilename(), '.blade.php')) {
        continue;
    }
    $n++;
    foreach (file($f->getPathname()) as $i => $line) {
        // método sobre un array literal ([]->, []?->) o sobre null sin nullsafe (null->); null?-> es válido
        if (preg_match('/(\[\s*\]\s*\??->|\bnull\s*->)\s*\w+\s*\(/i', $line)) {
            $bad[] = substr($f->getPathname(), strlen($root) + 1) . ':' . ($i + 1) . ' ' . trim($line);
        }
    }
}
$check("ninguna vista llama un método sobre [] o null literal ($n vistas revisadas)", $bad === [], $bad);

$v = file_get_contents($root . '/resources/views/trading/index.blade.php');
$check('trading: la etiqueta de cuenta de trades abiertos y cerrados usa las cuentas del usuario',
    substr_count($v, "\$filterOptions['accounts']->firstWhere('id', \$trade->broker_account_id)") === 2);
$c = file_get_contents($root . '/app/Http/Controllers/TradingController.php');
$check("trading: el controlador entrega 'accounts' (Collection de BrokerAccount con account_type)",
    str_contains($c, "'accounts'   => \$userAccounts") && preg_match("/get\(\['id', 'label', 'account_type', 'broker'\]\)/", $c) === 1);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "$fails FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

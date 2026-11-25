<?php
/**
 * D-71 (dueño, 25-nov): el perfil inversionista no ve nombres de estrategias.
 * - Dashboard: sin la sección «Estrategias — paper trading» (el resto igual).
 * - Trading Real: sin el filtro de estrategia ni la columna «Estrategia» (abiertas y cerradas); el filtro por URL no se
 *   aplica. Admin y consultor: sin cambios.
 * PHP puro. Uso: cd <raíz del proyecto> && php tests/Forensic/investor_hides_strategies_test.php
 */
declare(strict_types=1);

$root = getenv('TR2_TEST_ROOT') ?: getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$read = fn (string $f) => (string) @file_get_contents("{$root}/{$f}");
$dash = $read('resources/views/dashboard/index.blade.php');
$ctl = $read('app/Http/Controllers/TradingController.php');
$tr = $read('resources/views/trading/index.blade.php');

$check('D1: el dashboard oculta «Estrategias — paper trading» al inversionista', (bool) preg_match(
    "/@unless \(auth\(\)->user\(\)\?->isInversionista\(\)\)\s*<div[^>]*>\s*<div[^>]*>\s*<h3[^>]*>Estrategias — paper trading<\/h3>/", $dash));
$i = strpos($dash, 'Estrategias — paper trading');
$check('D2: el ocultamiento termina antes del bloque del collector (no se lleva otras secciones)',
    $i !== false && strpos($dash, '@endunless', $i) < strpos($dash, '{{-- 4. Data Collector'));
$check('D3: los resúmenes del mes (Real y Paper) quedan como estaban (solo se pidió la sección de estrategias)',
    substr_count($dash, 'isInversionista') === 1 && str_contains($dash, '— paper trading</h3>'));
$check('C1: el controlador ignora el filtro de estrategia del inversionista y avisa a la vista',
    str_contains($ctl, '$hideStrategy = (bool) $request->user()?->isInversionista();')
    && str_contains($ctl, "\$filterStrategy = \$hideStrategy ? 'all' : \$request->query('strategy', 'all');")
    && str_contains($ctl, "'hideStrategy'    => \$hideStrategy,"));
$check('T1: el filtro de estrategia no se muestra al inversionista', (bool) preg_match(
    '/@unless \(\$hideStrategy \?\? false\)\s*<select name="strategy".*?<\/select>\s*@endunless/s', $tr));
$check('T2: la columna «Estrategia» no se muestra al inversionista en las dos tablas (encabezado y celda)',
    substr_count($tr, '@unless ($hideStrategy ?? false)<th class="py-2 px-3 text-left font-normal">Estrategia</th>@endunless') === 2
    && substr_count($tr, "@unless (\$hideStrategy ?? false)<td class=\"py-2 px-3\" style=\"color:var(--color-text-primary);\">{{ trim(explode('—', \$trade->strategy)[0]) }}</td>@endunless") === 2);
$user = $read('app/Models/User.php');
$check('U1: el rol existe y es el de «inversionista»', str_contains($user, "return \$this->role === 'inversionista';"));

echo $fails === 0 ? "TODO OK\n" : "{$fails} FALLOS\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * D-46 / R-02 (p87): permisos por rol según el dueño (20-nov).
 *   Dashboard: todos · Paper: admin y consultor (solo mirar) · Real: admin e inversionista ·
 *   Backtesting, búsquedas, estrategias, collector y usuarios: solo admin.
 * Lee los permisos del modelo User (los mismos que usan las rutas, los Gates, el menú y el dashboard) y comprueba la
 * matriz completa; también que cada módulo esté protegido por su permiso y que Paper no tenga acciones que cambien algo.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/role_access_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$model = (string) file_get_contents($root . '/app/Models/User.php');
/** Roles con permiso según el cuerpo del método (in_array([...]) o isAdmin()). */
$roles = function (string $method) use ($model): ?array {
    if (! preg_match('/function ' . $method . '\(\): bool\s*\{(.*?)\n    \}/s', $model, $m)) {
        return null;
    }
    $body = $m[1];
    if (preg_match('/return \$this->isAdmin\(\);/', $body)) {
        return ['admin'];
    }
    if (preg_match("/in_array\(\\\$this->role, \[(.*?)\], true\)/", $body, $r)) {
        preg_match_all("/'([a-z]+)'/", $r[1], $x);
        sort($x[1]);

        return $x[1];
    }

    return null;
};

$want = [
    'canViewPaperTrading'  => ['admin', 'consultor'],
    'canViewRealTrading'   => ['admin', 'inversionista'],
    'canViewAnalysisTools' => ['admin'],
    'canManageUsers'       => ['admin'],
];
foreach ($want as $method => $roles_ok) {
    $got = $roles($method);
    $check("{$method}: " . implode(', ', $roles_ok), $got === $roles_ok, $got);
}

$routes = (string) file_get_contents($root . '/routes/web.php');
foreach ([
    'paper-trading' => 'viewPaperTrading', 'backtesting' => 'viewAnalysisTools', 'trading' => 'viewRealTrading',
    'strategies' => 'manageUsers', 'users' => 'manageUsers', 'collector' => 'manageUsers',
] as $prefix => $gate) {
    $check("ruta /{$prefix} protegida por {$gate}",
        (bool) preg_match("/middleware\('can:{$gate}'\)->prefix\('{$prefix}'\)/", $routes));
}
preg_match("/prefix\('paper-trading'\).*?\}\);/s", $routes, $p);
$check('Paper es solo mirar (sus rutas son GET)', isset($p[0]) && ! preg_match('/Route::(post|put|patch|delete)/', $p[0]), $p[0] ?? '');

$prov = (string) file_get_contents($root . '/app/Providers/AppServiceProvider.php');
foreach (['viewPaperTrading' => 'canViewPaperTrading', 'viewAnalysisTools' => 'canViewAnalysisTools',
          'viewRealTrading' => 'canViewRealTrading', 'manageUsers' => 'canManageUsers'] as $gate => $method) {
    $check("Gate {$gate} = User::{$method}", (bool) preg_match("/Gate::define\('{$gate}', function \(User \\\$user\) \{\s*return \\\$user->{$method}\(\);/", $prov));
}

$ctl = (string) file_get_contents($root . '/app/Http/Controllers/BacktestingController.php');
$check('las acciones del backtesting también piden el permiso en el controlador (7)', substr_count($ctl, "Gate::authorize('viewAnalysisTools')") >= 7,
    substr_count($ctl, "Gate::authorize('viewAnalysisTools')"));

$nav = (string) file_get_contents($root . '/resources/views/layouts/nav-links.blade.php')
    . (string) file_get_contents($root . '/resources/views/layouts/app.blade.php');
$check('el menú muestra Paper, Real y Estrategias/Backtest con los mismos permisos',
    str_contains($nav, "'paper-trading.index'") && substr_count($nav, 'canViewPaperTrading()') >= 2
    && substr_count($nav, 'canViewRealTrading()') >= 2 && substr_count($nav, 'canViewAnalysisTools()') >= 2);
$dash = (string) file_get_contents($root . '/resources/views/dashboard/index.blade.php');
$check('dashboard: bloque Real con viewRealTrading, enlace a Paper con viewPaperTrading, administración con manageUsers',
    str_contains($dash, "@can('viewRealTrading')") && str_contains($dash, "@can('viewPaperTrading')") && str_contains($dash, "@can('manageUsers')"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

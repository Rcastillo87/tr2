<?php
/**
 * F-05 — El JSON de la estrategia editado en el formulario se FUSIONA sobre la configuración de la estrategia (por clave
 * de primer nivel): las claves omitidas se conservan. Antes lo reemplazaba entero y una clave omitida se perdía.
 * PHP puro, sin base de datos ni Laravel.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/config_merge_test.php
 * Antes del parche: FALLA.
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

require $root . '/app/Services/BacktestPayload.php';
$merge = [\App\Services\BacktestPayload::class, 'mergeConfig'];
$base = ['ema_fast' => 9, 'ema_slow' => 21, 'allowed_regimes' => ['TRENDING', 'RANGING'], 'rsi' => ['period' => 14, 'low' => 30]];

if (! method_exists(\App\Services\BacktestPayload::class, 'mergeConfig')) {
    $check('BacktestPayload::mergeConfig existe', false, 'no existe (código anterior)');
} else {
    $got = $merge($base, ['ema_fast' => 12]);
    $check('JSON parcial: cambia ema_fast y CONSERVA las demás claves',
        $got === ['ema_fast' => 12, 'ema_slow' => 21, 'allowed_regimes' => ['TRENDING', 'RANGING'], 'rsi' => ['period' => 14, 'low' => 30]], $got);
    $got = $merge($base, ['nueva' => true]);
    $check('clave nueva se agrega', ($got['nueva'] ?? null) === true && $got['ema_slow'] === 21, $got);
    $got = $merge($base, ['allowed_regimes' => ['TRENDING']]);
    $check('una lista se reemplaza entera (no se mezclan elementos)', $got['allowed_regimes'] === ['TRENDING'], $got['allowed_regimes']);
    $got = $merge($base, ['rsi' => ['period' => 7]]);
    $check('un objeto anidado se reemplaza entero (fusión solo de primer nivel, predecible)', $got['rsi'] === ['period' => 7], $got['rsi']);
    $got = $merge($base, $base);
    $check('JSON completo = igual que antes', $got === $base);
    $got = $merge([], ['a' => 1]);
    $check('estrategia sin config: el JSON tal cual', $got === ['a' => 1]);
}

$ctl = file_get_contents($root . '/app/Http/Controllers/BacktestingController.php');
$check('controlador: fusiona el JSON editado con mergeConfig (ya no lo reemplaza)',
    str_contains($ctl, 'BacktestPayload::mergeConfig((array) ($strategy->config ?? []), $decoded)')
    && ! preg_match('/\$finalConfig\s*=\s*\$decoded;/', $ctl));
$check('controlador: un JSON inválido sigue rechazándose antes de fusionar',
    strpos($ctl, 'no son válidos') !== false && strpos($ctl, 'no son válidos') < strpos($ctl, 'mergeConfig('));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "$fails FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

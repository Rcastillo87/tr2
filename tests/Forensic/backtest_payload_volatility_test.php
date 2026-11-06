<?php
/**
 * F-01 — La protección por volatilidad solo viaja a Python si vino en el request (el formulario no la tiene); si no,
 * manda el JSON de la estrategia. PHP puro, sin base de datos ni Laravel.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/backtest_payload_volatility_test.php
 * Antes del parche: FALLA (el controlador enviaba siempre modo null, ×2.5 y 1.0 %, que pisaban el JSON).
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$svc = $root . '/app/Services/BacktestPayload.php';
$check('existe App\Services\BacktestPayload', is_file($svc), $svc);
if (is_file($svc)) {
    require $svc;
    $v = [\App\Services\BacktestPayload::class, 'volatility'];
    $check('formulario sin volatilidad -> no se envía nada (manda el JSON)', $v(['sl_pct' => '1.5']) === [], $v(['sl_pct' => '1.5']));
    $check("'none' -> apagada explícita (null)", $v(['volatility_protection_mode' => 'none']) === ['volatility_protection_mode' => null]);
    $got = $v(['volatility_protection_mode' => 'Close', 'volatility_atr_multiplier' => '3', 'volatility_widen_pct' => '0.5']);
    $check('modo y parámetros enviados -> viajan (modo en minúsculas, números como float)',
        $got === ['volatility_protection_mode' => 'close', 'volatility_atr_multiplier' => 3.0, 'volatility_widen_pct' => 0.5], $got);
    $got = $v(['volatility_protection_mode' => '', 'volatility_atr_multiplier' => '', 'volatility_widen_pct' => null]);
    $check('campos vacíos o null = no enviados', $got === [], $got);
    $got = $v(['volatility_atr_multiplier' => '2']);
    $check('solo el multiplicador -> solo el multiplicador (el modo sigue el JSON)', $got === ['volatility_atr_multiplier' => 2.0], $got);
}

// El controlador ya no inventa valores por defecto y usa el servicio
$ctl = file_get_contents($root . '/app/Http/Controllers/BacktestingController.php');
$check('controlador: sin defaults de volatilidad en el payload',
    !str_contains($ctl, "input('volatility_atr_multiplier', 2.5)") && !str_contains($ctl, "input('volatility_protection_mode', 'none')"));
$check('controlador: agrega la volatilidad con BacktestPayload::volatility($request->all())',
    substr_count($ctl, 'BacktestPayload::volatility($request->all())') === 1);

// La búsqueda ejecuta el backtest por el mismo camino: su formulario tampoco fuerza la volatilidad
require $root . '/app/Services/BacktestFromSearch.php';
$cfg = ['sl_pct' => 1.5, 'tp_pct' => 3.0, 'be_pct' => 2.0, 'max_duration' => 24, 'trailing_mode' => null,
        'trailing_distance_pct' => 1.0, 'trailing_activation_buffer_pct' => 0.0, 'trailing_atr_mult' => 2.0,
        'regime_adx_trending' => 25, 'regime_adx_ranging' => 20, 'regime_ambiguous_as' => 'RANGING',
        'volume_filter_period' => 20, 'volume_filter_mult' => 1.2, 'regime_filter' => true];
$form = \App\Services\BacktestFromSearch::formFields($cfg, 3, '60', ['BTCUSDT'], 24);
$keys = array_values(array_filter(array_keys($form), fn ($k) => str_starts_with($k, 'volatility_')));
$check('BacktestFromSearch::formFields sin volatility_* (manda el JSON, como la búsqueda)', $keys === [], $keys);
if (is_file($svc)) {
    $check('…y por lo tanto el payload de un backtest desde la búsqueda no trae volatilidad',
        \App\Services\BacktestPayload::volatility($form) === []);
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "$fails FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

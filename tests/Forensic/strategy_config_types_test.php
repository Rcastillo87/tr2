<?php
/**
 * N-08: el JSON editado de la estrategia (strategy_config_override) se valida contra la config guardada ANTES de
 * fusionarlo: cada clave conocida conserva su tipo en profundidad (número finito, booleano, texto, lista, objeto).
 * Las claves nuevas se aceptan (F-05). PHP puro, sin Laravel ni base.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/strategy_config_types_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

require getcwd() . '/app/Services/BacktestPayload.php';
$P = \App\Services\BacktestPayload::class;
$has = method_exists($P, 'configOverrideError');
$err = fn (array $base, array $o) => $has ? $P::configOverrideError($base, $o) : 'NO EXISTE';

$base = ['ema_fast' => 9, 'rsi_low' => 30.5, 'use_rsi' => true, 'mode' => 'cross', 'periods' => [5, 10, 20],
         'rsi' => ['period' => 14, 'levels' => [30, 70]], 'steps' => [[1.0, 0.5], [2.0, 1.0]], 'free' => null];

$check('T0: existe BacktestPayload::configOverrideError', $has);
$check('T1: tipos correctos (int↔float, bool, texto, listas, objeto) -> null',
    $err($base, ['ema_fast' => 12, 'rsi_low' => 25, 'use_rsi' => false, 'mode' => 'trend', 'periods' => [3, 7.5],
                 'rsi' => ['period' => 10, 'levels' => [25, 75]], 'steps' => [[1.5, 0.5]]]) === null);
$e = $err($base, ['ema_fast' => '20']);
$check('T2: «20» en texto donde se espera número -> error con la clave y lo recibido',
    is_string($e) && str_contains($e, '«ema_fast» debe ser un número') && str_contains($e, '"20"'), $e);
$e = $err($base, ['use_rsi' => 'false']);
$check('T3: «false» en texto donde se espera booleano -> error', is_string($e) && str_contains($e, '«use_rsi» debe ser true o false'), $e);
$e = $err($base, ['use_rsi' => 0]);
$check('T4: 0 donde se espera booleano -> error (no se convierte)', is_string($e) && str_contains($e, 'use_rsi'), $e);
$e = $err($base, ['ema_fast' => true]);
$check('T5: true donde se espera número -> error', is_string($e) && str_contains($e, '«ema_fast» debe ser un número'), $e);
$e = $err($base, ['rsi' => ['period' => '14']]);
$check('T6: anidado: «rsi.period» en texto -> error con la ruta', is_string($e) && str_contains($e, '«rsi.period»'), $e);
$e = $err($base, ['rsi' => ['levels' => [30, 'x']]]);
$check('T7: lista anidada: «rsi.levels[1]» -> error con la ruta', is_string($e) && str_contains($e, '«rsi.levels[1]»'), $e);
$e = $err($base, ['steps' => [[1.0, '0.5']]]);
$check('T8: lista de listas: «steps[0][1]» -> error', is_string($e) && str_contains($e, '«steps[0][1]»'), $e);
$e = $err($base, ['periods' => 20]);
$check('T9: número donde se espera lista -> error', is_string($e) && str_contains($e, '«periods» debe ser una lista'), $e);
$e = $err($base, ['rsi' => [14, 30]]);
$check('T10: lista donde se espera objeto -> error', is_string($e) && str_contains($e, '«rsi» debe ser un objeto'), $e);
$check('T11: clave nueva se acepta (F-05) y null en la base admite cualquier valor',
    $err($base, ['nueva' => 'x', 'free' => [1, 2]]) === null);
$check('T12: objeto vacío y lista vacía son válidos', $err($base, ['rsi' => [], 'periods' => []]) === null);

$ctl = file_get_contents(getcwd() . '/app/Http/Controllers/BacktestingController.php');
$v = strpos($ctl, 'configOverrideError(');
$m = strpos($ctl, 'mergeConfig((array)');
$check('C1: el controlador valida con configOverrideError ANTES de mergeConfig', $v !== false && $m !== false && $v < $m);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

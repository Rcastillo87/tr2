<?php
/**
 * R-14: el tick Real omitido (cuenta ocupada por el circuit breaker o la conciliación) llegaba como
 * ['signals' => 'texto'] y RealTradingTickJob::logAccountResults reventaba con array_filter (TypeError): cada tick
 * omitido quedaba como ERROR de PHP y no se distinguía del resto. Ahora App\Support\RealTickResults interpreta la
 * respuesta (pura, sin Laravel) y el job solo escribe sus líneas.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/real_tick_results_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

// Control: la lógica anterior con el omitido de un motor pre-p61 reproduce el TypeError visto en producción (13-nov)
$old = function (array $results): void {
    foreach ($results as $accountData) {
        $signals = $accountData['signals'] ?? [];
        array_filter($signals, fn ($r) => str_starts_with((string) $r, 'ABIERTA'));
    }
};
try {
    $old(['account_11_bybit' => ['signals' => 'la cuenta tiene otro proceso en curso: omitido']]);
    $check('R0-control: la lógica anterior reproduce el TypeError', false);
} catch (\TypeError $e) {
    $check('R0-control: la lógica anterior reproduce el TypeError', str_contains($e->getMessage(), 'array_filter'), $e->getMessage());
}

$file = getcwd() . '/app/Support/RealTickResults.php';
if (! is_file($file)) {
    $check('R1 existe App\\Support\\RealTickResults', false, $file);
    echo "\nRESULTADO: {$fails} FALLO(S)\n";
    exit(1);
}
require $file;
use App\Support\RealTickResults;

$lv = fn (array $lines) => array_map(fn ($l) => $l[0], $lines);

// R2. Omitido con la estructura nueva (p61): una advertencia, sin error
$l = RealTickResults::lines(['account_11_bybit' => ['skipped' => 'la cuenta tiene otro proceso en curso más de 15 s: tick omitido']]);
$check('R2 skipped -> 1 warning «tick omitido», ningún error', $lv($l) === ['warning'] && str_contains($l[0][1], 'tick omitido'), $l);

// R3. Omitido de un motor anterior (signals como texto): ya no revienta
try {
    $l = RealTickResults::lines(['account_11_bybit' => ['signals' => 'la cuenta tiene otro proceso en curso: omitido']]);
    $check('R3 signals como texto -> warning «tick omitido» (sin TypeError)', $lv($l) === ['warning'] && str_contains($l[0][1], 'omitido'), $l);
} catch (\Throwable $e) {
    $check('R3 signals como texto -> warning «tick omitido» (sin TypeError)', false, get_class($e) . ': ' . $e->getMessage());
}

// R4. Tick normal: mismo formato de siempre (resumen debug, abiertas info, errores error)
$l = RealTickResults::lines(['account_11_bybit' => [
    'monitor' => ['checked' => 2, 'closed' => 1, 'be_activated' => 0, 'errors' => 0],
    'signals' => ['VWAP' => 'ETHUSDT: ABIERTA long @ 1900', 'EMA' => 'BTCUSDT: sin señal', 'X' => 'ERROR: algo', 'Y' => 'SOLUSDT: sin señal'],
]]);
$debug = array_values(array_filter($l, fn ($x) => $x[0] === 'debug'));
$check('R4 resumen idéntico al de siempre', count($debug) === 1
    && $debug[0][1] === 'RealTrading tick: account_11_bybit | monitoreadas:2 cerradas:1 nuevas:0 errores:1 sin_senal:2', $debug);
$check('R4 cerradas (info) y error de señal (error)', in_array(['info', 'RealTrading account_11_bybit: 1 posicion(es) cerrada(s)'], $l, true)
    && in_array(['error', 'RealTrading ERROR: account_11_bybit | X -> ERROR: algo'], $l, true), $l);

// R5. Error de cuenta y respuesta que no es un objeto
$l = RealTickResults::lines(['a' => ['error' => 'Bybit rechaza las claves API: x'], 'b' => 'texto suelto']);
$check('R5 error de cuenta -> error; respuesta no-objeto -> warning', $lv($l) === ['error', 'warning'], $l);

// R6. El job delega en la clase (no conserva la lógica anterior)
$job = (string) file_get_contents(getcwd() . '/app/Jobs/RealTradingTickJob.php');
$check('R6 RealTradingTickJob::logAccountResults usa RealTickResults::lines y no array_filter',
    str_contains($job, 'RealTickResults::lines($results)') && ! str_contains($job, 'array_filter('));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

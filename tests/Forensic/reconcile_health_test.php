<?php
/**
 * C5-07 (p100): la conciliación de Real con fallos se ve (App\Support\ReconcileHealth + RealTradingReconcileJob).
 * A. Puro: errores de la respuesta del motor y regla del aviso (10 min seguidos con fallos → avisar; sin fallos → cerrar).
 * B. Estático: el job registra cada error, cuenta HTTP no exitoso y excepciones como fallo, y abre / cierra el incidente.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/reconcile_health_test.php
 */
declare(strict_types=1);

require getcwd() . '/app/Support/ReconcileHealth.php';

use App\Support\ReconcileHealth as H;

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

// A. errores de la respuesta
$check('A1: completa y sin errores: ninguno', H::errors(['status' => 'ok', 'complete' => true, 'results' => ['errors' => []]]) === []);
$e = H::errors(['complete' => false, 'results' => ['errors' => [
    ['trade_id' => 41, 'symbol' => 'BTCUSDT', 'note' => 'orphaned_api_error'],
    ['account_id' => 7, 'note' => 'error inesperado', 'error' => 'RuntimeError: x'],
    ['account_id' => 11, 'symbol' => 'ETHUSDT', 'error' => 'timeout'],
]]]);
$check('A2: cada error con su operación o cuenta', $e === ['#41 BTCUSDT: orphaned_api_error', 'cuenta #7: error inesperado',
    'cuenta #11 ETHUSDT: timeout'], $e);
$check('A3: respuesta ilegible es fallo', H::errors(null) === ['respuesta del motor ilegible']);
$check('A4: motor que dice incompleta sin detalle también es fallo', H::errors(['complete' => false, 'results' => []]) !== []);
$check('A5: motor anterior a p100 (sin complete ni errors) no es fallo', H::errors(['status' => 'ok', 'results' => ['ok' => []]]) === []);
$long = H::errors(['results' => ['errors' => [['trade_id' => 1, 'error' => str_repeat('x', 500)]]]]);
$check('A6: texto largo recortado', mb_strlen($long[0]) < 220, mb_strlen($long[0]));

// A. regla del aviso
$t0 = new DateTimeImmutable('2026-11-23T20:00:00+00:00');
$d = H::decide(null, true, $t0);
$check('A7: primer fallo: guarda la hora y no avisa todavía', $d['since'] === $t0->format(DATE_ATOM) && $d['action'] === null, $d);
$d = H::decide($t0->format(DATE_ATOM), true, $t0->modify('+9 minutes'));
$check('A8: 9 min con fallos: no avisa', $d['action'] === null && $d['since'] === $t0->format(DATE_ATOM), $d);
$d = H::decide($t0->format(DATE_ATOM), true, $t0->modify('+10 minutes'));
$check('A9: 10 min con fallos: avisa (conserva la hora del primer fallo)', $d['action'] === 'open' && $d['since'] === $t0->format(DATE_ATOM), $d);
$d = H::decide($t0->format(DATE_ATOM), false, $t0->modify('+12 minutes'));
$check('A10: conciliación completa: borra la racha y cierra el aviso', $d['since'] === null && $d['action'] === 'resolve', $d);
$check('A11: el umbral es 10 min', H::ALERT_AFTER_MIN === 10);

// B. el job
$job = file_get_contents(getcwd() . '/app/Jobs/RealTradingReconcileJob.php');
$check('B1: registra cada error de la respuesta', str_contains($job, '$errors = ReconcileHealth::errors(is_array($data) ? $data : null);')
    && str_contains($job, 'Log::warning("Reconciliacion: sin verificar — {$err}");'));
$check('B2: HTTP no exitoso, respuesta con errores y excepción cuentan como fallo',
    str_contains($job, '$this->track(true, ["el motor respondió HTTP {$response->status()}"]);')
    && str_contains($job, '$this->track($errors !== [], $errors);')
    && str_contains($job, "\$this->track(true, ['la conciliación no terminó: '"));
$check('B3: abre y cierra el mismo incidente real_reconcile', str_contains($job, "->openIncident('real_reconcile', 'error', 'broker'")
    && str_contains($job, "->resolveIncident('real_reconcile', 'broker'"));
$check('B4: la hora del primer fallo vive en caché y un fallo de los avisos no tumba el job',
    str_contains($job, 'Cache::put(self::FAILING_SINCE_KEY') && str_contains($job, 'Cache::forget(self::FAILING_SINCE_KEY)')
    && preg_match('/private function track\(.*?try \{.*?catch \(Throwable \$e\)/s', $job) === 1);

echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);

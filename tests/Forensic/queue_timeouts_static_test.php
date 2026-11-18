<?php
/**
 * R-08 (p68): regla de Laravel para cada trabajo en cola: espera HTTP < timeout del trabajo < retry_after de su
 * conexión. Si el trabajo dura más que retry_after, la cola lo da por perdido y lo reencola mientras sigue corriendo
 * (con tries=1 la copia termina fallida: MaxAttemptsExceeded; así fallaron 2 CollectOhlcvDataJob el 26-oct).
 * Conexiones: 'redis' (retry_after por defecto 90) y la de búsquedas (ParamSearchService::QUEUE_CONNECTION).
 * PHP puro: lee config/queue.php, los jobs y dónde se despachan.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/queue_timeouts_static_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$root = getcwd();
$read = fn (string $f) => (string) @file_get_contents("{$root}/{$f}");

$queue = $read('config/queue.php');
preg_match("/'redis'\s*=>\s*\[.*?'retry_after'\s*=>\s*\(int\)\s*env\('REDIS_QUEUE_RETRY_AFTER',\s*(\d+)\)/s", $queue, $m);
$retryRedis = isset($m[1]) ? (int) $m[1] : 0;
$svc = $read('app/Services/ParamSearchService.php');
preg_match("/QUEUE_CONNECTION\s*=\s*'([^']+)'/", $svc, $c);
$researchConn = $c[1] ?? '';
preg_match("/'" . preg_quote($researchConn, '/') . "'\s*=>\s*\[.*?'retry_after'\s*=>\s*(\d+)/s", $queue, $r);
$retryResearch = isset($r[1]) ? (int) $r[1] : 0;
$check('Q0 retry_after leídos de config/queue.php', $retryRedis > 0 && $retryResearch > 0,
    ['redis' => $retryRedis, $researchConn => $retryResearch]);

// Trabajos despachados en la conexión de búsquedas (todo lo demás va a 'redis')
$research = [];
foreach (['routes/console.php', 'app/Http/Controllers/ParamSearchController.php', 'app/Services/ParamSearchService.php'] as $f) {
    $code = $read($f);
    if (preg_match_all('/(\w+Job)(?:::dispatch\(|\()[^;]*?(?:QUEUE_CONNECTION|' . preg_quote($researchConn, '/') . ')/s', $code, $mm)) {
        $research = array_merge($research, $mm[1]);
    }
}
$research = array_values(array_unique($research));
$check('Q1 se reconocen los trabajos de la conexión de búsquedas', count($research) >= 2, $research);

foreach (glob("{$root}/app/Jobs/*.php") as $file) {
    $job = basename($file, '.php');
    $code = (string) file_get_contents($file);
    $timeout = preg_match('/public int \$timeout\s*=\s*(\d+)/', $code, $t) ? (int) $t[1] : 60;   // supervisor: 60
    $retry = in_array($job, $research, true) ? $retryResearch : $retryRedis;
    $http = preg_match_all('/->timeout\((\d+)\)/', $code, $h) ? max(array_map('intval', $h[1])) : null;
    $okRetry = $timeout < $retry;
    $okHttp = $http === null || $http < $timeout;
    $check("J {$job}: HTTP " . ($http ?? '-') . " < trabajo {$timeout} < retry_after {$retry}", $okRetry && $okHttp);
}

$rec = $read('app/Jobs/RealTradingReconcileJob.php');
$check('R1 conciliación: trabajo 85 s y HTTP 75 s', str_contains($rec, 'public int $timeout = 85;') && str_contains($rec, '->timeout(75)->post('));

echo 'RESULTADO: ' . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

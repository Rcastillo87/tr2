<?php
/**
 * R-07 (p65): los jobs Real no escriben en laravel.log las claves del broker aunque el motor las devuelva.
 * App\Support\SafeLogBody tapa api_key/api_secret/secret/password/token (JSON y texto) y recorta; los 3 jobs Real
 * (tick por cuenta, conciliación, circuit breaker) la usan para el cuerpo de una respuesta no exitosa. PHP puro.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/safe_log_body_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$root = getcwd();
$cls = $root . '/app/Support/SafeLogBody.php';
$check('B0 existe App\Support\SafeLogBody', is_file($cls));
if (! is_file($cls)) {
    echo "RESULTADO: {$fails} FALLO(S)\n";
    exit(1);
}
require $cls;
use App\Support\SafeLogBody;

$S = 'SECRET-r07-no-debe-salir';
$K = 'KEY-r07';
// 422 por defecto de FastAPI (forma real, con 'input' que repite la cuenta)
$fastapi = json_encode(['detail' => [['type' => 'missing', 'loc' => ['body', 'accounts', 0, 'subscriptions'], 'msg' => 'Field required',
    'input' => ['id' => 11, 'broker' => 'bybit', 'api_key' => $K, 'api_secret' => $S]]]]);
$out = SafeLogBody::of($fastapi);
$check('B1 422 de FastAPI: sin clave ni secreto', ! str_contains($out, $S) && ! str_contains($out, $K), $out);
$check('B2 conserva lo útil (qué campo falta y el mensaje)', str_contains($out, 'subscriptions') && str_contains($out, 'Field required')
    && str_contains($out, '"api_secret":"***"'), $out);
$check('B3 JSON con espacios y comillas escapadas dentro del secreto',
    ! str_contains(SafeLogBody::of('{"api_secret" : "a\\"b' . $S . '", "x": 1}'), $S));
$check('B4 texto plano api_key=… / secret: … / password=…',
    ! preg_match('/' . $S . '|' . $K . '/', SafeLogBody::of("api_key={$K}&secret: {$S} password={$S}")),
    SafeLogBody::of("api_key={$K}&secret: {$S} password={$S}"));
$check('B5 variantes de nombre (apiSecret, X-Api-Key, broker_api_secret)',
    ! str_contains(SafeLogBody::of('{"apiSecret":"' . $S . '","X-Api-Key":"' . $S . '","broker_api_secret":"' . $S . '"}'), $S));
$plain = '{"status":"ok","results":[{"account":"account_11_bybit","signals":[]}]}';
$check('B6 respuesta sin claves: intacta', SafeLogBody::of($plain) === $plain);
$long = str_repeat('x', 5000);
$o = SafeLogBody::of($long);
$check('B7 recorta respuestas largas (máx. 2000 + marca)', mb_strlen($o) < 2100 && str_ends_with($o, '[recortado]'), mb_strlen($o));
$check('B8 null y vacío no rompen', SafeLogBody::of(null) === '' && SafeLogBody::of('') === '');

// Los 3 jobs Real usan SafeLogBody para el cuerpo; ninguno escribe $response->body() crudo
foreach (['RealTradingAccountTickJob', 'RealTradingReconcileJob', 'CircuitBreakerMaxLossJob'] as $job) {
    $code = (string) @file_get_contents("{$root}/app/Jobs/{$job}.php");
    $raw = preg_match("/'body'\s*=>\s*\\\$response->body\(\)/", $code);
    $check("B9 {$job}: registra el cuerpo con SafeLogBody::of, nunca crudo",
        $code !== '' && ! $raw && str_contains($code, 'SafeLogBody::of($response->body())'));
}

echo 'RESULTADO: ' . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

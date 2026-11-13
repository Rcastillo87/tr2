<?php
/**
 * R-03 (p63): precios del dashboard. La consulta de las 2 últimas velas de 1m por moneda debe ir acotada al último día
 * (usa el índice; antes ROW_NUMBER recorría toda la serie: ~0,39 s por moneda en producción) y, si en ese día hay
 * menos de 2 velas (collector detenido o recién reanudado), repetir sin límite: resultado idéntico al anterior.
 * PHP puro: extrae lastTwoMinuteCloses() del controlador y la ejecuta contra un DB falso que registra las consultas.
 * La equivalencia contra la base real la verifica el instalador en una sola consulta.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/dashboard_prices_static_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$code = (string) @file_get_contents(getcwd() . '/app/Http/Controllers/DashboardController.php');
$check('D0 el controlador existe', $code !== '');
$p = strpos($code, 'private static function lastTwoMinuteCloses(');
$check('D1 existe lastTwoMinuteCloses() y la usa el bucle de precios',
    $p !== false && str_contains($code, 'self::lastTwoMinuteCloses($sym)'));
$check('D2 ya no queda la consulta ROW_NUMBER sobre toda la serie', !preg_match('/ROW_NUMBER\(\)\s+OVER/i', $code));
if ($p === false) {
    echo "RESULTADO: {$fails} FALLO(S)\n";
    exit(1);
}

// Extrae el método (hasta el siguiente método) y lo monta en una clase de prueba
$next = strpos($code, "\n    public function ", $p);
$body = substr($code, $p, $next === false ? null : $next - $p);
$body = rtrim($body);

class DB
{
    /** @var array<int, array{0:string,1:array}> */
    public static array $calls = [];
    /** @var array<int, array> respuestas en orden */
    public static array $answers = [];

    public static function select(string $sql, array $bindings = []): array
    {
        self::$calls[] = [$sql, $bindings];
        return array_shift(self::$answers) ?? [];
    }
}

eval('final class R03Probe { ' . str_replace('private static function', 'public static function', $body) . ' }');

$row = fn ($c) => (object) ['close' => $c];
$run = function (array $answers) {
    DB::$calls = [];
    DB::$answers = $answers;
    return R03Probe::lastTwoMinuteCloses('BTCUSDT');
};

// Caso normal: 2 velas en el último día → 1 sola consulta, acotada, LIMIT 2, con el símbolo como parámetro
$r = $run([[$row(101), $row(100)]]);
$sql0 = DB::$calls[0][0] ?? '';
$check('D3 normal: una sola consulta', count(DB::$calls) === 1, count(DB::$calls));
$check('D4 normal: acotada al último día, ORDER BY time DESC LIMIT 2, filtros broker/intervalo',
    str_contains($sql0, "time > now() - interval '1 day'") && str_contains($sql0, 'ORDER BY time DESC LIMIT 2')
    && str_contains($sql0, "broker = 'bybit'") && str_contains($sql0, "interval = '1'"), $sql0);
$check('D5 normal: el símbolo va como parámetro (no concatenado)',
    (DB::$calls[0][1] ?? null) === ['BTCUSDT'] && !str_contains($sql0, 'BTCUSDT'));
$check('D6 normal: devuelve las filas tal cual', count($r) === 2 && $r[0]->close === 101 && $r[1]->close === 100);

// Collector reanudado: 1 vela en el día → repite sin límite y devuelve ese resultado
$r = $run([[$row(999)], [$row(999), $row(321)]]);
$sql1 = DB::$calls[1][0] ?? '';
$check('D7 reanudado (1 vela en el día): repite la consulta', count(DB::$calls) === 2, count(DB::$calls));
$check('D8 la repetición no tiene límite de tiempo y mantiene LIMIT 2 y el parámetro',
    !str_contains($sql1, 'now()') && str_contains($sql1, 'ORDER BY time DESC LIMIT 2') && (DB::$calls[1][1] ?? null) === ['BTCUSDT'], $sql1);
$check('D9 reanudado: devuelve las 2 velas de la repetición', count($r) === 2 && $r[1]->close === 321);

// Collector detenido: 0 velas en el día → repite; moneda sin datos → vacío (como antes)
$r = $run([[], [$row(248), $row(277)]]);
$check('D10 detenido (0 velas en el día): repite y devuelve las últimas 2', count(DB::$calls) === 2 && count($r) === 2);
$r = $run([[], []]);
$check('D11 moneda sin datos: vacío, sin error', $r === [] && count(DB::$calls) === 2);

echo 'RESULTADO: ' . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

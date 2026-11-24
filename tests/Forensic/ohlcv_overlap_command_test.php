<?php
/**
 * C6-05: comando `ohlcv:overlap-check` (PHP puro, sin base). La consulta se prueba contra PostgreSQL en
 * ohlcv_overlap_check_test.py.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/ohlcv_overlap_command_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$file = "{$root}/app/Console/Commands/OhlcvOverlapCheck.php";
$check('K0: existe el comando', is_file($file));
if (is_file($file)) {
    eval('?>' . preg_replace('/^use Illuminate\\\\Console\\\\Command;$/m', '', str_replace('extends Command', '', file_get_contents($file))));
    $C = App\Console\Commands\OhlcvOverlapCheck::class;
    $check('K1: temporalidades legibles', $C::tf('1') === '1m' && $C::tf('5') === '5m' && $C::tf('60') === '1h'
        && $C::tf('240') === '4h' && $C::tf('D') === '1D');
    $s = $C::summarize([
        ['chunk' => '_hyper_1_123_chunk', 'symbol' => 'BTCUSDT', 'interval' => '1', 'lotes' => 8],
        ['chunk' => '_hyper_1_123_chunk', 'symbol' => 'SOLUSDT', 'interval' => '1', 'lotes' => 10],
        ['chunk' => '_hyper_1_124_chunk', 'symbol' => 'ETHUSDT', 'interval' => '5', 'lotes' => 1],
    ]);
    $check('K2: el aviso identifica fragmento, moneda, temporalidad y lotes',
        $s === '_hyper_1_123_chunk: BTCUSDT 1m (8), SOLUSDT 1m (10) · _hyper_1_124_chunk: ETHUSDT 5m (1)', $s);
}
$src = is_file($file) ? file_get_contents($file) : '';
$check('K3: corre en una transacción de solo lectura', str_contains($src, "DB::statement('SET TRANSACTION READ ONLY')"));
$check('K4: nunca repara (sin decompress_chunk / compress_chunk en el código)', ! preg_match('/\b(decompress_chunk|compress_chunk)\s*\(/', $src));
$check('K5: con solapes abre el aviso; sin solapes lo cierra; si falla no toca el aviso',
    preg_match("/^\\s*\\\$alerts->openIncident\\(self::INCIDENT, 'warning', 'collector'/m", $src)
    && preg_match('/^\\s*\\$alerts->resolveIncident\\(self::INCIDENT/m', $src)
    && preg_match('/catch \(\\\\Throwable \$e\).*?return self::FAILURE;/s', $src));
$check('K6: usa la consulta del archivo SQL compartido con la prueba de PostgreSQL',
    str_contains($src, "public const SQL_FILE = 'database/sql/ohlcv_overlap_batches.sql'") && is_file("{$root}/database/sql/ohlcv_overlap_batches.sql"));
$check('K7: recorre solo los fragmentos comprimidos de ohlcv_data', str_contains($src, "WHERE h.table_name = 'ohlcv_data'")
    && str_contains($src, 'c2.id = c.compressed_chunk_id'));
$cons = file_get_contents("{$root}/routes/console.php");
$check('K8: programado cada 3 h a los :10 (tras la compresión de las 05:38 / 17:38 UTC)',
    str_contains($cons, "Schedule::command('ohlcv:overlap-check')->cron('10 */3 * * *')"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * RQ-01.3 (PHP puro): origen de cada backtest.
 * - BacktestOrigin::forNewBacktest: «search» solo con una foto de búsqueda válida; cualquier otra cosa = manual.
 * - describe(): texto de pantalla (manual / búsqueda / «Origen no registrado»).
 * - Cableado (estático): el guardado toma el origen del atributo INTERNO de la petición (no de input()), solo al
 *   crear el backtest; BacktestFromSearch lo pone y el job le pasa la foto de su búsqueda.
 * La prueba contra la base real (transacción revertida) es backtest_origin_save_test.php.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/backtest_origin_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$root = getcwd();
$file = "{$root}/app/Support/BacktestOrigin.php";
$check('O0: existe App\Support\BacktestOrigin', is_file($file));
if (is_file($file)) {
    require $file;
}

if (class_exists('App\Support\BacktestOrigin')) {
    $O = 'App\Support\BacktestOrigin';
    $meta = $O::fromSearch(12, 'r34', 'gain', 'robust', 'survivors', '2026-11-08T14:00:00+00:00');

    $n = $O::forNewBacktest($meta);
    $check('O1: foto de búsqueda válida -> search con run, fila, foco, modo, monedas, fecha de búsqueda y de creación',
        $n['origin'] === 'search' && $n['origin_meta']['run_id'] === 12 && $n['origin_meta']['row_id'] === 'r34'
        && $n['origin_meta']['focus'] === 'gain' && $n['origin_meta']['mode'] === 'robust'
        && $n['origin_meta']['symbols_mode'] === 'survivors' && $n['origin_meta']['search_at'] === '2026-11-08T14:00:00+00:00'
        && strtotime((string) ($n['origin_meta']['created_at'] ?? '')) !== false, $n);

    $check('O2: sin atributo -> manual sin foto', $O::forNewBacktest(null) === ['origin' => 'manual', 'origin_meta' => null]);
    $bad = [
        'texto'           => 'search',
        'run_id texto'    => ['run_id' => '12', 'row_id' => 'r1'],
        'run_id 0'        => ['run_id' => 0, 'row_id' => 'r1'],
        'sin fila'        => ['run_id' => 12],
        'fila vacía'      => ['run_id' => 12, 'row_id' => ''],
        'lista'           => [12, 'r1'],
    ];
    $wrong = [];
    foreach ($bad as $k => $v) {
        if ($O::forNewBacktest($v)['origin'] !== 'manual') {
            $wrong[] = $k;
        }
    }
    $check('O3: atributo inválido (texto, run_id no entero o 0, sin fila, fila vacía, lista) -> manual', $wrong === [], $wrong);

    $x = $O::forNewBacktest($meta + ['origin' => 'manual', 'evil' => '<script>']);
    $check('O4: la foto guarda solo las claves conocidas', ! array_key_exists('evil', $x['origin_meta'])
        && ! array_key_exists('origin', $x['origin_meta']), array_keys($x['origin_meta']));

    $check('O5: describe manual', $O::describe('manual', null) === 'Manual (pantalla de backtesting)');
    $check('O6: describe null / desconocido -> «Origen no registrado»',
        $O::describe(null, null) === 'Origen no registrado' && $O::describe('otro', ['run_id' => 1]) === 'Origen no registrado');
    $d = $O::describe('search', $n['origin_meta']);
    $check('O7: describe búsqueda = «Búsqueda #12 · fila r34 · foco gain · modo robust · 2026-11-08»',
        $d === 'Búsqueda #12 · fila r34 · foco gain · modo robust · 2026-11-08', $d);
    $d = $O::describe('search', ['run_id' => 7, 'row_id' => 'r1', 'focus' => 'wr', 'mode' => null,
                                 'search_at' => '2026-10-31T12:00:00+00:00', 'recovered' => true]);
    $check('O8: recuperado del historial, sin modo', $d === 'Búsqueda #7 · fila r1 · foco wr · 2026-10-31 (recuperado del historial de la búsqueda)', $d);
}

// Cableado (estático)
$ctl = (string) @file_get_contents("{$root}/app/Http/Controllers/BacktestingController.php");
preg_match('/public function saveBacktest\(.*?\n    }\n/s', $ctl, $m);
$save = $m[0] ?? '';
$check('W1: saveBacktest lee el origen de $request->attributes (interno), nunca de input()',
    str_contains($save, '$request->attributes->get(BacktestOrigin::REQUEST_ATTRIBUTE)')
    && ! preg_match('/input\(\s*[\'"]origin/', $save));
$check('W2: el origen se fija solo al crear (new Backtest(BacktestOrigin::forNewBacktest(...)) dentro de if ($backtest === null))',
    (bool) preg_match('/if \(\$backtest === null\) \{[^}]*new Backtest\(BacktestOrigin::forNewBacktest\(\$origin\)\)/s', $save)
    && ! preg_match("/fill\(\[[^\]]*'origin/s", $save));
$svc = (string) @file_get_contents("{$root}/app/Services/BacktestFromSearch.php");
$check('W3: BacktestFromSearch pone la foto como atributo interno de la petición de guardado',
    str_contains($svc, '$req->attributes->set(BacktestOrigin::REQUEST_ATTRIBUTE, $origin)'));
$job = (string) @file_get_contents("{$root}/app/Jobs/CreateBacktestsFromSearchJob.php");
$check('W4: el job pasa BacktestOrigin::fromSearch(run, fila, foco, modo, monedas, fecha) a run()',
    (bool) preg_match('/BacktestOrigin::fromSearch\(\$run->id, \(string\) \$rowId, \$run->focus, \$run->mode,\s*\$this->symbolsMode/', $job)
    && (bool) preg_match('/\(int\) \$run->months, true, \$origin\)/', $job));
$model = (string) @file_get_contents("{$root}/app/Models/Backtest.php");
$check('W5: Backtest: origin y origin_meta asignables, origin_meta como array',
    str_contains($model, "'origin', 'origin_meta'") && str_contains($model, "'origin_meta' => 'array'"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * RQ-01.2 (PHP puro): «Crear en historial» desde una búsqueda.
 * - reconcileCreated: una fila «creada» cuyo backtest ya no existe vuelve a estar disponible (deleted); una creación
 *   en curso que se quedó colgada más de CREATE_STALE_AFTER_S pasa a error (disponible); lo demás no cambia.
 * - creationBlock: done y running bloquean; deleted, error y nada no.
 * - Cableado (estático): results() concilia y no expone el token; create() bloquea la búsqueda, rechaza lo creado o
 *   en curso y reserva con token antes de encolar; el job salta filas ajenas y libera las suyas si muere.
 * La prueba contra la base real (transacción revertida) es search_create_guard_test.php.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/search_create_rules_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$root = getcwd();
require "{$root}/app/Services/ParamSearchService.php";
$S = 'App\Services\ParamSearchService';
$has = method_exists($S, 'reconcileCreated') && method_exists($S, 'creationBlock') && defined("{$S}::CREATE_STALE_AFTER_S");
$check('R0: ParamSearchService::reconcileCreated, creationBlock y CREATE_STALE_AFTER_S existen', $has);

if ($has) {
    $now = strtotime('2026-11-11T12:00:00Z');
    $ago = fn (int $s) => gmdate('Y-m-d\TH:i:s+00:00', $now - $s);
    $stale = $S::CREATE_STALE_AFTER_S;
    $created = [
        'a' => ['status' => 'done', 'backtest_id' => 10, 'at' => $ago(60)],
        'b' => ['status' => 'done', 'backtest_id' => 11, 'at' => $ago(60)],          // borrado
        'c' => ['status' => 'done', 'backtest_id' => '12', 'at' => $ago(60)],        // id como texto, existe
        'd' => ['status' => 'done', 'backtest_id' => null, 'message' => 'x'],        // sin id
        'e' => ['status' => 'running', 'at' => $ago(600)],
        'f' => ['status' => 'running', 'at' => $ago($stale + 1)],
        'g' => ['status' => 'running'],                                               // sin fecha
        'h' => ['status' => 'error', 'error' => 'falló'],
        'i' => 'basura',
    ];
    $r = $S::reconcileCreated($created, [10, 12], $now);

    $check('R1: done con backtest existente -> sigue done (id entero y texto)', ($r['a']['status'] ?? '') === 'done'
        && ($r['c']['status'] ?? '') === 'done', [$r['a']['status'] ?? null, $r['c']['status'] ?? null]);
    $check('R2: done cuyo backtest se borró -> deleted, conserva el id anterior', ($r['b']['status'] ?? '') === 'deleted'
        && ($r['b']['backtest_id'] ?? null) === 11 && ($r['b']['previous_status'] ?? '') === 'done', $r['b'] ?? null);
    $check('R3: done sin id -> deleted (no se puede verificar: se puede volver a crear)', ($r['d']['status'] ?? '') === 'deleted');
    $check('R4: running reciente -> sigue running', ($r['e']['status'] ?? '') === 'running');
    $check('R5: running más viejo que el límite o sin fecha -> error disponible', ($r['f']['status'] ?? '') === 'error'
        && ($r['g']['status'] ?? '') === 'error' && str_contains($r['f']['error'] ?? '', 'volver a crear'), [$r['f'] ?? null, $r['g'] ?? null]);
    $check('R6: error queda igual; entrada que no es objeto se ignora', ($r['h'] ?? null) === $created['h'] && ! isset($r['i']));
    $check('R7: el límite cubre la espera en cola tras una búsqueda larga (MAX_MINUTES) + timeout del job (3900 s)',
        $stale > $S::MAX_MINUTES * 60 + 3900, $stale);

    $check('B1: done y running bloquean; deleted, error y sin estado no',
        $S::creationBlock($r['a']) !== null && $S::creationBlock($r['e']) !== null && $S::creationBlock($r['b']) === null
        && $S::creationBlock($r['f']) === null && $S::creationBlock(null) === null);
    $check('B2: el motivo de done nombra el backtest', str_contains((string) $S::creationBlock($r['a']), '#10'), $S::creationBlock($r['a']));
}

// Cableado (estático)
$ctl = (string) @file_get_contents("{$root}/app/Http/Controllers/ParamSearchController.php");
preg_match('/public function results\(.*?\n    }\n/s', $ctl, $m);
$res = $m[0] ?? '';
preg_match('/public function create\(.*?\n    }\n/s', $ctl, $m);
$cre = $m[0] ?? '';
$check('W1: results() usa createdStates() y no expone el token',
    str_contains($res, '$this->service->createdStates($run)') && str_contains($res, "array_diff_key(\$created[\$row['id']], ['token' => true])")
    && ! str_contains($res, "\$run->results['created']"));
$lock = strpos($cre, 'lockForUpdate()');
$blk = strpos($cre, 'ParamSearchService::creationBlock(');
$mark = strpos($cre, 'ParamSearchService::markCreated(');
$disp = strpos($cre, 'CreateBacktestsFromSearchJob::dispatch(');
$check('W2: create(): bloquea la búsqueda -> rechaza creado/en curso -> reserva -> encola (en ese orden)',
    $lock !== false && $blk !== false && $mark !== false && $disp !== false && $lock < $blk && $blk < $mark && $mark < $disp
    && str_contains($cre, 'DB::transaction('), [$lock, $blk, $mark, $disp]);
$check('W3: create() reserva con token y lo pasa al job; ids sin repetir', str_contains($cre, "'token' => \$token")
    && (bool) preg_match('/dispatch\(\$run->id, \$ids, \$data\[\'symbols\'\], \$request->user\(\)->id, \$token\)/', $cre)
    && str_contains($cre, 'array_unique($data[\'rows\'])'));
$job = (string) @file_get_contents("{$root}/app/Jobs/CreateBacktestsFromSearchJob.php");
$check('W4: el job salta filas creadas o ajenas antes de crear y marca su token al empezar',
    (bool) preg_match('/creationBlock\(\$state\) !== null && ! \$this->ownsReservation\(\$state\)\) \{\s*continue;/', $job)
    && str_contains($job, "'status' => 'running', 'symbols' => \$symbols, 'token' => \$this->token"));
$check('W5: el job libera sus filas si muere (failed) o si la búsqueda ya no sirve',
    (bool) preg_match('/public function failed\(\?Throwable \$e\): void\s*\{\s*\$this->releaseReservations\(/', $job)
    && str_contains($job, "\$this->releaseReservations(\$service, 'La búsqueda o el usuario ya no están disponibles.')"));
$check('W6: un solo lugar escribe results.created (markCreated)', substr_count($job . $ctl, "jsonb_set(") === 0
    && str_contains($job, 'ParamSearchService::markCreated('));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

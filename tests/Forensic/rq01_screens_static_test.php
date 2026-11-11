<?php
/**
 * RQ-01 pantallas (PHP puro, sin Laravel): el cableado de las vistas no se pierde en un cambio posterior.
 * La prueba que renderiza con la base real es rq01_screens_test.php (corre al instalar).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/rq01_screens_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$read = fn (string $p) => (string) @file_get_contents("{$root}/{$p}");

$sc = $read('app/Http/Controllers/StrategyController.php');
$si = $read('resources/views/strategies/index.blade.php');
$check('E1: Estrategias: conteo de Paper en UNA consulta agregada (sin N+1) y por config',
    str_contains($sc, "count(*) FILTER (WHERE status = 'open')") && str_contains($sc, "->groupBy('paper_strategy_config_id')")
    && str_contains($sc, "'paperByBacktest'"));
$check('E2: Estrategias: Trades/mes (N/D si falta), abiertos/cerrados y enlace a history#bt-<id>',
    str_contains($si, 'Trades/mes:') && str_contains($si, "'N/D'") && str_contains($si, "sum('open')")
    && str_contains($si, "route('backtesting.history', \$s->id) }}#bt-{{ \$bt_obj->id }}"));

$bc = $read('app/Http/Controllers/BacktestingController.php');
$hv = $read('resources/views/backtesting/history.blade.php');
$sv = $read('app/Services/SavedBacktests.php');
$check('H1: Historial: ancla bt-<id> y resaltado con :target', str_contains($hv, 'id="bt-{{ $r[\'id\'] }}"')
    && str_contains($hv, '.bt-card:target'));
$check('H2: Historial: origen con BacktestOrigin::describe y enlace a la búsqueda solo si el usuario la puede ver',
    str_contains($sv, 'BacktestOrigin::describe($b->origin, $b->origin_meta)') && str_contains($hv, "@if(\$r['run_exists'] && \$canSearch)") && str_contains($sv, "DB::table('param_search_runs')->whereIn('id', \$runIds)")
    && str_contains($bc, "\$canSearch = Gate::allows('manageUsers')"));
$check('H3: Historial: Trades/mes con la misma regla que las configs (StrategyConfigSync::tradesPerMonth)',
    str_contains($sv, 'StrategyConfigSync::tradesPerMonth($m, $cp,') && str_contains($hv, "['Trades/mes', \$fmtTpm(\$r['tpm']), null]"));

$ps = $read('resources/views/param-search/show.blade.php');
$check('B1: Búsqueda: una sola función de insignia (createdBadge) para las dos vistas',
    substr_count($ps, 'function createdBadge(') === 1 && str_contains($ps, 'const st = createdBadge(r);')
    && substr_count($ps, '✓ Creado #') === 2);
$check('B2: Búsqueda: deleted -> «borrado · disponible»; done -> enlace al historial; queued -> En cola',
    str_contains($ps, "c.status === 'deleted'") && str_contains($ps, 'borrado · disponible')
    && str_contains($ps, '#bt-${id}') && str_contains($ps, "c.phase === 'queued'"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

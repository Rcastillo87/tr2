<?php
/**
 * D-70 (dueño, 25-nov): estrellas con UNA sola fórmula y resultados del backtest con UN solo retorno.
 * A: la fórmula (App\Helpers\RatingHelper) da la tabla aprobada con las 15 configs; bordes, topes y datos faltantes.
 * B: un backtest guardado = promedio de las estrellas de sus monedas; guardados viejos sin detalle ni DD.
 * C: meses con el retorno real (App\Support\BacktestMonths): el acumulado termina en el retorno de la moneda.
 * D: todas las pantallas usan la misma fórmula (backtest, historial, Estrategias, búsqueda, Paper/config, Real).
 * E: «24 meses» son 24 (sin desborde), el consolidado suma los retornos de las monedas, con una moneda no hay fila
 *    CONSOLIDADO y al guardar no se pierde el DD.
 * PHP puro. Uso: cd <raíz del proyecto> && php tests/Forensic/rating_unified_test.php
 */
declare(strict_types=1);

$root = getenv('TR2_TEST_ROOT') ?: getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$read = fn (string $f) => (string) @file_get_contents("{$root}/{$f}");

require_once "{$root}/app/Helpers/RatingHelper.php";
$R = App\Helpers\RatingHelper::class;
$new = method_exists($R, 'detail');
$check('A0: la fórmula nueva existe (RatingHelper::detail)', $new);

if ($new) {
    // ── A: la tabla aprobada (lectura del 25-nov: trades, PF, retorno, DD, meses positivos) ──
    $cfgs = [
        59 => [91, 1.22, 12.13, 6.84, 11, 23, 3.0], 61 => [40, 1.80, 14.82, 3.51, 12, 23, 4.0], 64 => [83, 1.13, 4.23, 8.20, 10, 23, 2.4],
        67 => [167, 1.16, 16.61, 12.27, 11, 23, 2.5], 68 => [145, 1.38, 27.14, 5.77, 16, 23, 4.0], 69 => [53, 1.55, 13.39, 5.00, 10, 23, 3.6],
        70 => [156, 1.25, 30.01, 11.83, 13, 23, 3.0], 71 => [85, 1.25, 11.44, 8.38, 16, 23, 3.1], 72 => [104, 1.23, 9.62, 4.35, 12, 23, 3.4],
        73 => [123, 1.43, 40.18, 17.26, 15, 23, 3.3], 74 => [356, 1.22, 61.23, 13.51, 14, 23, 3.5], 75 => [182, 1.36, 50.17, 8.06, 17, 23, 4.5],
        77 => [80, 1.67, 37.48, 6.49, 15, 23, 4.6], 78 => [160, 1.28, 14.90, 4.73, 13, 23, 3.7], 79 => [244, 1.13, 24.86, 15.42, 14, 23, 2.7],
    ];
    $bad = [];
    foreach ($cfgs as $id => [$n, $pf, $ret, $dd, $pos, $tot, $want]) {
        $got = $R::calculate($pf, $ret, $dd, $pos / $tot * 100, $n);
        if (abs($got - $want) > 1e-9) {
            $bad[$id] = [$got, $want];
        }
    }
    $check('A1: las 15 configs dan las estrellas de la tabla aprobada (2,4 a 4,6)', $bad === [], $bad);
    $d = $R::detail(1.80, 14.82, 3.51, 12 / 23 * 100, 40);
    $check('A2: BTC #61: notas PF 5, retorno÷caída 4, meses 3, caída 5; tope de 4 por menos de 50 operaciones',
        $d['parts'] === ['pf' => 5, 'recovery' => 4, 'consist' => 3, 'dd' => 5] && $d['rating'] === 4.0 && $d['cap'] === 'menos de 50 operaciones', $d);
    $check('A3: bordes de cada nota (el corte cuenta para la nota de arriba)',
        $R::detail(1.5, 10, 2, 70, 100)['parts'] === ['pf' => 5, 'recovery' => 5, 'consist' => 5, 'dd' => 5]
        && $R::detail(1.0, 5, 10, 40, 100)['parts'] === ['pf' => 2, 'recovery' => 2, 'consist' => 2, 'dd' => 3]
        && $R::detail(0.99, 1, 25.01, 39.9, 100)['parts'] === ['pf' => 1, 'recovery' => 1, 'consist' => 1, 'dd' => 1]);
    $check('A4: menos de 30 operaciones: máximo 2 (aunque todo sea excelente)', $R::calculate(3.0, 50, 2, 90, 29) === 2.0);
    $check('A5: sin ganancia: máximo 1,5', $R::calculate(1.6, 0.0, 2, 90, 200) === 1.5 && $R::calculate(1.6, -3.0, 2, 90, 200) === 1.5);
    $check('A6: sin pérdidas (PF vacío) con ganancia = nota 5 de PF; sin DD guardado = notas neutras (3)',
        $R::detail(null, 10, 3, 60, 100)['parts']['pf'] === 5
        && $R::detail(1.3, 10, null, 60, 100)['parts'] === ['pf' => 4, 'recovery' => 3, 'consist' => 4, 'dd' => 3]);
    $check('A7: nunca menos de 1 estrella; color igual que antes', $R::calculate(0.5, -50, 60, 0, 5) === 1.0
        && $R::getColor(4.0) === '#F5C518' && $R::getColor(1.9) === '#E24B4A' && $R::stars(3.6) === '★★★★☆');

    // ── B: backtests guardados ──
    $sol = ['total_trades' => 156, 'profit_factor' => 1.25, 'total_return_pct' => 30.01, 'max_drawdown_pct' => 11.83];
    $eth = ['total_trades' => 145, 'profit_factor' => 1.38, 'total_return_pct' => 27.14, 'max_drawdown_pct' => 5.77];
    $mk = fn (int $pos, int $tot) => array_map(fn ($i) => ['month' => sprintf('2025-%02d', $i % 12 + 1), 'total_pnl' => $i < $pos ? 10 : -10],
        range(0, $tot - 1));
    $multi = ['rating' => 1.1, 'individual_results' => [
        ['symbol' => 'SOLUSDT', 'aggregate_metrics' => $sol, 'monthly_breakdown' => $mk(13, 23)],
        ['symbol' => 'ETHUSDT', 'aggregate_metrics' => $eth, 'monthly_breakdown' => $mk(16, 23)],
    ]];
    $check('B1: un backtest de varias monedas = promedio de las estrellas de cada moneda (no la guardada)',
        $R::fromMetrics($multi) === round((3.0 + 4.0) / 2, 1), $R::fromMetrics($multi));
    $old = ['win_rate' => 0.44, 'profit_factor' => 1.25, 'total_return_pct' => 30.0, 'consist_pct' => 0.565, 'total_trades' => 156];
    $o = $R::forMetrics($old);
    $check('B2: guardado viejo sin detalle ni DD: consistencia en fracción pasa a %, DD neutro',
        abs($o['inputs']['consist'] - 56.5) < 1e-9 && $o['inputs']['dd'] === null && $o['parts']['dd'] === 3, $o);
    $check('B3: PF «sin pérdidas» guardado como 999.99 cuenta como sin pérdidas', $R::inputs(['profit_factor' => 999.99])['pf'] === null);
    $dt = $R::fromMetricsDetail($multi + ['profit_factor' => 1.31, 'consist_pct' => 60.9]);
    $check('B4: detalle para la tarjeta de Real: notas promedio de las monedas, PF del backtest, peor caída',
        $dt['values']['pf'] === 1.31 && $dt['values']['dd'] === 11.83 && $dt['rating'] === 3.5 && count($dt['parts']) === 4, $dt);
}

// ── C: meses con el retorno real ──
$f = "{$root}/app/Support/BacktestMonths.php";
$check('C0: existe App\Support\BacktestMonths', is_file($f));
if (is_file($f)) {
    require_once $f;
    $M = App\Support\BacktestMonths::class;
    $mb = [['month' => '2025-02', 'total_trades' => 3, 'wins' => 1, 'losses' => 2, 'total_pnl' => -1100.0, 'total_pnl_pct' => -10.0],
           ['month' => '2025-01', 'total_trades' => 4, 'wins' => 3, 'losses' => 1, 'total_pnl' => 1000.0, 'total_pnl_pct' => 9.8]];
    $r = $M::build($mb, 10000);
    $check('C1: cada mes sobre el saldo al empezar el mes; ordenados por mes', array_keys($r) === ['2025-01', '2025-02']
        && abs($r['2025-01']['pct'] - 10.0) < 1e-9 && abs($r['2025-02']['pct'] - (-10.0)) < 1e-9, $r);
    $check('C2: el acumulado termina en lo que creció la cuenta (−1 %: +10 % y −10 % no dan 0)',
        abs($r['2025-02']['acum'] - (-1.0)) < 1e-9 && $r['2025-01']['trades'] === 4);
    // SOL: el acumulado coincide con el retorno de la moneda (antes 27,91 % contra 30,01 %)
    $pnls = [869, 278, -236, -18, -87, 209, -194, 207, 542, -261, 211, 573, -85, 320, 540, 275, 458, -304, 456, 170, -45, -488, -599];
    $rows = [];
    foreach ($pnls as $i => $p) {
        $rows[] = ['month' => sprintf('%04d-%02d', 2024 + intdiv($i + 11, 12), ($i + 11) % 12 + 1), 'total_pnl' => (float) $p];
    }
    $s = $M::build($rows, 10000);
    $last = end($s);
    $check('C3: con una moneda, el último acumulado = retorno de la moneda (ganancia total ÷ saldo inicial)',
        abs($last['acum'] - array_sum($pnls) / 10000 * 100) < 1e-9, $last['acum']);
    $st = $M::stats($s);
    $check('C4: meses positivos y promedio con esos meses', $st['consist'] === round(13 / 23 * 100, 1) && is_float($st['avg']), $st);
    $f2 = $M::build([['month' => '2024-11', 'total_pnl_pct' => 2.0], ['month' => '2024-12', 'total_pnl_pct' => 3.0]], 10000);
    $check('C5: guardado sin la ganancia en dinero: usa el % del mes, compuesto', abs(end($f2)['acum'] - 5.06) < 1e-9, end($f2));
}

// ── D: una sola fórmula en todo el sistema ──
$files = ['app/Helpers/RatingHelper.php', 'resources/views/backtesting/partials/results.blade.php', 'app/Services/SavedBacktests.php',
          'resources/views/strategies/index.blade.php', 'resources/views/trading/accounts.blade.php',
          'resources/views/trading/partials/subscriptions_list.blade.php', 'app/Services/ParamSearchService.php', 'app/Services/StrategyConfigSync.php'];
$copies = [];
foreach (['app', 'resources'] as $dir) {
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator("{$root}/{$dir}", FilesystemIterator::SKIP_DOTS));
    foreach ($it as $file) {
        $src = (string) file_get_contents((string) $file);
        if (preg_match('/>=\s*65\s*\?\s*5|\$sWr\b|\$sSharpe\b|calcRating5/', $src)) {
            $copies[] = substr((string) $file, strlen($root) + 1);
        }
    }
}
$check('D1: no queda ninguna copia de la fórmula vieja (umbrales de win rate y Sharpe)', $copies === [], $copies);
$check('D2: resultados del backtest: cada moneda con RatingHelper::forMetrics; el guardado anterior con fromMetrics',
    str_contains($read($files[1]), '\App\Helpers\RatingHelper::forMetrics($ia, $monthly)')
    && str_contains($read($files[1]), '$prevRating = \App\Helpers\RatingHelper::fromMetrics((array) $prevM);'));
$check('D3: historial y Estrategias: siempre la fórmula vigente', str_contains($read($files[2]), 'return RatingHelper::fromMetrics($m);')
    && str_contains($read($files[3]), '\App\Helpers\RatingHelper::fromMetrics((array) $metrics)'));
$check('D4: Real (agregar configuración y suscripciones) con la fórmula única y sus cuatro notas',
    str_contains($read($files[4]), 'RatingHelper::fromMetricsDetail(') && str_contains($read($files[4]), 'RatingHelper::LABELS[$key]')
    && str_contains($read($files[5]), '\App\Helpers\RatingHelper::fromMetrics((array) ($bt->metrics ?? []))'));
$check('D5: búsqueda (por moneda: PF, retorno, DD, meses, operaciones) y la config de Paper/Real (star_rating)',
    str_contains($read($files[6]), "RatingHelper::calculate(\$pfS, (float) (\$s['ret'] ?? 0),")
    && str_contains($read($files[7]), "'star_rating'         => RatingHelper::fromMetrics(\$m),"));

// ── E: pantalla y controlador del backtest ──
$ctl = $read('app/Http/Controllers/BacktestingController.php');
$check('E1: «24 meses» son 24 (sin desborde desde el 31 del mes)', str_contains($ctl, '->subMonthsNoOverflow($months - 1)->startOfMonth()')
    && ! str_contains($ctl, '->subMonths($months - 1)'));
$check('E2: el consolidado es la suma de los retornos de las monedas (ya no la suma de los % de cada operación)',
    ! str_contains($ctl, '$totalPnl = array_sum($monthlyTotals)') && str_contains($ctl, '\App\Support\BacktestMonths::build('));
$res = $read('resources/views/backtesting/partials/results.blade.php');
$check('E3: con una moneda no hay fila CONSOLIDADO', (bool) preg_match('/FILA DEL CONSOLIDADO ACTUAL[^\n]*\n\s*@if\(\$isMulti\)/', $res));
$check('E4: al guardar se conservan las métricas del servidor y el DD', str_contains($res,
    "\$payload['metrics'] = array_merge((array) (\$result['save_payload']['metrics'] ?? []), [")
    && str_contains($res, "'max_drawdown_pct' => \$aggGlobal['max_drawdown_pct'] ?? null,"));
$check('E5: las tablas usan los meses con retorno real (ningún % por operación sumado)', ! str_contains($res, "total_pnl_pct")
    && str_contains($res, "\$acum = \$found['acum'];") && str_contains($res, '$monthlyAcum[$month]'));

echo $fails === 0 ? "TODO OK\n" : "{$fails} FALLOS\n";
exit($fails === 0 ? 0 : 1);

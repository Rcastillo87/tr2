<?php
/**
 * RQ-01.4 (PHP puro): lista de backtests guardados.
 * - filters(): solo valores conocidos; moneda saneada; orden por defecto «recent».
 * - normalized()/rating(): las mismas cifras que la tarjeta del historial (fracciones antiguas pasadas a %).
 * - Cableado (estático): filtros en SQL, enriquecimiento con dos consultas agregadas (sin N+1), ruta y botón.
 * La prueba contra la base real es saved_backtests_screen_test.php (corre al instalar).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/saved_backtests_test.php
 */
declare(strict_types=1);

namespace App\Helpers {
    if (! class_exists(RatingHelper::class)) {
        class RatingHelper   // doble: la regla real se prueba en la integración
        {
            public static function calculate($wr, $sh, $pf, $ret, $c): float { return round(($wr + $ret + $c) / 100, 4); }
        }
    }
}

namespace {
    $root = getcwd();
    $fails = 0;
    $check = function (string $name, bool $ok, $d = '') use (&$fails): void {
        $fails += $ok ? 0 : 1;
        printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
    };
    $file = "{$root}/app/Services/SavedBacktests.php";
    $check('L0: existe App\Services\SavedBacktests', is_file($file));
    if (is_file($file)) {
        require $file;
        $S = 'App\Services\SavedBacktests';

        $f = $S::filters(['strategy' => '7', 'paper' => 'active', 'origin' => 'unknown', 'symbol' => " ena'; drop", 'sort' => 'rating']);
        $check('L1: filtros válidos se conservan; la moneda queda en letras y números en mayúsculas',
            $f === ['strategy' => 7, 'paper' => 'active', 'origin' => 'unknown', 'symbol' => 'ENADROP', 'sort' => 'rating'], $f);
        $g = $S::filters(['strategy' => '7x', 'paper' => 'x', 'origin' => 'search ', 'symbol' => '', 'sort' => 'id; --']);
        $check('L2: valores desconocidos = sin filtro; orden por defecto reciente',
            $g === ['strategy' => null, 'paper' => null, 'origin' => null, 'symbol' => null, 'sort' => 'recent'], $g);
        $check('L3: filtros vacíos', $S::filters([]) === ['strategy' => null, 'paper' => null, 'origin' => null, 'symbol' => null, 'sort' => 'recent']);

        $n = $S::normalized(['win_rate' => 0.55, 'avg_monthly_pnl' => -0.012, 'consist_pct' => 0.8]);
        $m = $S::normalized(['win_rate' => 55.0, 'avg_monthly_pnl' => 1.6, 'consist_pct' => 80.0]);
        $check('L4: win rate y consistencia en fracción pasan a %; el retorno mensual nunca se escala (0,71 % sigue 0,71 %)',
            abs($n['wr'] - 55) < 1e-9 && $n['ret'] === -0.012 && abs($n['consist'] - 80) < 1e-9
            && $m === ['wr' => 55.0, 'ret' => 1.6, 'consist' => 80.0]
            && $S::normalized(['avg_monthly_pnl' => 0.71])['ret'] === 0.71, [$n, $m]);
        $check('L5: rating guardado manda; si no hay, se calcula con las métricas normalizadas',
            $S::rating(['rating' => 4.2]) === 4.2 && $S::rating(['win_rate' => 0.55, 'avg_monthly_pnl' => 0.0, 'consist_pct' => 0.8]) === 1.35);
    $hist = (string) @file_get_contents("{$root}/resources/views/backtesting/history.blade.php");
    $check('L7: el historial ya no multiplica por 100 el retorno mensual', ! str_contains($hist, '$ret *= 100'));
        $check('L6: catálogos de estado y origen', array_keys($S::PAPER) === ['active', 'stopped', 'none']
            && array_keys($S::ORIGINS) === ['search', 'manual', 'unknown']);
    }

    $svc = (string) @file_get_contents($file);
    $check('W1: estado en Paper filtrado en SQL con EXISTS (no en PHP)', substr_count($svc, '->whereExists(') >= 2
        && str_contains($svc, '->whereNotExists($configs(true))') && str_contains($svc, "'none'    => \$q->whereNotExists(\$configs())"));
    $check('W2: la página se enriquece con 2 consultas agregadas (configs por backtest, trades cerrados por config)',
        substr_count($svc, "DB::table(") === 2 && str_contains($svc, "->where('status', 'closed')")
        && str_contains($svc, "->groupBy('paper_strategy_config_id')"));
    $check('W3: moneda con parámetro enlazado (no concatenada)', str_contains($svc, "s ILIKE ?)\",\n                ['%' . \$f['symbol'] . '%']"));
    $check('W4: Trades/mes con la regla de las configs', str_contains($svc, 'StrategyConfigSync::tradesPerMonth('));
    $web = (string) @file_get_contents("{$root}/routes/web.php");
    $ctl = (string) @file_get_contents("{$root}/app/Http/Controllers/BacktestingController.php");
    $idx = (string) @file_get_contents("{$root}/resources/views/strategies/index.blade.php");
    $check('W5: ruta /backtesting/guardados (grupo viewAnalysisTools), acción con Gate y botón en Estrategias',
        str_contains($web, "Route::get('/guardados',") && str_contains($ctl, 'public function saved(')
        && (bool) preg_match('/function saved\([^)]*\)\s*\{\s*Gate::authorize\(\'viewAnalysisTools\'\)/', $ctl)
        && str_contains($idx, "route('backtesting.saved')"));

    echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
    exit($fails === 0 ? 0 : 1);
}

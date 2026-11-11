<?php
/**
 * RQ-01.4 (integración, Laravel + base real): «Backtests guardados».
 * Compara la lista con consultas independientes sobre los datos reales: estado en Paper, conteo y P&L de trades
 * cerrados, filtros (Paper, origen, moneda, estrategia), totales de la cabecera; y renderiza la pantalla.
 * Solo lectura más 1 backtest de prueba, en una transacción que se revierte.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/saved_backtests_screen_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BacktestingController;
use App\Models\Backtest;
use App\Models\Strategy;
use App\Models\User;
use App\Services\SavedBacktests;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails) {
    $fails += $ok ? 0 : 1;
    echo ($ok ? 'PASS ' : 'FAIL ') . $name . ($detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '') . "\n";
};

DB::beginTransaction();
try {
    $admin = User::where('role', 'admin')->orderBy('id')->first();
    $strategy = Strategy::orderBy('id')->first();
    if (! $admin || ! $strategy) {
        echo "SKIP  hace falta un usuario admin y una estrategia\n";
        DB::rollBack();
        exit(2);
    }
    Auth::login($admin);
    view()->share('errors', new Illuminate\Support\ViewErrorBag());
    $probe = Backtest::create(['strategy_id' => $strategy->id, 'symbols' => ['ZZPROBEUSDT'], 'interval' => '60', 'months' => 6,
        'config_params' => ['t' => 'rq014'], 'strategy_snapshot' => [], 'metrics' => ['total_trades' => 3, 'avg_monthly_pnl' => 0.71],
        'approved' => false, 'origin' => 'manual']);

    $svc = app(SavedBacktests::class);
    $all = function (array $in) use ($svc): array {
        $f = SavedBacktests::filters($in);
        $rows = [];
        for ($page = 1; ; $page++) {
            $p = $svc->page($f, $page);
            foreach ($p->items() as $r) {
                $rows[$r['id']] = $r;
            }
            if ($page >= $p->lastPage()) {
                return $rows;
            }
        }
    };

    $rows = $all([]);
    $total = (int) DB::scalar('SELECT count(*) FROM backtests');
    $check("G1: sin filtros aparecen los {$total} backtests, cada uno una vez", count($rows) === $total, count($rows));

    // Estado en Paper y trades, contra SQL independiente
    $truth = collect(DB::select("SELECT b.id,
            CASE WHEN bool_or(c.active) THEN 'active' WHEN count(c.id) > 0 THEN 'stopped' ELSE 'none' END AS paper
          FROM backtests b LEFT JOIN paper_strategy_configs c ON c.backtest_id = b.id GROUP BY b.id"))->keyBy('id');
    $tr = collect(DB::select("SELECT c.backtest_id AS id, count(t.id) AS n, coalesce(sum(t.pnl_pct), 0) AS pnl
          FROM paper_strategy_configs c JOIN paper_trades t ON t.paper_strategy_config_id = c.id AND t.status = 'closed'
         GROUP BY c.backtest_id"))->keyBy('id');
    $bad = [];
    foreach ($rows as $id => $r) {
        $n = (int) ($tr[$id]->n ?? 0);
        $pnl = round((float) ($tr[$id]->pnl ?? 0), 2);
        if ($r['paper'] !== ($truth[$id]->paper ?? null) || $r['paper_n'] !== $n || abs($r['paper_pnl'] - $pnl) > 0.011) {
            $bad[$id] = [$r['paper'], $truth[$id]->paper ?? null, $r['paper_n'], $n, $r['paper_pnl'], $pnl];
        }
    }
    $check('G2: estado en Paper, trades cerrados y P&L de cada backtest = SQL independiente', $bad === [], array_slice($bad, 0, 3, true));
    $active = $truth->where('paper', 'active')->count();
    $check("G3: hay backtests operando en Paper ({$active})", $active > 0);

    // Filtros
    foreach (['active', 'stopped', 'none'] as $k) {
        $ids = array_keys($all(['paper' => $k]));
        $exp = $truth->where('paper', $k)->keys()->map(fn ($v) => (int) $v)->sort()->values()->all();
        sort($ids);
        $check("F1: filtro Paper «{$k}» = " . count($exp) . ' backtests', $ids === $exp, [count($ids), count($exp)]);
    }
    foreach (['search' => "origin = 'search'", 'manual' => "origin = 'manual'", 'unknown' => 'origin IS NULL'] as $k => $where) {
        $exp = (int) DB::scalar("SELECT count(*) FROM backtests WHERE {$where}");
        $check("F2: filtro origen «{$k}» = {$exp}", count($all(['origin' => $k])) === $exp, count($all(['origin' => $k])));
    }
    $sym = $all(['symbol' => 'zzprobe']);
    $check('F3: filtro de moneda parcial y sin importar mayúsculas encuentra el de prueba', array_keys($sym) === [$probe->id], array_keys($sym));
    $byStrategy = $all(['strategy' => (string) $strategy->id]);
    $check('F4: filtro de estrategia', count($byStrategy) === (int) DB::scalar('SELECT count(*) FROM backtests WHERE strategy_id = ?', [$strategy->id])
        && collect($byStrategy)->every(fn ($r) => $r['strategy_id'] === $strategy->id));
    $check('F5: el retorno mensual 0,71 % se muestra como 0,71 %, no 71 %', abs($rows[$probe->id]['ret_month'] - 0.71) < 1e-9, $rows[$probe->id]['ret_month']);

    // Pantalla
    $req = Request::create('/backtesting/guardados', 'GET', ['paper' => 'active']);
    $req->setUserResolver(fn () => Auth::user());
    app()->instance('request', $req);
    try {
        $html = (string) app(BacktestingController::class)->saved($req, $svc)->render();
    } catch (Throwable $e) {
        $html = 'EXCEPCION: ' . $e->getMessage() . ' @ ' . basename($e->getFile()) . ':' . $e->getLine();
    }
    $firstActive = $truth->where('paper', 'active')->keys()->first();
    $check('P1: la pantalla renderiza con el filtro «Operando», enlaza al historial y muestra la cabecera de totales',
        ! str_starts_with($html, 'EXCEPCION') && str_contains($html, 'operando en Paper')
        && ($firstActive === null || str_contains($html, '#bt-' . $firstActive . '"')), substr($html, 0, 200));
} finally {
    DB::rollBack();
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

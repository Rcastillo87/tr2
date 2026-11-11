<?php
/**
 * RQ-01.2 (integración, Laravel + base real): «Crear en historial» por los caminos reales.
 * - results(): una fila creada cuyo backtest se borró vuelve a estar disponible; una creación colgada también.
 * - create(): rechaza (409) filas ya creadas o en curso; reserva con token y encola una sola vez.
 * - El job: no crea filas ajenas ni ya creadas; crea las suyas; si muere, las libera.
 * Todo en una transacción que se revierte; la cola es falsa y el creador de backtests es un doble (sin motor).
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/search_create_guard_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\ParamSearchController;
use App\Jobs\CreateBacktestsFromSearchJob;
use App\Models\Backtest;
use App\Models\ParamSearchRun;
use App\Models\Strategy;
use App\Models\User;
use App\Services\BacktestFromSearch;
use App\Services\ParamSearchService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails) {
    $fails += $ok ? 0 : 1;
    echo ($ok ? 'PASS ' : 'FAIL ') . $name . ($detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '') . "\n";
};

/** Doble del creador: registra las llamadas y devuelve un backtest existente (no corre el motor). */
final class FakeCreator extends BacktestFromSearch
{
    public array $calls = [];

    public function __construct(private int $backtestId)
    {
    }

    public function run(User $user, Strategy $strategy, array $cfg, string $interval, array $symbols, int $months, bool $save,
                        ?array $origin = null): array
    {
        $this->calls[] = [$interval, $symbols, $origin['row_id'] ?? null];

        return ['saved' => ['backtest_id' => $this->backtestId, 'message' => 'ok (doble)']];
    }
}

$sym = ['role' => 'win', 'why' => null, 'n' => 60, 'wins' => 30, 'wr' => 50.0, 'sharpe' => 1.0, 'pf' => 1.4, 'ret' => 10.0,
        'dd' => 5.0, 'gp' => 100.0, 'gl' => 70.0, 'm' => array_fill(0, 24, 0.4), 'm1' => true];
$seg = ['n' => 40, 'pf' => 1.3, 'ret' => 2.5, 'pos' => 1];
$months = array_map(fn ($i) => sprintf('2025-%02d', $i % 12 + 1), range(0, 23));
$row = fn (string $id) => ['id' => $id, 'symbol' => 'SOLUSDT', 'interval' => '60', 'cfg' => ['sl_pct' => 1.5, 'tp_pct' => 3.0],
    'symbols' => ['SOLUSDT' => $sym], 'survivors' => ['SOLUSDT'], 'discarded' => [], 'is' => $seg, 'oos' => $seg, 'oos_ok' => true,
    'ret_total' => 10.0, 'consist' => 100.0];

DB::beginTransaction();
try {
    Queue::fake();
    $strategy = Strategy::orderBy('id')->first();
    $admin = User::where('role', 'admin')->orderBy('id')->first() ?? User::orderBy('id')->first();
    $existing = (int) Backtest::query()->min('id');
    if (! $strategy || ! $admin || $existing === 0) {
        echo "SKIP  hace falta una estrategia, un usuario y al menos un backtest\n";
        DB::rollBack();
        exit(2);
    }
    Auth::login($admin);
    $gone = (int) DB::scalar('SELECT coalesce(max(id), 0) + 100000 FROM backtests');
    $iso = fn (int $ago) => gmdate('Y-m-d\TH:i:s+00:00', time() - $ago);

    $results = ['version' => 3, 'focus' => 'gain', 'mode' => 'symbol', 'months' => $months, 'tested' => 40, 'survivors' => 4,
        'min_trades' => 30, 'rows' => [$row('ra'), $row('rb'), $row('rc'), $row('rd')], 'near' => [],
        'period' => ['start' => '2024-10-01', 'split' => '2026-02-01', 'end' => '2026-10-01'],
        'created' => [
            'ra' => ['status' => 'done', 'backtest_id' => $existing, 'at' => $iso(60)],
            'rb' => ['status' => 'done', 'backtest_id' => $gone, 'at' => $iso(60)],
            'rc' => ['status' => 'running', 'at' => $iso(ParamSearchService::CREATE_STALE_AFTER_S + 60)],
        ]];
    $run = ParamSearchRun::create(['strategy_id' => $strategy->id, 'user_id' => $admin->id, 'intervals' => ['60'],
        'search_symbols' => ['SOLUSDT'], 'validation_symbols' => [], 'months' => 24, 'samples' => 40, 'seed' => 1,
        'status' => 'done', 'focus' => 'gain', 'mode' => 'symbol']);
    DB::table('param_search_runs')->where('id', $run->id)->update(['results' => json_encode($results), 'strategy_code_md5' => null]);
    $run->refresh();

    $ctrl = app(ParamSearchController::class);
    $created = fn () => collect($ctrl->results(Request::create('/', 'GET'), $run->fresh())->getData(true)['rows'])
        ->keyBy('id')->map(fn ($r) => $r['created'])->all();
    $post = function (array $rows) use ($ctrl, $run) {
        $req = Request::create('/', 'POST', ['rows' => $rows, 'symbols' => 'survivors']);
        $req->setUserResolver(fn () => Auth::user());
        $resp = $ctrl->create($req, $run->fresh());

        return [$resp->getStatusCode(), $resp->getData(true)];
    };
    $raw = fn (string $id) => ($run->fresh()->results['created'][$id] ?? null);

    // G1. Lectura conciliada
    $c = $created();
    $check('G1: creada con backtest existente -> done; con backtest borrado -> deleted; colgada -> error',
        ($c['ra']['status'] ?? '') === 'done' && ($c['rb']['status'] ?? '') === 'deleted' && ($c['rc']['status'] ?? '') === 'error'
        && ($c['rd'] ?? null) === null, array_map(fn ($x) => $x['status'] ?? null, $c));

    // G2. Ya creada -> 409
    [$code, $out] = $post(['ra']);
    $check('G2: crear una fila cuyo backtest existe -> 409 con el número del backtest', $code === 409
        && str_contains($out['error'] ?? '', "#{$existing}"), [$code, $out['error'] ?? null]);
    Queue::assertNothingPushed();

    // G3. Backtest borrado (y fila repetida en el pedido) -> se reserva y se encola UNA vez
    [$code, $out] = $post(['rb', 'rb']);
    $st = $raw('rb');
    $jobs = Queue::pushed(CreateBacktestsFromSearchJob::class);
    $token = $jobs->first()?->token;
    $check('G3: fila con backtest borrado -> 200, reservada (running/queued) con token, un job con la fila una vez',
        $code === 200 && ($st['status'] ?? '') === 'running' && ($st['phase'] ?? '') === 'queued' && is_string($token)
        && $token === ($st['token'] ?? null) && $jobs->count() === 1 && $jobs->first()->rowIds === ['rb'],
        [$code, $st, $jobs->count(), $jobs->first()?->rowIds]);

    // G4. Doble clic / otra pestaña -> 409
    [$code, $out] = $post(['rb']);
    $check('G4: volver a pedir la fila en curso -> 409 «ya se está creando», sin otro job', $code === 409
        && str_contains($out['error'] ?? '', 'ya se está creando') && Queue::pushed(CreateBacktestsFromSearchJob::class)->count() === 1,
        [$code, $out['error'] ?? null]);
    $check('G5: la pantalla ve «en curso» y no recibe el token', ($created()['rb']['status'] ?? '') === 'running'
        && ! array_key_exists('token', $created()['rb'] ?? []));

    $service = app(ParamSearchService::class);
    // G6. Job con otro token: no toca la fila reservada por otro pedido
    $fake = new FakeCreator($existing);
    (new CreateBacktestsFromSearchJob($run->id, ['rb'], 'survivors', $admin->id, 'otro'))->handle($fake, $service);
    $check('G6: job de otro pedido -> no crea y deja la reserva intacta', $fake->calls === [] && ($raw('rb')['token'] ?? null) === $token);

    // G7. Job legado (sin token) sobre una fila ya creada -> no crea otra vez
    (new CreateBacktestsFromSearchJob($run->id, ['ra'], 'survivors', $admin->id))->handle($fake, $service);
    $check('G7: job anterior a p51 sobre fila ya creada -> no crea', $fake->calls === [] && ($raw('ra')['status'] ?? '') === 'done');

    // G8. Job dueño de la reserva -> crea una vez y queda done con el id
    (new CreateBacktestsFromSearchJob($run->id, ['rb'], 'survivors', $admin->id, $token))->handle($fake, $service);
    $check('G8: job dueño -> crea una vez, done con backtest_id y origen de la fila', count($fake->calls) === 1
        && ($fake->calls[0][2] ?? null) === 'rb' && ($raw('rb')['status'] ?? '') === 'done' && ($raw('rb')['backtest_id'] ?? null) === $existing,
        [$fake->calls, $raw('rb')]);

    // G9. El job muere: sus filas vuelven a estar disponibles; las ajenas no se tocan
    [$code] = $post(['rc', 'rd']);
    $t2 = Queue::pushed(CreateBacktestsFromSearchJob::class)->last()->token;
    ParamSearchService::markCreated($run->id, 'rd', ['status' => 'running', 'phase' => 'queued', 'token' => 'ajeno']);
    (new CreateBacktestsFromSearchJob($run->id, ['rc', 'rd'], 'survivors', $admin->id, $t2))->failed(new RuntimeException('timeout'));
    $check('G9: failed() libera solo sus filas (rc -> error disponible; rd de otro pedido sigue en curso)', $code === 200
        && ($raw('rc')['status'] ?? '') === 'error' && ($raw('rd')['status'] ?? '') === 'running', [$raw('rc'), $raw('rd')]);
} finally {
    DB::rollBack();
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

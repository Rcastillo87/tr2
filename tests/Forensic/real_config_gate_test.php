<?php
/**
 * Prueba forense p01 (REAL-04): una config Paper desactivada/borrada NO puede seguir abriendo posiciones Real.
 * TODO corre dentro de una transacción que se revierte al final: no deja cambios en la base.
 * No llama al motor Python ni a Bybit (Http::fake) y no encola nada (Queue::fake).
 *
 * Uso: cd <raíz del proyecto> && php tests/Forensic/real_config_gate_test.php
 * Antes del parche debe FALLAR en los casos A2/A4/C/D (reproduce el bug); después, todo PASS.
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
config(['session.driver' => 'array']);

use App\Http\Controllers\BacktestingController;
use App\Jobs\RealTradingAccountTickJob;
use App\Jobs\RealTradingTickJob;
use App\Models\Backtest;
use App\Models\RealStrategySubscription;
use App\Models\RealTrade;
use App\Models\User;
use App\Services\StrategyConfigSync;
use App\Services\UserDeactivation;
use Illuminate\Http\Client\Factory as HttpFactory;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;

$fails = 0;
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    if (! $ok) {
        $fails++;
    }
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
};

$counts = fn () => [
    'subs'     => DB::table('real_strategy_subscriptions')->count(),
    'configs'  => DB::table('paper_strategy_configs')->count(),
    'backtest' => DB::table('backtests')->count(),
    'active_c' => DB::table('paper_strategy_configs')->where('active', true)->count(),
    'paused_s' => DB::table('real_strategy_subscriptions')->where('status', 'paused')->count(),
];
$before = $counts();

/** Ids de suscripción que el job de la cuenta enviaría al motor (null = no hubo pedido). */
$sentSubIds = function (int $accountId): ?array {
    Http::swap(new HttpFactory());
    Http::fake(['*' => Http::response(['status' => 'ok', 'results' => [], 'features' => ['sub_entries']], 200)]);
    (new RealTradingAccountTickJob($accountId))->handle();
    $recorded = Http::recorded();
    if ($recorded->isEmpty()) {
        return null;
    }
    [$request] = $recorded->last();
    $accounts = $request->data()['accounts'] ?? [];

    return collect($accounts[0]['subscriptions'] ?? [])->pluck('subscription_id')->map(fn ($v) => (int) $v)->all();
};
/** Suscripciones del pedido al motor: [id => entries_allowed] (null = no hubo pedido). */
$sentSubs = function (int $accountId): ?array {
    Http::swap(new HttpFactory());
    Http::fake(['*' => Http::response(['status' => 'ok', 'results' => [], 'features' => ['sub_entries']], 200)]);
    (new RealTradingAccountTickJob($accountId))->handle();
    $recorded = Http::recorded();
    if ($recorded->isEmpty()) {
        return null;
    }
    [$request] = $recorded->last();
    $out = [];
    foreach ($request->data()['accounts'][0]['subscriptions'] ?? [] as $s) {
        $out[(int) $s['subscription_id']] = (bool) ($s['entries_allowed'] ?? true);
    }
    return $out;
};
$cfgActive = fn (int $id, bool $v) => DB::table('paper_strategy_configs')->where('id', $id)->update(['active' => $v]);

DB::beginTransaction();
try {
    echo "=== 0. Estado REAL (antes de tocar nada): suscripciones activas con la config Paper apagada\n";
    $exposed = DB::table('real_strategy_subscriptions as s')
        ->join('paper_strategy_configs as c', 'c.id', '=', 's.paper_strategy_config_id')
        ->join('broker_accounts as a', 'a.id', '=', 's.broker_account_id')
        ->where('s.status', 'active')->where('c.active', false)->where('a.status', 'active')
        ->get(['s.id as sub', 's.broker_account_id as acc', 's.symbol as sym']);
    if ($exposed->isEmpty()) {
        echo "INFO  A0: no hay suscripción activa con config apagada en cuenta ACTIVA (nada que comprobar con el estado real)\n";
    }
    foreach ($exposed as $e) {
        $ids = $sentSubIds((int) $e->acc);
        $check("A0 estado real: sub #{$e->sub} ({$e->sym}, config APAGADA) NO viaja al motor",
            $ids === null || ! in_array((int) $e->sub, $ids, true), json_encode($ids));
    }

    echo "=== 0b. Fixture controlado (se fuerza dentro de la transacción: cuenta, suscripción y config activas)\n";
    $sub = RealStrategySubscription::query()
        ->whereNotNull('paper_strategy_config_id')
        ->whereHas('paperStrategyConfig')
        ->whereHas('brokerAccount')
        ->orderBy('id')
        ->first();
    if (! $sub) {
        echo "SKIP  no existe ninguna suscripción con config y cuenta para armar el fixture\n";
        DB::rollBack();
        exit(2);
    }
    $accountId = (int) $sub->broker_account_id;
    $subId     = (int) $sub->id;
    $cfgId     = (int) $sub->paper_strategy_config_id;
    DB::table('broker_accounts')->where('id', $accountId)->update(['status' => 'active']);
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'active']);
    DB::table('paper_strategy_configs')->where('id', $cfgId)->update(['active' => true]);
    echo "     suscripción #{$subId}, config #{$cfgId}, cuenta #{$accountId} (forzadas a activas SOLO dentro de la transacción)\n";

    echo "=== A. Payload que el job envía al motor\n";
    $ids = $sentSubIds($accountId);
    $check('A1 config activa -> la suscripción SÍ viaja', in_array($subId, $ids ?? [], true), json_encode($ids));

    $cfgActive($cfgId, false);
    $ids = $sentSubIds($accountId);
    $check('A2 config DESACTIVADA (stop-paper) -> la suscripción NO viaja',
        $ids === null || ! in_array($subId, $ids, true), json_encode($ids));

    // Control: con el filtro VIEJO (solo status de la suscripción) esa misma suscripción SÍ habría viajado
    $old = RealStrategySubscription::where('broker_account_id', $accountId)->where('status', 'active')
        ->pluck('id')->map(fn ($v) => (int) $v)->all();
    $check('A2-control: con el filtro VIEJO la suscripción SÍ habría viajado (el escenario reproduce el bug)', in_array($subId, $old, true));

    $cfgActive($cfgId, true);
    $ids = $sentSubIds($accountId);
    $check('A3 config reactivada -> vuelve a viajar', in_array($subId, $ids ?? [], true), json_encode($ids));

    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['paper_strategy_config_id' => null]);
    $ids = $sentSubIds($accountId);
    $check('A4 suscripción HUÉRFANA (config NULL) -> NO viaja', $ids === null || ! in_array($subId, $ids, true), json_encode($ids));
    $old = RealStrategySubscription::where('broker_account_id', $accountId)->where('status', 'active')
        ->pluck('id')->map(fn ($v) => (int) $v)->all();
    $check('A4-control: con el filtro VIEJO la suscripción huérfana SÍ habría viajado', in_array($subId, $old, true));
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['paper_strategy_config_id' => $cfgId]);

    // A5 (D-03, 13-nov): pausada CON operación abierta viaja SIN entradas (termina su ciclo); SIN operación no viaja
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'paused']);
    $hasOpenA5 = RealTrade::where('subscription_id', $subId)->whereIn('status', ['open', 'pending_close'])->exists();
    $sentA5 = $sentSubs($accountId);
    if ($hasOpenA5) {
        $check('A5a suscripción pausada CON operación abierta -> viaja SIN entradas (D-03)',
            is_array($sentA5) && array_key_exists($subId, $sentA5) && $sentA5[$subId] === false, json_encode($sentA5));
    } else {
        $check('A5a suscripción pausada sin operación abierta -> NO viaja', $sentA5 === null || ! array_key_exists($subId, $sentA5),
            json_encode($sentA5));
    }
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'active']);
    $idle = DB::table('real_strategy_subscriptions as s')->join('paper_strategy_configs as c', 'c.id', '=', 's.paper_strategy_config_id')
        ->where('s.broker_account_id', $accountId)->where('s.id', '<>', $subId)->where('c.active', true)
        ->whereNotExists(fn ($e) => $e->selectRaw('1')->from('real_trades as t')->whereColumn('t.subscription_id', 's.id')
            ->whereIn('t.status', ['open', 'pending_close']))->value('s.id');
    if ($idle) {
        DB::table('real_strategy_subscriptions')->where('id', $idle)->update(['status' => 'paused']);
        $sentA5 = $sentSubs($accountId);
        $check("A5b suscripción pausada #{$idle} SIN operación abierta -> NO viaja (comportamiento previo intacto)",
            $sentA5 === null || ! array_key_exists((int) $idle, $sentA5), json_encode($sentA5));
    } else {
        echo "SKIP  A5b: no hay otra suscripción con config activa y sin operación abierta en la cuenta #{$accountId}\n";
    }

    echo "=== B. El scope coincide con la consulta cruda\n";
    $viaScope = RealStrategySubscription::runnable()->count();
    $viaSql = DB::table('real_strategy_subscriptions as s')
        ->join('paper_strategy_configs as c', 'c.id', '=', 's.paper_strategy_config_id')
        ->join('users as u', 'u.id', '=', 's.user_id')
        ->where('s.status', 'active')->where('c.active', true)->where('u.is_active', true)->count();
    $check('B1 runnable() == SQL crudo', $viaScope === $viaSql, "scope={$viaScope} sql={$viaSql}");

    echo "=== C. El despachador no encola cuentas sin suscripciones operables\n";
    $accSubCfgs = DB::table('real_strategy_subscriptions')->where('broker_account_id', $accountId)
        ->whereNotNull('paper_strategy_config_id')->pluck('paper_strategy_config_id')->all();
    DB::table('paper_strategy_configs')->whereIn('id', $accSubCfgs)->update(['active' => false]);
    $hasOpen = RealTrade::where('broker_account_id', $accountId)->whereIn('status', ['open', 'pending_close'])->exists();
    if ($hasOpen) {
        echo "SKIP  C1: la cuenta tiene posiciones abiertas (se despacha igual para gestionarlas)\n";
    } else {
        Queue::fake();
        (new RealTradingTickJob())->handle();
        $pushed = Queue::pushed(RealTradingAccountTickJob::class, fn ($job) => $job->accountId === $accountId)->count();
        $check('C1 todas sus configs inactivas y sin posiciones -> la cuenta NO se despacha', $pushed === 0, "despachos={$pushed}");
    }
    DB::table('paper_strategy_configs')->whereIn('id', $accSubCfgs)->update(['active' => true]);

    echo "=== D. Borrar un backtest\n";
    $btId = DB::table('paper_strategy_configs')->where('id', $cfgId)->value('backtest_id');
    if (! $btId) {
        echo "SKIP  D: la config #{$cfgId} no tiene backtest asociado\n";
    } else {
        $btId = (int) $btId;
        $cfgIds = DB::table('paper_strategy_configs')->where('backtest_id', $btId)->pluck('id')->all();
        DB::table('paper_strategy_configs')->whereIn('id', $cfgIds)->update(['active' => false]); // que no esté "operando"
        // Reglas de borrado vigentes (p40b, CFG-05): bloquean los trades Real por reconciliar y los Paper abiertos
        $openReal = RealTrade::whereIn('paper_strategy_config_id', $cfgIds)
            ->whereIn('status', RealTrade::RECONCILE_STATUSES)->count();
        $openPaper = DB::table('paper_trades')->whereIn('paper_strategy_config_id', $cfgIds)->where('status', 'open')->count();
        $subsOfBt = DB::table('real_strategy_subscriptions')->whereIn('paper_strategy_config_id', $cfgIds)->pluck('id')->all();
        $statusBefore = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->pluck('status', 'id')->all();

        Gate::before(fn ($user = null) => true);
        $req = Request::create('/backtest/' . $btId, 'DELETE');
        $req->setLaravelSession(app('session.store'));
        app()->instance('request', $req);
        try {
            app(BacktestingController::class)->destroyBacktest(Backtest::findOrFail($btId), app(StrategyConfigSync::class));
            if ($openReal > 0 || $openPaper > 0) {
                $check('D1 con posición Real por reconciliar o Paper abierta NO se borra', Backtest::find($btId) !== null,
                       "real={$openReal} paper={$openPaper}");
                $statusAfter = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->pluck('status', 'id')->all();
                $check('D2 sus suscripciones siguen como estaban (no se tocó nada)', $statusAfter === $statusBefore);
            } else {
                $check('D1 sin posiciones abiertas -> el backtest se borra', Backtest::find($btId) === null);
                $left = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->where('status', 'active')->count();
                $check('D2 NINGUNA suscripción queda activa tras borrar (antes quedaban huérfanas activas)', $left === 0, "activas={$left}");
                $orph = DB::table('real_strategy_subscriptions')->whereIn('id', $subsOfBt)->whereNull('paper_strategy_config_id')->count();
                $check('D3 las suscripciones quedaron huérfanas pero PAUSADAS', $orph === count($subsOfBt), "huérfanas={$orph}/" . count($subsOfBt));
                $ids = $sentSubIds($accountId);
                $check('D4 el motor ya no recibe esas suscripciones', $ids === null || array_intersect($subsOfBt, $ids) === [], json_encode($ids));
            }
        } catch (\Throwable $e) {
            $check('D destroyBacktest sin excepción', false, get_class($e) . ': ' . substr($e->getMessage(), 0, 200));
        }
    }

    echo "=== E. Usuario inactivo (p62, decisión del dueño 13-nov)\n";
    $uid = (int) DB::table('broker_accounts')->where('id', $accountId)->value('user_id');
    $userSubs = fn () => DB::table('real_strategy_subscriptions')->where('user_id', $uid)->pluck('status', 'id')->all();
    $liveOf = fn (array $ids) => DB::table('real_trades')->whereIn('subscription_id', $ids)
        ->whereIn('status', RealTrade::RECONCILE_STATUSES)->distinct()->pluck('subscription_id')->map(fn ($v) => (int) $v)->all();
    $tradesBefore = DB::table('real_trades')->where('user_id', $uid)->count();
    DB::table('paper_strategy_configs')->where('id', $cfgId)->update(['active' => true]);
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'active']);

    // E1. Inactivado por SQL (sin pasar por la pantalla) con una suscripción activa
    DB::table('users')->where('id', $uid)->update(['is_active' => false]);
    $old = RealStrategySubscription::where('status', 'active')
        ->whereHas('paperStrategyConfig', fn ($c) => $c->where('active', true))->whereKey($subId)->exists();
    $check('E1-control: con el filtro anterior, la suscripción del usuario inactivado por SQL SÍ habría abierto', $old);
    $check('E1 runnable() excluye al usuario inactivo (U-1)', ! RealStrategySubscription::runnable()->whereKey($subId)->exists());
    $sent = $sentSubs($accountId);
    $withEntries = array_keys(array_filter($sent ?? []));
    $check('E1 el motor no recibe ninguna suscripción con entradas de ese usuario',
        array_intersect($withEntries, array_keys($userSubs())) === [], json_encode($sent));
    // Con operaciones abiertas y config Paper activa (con la config apagada no viajan: regla vigente, igual que Paper)
    $liveOpen = DB::table('real_trades as t')->join('real_strategy_subscriptions as s', 's.id', '=', 't.subscription_id')
        ->join('paper_strategy_configs as c', 'c.id', '=', 's.paper_strategy_config_id')
        ->where('s.user_id', $uid)->where('c.active', true)->whereIn('t.status', ['open', 'pending_close'])
        ->distinct()->pluck('t.subscription_id')->map(fn ($v) => (int) $v)->all();
    $check('E2 sus suscripciones con operaciones abiertas (config activa) SÍ viajan, sin entradas (terminan su ciclo)',
        $liveOpen === [] || collect($liveOpen)->every(fn ($id) => array_key_exists($id, $sent ?? []) && ($sent[$id] === false)),
        json_encode(['abiertas' => $liveOpen, 'enviadas' => $sent]));
    DB::table('users')->where('id', $uid)->update(['is_active' => true]);

    // E3. Inactivar por la pantalla (UserDeactivation): sin operaciones vivas -> eliminadas; con vivas -> pausadas
    $subsBefore = $userSubs();
    $live = $liveOf(array_keys($subsBefore));
    $r = app(UserDeactivation::class)->setActive(User::findOrFail($uid), false);
    $subsAfter = $userSubs();
    $sorted = function (array $a): array { $a = array_values(array_map('intval', $a)); sort($a); return $a; };
    $gone = $sorted(array_diff(array_keys($subsBefore), array_keys($subsAfter)));
    $check('E3 eliminadas exactamente las suscripciones sin operaciones vivas',
        $gone === $sorted(array_diff(array_keys($subsBefore), $live)) && $r['deleted'] === count($gone),
        json_encode(['antes' => count($subsBefore), 'vivas' => $live, 'eliminadas' => $gone, 'r' => $r]));
    $retiring = DB::table('real_strategy_subscriptions')->where('user_id', $uid)->where('retire_on_close', true)->pluck('id')->all();
    $check('E3 las de operaciones vivas siguen, pausadas y marcadas para eliminarse al cerrar (retire_on_close)',
        $sorted(array_keys($subsAfter)) === $sorted($live) && collect($subsAfter)->every(fn ($st) => $st === 'paused')
        && $sorted($retiring) === $sorted($live), json_encode(['subs' => $subsAfter, 'retire' => $retiring]));
    $check('E4 ningún trade borrado (historial intacto) y el usuario existe',
        DB::table('real_trades')->where('user_id', $uid)->count() === $tradesBefore && User::find($uid) !== null);

    // E5. Limpieza: conserva las de operaciones vivas y elimina una suscripción sin operaciones del usuario inactivo
    $extra = DB::table('real_strategy_subscriptions')->insertGetId(['user_id' => $uid, 'broker_account_id' => $accountId,
        'paper_strategy_config_id' => null, 'strategy' => 'p62-prueba', 'symbol' => 'XXXUSDT', 'interval' => '240',
        'status' => 'paused', 'created_at' => now(), 'updated_at' => now()]);
    $purged = app(UserDeactivation::class)->purgeFinished();
    $check('E5 purgeFinished elimina la sin operaciones y conserva las vivas',
        ! DB::table('real_strategy_subscriptions')->where('id', $extra)->exists() && $sorted(array_keys($userSubs())) === $sorted($live),
        json_encode(['purgadas' => $purged, 'quedan' => $userSubs()]));

    // E6. ensureSubscriptions no crea suscripciones para el usuario inactivo (U-3)
    $freeCfg = \App\Models\PaperStrategyConfig::whereNotExists(fn ($e) => $e->selectRaw('1')->from('real_strategy_subscriptions as r')
        ->whereColumn('r.paper_strategy_config_id', 'paper_strategy_configs.id')->where('r.broker_account_id', $accountId))->first();
    if (! $freeCfg) {
        echo "SKIP  E6: todas las configs ya tienen suscripción en la cuenta #{$accountId}\n";
    } else {
        $n0 = count($userSubs());
        app(StrategyConfigSync::class)->ensureSubscriptions($freeCfg, [$accountId]);
        $check("E6 ensureSubscriptions (config #{$freeCfg->id} sin suscripción) no crea nada para el usuario inactivo",
            count($userSubs()) === $n0, json_encode($userSubs()));
    }

    // E7. Reactivar: no recupera las eliminadas (elige de nuevo)
    app(UserDeactivation::class)->setActive(User::findOrFail($uid), true);
    $check('E7 reactivado: activo y sin las suscripciones eliminadas', User::find($uid)->is_active && $sorted(array_keys($userSubs())) === $sorted($live),
        json_encode($userSubs()));

    echo "=== F. Pausa manual y suscripciones por eliminar (decisiones del dueño D-03, D-04)\n";
    // F1. Reactivado: una marcada para eliminarse no se puede volver a activar desde la pantalla
    if ($live !== []) {
        $rid = (int) $live[0];
        \Illuminate\Support\Facades\Auth::setUser(User::findOrFail($uid));
        $resp = app(\App\Http\Controllers\RealStrategySubscriptionController::class)
            ->toggle(\App\Models\BrokerAccount::findOrFail((int) DB::table('real_strategy_subscriptions')->where('id', $rid)->value('broker_account_id')),
                RealStrategySubscription::findOrFail($rid));
        $check('F1 reactivar una suscripción marcada para eliminarse -> rechazado, sigue pausada',
            DB::table('real_strategy_subscriptions')->where('id', $rid)->value('status') === 'paused'
            && $resp->getSession()?->get('errors') !== null, (string) DB::table('real_strategy_subscriptions')->where('id', $rid)->value('status'));
    } else {
        echo "SKIP  F1: el usuario no tenía operaciones vivas\n";
    }
    // F2. Usuario reactivado: la limpieza elimina igual una marcada sin operaciones vivas (D-04, opción a)
    $ret = DB::table('real_strategy_subscriptions')->insertGetId(['user_id' => $uid, 'broker_account_id' => $accountId,
        'paper_strategy_config_id' => null, 'strategy' => 'p62-retiro', 'symbol' => 'YYYUSDT', 'interval' => '240',
        'status' => 'paused', 'retire_on_close' => true, 'created_at' => now(), 'updated_at' => now()]);
    app(UserDeactivation::class)->purgeFinished();
    $check('F2 usuario activo: la marcada sin operaciones vivas se elimina; las vivas se conservan',
        ! DB::table('real_strategy_subscriptions')->where('id', $ret)->exists() && $sorted(array_keys($userSubs())) === $sorted($live),
        json_encode($userSubs()));
    // F3. Pausa manual (usuario activo, config activa) con operación abierta: viaja sin entradas (D-03)
    DB::table('real_strategy_subscriptions')->where('id', $subId)->update(['status' => 'paused', 'retire_on_close' => false]);
    DB::table('paper_strategy_configs')->where('id', $cfgId)->update(['active' => true]);
    $hasOpenTrade = DB::table('real_trades')->where('subscription_id', $subId)->whereIn('status', ['open', 'pending_close'])->exists();
    if ($hasOpenTrade) {
        $sent = $sentSubs($accountId);
        $check('F3 suscripción pausada a mano con operación abierta -> viaja SIN entradas (termina su ciclo)',
            is_array($sent) && array_key_exists($subId, $sent) && $sent[$subId] === false, json_encode($sent));
        $oldWinding = RealStrategySubscription::whereKey($subId)->whereHas('user', fn ($u) => $u->where('is_active', false))->exists();
        $check('F3-control: con la regla anterior (solo usuarios inactivos) NO habría viajado', ! $oldWinding);
        // F4. Defensa: si el motor no confirma 'sub_entries' (motor anterior), la pausada NO viaja (podría abrir)
        \Illuminate\Support\Facades\Cache::forget('engine:features:sub_entries');
        Http::swap(new HttpFactory());
        Http::fake(['*' => Http::response(['status' => 'ok', 'results' => []], 200)]);   // /health sin 'features'
        (new RealTradingAccountTickJob($accountId))->handle();
        $last = Http::recorded()->last();
        $subsSent = $last ? collect($last[0]->data()['accounts'][0]['subscriptions'] ?? [])->pluck('subscription_id')->map(fn ($v) => (int) $v)->all() : [];
        $check('F4 motor sin sub_entries -> la suscripción pausada NO viaja', ! in_array($subId, $subsSent, true), json_encode($subsSent));
        \Illuminate\Support\Facades\Cache::forget('engine:features:sub_entries');
    } else {
        echo "SKIP  F3: la suscripción #{$subId} no tiene operación abierta\n";
    }

    echo "=== G. Borrar suscripción o cuenta con una operación sin confirmar (orphaned) (R-04)\n";
    $g = DB::table('real_trades as t')->join('real_strategy_subscriptions as s', 's.id', '=', 't.subscription_id')
        ->whereIn('t.status', ['open', 'pending_close'])->orderBy('t.id')
        ->first(['t.id as trade', 's.id as sub', 't.broker_account_id as acc']);
    if ($g) {
        $acc = \App\Models\BrokerAccount::findOrFail((int) $g->acc);
        \Illuminate\Support\Facades\Auth::setUser(User::findOrFail((int) $acc->user_id));
        DB::table('real_trades')->where('id', $g->trade)->update(['status' => 'orphaned']);
        $oldRule = DB::table('real_trades')->where('subscription_id', $g->sub)->whereIn('status', ['open', 'pending_open', 'pending_close'])->exists();
        $resp = app(\App\Http\Controllers\RealStrategySubscriptionController::class)
            ->destroy($acc, RealStrategySubscription::findOrFail((int) $g->sub));
        $check("G1 suscripción #{$g->sub} con la operación #{$g->trade} sin confirmar -> NO se elimina",
            DB::table('real_strategy_subscriptions')->where('id', $g->sub)->exists() && $resp->getSession()?->get('errors') !== null);
        $onlyOrphan = DB::table('real_trades')->where('subscription_id', $g->sub)->whereIn('status', RealTrade::RECONCILE_STATUSES)->pluck('status')->unique()->all();
        if ($onlyOrphan === ['orphaned']) {
            $check('G1-control: con el filtro anterior (sin orphaned) se habría eliminado', ! $oldRule);
        }
        // G2. Sin suscripciones (la operación ya no tiene suscripción) pero con la operación sin confirmar: la cuenta no se borra
        DB::table('real_strategy_subscriptions')->where('broker_account_id', $acc->id)->delete();   // FK: subscription_id -> NULL
        $resp = app(\App\Http\Controllers\BrokerAccountController::class)->destroy($acc->fresh());
        $check("G2 cuenta #{$acc->id} sin suscripciones y con la operación sin confirmar -> NO se elimina",
            DB::table('broker_accounts')->where('id', $acc->id)->exists() && $resp->getSession()?->get('errors') !== null);
        // G3. Control positivo: sin operaciones vivas ni sin confirmar, la cuenta SÍ se borra (no se bloqueó todo)
        // (en un punto de guardado: un error ajeno a R-04 al borrar la cuenta se informa, no tumba la prueba)
        DB::beginTransaction();
        try {
            DB::table('real_trades')->where('broker_account_id', $acc->id)->whereIn('status', RealTrade::RECONCILE_STATUSES)->update(['status' => 'closed']);
            app(\App\Http\Controllers\BrokerAccountController::class)->destroy($acc->fresh());
            $check("G3 control: sin operaciones vivas la cuenta #{$acc->id} se elimina", ! DB::table('broker_accounts')->where('id', $acc->id)->exists());
        } catch (\Illuminate\Database\QueryException $qe) {
            echo 'SKIP  G3: la base no deja borrar la cuenta por otra razón (anterior a R-04): ' . substr($qe->getMessage(), 0, 160) . "\n";
        } finally {
            DB::rollBack();
        }
    } else {
        echo "SKIP  G: no hay ninguna operación abierta con suscripción para armar el caso\n";
    }
} catch (\Throwable $e) {
    $fails++;
    echo 'FAIL  excepción inesperada: ' . get_class($e) . ': ' . $e->getMessage() . "\n";
} finally {
    DB::rollBack();
}

echo "=== Z. La base quedó intacta\n";
$after = $counts();
$check('Z1 conteos idénticos antes/después (rollback)', $before === $after, json_encode(['antes' => $before, 'despues' => $after]));

echo "\n" . ($fails === 0 ? 'TODO OK' : "FALLOS: {$fails}") . "\n";
exit($fails === 0 ? 0 : 1);

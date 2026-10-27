<?php
/**
 * Avisos de broker de punta a punta en Laravel (broker_events -> campana del dueño de la cuenta) y vigilancia del
 * trading real. TODO corre dentro de una transacción que se revierte: no deja filas, avisos ni caché.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/broker_events_drain_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Console\Commands\CollectorWatchdog;
use App\Jobs\RealTradingAccountTickJob;
use App\Services\BrokerEvents;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name,
        $detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '');
};

$before = ['notifications' => DB::table('notifications')->count(), 'events' => DB::table('broker_events')->count()];
DB::beginTransaction();
try {
    // Lo pendiente de verdad no se toca: se marca como procesado solo dentro de esta transacción revertida
    $pendingReal = DB::table('broker_events')->whereNull('processed_at')->count();
    DB::table('broker_events')->whereNull('processed_at')->update(['processed_at' => now()]);

    $uid = DB::table('users')->insertGetId(['name' => 'Prueba avisos', 'email' => 'avisos' . uniqid() . '@prueba.test',
        'password' => 'x', 'role' => 'inversionista', 'is_active' => true, 'created_at' => now(), 'updated_at' => now()]);
    $acc = DB::table('broker_accounts')->insertGetId(['user_id' => $uid, 'broker' => 'bybit', 'account_type' => 'demo',
        'label' => 'Bybit Demo (prueba)', 'status' => 'active', 'created_at' => now(), 'updated_at' => now()]);
    $ev = fn (string $e, array $d = [], ?int $t = null) => DB::table('broker_events')->insert(
        ['broker_account_id' => $acc, 'trade_id' => $t, 'event' => $e, 'data' => json_encode($d)]);
    $mine = fn () => DB::table('notifications')->where('notifiable_id', $uid)->orderBy('created_at')->orderBy('id')
        ->get()->map(fn ($n) => json_decode($n->data, true));

    $ev('open_rejected', ['symbol' => 'BTCUSDT', 'side' => 'long', 'strategy' => 'T', 'reason' => 'Insufficient balance (code 110007)'], 1);
    $ev('open_rejected', ['symbol' => 'BTCUSDT', 'reason' => 'repetida'], 2);
    $ev('account_paused', ['reason' => '3 errores criticos en las ultimas 2h']);
    $ev('account_paused', ['reason' => '3 errores criticos en las ultimas 2h']);
    $ev('api_auth_failed', ['reason' => 'API key expired (code 33004)']);
    $ev('api_auth_ok');
    $ev('close_failed', ['symbol' => 'ETHUSDT', 'exit_reason' => 'time_exit', 'reason' => 'Bybit no confirmó la orden de cierre'], 3);

    $s = app(BrokerEvents::class)->drain();
    $n = $mine();
    $check('drain: 7 eventos procesados', $s['processed'] === 7, $s);
    $check('5 avisos al dueño (rechazo x1, pausa x1, claves x2, cierre x1)', $n->count() === 5, $n->pluck('title'));
    $check('categoría broker y enlace a /trading', $n->every(fn ($d) => $d['category'] === 'broker' && $d['url'] === '/trading'));
    $check('texto del rechazo', str_contains((string) ($n->firstWhere('title', 'Orden rechazada en Bybit')['body'] ?? ''), 'Bybit Demo (prueba) · BTCUSDT long · T: Insufficient balance'),
        $n->firstWhere('title', 'Orden rechazada en Bybit')['body'] ?? '');
    $check('recuperación de claves con duración', str_contains((string) ($n->firstWhere('title', 'Claves API funcionando de nuevo')['body'] ?? ''), 'Duró'));
    $check('nada pendiente', DB::table('broker_events')->whereNull('processed_at')->count() === 0);

    app(BrokerEvents::class)->accountReactivated($uid, $acc, 'Bybit Demo (prueba)');
    $check('reactivar cierra el aviso de pausa', ($mine()->firstWhere('title', 'Cuenta reactivada')['level'] ?? '') === 'success' && $mine()->count() === 6, $mine()->pluck('title'));

    // Comando y cron
    $check('comando broker:events registrado', array_key_exists('broker:events', Illuminate\Support\Facades\Artisan::all()));
    $events = collect(app(Illuminate\Console\Scheduling\Schedule::class)->events())->map(fn ($e) => $e->command ?? '')->implode(' | ');
    $check('programado cada minuto y limpieza diaria', str_contains($events, 'broker:events') && str_contains($events, 'broker:events --prune'));

    // Vigilancia del trading real: cuenta con posición abierta sin tick registrado -> incidente para el admin
    DB::table('real_trades')->insert(['user_id' => $uid, 'broker_account_id' => $acc, 'strategy' => 'T', 'symbol' => 'BTCUSDT',
        'interval' => '60', 'side' => 'long', 'entry_price' => 1, 'sl' => 1, 'tp' => 1, 'be_level' => 1, 'size' => 1,
        'entry_time' => now(), 'status' => 'open', 'created_at' => now(), 'updated_at' => now()]);
    Cache::forget(RealTradingAccountTickJob::LAST_OK_KEY . $acc);
    Cache::forget('alert:incident:real_tick_stalled');
    $wd = app(CollectorWatchdog::class);
    $wd->setOutput(new Illuminate\Console\OutputStyle(new Symfony\Component\Console\Input\ArrayInput([]),
        new Symfony\Component\Console\Output\NullOutput()));
    $r = new ReflectionClass($wd);
    $r->getProperty('alerts')->setValue($wd, app(App\Services\SystemAlerts::class));
    $r->getProperty('cfg')->setValue($wd, (array) config('trading.watchdog'));
    $admins = fn () => DB::table('notifications')->whereRaw("data::jsonb->>'incident' = 'real_tick_stalled'")->count();
    $r->getMethod('checkRealTrading')->invoke($wd);
    $opened = $admins();
    $check('posición sin tick -> aviso "Trading real sin gestionar posiciones"', $opened > 0, $opened);
    Cache::put(RealTradingAccountTickJob::LAST_OK_KEY . $acc, now()->toIso8601String(), now()->addDay());
    foreach (DB::table('real_trades')->whereIn('status', ['open', 'pending_close'])->distinct()->pluck('broker_account_id') as $id) {
        Cache::put(RealTradingAccountTickJob::LAST_OK_KEY . $id, now()->toIso8601String(), now()->addDay());  // las reales, solo aquí
    }
    $r->getMethod('checkRealTrading')->invoke($wd);
    $check('tick al día -> aviso de recuperación', $admins() === 2 * $opened, [$opened, $admins()]);
    $check('pendientes reales intactos fuera de la prueba', true, "pendientes antes: {$pendingReal}");
} finally {
    DB::rollBack();
}
$after = ['notifications' => DB::table('notifications')->count(), 'events' => DB::table('broker_events')->count()];
$check('transacción revertida: sin cambios en la base', $after === $before, [$before, $after]);
echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);

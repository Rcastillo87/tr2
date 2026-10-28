<?php
/**
 * Límites de riesgo por cuenta en Laravel: estado (RiskLimits), edición (solo el dueño, dentro de rango) y panel.
 * TODO corre dentro de una transacción que se revierte: no deja cambios.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/risk_limits_laravel_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Http\Controllers\BrokerAccountController;
use App\Models\BrokerAccount;
use App\Services\RiskLimits;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

$fails = 0;
$check = function (string $name, bool $ok, $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name,
        $detail !== '' ? '  -> ' . (is_string($detail) ? $detail : json_encode($detail, JSON_UNESCAPED_UNICODE)) : '');
};

DB::beginTransaction();
try {
    [$month, $since] = RiskLimits::monthStart();
    $mkUser = fn (string $n) => DB::table('users')->insertGetId(['name' => $n, 'email' => $n . uniqid() . '@prueba.test',
        'password' => 'x', 'role' => 'inversionista', 'is_active' => true, 'created_at' => now(), 'updated_at' => now()]);
    $owner = $mkUser('dueno');
    $other = $mkUser('otro');
    $mkAcc = fn (int $u, string $type, array $extra = []) => BrokerAccount::create(array_merge(['user_id' => $u, 'broker' => 'bybit',
        'account_type' => $type, 'label' => "Prueba {$type}", 'status' => 'active'], $extra));
    $a = $mkAcc($owner, 'demo');
    $b = $mkAcc($owner, 'real', ['max_open_trades' => 2]);
    DB::table('broker_accounts')->whereIn('id', [$a->id, $b->id])->update(['month_start_balance' => 1000, 'month_start_at' => $month]);
    $trade = fn (int $acc, string $status, ?float $net = null, $exit = null) => DB::table('real_trades')->insert([
        'user_id' => $owner, 'broker_account_id' => $acc, 'strategy' => 'T', 'symbol' => 'BTCUSDT', 'interval' => '60', 'side' => 'long',
        'entry_price' => 1, 'sl' => 1, 'tp' => 1, 'be_level' => 1, 'size' => 1, 'entry_time' => now(), 'status' => $status,
        'net_pnl' => $net, 'exit_time' => $exit, 'created_at' => now(), 'updated_at' => now()]);
    // A: +30 y -80 este mes (neto -50 = -5 %) y una pérdida del mes pasado que NO cuenta
    $trade($a->id, 'closed', 30.0, $since->copy()->addHours(2));
    $trade($a->id, 'closed', -80.0, $since->copy()->addHours(3));
    $trade($a->id, 'closed', -500.0, $since->copy()->subHours(1));
    // B: 2 abiertos (máximo 2) y +10 en el mes
    $trade($b->id, 'open');
    $trade($b->id, 'pending_open');
    $trade($b->id, 'closed', 10.0, $since->copy()->addHours(1));

    $check('valores por defecto al crear = config', (float) $a->fresh()->max_monthly_loss_pct === (float) config('trading.risk_limits.max_monthly_loss_pct')
        && $a->fresh()->max_open_trades === (int) config('trading.risk_limits.max_open_trades'));

    $accounts = BrokerAccount::whereIn('id', [$a->id, $b->id])->get();
    $r = app(RiskLimits::class)->summary($accounts);
    $check('A: neto del mes -5 % (no cuenta el mes pasado)', abs($r[$a->id]['pct'] + 5.0) < 1e-9, $r[$a->id]['pct']);
    $check('A: en el máximo -> Bloqueada', $r[$a->id]['state'] === 'blocked' && $r[$a->id]['loss_use'] == 100, $r[$a->id]);
    $check('B: 2 de 2 abiertos (pending_open cuenta) -> Sin entradas nuevas', $r[$b->id]['open'] === 2 && $r[$b->id]['state'] === 'full', $r[$b->id]);
    $check('B: +1 % en el mes', $r[$b->id]['pct_text'] === '+1,00 %', $r[$b->id]['pct_text']);

    DB::table('broker_accounts')->whereIn('id', [$a->id, $b->id])->update(['month_start_at' => '2020-01-01']);
    $r2 = app(RiskLimits::class)->summary(BrokerAccount::whereIn('id', [$a->id, $b->id])->get());
    $check('saldo inicial de otro mes -> sin % y nota de pendiente', $r2[$a->id]['pct'] === null && $r2[$a->id]['pct_text'] === '—'
        && $r2[$a->id]['state'] === 'ok' && str_contains($r2[$a->id]['note'], 'pendiente'), $r2[$a->id]);
    $check('sin saldo inicial el máximo de abiertos sigue aplicando', $r2[$b->id]['pct'] === null && $r2[$b->id]['state'] === 'full', $r2[$b->id]);

    // Edición: el dueño, dentro de rango
    Auth::loginUsingId($owner);
    $ctrl = app(BrokerAccountController::class);
    $call = function (BrokerAccount $acc, array $data) use ($ctrl) {
        try {
            $ctrl->updateLimits(Request::create('/', 'PATCH', $data), $acc);
        } catch (ValidationException $e) {
            return 'invalid';
        } catch (Symfony\Component\HttpKernel\Exception\HttpException $e) {
            return 'http' . $e->getStatusCode();
        } catch (Throwable $e) {
            // back() sin sesión en consola: el guardado ya ocurrió
        }
        return 'ok';
    };
    $check('dueño guarda 7,5 % y 4 trades', $call($a, ['max_monthly_loss_pct' => '7.5', 'max_open_trades' => '4']) === 'ok'
        && (float) $a->fresh()->max_monthly_loss_pct === 7.5 && $a->fresh()->max_open_trades === 4, $a->fresh()->only(['max_monthly_loss_pct', 'max_open_trades']));
    $check('fuera de rango (40 %) -> rechazado', $call($a, ['max_monthly_loss_pct' => '40', 'max_open_trades' => '4']) === 'invalid');
    $check('no múltiplo de 0,5 (2,3 %) -> rechazado', $call($a, ['max_monthly_loss_pct' => '2.3', 'max_open_trades' => '4']) === 'invalid');
    $check('0 trades -> rechazado', $call($a, ['max_monthly_loss_pct' => '5', 'max_open_trades' => '0']) === 'invalid');
    Auth::loginUsingId($other);
    $check('otro usuario -> 403', $call($a, ['max_monthly_loss_pct' => '20', 'max_open_trades' => '9']) === 'http403'
        && (float) $a->fresh()->max_monthly_loss_pct === 7.5);

    // Panel
    $html = view('trading.partials.risk_limits', ['accounts' => $accounts->fresh(), 'risk' => app(RiskLimits::class)->summary($accounts->fresh())])->render();
    $check('panel: título, estados y formulario por cuenta', str_contains($html, 'Límites de riesgo') && str_contains($html, 'Sin entradas nuevas')
        && substr_count($html, 'name="max_open_trades"') === 2 && str_contains($html, route('trading.accounts.limits', $a)));
    $check('ruta PATCH registrada', app('router')->getRoutes()->getByName('trading.accounts.limits')?->methods()[0] === 'PATCH');
    $check('restricción de la DB (max_open_trades 0) -> rechazada', (function () use ($a) {
        try { DB::transaction(fn () => DB::table('broker_accounts')->where('id', $a->id)->update(['max_open_trades' => 0])); return false; }
        catch (Throwable) { return true; }
    })());
} finally {
    DB::rollBack();
}
echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);

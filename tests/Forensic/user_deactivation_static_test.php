<?php
/**
 * U-1..U-3 y R-01 (p62, decisión del dueño 13-nov): reglas estáticas de la inactivación de usuarios. PHP puro (lee el
 * código, sin Laravel ni base); el comportamiento contra la base real lo prueba real_config_gate_test.php (sección E).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/user_deactivation_static_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$src = fn (string $f) => is_file(getcwd() . '/' . $f) ? (string) file_get_contents(getcwd() . '/' . $f) : '';
$method = function (string $code, string $name): string {
    $p = strpos($code, "function {$name}(");
    if ($p === false) {
        return '';
    }
    $next = strpos($code, "\n    public function ", $p + 10);
    return substr($code, $p, $next === false ? null : $next - $p);
};

$sub = $src('app/Models/RealStrategySubscription.php');
$runnable = $method($sub, 'scopeRunnable');
$check('S1 runnable() exige usuario activo (U-1)', str_contains($runnable, "whereHas('user'") && str_contains($runnable, "'is_active', true"), $runnable);
$winding = $method($sub, 'scopeWindingDown');
$check('S2 windingDown(): pausada O usuario inactivo, config activa, con operaciones abiertas (D-03, D-04)',
    str_contains($winding, "where('status', 'paused')") && str_contains($winding, "'is_active', false")
    && str_contains($winding, "'active', true") && str_contains($winding, "'open', 'pending_close'"), $winding);

$svc = $src('app/Services/UserDeactivation.php');
$check('S3 UserDeactivation: setActive en transacción; elimina sin operaciones vivas; las vivas pausadas y marcadas',
    str_contains($svc, 'DB::transaction') && str_contains($svc, '$sub->delete()')
    && str_contains($svc, "'status' => 'paused', 'retire_on_close' => true") && str_contains($svc, 'RealTrade::RECONCILE_STATUSES'));
$check('S3b purgeFinished elimina las marcadas aunque el usuario esté activo (D-04 opción a)',
    str_contains($method($svc, 'purgeFinished'), "where('retire_on_close', true)"));
$tog = $method($src('app/Http/Controllers/RealStrategySubscriptionController.php'), 'toggle');
$check('S3c no se puede reactivar desde la pantalla una suscripción marcada para eliminarse',
    str_contains($tog, '$activating && $subscription->retire_on_close') && str_contains($tog, 'withErrors'), $tog);
$mig = $src('database/sql-migrations/2026_11_13_01_subscription_retire.up.sql');
$check('S3d migración retire_on_close idempotente con su down',
    str_contains($mig, 'ADD COLUMN IF NOT EXISTS retire_on_close boolean NOT NULL DEFAULT false')
    && str_contains($src('database/sql-migrations/2026_11_13_01_subscription_retire.down.sql'), 'DROP COLUMN IF EXISTS retire_on_close'));
$check('S4 UserDeactivation nunca borra trades ni usuarios', ! preg_match('/RealTrade::[^;]*->delete\(|\$user->delete\(/', $svc));

$um = $src('app/Http/Controllers/UserManagementController.php');
$check('S5 inactivar desde Usuarios usa UserDeactivation::setActive (una transacción, U-2)',
    str_contains($um, 'UserDeactivation::class)->setActive(') && ! str_contains($um, "->update(['status' => 'paused'])"));

$prof = $method($src('app/Http/Controllers/ProfileController.php'), 'destroy');
$check('S6 Perfil: el borrado propio está bloqueado (R-01): sin ->delete() ni logout, con mensaje en el formulario',
    $prof !== '' && ! str_contains($prof, '->delete()') && ! str_contains($prof, 'logout') && str_contains($prof, "'userDeletion'"), $prof);

$ens = $method($src('app/Services/StrategyConfigSync.php'), 'ensureSubscriptions');
$check('S7 ensureSubscriptions no crea suscripciones para usuarios inactivos (U-3)', str_contains($ens, "'is_active', true"), $ens);

$job = $src('app/Jobs/RealTradingAccountTickJob.php');
$check('S8 el tick envía windingDown() con entries_allowed=false y las operables con true',
    str_contains($job, '->windingDown()') && str_contains($job, "'entries_allowed'          => \$entries")
    && str_contains($job, '$subPayload($sub, true)') && str_contains($job, '$subPayload($sub, false)'));

$check('S8b defensa: las suscripciones sin entradas solo viajan si el motor confirma sub_entries',
    str_contains($job, '! self::engineSupportsSubEntries()') && str_contains($job, "in_array('sub_entries'"));
$check('S8c el motor anuncia sub_entries en /health', str_contains($src('python-engine/main.py'), 'FEATURES = ["sub_entries"]'));

$con = $src('routes/console.php');
$check('S9 limpieza programada cada 5 min (purgeFinished)', str_contains($con, 'UserDeactivation::class)->purgeFinished()')
    && str_contains($con, "->everyFiveMinutes()->name('inactive-users-purge')"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * R-04 (p64): no se borra una suscripción ni una cuenta con operaciones vivas o sin confirmar con el broker (`orphaned`):
 * la conciliación las recupera con las claves de la cuenta. «Viva» = RealTrade::RECONCILE_STATUSES en todos lados.
 * PHP puro (lee el código); el comportamiento contra la base real lo prueba real_config_gate_test.php (sección G).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/live_trades_delete_static_test.php
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

$trade = $src('app/Models/RealTrade.php');
$check('L0 RECONCILE_STATUSES incluye orphaned', (bool) preg_match("/RECONCILE_STATUSES\s*=\s*\[[^\]]*'orphaned'/", $trade));

$open = $method($src('app/Models/RealStrategySubscription.php'), 'openTrades');
$check('L1 openTrades() de la suscripción usa RealTrade::RECONCILE_STATUSES (incluye orphaned)',
    str_contains($open, 'RealTrade::RECONCILE_STATUSES') && !str_contains($open, "['open', 'pending_open', 'pending_close']"), $open);

$live = $method($src('app/Models/BrokerAccount.php'), 'hasLiveTrades');
$check('L2 BrokerAccount::hasLiveTrades() filtra por la cuenta y por RECONCILE_STATUSES',
    str_contains($live, "where('broker_account_id', \$this->id)") && str_contains($live, 'RealTrade::RECONCILE_STATUSES')
    && str_contains($live, '->exists()'), $live);

$dAcc = $method($src('app/Http/Controllers/BrokerAccountController.php'), 'destroy');
$pLive = strpos($dAcc, '$account->hasLiveTrades()');
$pDel = strpos($dAcc, '$account->delete()');
$check('L3 borrar cuenta: revisa operaciones vivas ANTES de borrar y responde con error',
    $pLive !== false && $pDel !== false && $pLive < $pDel && substr_count($dAcc, 'withErrors') >= 2, $dAcc);
$check('L4 borrar cuenta: sigue exigiendo que no tenga suscripciones', str_contains($dAcc, '$account->subscriptions()->exists()'));

$dSub = $method($src('app/Http/Controllers/RealStrategySubscriptionController.php'), 'destroy');
$pOpen = strpos($dSub, '$subscription->openTrades()->exists()');
$pSubDel = strpos($dSub, '$subscription->delete()');
$check('L5 borrar suscripción: revisa openTrades() ANTES de borrar', $pOpen !== false && $pSubDel !== false && $pOpen < $pSubDel, $dSub);

echo 'RESULTADO: ' . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

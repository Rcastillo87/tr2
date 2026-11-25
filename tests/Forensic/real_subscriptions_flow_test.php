<?php
/**
 * Suscripciones Real y Paper (dueño, 24-nov). PHP puro, sin base de datos.
 * A: al implementar en Paper no se crea nada en Real (antes: una suscripción PAUSADA en todas las cuentas, que parecía
 *    elegida); solo una moneda nueva de un backtest que ya opera en Real entra activa en esas cuentas (opción A).
 * B: fuera de Paper = fuera de Real (Detener, moneda quitada del backtest, backtest eliminado): sin operación viva se
 *    borra; con operación viva se pausa y se borra sola al cerrar (retire_on_close) — App\Support\SubscriptionRetirement.
 * C: activar una suscripción ya no pausa en silencio la otra de la misma moneda (parecía que el botón no cambiaba nada).
 * D: la lista muestra el estado de cada moneda, el botón con su moneda y el aviso de misma moneda
 *    (App\Support\SubscriptionRows); eliminar usa SweetAlert, no confirm() del navegador.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/real_subscriptions_flow_test.php
 */
declare(strict_types=1);

$root = getenv('TR2_TEST_ROOT') ?: getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$read = fn (string $f) => is_file("{$root}/{$f}") ? (string) file_get_contents("{$root}/{$f}") : '';
$code = fn (string $s) => preg_replace('#^\s*(//|\*|/\*).*$#m', '', $s);   // sin comentarios
$method = function (string $src, string $name): string {
    $p = strpos($src, "function {$name}(");
    if ($p === false) {
        return '';
    }
    $b = strpos($src, '{', $p);
    $depth = 0;
    for ($i = $b, $n = strlen($src); $i < $n; $i++) {
        $depth += $src[$i] === '{' ? 1 : ($src[$i] === '}' ? -1 : 0);
        if ($depth === 0) {
            return substr($src, $p, $i - $p + 1);
        }
    }
    return '';
};

// ── A/B: reglas puras ──
foreach (['SubscriptionRetirement', 'SubscriptionRows'] as $cls) {
    $f = "{$root}/app/Support/{$cls}.php";
    $check("P0: existe App\\Support\\{$cls}", is_file($f));
    if (is_file($f)) {
        require_once $f;
    }
}
if (class_exists('App\Support\SubscriptionRetirement')) {
    $R = App\Support\SubscriptionRetirement::class;
    $check('B1: sin operación viva se borra; con operación viva se retira al cerrar',
        $R::split([5 => false, 7 => true, 9 => false]) === ['delete' => [5, 9], 'retire' => [7]]);
    $check('B2: sin suscripciones, nada', $R::split([]) === ['delete' => [], 'retire' => []]);
}
if (class_exists('App\Support\SubscriptionRows')) {
    $W = App\Support\SubscriptionRows::class;
    $subs = [
        ['id' => 116, 'symbol' => 'DOGEUSDT', 'strategy' => 'Tendencia — DOGEUSDT (H4)', 'status' => 'active', 'retire_on_close' => false],
        ['id' => 121, 'symbol' => 'DOGEUSDT', 'strategy' => 'Ruptura — DOGEUSDT (H4)', 'status' => 'paused', 'retire_on_close' => false],
        ['id' => 130, 'symbol' => 'BTCUSDT', 'strategy' => 'Multi — BTCUSDT (H4)', 'status' => 'active', 'retire_on_close' => false],
        ['id' => 131, 'symbol' => 'SOLUSDT', 'strategy' => 'Multi — SOLUSDT (H4)', 'status' => 'paused', 'retire_on_close' => true],
        ['id' => 132, 'symbol' => 'SOLUSDT', 'strategy' => 'Otra — SOLUSDT (H2)', 'status' => 'active', 'retire_on_close' => false],
    ];
    $r = $W::build($subs);
    $check('D1: cada moneda con su propio estado (no el de la primera del grupo)',
        $r[116]['label'] === 'Activa' && $r[121]['label'] === 'Pausada' && $r[130]['state'] === 'active'
        && $r[131]['state'] === 'retiring' && $r[131]['label'] === 'Se elimina al cerrar su operación', $r);
    $check('D2: aviso de misma moneda en las dos configs de DOGE, no en BTC',
        $r[116]['shares'] === ['Ruptura — DOGEUSDT (H4)'] && $r[121]['shares'] === ['Tendencia — DOGEUSDT (H4)']
        && $r[130]['shares'] === []);
    $check('D3: una que se elimina al cerrar no cuenta como misma moneda para la otra', $r[132]['shares'] === []
        && $r[131]['shares'] === ['Otra — SOLUSDT (H2)']);
    $n = $W::sharedNote($r[116]['shares']);
    $check('D4: texto del aviso', $W::sharedNote([]) === null && is_string($n) && str_contains($n, '«Ruptura — DOGEUSDT (H4)»')
        && str_contains($n, 'solo una opera'), $n);
}

// ── A/B: StrategyConfigSync ──
$sync = $code($read('app/Services/StrategyConfigSync.php'));
$ens = $method($sync, 'ensureSubscriptions');
$check('A1: al implementar sin cuentas donde ya opera no se crea ninguna suscripción',
    (bool) preg_match('/if \(\$liveAccounts === \[\]\) \{\s*return;\s*\}/', $ens), $ens);
$check('A2: solo en las cuentas donde ya opera, y activa (nunca pausada)', str_contains($ens, "whereIn('id', \$liveAccounts)")
    && str_contains($ens, "'status'   => 'active'") && ! str_contains($ens, "'paused'") && str_contains($ens, "'is_active', true"), $ens);
$check('A3: ya no existe ensurePausedSubscriptions', ! str_contains($sync, 'function ensurePausedSubscriptions'));
$ret = $method($sync, 'retireSubscriptions');
$check('B3: retireSubscriptions: operación viva -> pausa + retire_on_close; si no, borra', str_contains($ret, 'SubscriptionRetirement::split(')
    && str_contains($ret, 'UserDeactivation::hasLiveTrades(') && str_contains($ret, "update(['status' => 'paused', 'retire_on_close' => true])")
    && str_contains($ret, "whereIn('id', \$plan['delete'])->delete()") && str_contains($ret, 'lockForUpdate()'), $ret);
$deact = $method($sync, 'deactivateBacktest');
$check('B4: Detener en Paper saca de Real (dentro de la transacción)', str_contains($deact, 'DB::transaction(')
    && strpos($deact, '$this->retireSubscriptions(') > strpos($deact, "update(['active' => false])"), $deact);
$del = $method($sync, 'deleteBacktest');
$check('B5: eliminar el backtest saca de Real (antes solo pausaba) y antes de borrar las configs',
    str_contains($del, '$this->retireSubscriptions(') && ! str_contains($del, "->update(['status' => 'paused'])")
    && strpos($del, '$this->retireSubscriptions(') < strpos($del, 'PaperStrategyConfig::whereIn(\'id\', $ids)->delete()'), $del);
$sfb = $method($sync, 'syncFromBacktest');
$check('B6: una moneda quitada del backtest sale de Real', (bool) preg_match(
    "/\\\$summary\['deactivated'\]\[\] = \(string\) \\\$symbol;\s*\\\$this->retireSubscriptions\(\[\(int\) \\\$config->id\]\);/", $sfb));

// ── C: controlador ──
$ctl = $code($read('app/Http/Controllers/RealStrategySubscriptionController.php'));
$tog = $method($ctl, 'toggle');
$check('C1: activar no pausa otra suscripción de la misma moneda', ! str_contains($ctl, 'enforceSingleActivePerSymbol')
    && ! preg_match("/where\('symbol'/", $tog), $tog);
$check('C2: sigue bloqueando reactivar una que se elimina al cerrar', str_contains($tog, 'retire_on_close'));
$eng = $read('python-engine/trading/real_trader.py');
$check('C3: el motor sigue impidiendo dos posiciones en la misma moneda de la cuenta',
    str_contains($eng, "if await self.has_open_trade(sub['subscription_id'], symbol):") && str_contains($eng, 'posicion abierta en Bybit (no registrada en DB)'));

// ── D: pantalla ──
$blade = $read('resources/views/trading/partials/subscriptions_list.blade.php');
$check('D5: la lista usa SubscriptionRows y ya no el estado de la primera moneda del grupo',
    str_contains($blade, '\App\Support\SubscriptionRows::build(') && ! str_contains($blade, '$status = $first->status')
    && str_contains($blade, "\$row = \$rows[\$sub->id];") && str_contains($blade, "{{ \$row['label'] }}"));
$check('D6: el botón dice la moneda', str_contains($blade, "'⏸️ Pausar ' . \$coin") && str_contains($blade, "'▶️ Reanudar ' . \$coin"));
$check('D7: eliminar y pausar con SweetAlert (sin confirm() del navegador)', ! str_contains($blade, 'confirm(\'')
    && str_contains($blade, 'onsubmit="return confirmSubDelete(event, @js($sub->strategy))"')
    && str_contains($blade, 'return confirmSubToggle(event, @js($sub->strategy)'));
$check('D8: una que se elimina al cerrar no muestra botones', (bool) preg_match(
    "/@if \(\\\$row\['state'\] === 'retiring'\)(?:(?!@else).)*Quitada de Paper(?:(?!@else).)*@else/s", $blade));
$acc = $read('resources/views/trading/accounts.blade.php');
$tg = $method($acc, 'confirmSubToggle');
$check('D9: confirmación de activar avisa la misma moneda (sin «pausará automáticamente») y escapa el nombre',
    str_contains($tg, 'sharedWith') && ! str_contains($acc, 'pausará automáticamente') && str_contains($tg, '${esc(name)}'), $tg);
$sd = $method($acc, 'confirmSubDelete');
$check('D10: confirmación de eliminar con SweetAlert', str_contains($sd, 'Swal.fire(') && str_contains($sd, "'Eliminar suscripción'"));

echo $fails === 0 ? "TODO OK\n" : "{$fails} FALLOS\n";
exit($fails === 0 ? 0 : 1);

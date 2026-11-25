<?php
/**
 * D-72 (dueño, 25-nov): en Trading — Cuentas el inversionista no ve nombres de estrategias: la lista de suscripciones,
 * el aviso de misma moneda, las confirmaciones, los mensajes y el modal «Agregar configuración» dicen
 * «Config #N · moneda · temporalidad». El admin sigue viendo los nombres.
 * PHP puro. Uso: cd <raíz del proyecto> && php tests/Forensic/investor_accounts_labels_test.php
 */
declare(strict_types=1);

$root = getenv('TR2_TEST_ROOT') ?: getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$read = fn (string $f) => (string) @file_get_contents("{$root}/{$f}");
require_once "{$root}/app/Support/StrategyLabel.php";
$L = App\Support\StrategyLabel::class;
$has = method_exists($L, 'anon');
$check('A0: existe StrategyLabel::anon', $has);
if ($has) {
    $check('A1: una config: «Config #74 · DOGEUSDT · H4»', $L::anon([74], ['DOGEUSDT'], '240') === 'Config #74 · DOGEUSDT · H4');
    $check('A2: un backtest de varias monedas: todas sus configs y monedas, sin repetir',
        $L::anon([80, 81, 80], ['SOLUSDT', 'ETHUSDT', 'SOLUSDT'], '120') === 'Configs #80, #81 · SOLUSDT, ETHUSDT · H2');
    $check('A3: sin config (vieja) y temporalidad desconocida', $L::anon([], ['BTCUSDT'], '7') === 'Config · BTCUSDT · 7'
        && $L::anon([null, 0], ['BTCUSDT'], 'D') === 'Config · BTCUSDT · D1');
    $check('A4: nunca lleva el nombre de la estrategia', ! str_contains($L::anon([59], ['DOGEUSDT'], '240'), '—'));
}
$list = $read('resources/views/trading/partials/subscriptions_list.blade.php');
$check('L1: la lista decide por el rol y arma «Config #N» para el inversionista', str_contains($list, '$anon = (bool) auth()->user()?->isInversionista();')
    && str_contains($list, '\App\Support\StrategyLabel::anon([(int) $s->paper_strategy_config_id], [(string) $s->symbol], (string) $s->interval)'));
$check('L2: el aviso de misma moneda usa esa etiqueta (no el nombre)', str_contains($list, "'strategy' => \$subName(\$s),"));
$check('L3: el título del grupo usa la etiqueta para el inversionista', str_contains($list,
    "\\App\\Support\\StrategyLabel::anon(\$subs->pluck('paper_strategy_config_id')->all(), \$symbols, (string) \$interval)"));
$check('L4: las confirmaciones de pausar y eliminar usan la etiqueta', str_contains($list, 'confirmSubToggle(event, @js($subName($sub)),')
    && str_contains($list, 'confirmSubDelete(event, @js($subName($sub)))') && ! str_contains($list, '@js($sub->strategy)'));
$acc = $read('resources/views/trading/accounts.blade.php');
$check('M1: el modal «Agregar configuración» usa la etiqueta para el inversionista', str_contains($acc,
    "auth()->user()?->isInversionista() ? \\App\\Support\\StrategyLabel::anon(\$group['config_ids'], \$group['symbols'], (string) \$group['interval']) : \$group['display_name']"));
$ctl = $read('app/Http/Controllers/RealStrategySubscriptionController.php');
$check('C1: los mensajes de activar, pausar y eliminar usan la etiqueta para el inversionista',
    substr_count($ctl, '$name = $this->label($subscription);') === 2 && ! str_contains($ctl, '"Estrategia \"{$subscription->strategy}\"')
    && str_contains($ctl, 'auth()->user()?->isInversionista()'));

echo $fails === 0 ? "TODO OK\n" : "{$fails} FALLOS\n";
exit($fails === 0 ? 0 : 1);

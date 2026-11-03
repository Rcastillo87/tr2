<?php
/**
 * Textos y agrupación de los avisos de broker (App\Services\BrokerEventMessages). PHP puro, sin base de datos.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/broker_event_messages_test.php
 */
declare(strict_types=1);

require getcwd() . '/app/Services/BrokerEventMessages.php';

use App\Services\BrokerEventMessages as M;

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$m = fn (string $e, array $d = [], ?int $t = null) => M::for($e, $d, 'Bybit Real', 7, $t);

$expect = [   // evento => [nivel, modo]
    'open_rejected' => ['warning', 'throttle'], 'open_unconfirmed' => ['error', 'notify'],
    'close_failed' => ['error', 'throttle'], 'close_unconfirmed' => ['error', 'throttle'],
    'account_paused' => ['error', 'open'], 'max_loss_close' => ['error', 'notify'],
    'api_auth_failed' => ['error', 'open'], 'api_auth_ok' => ['success', 'resolve'],
    'liquidation_risk' => ['error', 'notify'],
    'monthly_limit_reached' => ['error', 'open'], 'monthly_limit_reset' => ['success', 'resolve'],
    'reconcile_closed' => ['warning', 'notify'], 'reconcile_adopted' => ['warning', 'notify'],
    'reconcile_discarded' => ['info', 'notify'],
    'protection_failed' => ['error', 'open'], 'protection_restored' => ['success', 'resolve'],
];
foreach ($expect as $e => [$level, $mode]) {
    $r = $m($e, ['symbol' => 'BTCUSDT'], 5);
    $check("{$e}: {$level}/{$mode} con título y texto", $r && $r['level'] === $level && $r['mode'] === $mode
        && $r['title'] !== '' && str_contains($r['body'], 'Bybit Real'), $r);
}
$check('evento desconocido -> sin aviso', $m('xyz') === null);
$hedge = $m('open_rejected', ['symbol' => 'BTCUSDT', 'side' => 'long', 'reason' => 'position idx not match position mode (code 10001)']);
$check('rechazo por modo Hedge: explica cómo pasar a One-Way', str_contains($hedge['body'] ?? '', 'modo Hedge')
    && str_contains($hedge['body'] ?? '', 'One-Way') && str_contains($hedge['body'] ?? '', 'No se abrió ninguna posición'), $hedge['body'] ?? null);
$other = $m('open_rejected', ['symbol' => 'BTCUSDT', 'reason' => 'Insufficient balance (code 110007)']);
$check('otro rechazo: sin la explicación de Hedge', ! str_contains($other['body'] ?? '', 'Hedge'), $other['body'] ?? null);
$pf = $m('protection_failed', ['symbol' => 'SOLUSDT', 'side' => 'long', 'strategy' => 'VWAP', 'sl' => 99.198, 'tp' => 104.208, 'stage' => 'open'], 41);
$pr = $m('protection_restored', ['symbol' => 'SOLUSDT', 'side' => 'long', 'sl' => 99.198, 'tp' => 104.208], 41);
$check('protección: mismo incidente por trade para abrir y cerrar', ($pf['key'] ?? 1) === ($pr['key'] ?? 2) && ($pf['key'] ?? '') === 'protection:7:41', [$pf['key'] ?? null, $pr['key'] ?? null]);
$check('protección: incidentes distintos por trade', ($pf['key'] ?? 1) !== ($m('protection_failed', ['symbol' => 'SOLUSDT'], 42)['key'] ?? 1));
$check('protección: el aviso dice SL/TP de la estrategia y el stop provisional',
    str_contains($pf['body'] ?? '', 'SL 99,198 / TP 104,208') && str_contains($pf['body'] ?? '', 'stop provisional de la orden (2 % / 4 %)')
    && str_contains($pf['body'] ?? '', 'SOLUSDT #41 long · VWAP'), $pf['body'] ?? null);
$r = $m('protection_failed', ['symbol' => 'SOLUSDT', 'sl' => 99.2, 'exchange_sl' => 98.0, 'stage' => 'monitor'], 41);
$check('protección (monitor): muestra el SL que sigue en Bybit', str_contains($r['body'] ?? '', 'SL 98 en Bybit'), $r['body'] ?? null);
$check('protección restaurada: texto con el SL/TP', str_contains($pr['body'] ?? '', 'ya está en Bybit (SL 99,198 / TP 104,208)'), $pr['body'] ?? null);
// Todo evento que emite el motor tiene texto (broker_events.EVENTS ↔ BrokerEventMessages)
$py = file_get_contents(getcwd() . '/python-engine/trading/broker_events.py');
preg_match('/EVENTS = frozenset\(\{(.*?)\}\)/s', $py, $mm);
preg_match_all("/^\s*'([a-z_]+)',/m", $mm[1] ?? '', $ev);
$missing = array_values(array_filter($ev[1], fn ($e) => $m($e, ['symbol' => 'BTCUSDT'], 1) === null));
$check('cada evento del motor tiene aviso (' . count($ev[1]) . ' eventos)', count($ev[1]) >= 16 && $missing === [], $missing);
$check('pausa y claves: mismo incidente para abrir y cerrar', $m('api_auth_failed')['key'] === $m('api_auth_ok')['key']
    && $m('account_paused')['key'] === 'account_paused:7');
$check('límite de repetición por cuenta y símbolo', $m('open_rejected', ['symbol' => 'BTCUSDT'])['key'] !== $m('open_rejected', ['symbol' => 'ETHUSDT'])['key']);
$r = $m('reconcile_adopted', ['symbol' => 'SOLUSDT', 'protected' => false], 9);
$check('adoptada sin configuración -> error y lo dice', $r['level'] === 'error' && str_contains($r['body'], 'SL/TP provisional'), $r);
$r = $m('open_rejected', ['symbol' => 'BTCUSDT', 'side' => 'long', 'strategy' => 'VWAP', 'reason' => str_repeat('x', 400)]);
$check('motivo largo recortado', mb_strlen($r['body']) < 300 && str_contains($r['body'], '…'), mb_strlen($r['body']));
$r = $m('close_failed', ['symbol' => 'ETHUSDT', 'exit_reason' => 'time_exit'], 3);
$check('motivo de cierre traducido y referencia del trade', str_contains($r['body'], 'ETHUSDT #3 (tiempo máximo)'), $r['body']);
$r = $m('max_loss_close', ['symbol' => 'BTCUSDT', 'loss_pct' => 2.4567, 'limit_pct' => 1.8], 4);
$check('pérdida máxima con porcentajes', str_contains($r['body'], '2,46 %') && str_contains($r['body'], 'límite 1,80 %'), $r['body']);
$check('reactivación', M::reactivated('Bybit Real')['title'] === 'Cuenta reactivada');
$r = $m('liquidation_risk', ['symbol' => 'BTCUSDT', 'side' => 'long', 'sl' => 98.5, 'liq_price' => 99.1, 'leverage' => 50, 'closed' => true], 8);
$check('liquidación: cerrada, con SL, liquidación y apalancamiento', $r['title'] === 'Posición cerrada: riesgo de liquidación'
    && str_contains($r['body'], '(98,5)') && str_contains($r['body'], '(99,1)') && str_contains($r['body'], '50x'), $r['body']);
$r = $m('liquidation_risk', ['symbol' => 'BTCUSDT', 'closed' => false], 8);
$check('liquidación sin cerrar: pide cerrarla en Bybit', str_contains($r['title'], 'ciérrala'), $r['title']);
$r = $m('reconcile_adopted', ['symbol' => 'BTCUSDT', 'kind' => 'pending', 'protected' => true], 9);
$check('adoptada tras apertura interrumpida', str_contains($r['body'], 'se interrumpió'), $r['body']);
$r = $m('monthly_limit_reached', ['pct' => -5.2, 'limit' => 5.0]);
$check('límite mensual: porcentaje y máximo', str_contains($r['body'], '-5,20 %') && str_contains($r['body'], 'máximo −5 %'), $r['body']);
$check('límite mensual: mismo incidente para abrir y cerrar', $r['key'] === $m('monthly_limit_reset')['key']);
echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);

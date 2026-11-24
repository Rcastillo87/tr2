<?php
/**
 * D-66 (p111): opciones de los límites de riesgo en Laravel. PHP puro, sin base.
 * - A: App\Services\RiskLimits::evaluate (la regla del panel, la misma del motor): pausa en curso y terminada, conteo
 *   desde que se reanudó, «sin límite» en cada límite, interruptor general, huérfanas en el conteo de abiertos.
 * - B: formulario y validación (BrokerAccountController::updateLimits): checkbox «Sin límite» con su oculto, pausa 1–30.
 * - C: avisos (monthly_limit_reached con la pausa, loss_pause_ended), vigilante y configuración.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/risk_limit_options_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

require "{$root}/app/Services/RiskLimits.php";
$R = App\Services\RiskLimits::class;
$since = 1_000_000;            // inicio del mes (segundos Unix)
$now = $since + 10 * 86400;    // 10 días después
$acc = fn (array $o = []) => $o + ['max_loss' => 5.0, 'max_open' => 3, 'month_at' => '2026-11-01', 'month_balance' => 1000.0,
    'loss_enabled' => true, 'open_enabled' => true, 'pause_days' => null, 'paused_until' => null, 'paused_until_text' => null,
    'period_start' => null, 'period_start_text' => null, 'period_balance' => null];
$ev = fn (array $a, float $pnl = 0.0, int $open = 0, bool $opt = true, ?array $unr = null) => $R::evaluate($a, $pnl, $open, '2026-11-01', $since, $now, $opt, '1 de diciembre', $unr);

$r = $ev($acc(), -20.0, 1);
$check('A1: como hoy (sin pausa, límites activos): -2 % y 1/3 -> opera normal', $r['state'] === 'ok' && $r['label'] === 'Mes'
    && $r['pct_text'] === '−2,00 %' && $r['loss_on'] && $r['open_on'] && $r['note'] === '', $r);
$r = $ev($acc(), -50.0);
$check('A2: sin pausa, llega al límite -> bloqueada hasta el día 1 (como hoy)', $r['state'] === 'blocked'
    && str_contains($r['note'], 'sin entradas hasta el 1 de diciembre'), $r['note']);
$r = $ev($acc(['pause_days' => 3]), -50.0);
$check('A3: con pausa, llega al límite -> «pausa de 3 día(s)» desde el próximo ciclo', $r['state'] === 'blocked'
    && str_contains($r['note'], 'pausa de 3 día(s)'), $r['note']);
$r = $ev($acc(['pause_days' => 3, 'paused_until' => $now + 3600, 'paused_until_text' => '13-nov 10:00']), 30.0);
$check('A4: pausa en curso -> «En pausa hasta …» aunque mejore', $r['state'] === 'paused' && $r['paused_text'] === '13-nov 10:00'
    && str_contains($r['note'], 'hasta el 13-nov 10:00') && str_contains($r['note'], 'se cuenta de cero'), $r);
$r = $ev($acc(['pause_days' => 3, 'paused_until' => $now - 60, 'paused_until_text' => '10-nov 09:59']));
$check('A5: pausa terminada sin reanudar -> sigue en pausa hasta el próximo ciclo', $r['state'] === 'paused' && $r['paused_text'] === null
    && str_contains($r['note'], 'próximo ciclo'), $r);
$r = $ev($acc(['pause_days' => 3, 'period_start' => $since + 5 * 86400, 'period_start_text' => '13-nov', 'period_balance' => 2000.0]), -50.0);
$check('A6: tras reanudar -> «Desde 13-nov» y % sobre la base nueva (-50/2000)', $r['label'] === 'Desde 13-nov' && $r['pct_text'] === '−2,50 %'
    && $r['state'] === 'ok', $r);
$r = $ev($acc(['period_start' => $since - 86400, 'period_start_text' => '31-oct', 'period_balance' => 2000.0]), -50.0);
$check('A7: período del mes anterior -> cuenta el mes con su saldo', $r['label'] === 'Mes' && $r['pct_text'] === '−5,00 %' && $r['state'] === 'blocked', $r);
$r = $ev($acc(['loss_enabled' => false, 'month_at' => null, 'paused_until' => $now + 3600, 'paused_until_text' => 'x']), -900.0);
$check('A8: pérdida «sin límite» -> opera aunque pierda, sin pausa, sin pedir saldo del mes, y lo avisa',
    $r['state'] === 'ok' && ! $r['loss_on'] && $r['loss_use'] == 0
    && $r['note'] === 'Protecciones desactivadas: pérdida del mes sin límite.', $r);
$r = $ev($acc(['open_enabled' => false]), 0.0, 9);
$check('A9: trades «sin límite» -> 9 de 3 opera normal y lo avisa', $r['state'] === 'ok' && ! $r['open_on']
    && $r['note'] === 'Protecciones desactivadas: trades abiertos sin límite.', $r);
$r = $ev($acc(['loss_enabled' => false, 'open_enabled' => false]), 0.0, 9);
$check('A10: los dos «sin límite» -> un solo aviso con los dos', $r['note'] === 'Protecciones desactivadas: pérdida del mes y trades abiertos sin límite.', $r['note']);
$r = $ev($acc(['open_enabled' => true]), 0.0, 3);
$check('A11: 3 de 3 con el límite activo -> sin entradas nuevas', $r['state'] === 'full', $r);
$r = $ev($acc(['loss_enabled' => false, 'open_enabled' => false, 'pause_days' => 3]), -50.0, 3, false);
$check('A12: interruptor general apagado -> como antes de p111 (bloqueada hasta el día 1, sin pausa)', $r['state'] === 'blocked'
    && str_contains($r['note'], 'hasta el 1 de diciembre') && $r['loss_on'] && $r['open_on'], $r);
// C6-02 (p116): antes «ok» («Opera normal») con una nota; el motor no abre (D-51): ahora es un estado propio
$r = $ev($acc(['month_at' => null]), 0.0, 1);
$check('A13: límite activo sin saldo del mes -> «esperando saldo base», no «ok» (el motor no abre, D-51)',
    $r['state'] === 'waiting_baseline' && str_contains($r['note'], 'Falta el saldo inicial del mes')
    && str_contains($r['note'], 'Las abiertas se siguen gestionando') && str_contains($r['note'], 'reintenta cada minuto'), $r);
$r = $ev($acc());
$check('A13b: con el saldo del mes disponible vuelve a «ok»', $r['state'] === 'ok' && $r['note'] === '', $r);
$r = $ev($acc(['month_at' => null, 'loss_enabled' => false]));
$check('A13c: con la pérdida «sin límite» no se exige el saldo base (como el motor)', $r['state'] === 'ok', $r);
$r = $ev($acc(), 0.0, 1, true, ['id' => 123, 'symbol' => 'ADAUSDT', 'status' => 'orphaned']);
$check('A16: operación sin confirmar -> «unresolved» con su número y moneda (D-50: el motor no abre)',
    $r['state'] === 'unresolved' && str_contains($r['note'], '#123 ADAUSDT sin confirmar con Bybit'), $r);
$r = $ev($acc(['month_at' => null]), 0.0, 1, true, ['id' => 123, 'symbol' => 'ADAUSDT', 'status' => 'orphaned']);
$check('A17: el orden es el del motor: saldo base antes que operación sin confirmar', $r['state'] === 'waiting_baseline', $r['state']);
$r = $ev($acc(), -60.0, 1, true, ['id' => 123, 'symbol' => 'ADAUSDT', 'status' => 'pending_open']);
$check('A18: operación sin confirmar antes que pérdida máxima (como el motor)', $r['state'] === 'unresolved', $r['state']);
$r = $ev($acc(['pause_days' => 3, 'paused_until' => $now + 60, 'paused_until_text' => 'x', 'month_at' => null]), 0.0, 0, true,
    ['id' => 1, 'symbol' => 'X', 'status' => 'orphaned']);
$check('A19: la pausa va primero (como el motor)', $r['state'] === 'paused', $r['state']);
$check('A20b: el panel le pasa a la regla la operación dudosa de cada cuenta',
    str_contains(file_get_contents("{$root}/app/Services/RiskLimits.php"), "\$unresolved[\$a->id] ?? null);"));
$check('A20: la consulta de operaciones dudosas usa la regla del motor (orphaned o pending_open de más de 3 min)',
    str_contains($svc_src = file_get_contents("{$root}/app/Services/RiskLimits.php"), "->where('status', 'orphaned')->orWhere(fn (\$p) => \$p->where('status', 'pending_open')")
    && str_contains($svc_src, 'RealTrade::PENDING_OPEN_STALE_MIN'));
$check('A14: el conteo de abiertos incluye las huérfanas (como el motor, C5-16)',
    $R::OPEN_STATUSES === ['pending_open', 'open', 'pending_close', 'orphaned']);

$svc = file_get_contents("{$root}/app/Services/RiskLimits.php");
$check('A15: la pérdida se suma desde el período (si empezó este mes) o desde el día 1, en una consulta para todas las cuentas',
    str_contains($svc, "CASE WHEN ?::boolean AND ba.loss_period_start > ?::timestamp AND ba.loss_period_balance > 0")
    && str_contains($svc, "[\$options ? 'true' : 'false', \$since, \$since]"));

$ctl = file_get_contents("{$root}/app/Http/Controllers/BrokerAccountController.php");
$check('B1: validación: «sin límite» booleanos y pausa entera de 1 a 30 (vacía permitida)',
    str_contains($ctl, "'monthly_loss_unlimited' => ['nullable', 'boolean']") && str_contains($ctl, "'open_trades_unlimited'  => ['nullable', 'boolean']")
    && str_contains($ctl, "'loss_pause_days'        => ['nullable', 'integer', 'min:1', 'max:30']"));
$check('B2: guarda activado = no marcado, conserva el número y la pausa vacía = null',
    str_contains($ctl, "'monthly_loss_enabled'      => \$lossOn") && str_contains($ctl, "'open_trades_limit_enabled' => \$openOn")
    && str_contains($ctl, "\$lossOn = ! \$request->boolean('monthly_loss_unlimited')") && str_contains($ctl, "\$days = \$validated['loss_pause_days'] ?? null"));
$blade = file_get_contents("{$root}/resources/views/trading/partials/risk_limits.blade.php");
$check('B3: formulario: «Sin límite» en los dos (con su oculto 0) y campo de pausa 1–30',
    substr_count($blade, '> Sin límite') === 2 && str_contains($blade, '<input type="hidden" name="monthly_loss_unlimited" value="0">')
    && str_contains($blade, '<input type="hidden" name="open_trades_unlimited" value="0">')
    && str_contains($blade, 'name="loss_pause_days" value="{{ $r[\'pause_days\'] }}" min="1" max="30"'));
$check('B4b: panel: los dos estados nuevos con su texto (no «Opera normal»)',
    str_contains($blade, "'waiting_baseline' => ['Esperando saldo base · sin entradas nuevas', 'var(--color-neutral)']")
    && str_contains($blade, "'unresolved' => ['Operación sin confirmar · sin entradas nuevas', 'var(--color-neutral)']"));
$check('B4: panel: «/ sin límite», etiqueta del conteo y estado «En pausa hasta …»',
    substr_count($blade, '/ sin límite') === 2 && str_contains($blade, "{{ \$r['label'] }}")
    && str_contains($blade, "\$stateLabel = 'En pausa hasta ' . \$r['paused_text'];"));
preg_match_all('/@(if|endif)\b/', $blade, $m);
$check('B5: Blade con @if / @endif balanceados', count(array_keys($m[1], 'if')) === count(array_keys($m[1], 'endif')), array_count_values($m[1]));
$model = file_get_contents("{$root}/app/Models/BrokerAccount.php");
$check('B6: el modelo permite guardar las tres opciones', str_contains($model, "'monthly_loss_enabled',") && str_contains($model, "'open_trades_limit_enabled',")
    && str_contains($model, "'loss_pause_days',"));

$msg = file_get_contents("{$root}/app/Services/BrokerEventMessages.php");
$check('C1: aviso de pérdida máxima con la pausa y hasta cuándo', str_contains($msg, "isset(\$data['paused_until'])")
    && str_contains($msg, "no se abren posiciones hasta el {\$data['paused_until']}"));
$check('C2: aviso «Terminó la pausa por pérdida» cierra el de pérdida máxima',
    (bool) preg_match("/'loss_pause_ended' => \\[\\s*'level' => 'success', 'mode' => 'resolve', 'key' => \"monthly_limit:\\{\\\$accountId\\}\"/", $msg));
$wd = file_get_contents("{$root}/app/Console/Commands/CollectorWatchdog.php");
$check('C3: el vigilante no pide saldo del mes a cuentas con la pérdida «sin límite»', str_contains($wd, "->where('monthly_loss_enabled', true)"));
$cfg = file_get_contents("{$root}/config/trading.php");
$check('C4: interruptor general en la configuración (mismo nombre que el motor), encendido por defecto',
    str_contains($cfg, "'risk_limit_options' => (bool) env('RISK_LIMIT_OPTIONS_ENABLED', true)"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

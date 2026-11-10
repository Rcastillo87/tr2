<?php
/**
 * CFG-05 (PHP puro, revisión del código): borrar un backtest pasa por StrategyConfigSync::deleteBacktest, que bloquea
 * con config activa, trade Paper abierto o trade Real en RealTrade::RECONCILE_STATUSES (incluye 'orphaned'), comprueba
 * dentro de la transacción con las configs bloqueadas y deja auditoría 'deleted'. La prueba contra la base real
 * (transacción revertida) es backtest_delete_test.php.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/backtest_delete_rules_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok) use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s\n", $ok ? 'PASS' : 'FAIL', $name);
};
$root = getcwd();
$sync = file_get_contents("{$root}/app/Services/StrategyConfigSync.php");
preg_match('/public function deleteBacktest\(.*?\n    \}\n/s', $sync, $m);
$body = $m[0] ?? '';

$check('B0: existe StrategyConfigSync::deleteBacktest', $body !== '');
$check('B1: todo dentro de DB::transaction', str_contains($body, 'DB::transaction('));
$tx = strpos($body, 'DB::transaction(');
$lock = strpos($body, 'lockForUpdate()');
$check('B2: bloquea las configs (lockForUpdate) dentro de la transacción', $lock !== false && $lock > $tx);
$check('B3: bloquea si hay config activa', (bool) preg_match("/where\('active', true\)->isNotEmpty\(\)/", $body));
$check('B4: bloquea si hay trades Paper abiertos',
    (bool) preg_match("/paper_trades'\)->whereIn\('paper_strategy_config_id', \\\$ids\)->where\('status', 'open'\)/", $body));
$check('B5: bloquea con trades Real en RealTrade::RECONCILE_STATUSES (incluye orphaned)',
    str_contains($body, "whereIn('status', RealTrade::RECONCILE_STATUSES)"));
$check("B6: auditoría 'deleted' por config antes de borrar",
    (bool) preg_match("/audit\(\\\$config, 'deleted'.*?SOURCE_DELETE/s", $body)
    && strpos($body, "'deleted'") < strpos($body, 'PaperStrategyConfig::whereIn(\'id\', $ids)->delete()'));
$check("B6b: la fila 'deleted' guarda config_id y backtest_id en new_params (las FK SET NULL los anulan)",
    (bool) preg_match("/'deleted' => \['config_id' => .*'backtest_id' => /", $body));
$check('B7: pausa las suscripciones Real activas', (bool) preg_match("/update\(\['status' => 'paused'\]\)/", $body));
$check('B8: las comprobaciones van antes de cualquier escritura',
    strpos($body, 'RECONCILE_STATUSES') < strpos($body, "'paused'"));

$ctl = file_get_contents("{$root}/app/Http/Controllers/BacktestingController.php");
preg_match('/public function destroyBacktest\(.*?\n    \}\n/s', $ctl, $c);
$cb = $c[0] ?? '';
$check('C1: destroyBacktest delega en $sync->deleteBacktest', str_contains($cb, '$sync->deleteBacktest($backtest'));
$check('C2: destroyBacktest no borra por su cuenta', ! str_contains($cb, '->delete()'));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

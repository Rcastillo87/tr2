<?php
/**
 * D-63 (C5-13): borrar una estrategia. PHP puro, sin base de datos.
 * - A: regla App\Support\StrategyDeletionPlan (qué bloquea, qué suscripciones se borran ya y cuáles al cerrar).
 * - B: mensaje final con lo borrado.
 * - C: StrategyConfigSync::deleteStrategy (revisión del código): todo en una transacción con bloqueo, comprobaciones
 *   antes de escribir, auditoría antes de borrar las configs, nunca borra operaciones Real, orden compatible con las FK.
 * - D: el controlador delega (antes borraba directo y con configs detenidas daba error 500 por la FK RESTRICT).
 * La prueba contra la base real (transacción revertida) es strategy_delete_test.php (a mano en el servidor).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/strategy_delete_rules_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$planFile = "{$root}/app/Support/StrategyDeletionPlan.php";
$check('A0: existe App\Support\StrategyDeletionPlan', is_file($planFile));
if (is_file($planFile)) {
    require $planFile;
    $P = App\Support\StrategyDeletionPlan::class;

    $r = $P::decide([1 => false, 2 => true], false, 0, [7 => false]);
    $check('A1: una config activa en Paper bloquea, con el mensaje de siempre', $r['error'] === $P::ACTIVE_PAPER
        && $r['delete_subs'] === [] && $r['retire_subs'] === [], $r);
    $r = $P::decide([], true, 0, []);
    $check('A2: config activa de legado (sin backtest, por etiqueta) también bloquea', $r['error'] === $P::ACTIVE_PAPER, $r);
    $r = $P::decide([1 => false], false, 2, [7 => false]);
    $check('A3: búsqueda en cola o en curso bloquea y dice cuántas', str_contains((string) $r['error'], '2 búsqueda(s) en cola o en curso')
        && $r['delete_subs'] === [], $r);
    $r = $P::decide([1 => true], false, 3, []);
    $check('A4: Paper activa se informa primero (antes que las búsquedas)', $r['error'] === $P::ACTIVE_PAPER, $r);
    $r = $P::decide([1 => false, 2 => false], false, 0, [7 => false, 8 => true, 9 => false]);
    $check('A5: configs detenidas: no bloquea; suscripción sin operación viva se borra, con operación viva se retira al cerrar',
        $r['error'] === null && $r['delete_subs'] === [7, 9] && $r['retire_subs'] === [8], $r);
    $r = $P::decide([], false, 0, []);
    $check('A6: estrategia sin configs ni suscripciones: se borra', $r['error'] === null && $r['delete_subs'] === [] && $r['retire_subs'] === [], $r);

    $s = $P::summary('Cruce', ['backtests' => 3, 'searches' => 5, 'configs' => 2, 'paper_trades' => 140, 'subs_deleted' => 1, 'subs_retired' => 0]);
    $check('B1: el mensaje dice lo borrado', $s === 'Estrategia Cruce eliminada: 3 backtests, 5 búsquedas, 2 configuraciones, 140 operaciones de Paper, 1 suscripción Real.', $s);
    $s = $P::summary('X', ['backtests' => 1, 'searches' => 0, 'configs' => 1, 'paper_trades' => 1, 'subs_deleted' => 0, 'subs_retired' => 1]);
    $check('B2: singulares, sin los ceros, y aviso de la suscripción que se borra al cerrar',
        $s === 'Estrategia X eliminada: 1 backtest, 1 configuración, 1 operación de Paper. 1 suscripción Real tiene una operación abierta: se pausó y se eliminará sola al cerrar.', $s);
    $s = $P::summary('Y', ['backtests' => 0, 'searches' => 0, 'configs' => 0, 'paper_trades' => 0, 'subs_deleted' => 0, 'subs_retired' => 2]);
    $check('B3: sin nada más que la estrategia', $s === 'Estrategia Y eliminada. 2 suscripciones Real tienen una operación abierta: se pausaron y se eliminarán solas al cerrar.', $s);
}

$sync = file_get_contents("{$root}/app/Services/StrategyConfigSync.php");
preg_match('/public function deleteStrategy\(.*?\n    \}\n/s', $sync, $m);
$b = $m[0] ?? '';
$pos = fn (string $needle) => strpos($b, $needle);
$check('C0: existe StrategyConfigSync::deleteStrategy', $b !== '');
$check('C1: todo dentro de DB::transaction, con la estrategia, backtests, configs y suscripciones bloqueadas',
    $b !== '' && $pos('DB::transaction(') < $pos('Strategy::whereKey($strategy->id)->lockForUpdate()')
    && substr_count($b, 'lockForUpdate()') === 4);
$guard = "if (\$plan['error'] !== null) {\n                return ['error' => \$plan['error'], 'message' => null];\n            }";
$check('C2: la regla decide y, si bloquea, sale antes de cualquier escritura',
    $b !== '' && $pos($guard) !== false && $pos('StrategyDeletionPlan::decide(') < $pos($guard)
    && $pos($guard) < $pos('$this->audit(') && $pos($guard) < $pos('->delete()') && $pos($guard) < $pos('->update('));
$check('C3: búsquedas en curso según ParamSearchRun::ACTIVE', str_contains($b, "whereIn('status', ParamSearchRun::ACTIVE)"));
$check('C4: operación viva por suscripción con la regla de D-04 (UserDeactivation::hasLiveTrades)', str_contains($b, 'UserDeactivation::hasLiveTrades('));
$check("C5: auditoría 'deleted' por config (con strategy_id) antes de borrar las configs",
    (bool) preg_match("/'strategy_id' => \(int\) \\\$strategy->id/", $b)
    && $pos("self::SOURCE_STRATEGY_DELETE") !== false && $pos("self::SOURCE_STRATEGY_DELETE") < $pos("PaperStrategyConfig::whereIn('id', \$ids)->delete()"));
$check('C6: borra lo de Paper de esas configs (operaciones y registro de evaluación)',
    str_contains($b, "DB::table('paper_trades')->whereIn('paper_strategy_config_id', \$ids)->delete()")
    && str_contains($b, "DB::table('paper_eval_state')") && str_contains($b, "DB::table('paper_eval_log')"));
$check('C7: nunca borra ni cambia operaciones Real', ! preg_match('/real_trades|RealTrade::/', $b));
$check('C8: suscripciones: retira al cerrar (pausada + retire_on_close) o borra',
    str_contains($b, "whereIn('id', \$plan['retire_subs'])->update(['status' => 'paused', 'retire_on_close' => true])")
    && str_contains($b, "whereIn('id', \$plan['delete_subs'])->delete()"));
$check('C9: orden de las FK: configs antes que backtests (RESTRICT), backtests y búsquedas antes que la estrategia',
    $b !== '' && $pos("PaperStrategyConfig::whereIn('id', \$ids)->delete()") < $pos("Backtest::whereIn('id', \$backtestIds)->delete()")
    && $pos("ParamSearchRun::where('strategy_id', \$strategy->id)->delete()") < $pos('$strategy->delete()')
    && $pos("Backtest::whereIn('id', \$backtestIds)->delete()") < $pos('$strategy->delete()'));

$ctl = file_get_contents("{$root}/app/Http/Controllers/StrategyController.php");
preg_match('/public function destroy\(.*?\n    \}\n/s', $ctl, $c);
$cb = $c[0] ?? '';
$check('D1: destroy delega en $sync->deleteStrategy', str_contains($cb, '$sync->deleteStrategy($strategy, auth()->id())'));
$check('D2: destroy no borra por su cuenta', $cb !== '' && ! str_contains($cb, '->delete()'));
$check('D3: destroy exige admin', str_contains($cb, "Gate::authorize('manageUsers')"));

$sub = file_get_contents("{$root}/app/Http/Controllers/RealStrategySubscriptionController.php");
$check('E1: reactivar una suscripción que se borrará al cerrar: el aviso nombra los motivos (usuario inactivado, '
    . 'config fuera de Paper o eliminada: 24-nov)',
    str_contains($sub, '(su usuario fue inactivado, o su configuración salió de Paper o fue eliminada)'));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

<?php
/**
 * D-40 (p79): el texto de ayuda «Razón de cierre» de Trading Real (maqueta aprobada el 19-nov) nombra TODOS los motivos
 * que hoy puede tener una operación Real y ninguno que ya no existe (TP2–TP4, reconciled_sl_tp_bybit). Los motivos se
 * leen del motor (regla común del stop y cierres del bot), así esta prueba falla si aparece uno nuevo sin explicar.
 * También vigila que la corrección de las operaciones ya cerradas use la misma regla que el motor.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/exit_reason_help_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$view = (string) file_get_contents($root . '/resources/views/trading/index.blade.php');
preg_match('/Razón de cierre<\/span> — (.*?)<\/div>/s', $view, $m);
$help = strip_tags($m[1] ?? '');
$check('existe el texto de ayuda «Razón de cierre»', $help !== '');

// Motivos que hoy produce Real: la regla común del stop + los cierres del bot + los de Bybit / conciliación
$rules = (string) file_get_contents($root . '/python-engine/backtesting/exit_reasons.py');
preg_match_all("/= '([a-z_]+)', '([a-z_]+)', '([a-z_]+)'/", $rules, $c);
$reasons = array_slice($c[0] ? array_merge($c[1], $c[2], $c[3]) : [], 0);
$rt = (string) file_get_contents($root . '/python-engine/trading/real_trader.py');
preg_match_all('/close_trade\((?:trade|row|open_row), ["\']([a-z_0-9]+)["\']/', $rt, $c);
$reasons = array_merge($reasons, $c[1], ['take_profit_1', 'time_exit', 'time_exit_profit', 'closed_other']);
$reasons = array_values(array_unique($reasons));
$check('se leyeron los motivos del motor (stop, break-even, trailing y los cierres del bot)',
    count(array_intersect($reasons, ['stop_loss', 'break_even', 'trailing_stop', 'circuit_breaker_max_loss', 'liquidation_risk',
        'volatility_protection', 'opposite_signal'])) === 7, $reasons);
// la tabla del historial muestra el motivo con «_» -> espacio
$missing = array_values(array_filter($reasons, fn ($r) => ! str_contains($help, str_replace('_', ' ', $r))));
$check('la ayuda explica cada motivo tal como se ve en la tabla («_» -> espacio)', $missing === [], $missing);
$check('la ayuda ya no nombra motivos que no existen (TP2–TP4, reconciled_sl_tp_bybit)',
    ! preg_match('/take_profit_1-4|reconciled|take profit [234]/', $help), $help);
$check('break even explicado: el stop estaba en la entrada', str_contains($help, 'break even: el stop ya estaba en la entrada'));

// Corrección de las ya cerradas: misma regla que stop_exit_reason
$sql = (string) file_get_contents($root . '/ops/datafix/2026_11_19_d40_break_even.sql');
$rule = "exit_reason = 'stop_loss' AND t.be_activated AND NOT COALESCE(t.trailing_applied, false)\n"
      . "   AND ((t.side = 'long' AND t.sl >= t.entry_price) OR (t.side = 'short' AND t.sl <= t.entry_price))";
$check('corrección: Real y Paper con la regla del motor (BE, sin trailing, stop en la entrada o mejor)', substr_count($sql, $rule) === 2);
$check('corrección: Real deja el valor anterior en su historial; solo cambia el motivo',
    str_contains($sql, "'action', 'exit_reason_corrected'") && str_contains($sql, "'from', 'stop_loss', 'to', 'break_even'")
    && preg_match_all('/\bSET\b(.*?)\bWHERE\b/s', $sql, $sets) === 2
    && array_filter($sets[1], fn ($x) => preg_match('/\b(pnl|net_pnl|pnl_pct|exit_price|balance\w*|sl|tp|size)\s*=/', $x)) === []);
$check('regla del motor igual a la de la corrección', str_contains($rules, "if be_activated and (float(sl) >= float(entry) if side == 'long' else float(sl) <= float(entry)):")
    && str_contains($rules, 'if trailing_applied:'));

echo $fails === 0 ? "TODO OK\n" : "FALLAS: $fails\n";
exit($fails === 0 ? 0 : 1);

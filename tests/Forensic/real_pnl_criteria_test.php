<?php
/**
 * C5-08 (p105, D-60): un solo criterio de resultado para las operaciones Real (App\Support\RealPnl): el NETO y, solo
 * si falta, el bruto. A. Puro: resultado por operación y KPI (ganadoras, win rate, total, PF), con los casos que antes
 * se contradecían (gana en bruto y pierde en neto; suma neta exactamente 0; una operación sin neto). B. Cableado:
 * el filtro «Ganadoras / Perdedoras» de Trading y los KPI de Trading y del Dashboard usan ese criterio.
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/real_pnl_criteria_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$f = "{$root}/app/Support/RealPnl.php";
$check('A0: existe App\Support\RealPnl', is_file($f));
if (is_file($f)) {
    require $f;
    $P = 'App\Support\RealPnl';
    $t = fn ($net, $gross) => (object) ['net_pnl' => $net, 'pnl' => $gross];
    $check('A1: resultado = neto', $P::of($t(-0.5, 1.2)) === -0.5);
    $check('A2: sin neto: el bruto', $P::of($t(null, 3.0)) === 3.0);
    $check('A3: sin neto ni bruto: 0', $P::of($t(null, null)) === 0.0);
    $check('A4: también con arreglos', $P::of(['net_pnl' => 2.5, 'pnl' => 3]) === 2.5);
    // gana en bruto (+1,2) y pierde en neto (−0,5): es perdedora en todos los números
    $s = $P::stats([$t(10.0, 12.0), $t(-0.5, 1.2), $t(-4.0, -3.0)]);
    $check('A5: gana en bruto y pierde en neto: cuenta como perdedora (1 de 3 ganadoras)',
        $s['wins'] === 1 && $s['total_closed'] === 3 && $s['win_rate'] === 33.33, $s);
    $check('A6: total, ganancia y pérdida con el mismo criterio; PF = 10 / 4,5',
        $s['total_pnl'] === 5.5 && $s['gross_profit'] === 10.0 && $s['gross_loss'] === 4.5 && $s['profit_factor'] === 2.22, $s);
    // suma neta exactamente 0: antes se cambiaba a la suma bruta
    $s = $P::stats([$t(5.0, 6.0), $t(-5.0, -4.0)]);
    $check('A7: suma neta exactamente 0: el total es 0 (antes saltaba a la suma bruta, +2)', $s['total_pnl'] === 0.0, $s);
    // una operación sin neto: cuenta con su bruto en todo (antes 0 en la ganancia y su bruto al contar ganadoras)
    $s = $P::stats([$t(null, 4.0), $t(-1.0, -0.8)]);
    $check('A8: una operación sin neto cuenta con su bruto en ganadoras, total y ganancia',
        $s['wins'] === 1 && $s['total_pnl'] === 3.0 && $s['gross_profit'] === 4.0 && $s['profit_factor'] === 4.0, $s);
    $check('A9: break-even exacto (0) es perdedora, como el filtro (<= 0)', $P::stats([$t(0.0, 0.3)])['wins'] === 0);
    $check('A10: sin pérdidas: PF null; sin operaciones: todo en 0',
        $P::stats([$t(1.0, 1.0)])['profit_factor'] === null && $P::stats([])['win_rate'] === 0.0 && $P::stats([])['total_closed'] === 0);
    $check('A11: el SQL del filtro es el mismo criterio', $P::NET_SQL === 'COALESCE(net_pnl, pnl)');
}

// B. Cableado
$tc = (string) file_get_contents("{$root}/app/Http/Controllers/TradingController.php");
$dc = (string) file_get_contents("{$root}/app/Http/Controllers/DashboardController.php");
$check('B1: Trading: «Ganadoras» y «Perdedoras» filtran con el neto (no con el bruto)',
    str_contains($tc, "\$closedQuery->whereRaw(RealPnl::NET_SQL . ' > 0');")
    && str_contains($tc, "\$closedQuery->whereRaw(RealPnl::NET_SQL . ' <= 0');")
    && ! preg_match("/closedQuery->where\('pnl', '(>|<=)', 0\)/", $tc));
$check('B2: Trading: KPI con RealPnl::stats y curva con RealPnl::of; sin el salto a bruto cuando la suma da 0',
    str_contains($tc, '$kpi          = RealPnl::stats($closedTrades);') && str_contains($tc, 'RealPnl::of($trade)')
    && ! str_contains($tc, "sum('net_pnl') ?:"));
$check('B3: Dashboard: el bloque de Real usa el mismo criterio (antes ganadoras con el bruto)',
    str_contains($dc, '\App\Support\RealPnl::stats((clone $closedRealMonth)->get') && ! str_contains($dc, "closedRealMonth)->where('pnl', '>', 0)"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

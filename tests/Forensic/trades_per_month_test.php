<?php
/**
 * RQ-01.1: Trades/mes de cada config Paper = trades cerrados por la estrategia en SU moneda (sin el cierre forzado al
 * final del rango) / meses del periodo efectivo del backtest de origen. Antes la columna avg_monthly_trades existía
 * pero ningún código la llenaba (vacía en todas las configs). PHP puro, sin Laravel ni base.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/trades_per_month_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

require getcwd() . '/app/Services/StrategyConfigSync.php';
$S = \App\Services\StrategyConfigSync::class;
$has = method_exists($S, 'tradesPerMonth') && method_exists($S, 'consistentTradeCounts');
$check('T0: existen tradesPerMonth y consistentTradeCounts', $has);
$tpm = fn (...$a) => $has ? $S::tradesPerMonth(...$a) : 'NO EXISTE';
$P = ['start_date' => '2024-10-01', 'end_date' => '2026-09-30'];          // 729 días = 23,95 meses

$check('T1: por moneda: 48 trades de SOL en 729 días -> 2,00/mes',
    $tpm(['trades_by_symbol' => ['SOLUSDT' => 48, 'ETHUSDT' => 96], 'total_trades' => 144], $P, 24, 'SOLUSDT', 2) === 2.0,
    $tpm(['trades_by_symbol' => ['SOLUSDT' => 48, 'ETHUSDT' => 96], 'total_trades' => 144], $P, 24, 'SOLUSDT', 2));
$check('T2: cada moneda con lo suyo (ETH 96 -> 4,01/mes), no el total del backtest',
    $tpm(['trades_by_symbol' => ['SOLUSDT' => 48, 'ETHUSDT' => 96], 'total_trades' => 144], $P, 24, 'ETHUSDT', 2) === 4.01);
$check('T3: backtest viejo de 1 moneda: total_trades menos el cierre forzado si se conoce',
    $tpm(['total_trades' => 49, 'closed_at_end' => 1], $P, 24, 'SOLUSDT', 1) === 2.0
    && $tpm(['total_trades' => 48], $P, 24, 'SOLUSDT', 1) === 2.0);
$check('T4: backtest viejo de varias monedas sin dato por moneda -> null (N/D, no se inventa)',
    $tpm(['total_trades' => 144], $P, 24, 'SOLUSDT', 2) === null);
$check('T5: sin fechas usa los meses pedidos (48 / 24 = 2,00)', $tpm(['total_trades' => 48], [], 24, 'X', 1) === 2.0);
$check('T6: periodo inválido o < medio mes -> null',
    $tpm(['total_trades' => 5], ['start_date' => '2026-01-10', 'end_date' => '2026-01-12'], 0, 'X', 1) === null
    && $tpm(['total_trades' => 5], ['start_date' => 'x', 'end_date' => 'y'], 0, 'X', 1) === null
    && $tpm(['total_trades' => 5], ['start_date' => '2026-02-01', 'end_date' => '2026-01-01'], 0, 'X', 1) === null);

$c = fn (array $m, array $syms) => $has ? $S::consistentTradeCounts($m, $syms) : [];
$m = $c(['total_trades' => 145, 'trades_by_symbol' => ['SOLUSDT' => 48, 'ETHUSDT' => 96], 'closed_at_end' => 1], ['SOLUSDT', 'ETHUSDT']);
$check('C1: conteos que cuadran con el total firmado (48 + 96 + 1 = 145) se conservan',
    ($m['trades_by_symbol'] ?? null) === ['SOLUSDT' => 48, 'ETHUSDT' => 96] && ($m['closed_at_end'] ?? null) === 1, $m);
$m = $c(['total_trades' => 145, 'trades_by_symbol' => ['SOLUSDT' => 60, 'ETHUSDT' => 96], 'closed_at_end' => 1], ['SOLUSDT', 'ETHUSDT']);
$check('C2: conteos que no cuadran con el total firmado se descartan', ! isset($m['trades_by_symbol']) && ! isset($m['closed_at_end']), $m);
$m = $c(['total_trades' => 48, 'trades_by_symbol' => ['BTCUSDT' => 48], 'closed_at_end' => 0], ['SOLUSDT']);
$check('C3: una moneda que no es del backtest se descarta', ! isset($m['trades_by_symbol']), $m);
$m = $c(['total_trades' => 52, 'trades_by_symbol' => ['SOLUSDT' => 48], 'closed_at_end' => 4], ['SOLUSDT']);
$check('C4: más cierres forzados que monedas se descarta', ! isset($m['trades_by_symbol']), $m);

$ctl = file_get_contents(getcwd() . '/app/Http/Controllers/BacktestingController.php');
$check('W1: al ejecutar se guardan trades_by_symbol (sin end_of_data) y closed_at_end',
    str_contains($ctl, "\$tradesBySymbol[\$sym] = max(0, (int) (\$agg['total_trades'] ?? 0) - \$atEnd);")
    && str_contains($ctl, "'trades_by_symbol' => \$tradesBySymbol,") && str_contains($ctl, "'closed_at_end' => \$closedAtEnd,"));
$check('W2: al guardar se validan contra el total firmado', str_contains($ctl, 'StrategyConfigSync::consistentTradeCounts($metrics, $signed[\'symbols\'])'));
$sync = file_get_contents(getcwd() . '/app/Services/StrategyConfigSync.php');
$check('W3: cada config Paper (alta y actualización) recibe avg_monthly_trades de su moneda',
    substr_count($sync, 'array_merge($metricAttrs, $perSymbolTrades($symbol), [') === 2);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

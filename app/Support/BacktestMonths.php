<?php

namespace App\Support;

/**
 * Meses del backtest con el retorno REAL de la cuenta (dueño, 25-nov): cada mes se mide sobre el saldo con que empezó
 * el mes (ganancia del mes ÷ saldo al empezar), y el acumulado es lo que creció la cuenta. Así el último acumulado es
 * exactamente el retorno de la moneda (antes se sumaban los % de cada operación: 27,91 % contra 30,01 % de SOL).
 * Puro; lo usan BacktestingController (consistencia y promedio guardados) y backtesting/partials/results.
 */
final class BacktestMonths
{
    /**
     * @param array<int, array> $monthly monthly_breakdown del motor (month, total_trades, wins, losses, total_pnl, total_pnl_pct)
     * @param float             $initial saldo inicial de la moneda
     * @return array<string, array{month: string, trades: int, wins: int, losses: int, pct: float, acum: float}> por mes
     */
    public static function build(array $monthly, float $initial): array
    {
        usort($monthly, fn ($a, $b) => strcmp((string) ($a['month'] ?? ''), (string) ($b['month'] ?? '')));
        $initial = $initial > 0 ? $initial : 10000.0;
        $balance = $initial;
        $out = [];
        foreach ($monthly as $m) {
            if (array_key_exists('total_pnl', $m) && is_numeric($m['total_pnl'])) {
                $pnl = (float) $m['total_pnl'];
                $pct = $balance > 0 ? $pnl / $balance * 100 : 0.0;
            } else {   // guardados sin la ganancia en dinero: el % del mes como venía
                $pct = (float) ($m['total_pnl_pct'] ?? 0);
                $pnl = $balance * $pct / 100;
            }
            $balance += $pnl;
            $out[(string) $m['month']] = [
                'month'  => (string) $m['month'],
                'trades' => (int) ($m['total_trades'] ?? 0),
                'wins'   => (int) ($m['wins'] ?? 0),
                'losses' => (int) ($m['losses'] ?? 0),
                'pct'    => $pct,
                'acum'   => ($balance / $initial - 1) * 100,
            ];
        }

        return $out;
    }

    /** % de meses positivos y promedio mensual (para guardar y para las estrellas). */
    public static function stats(array $months): array
    {
        $p = array_column($months, 'pct');

        return [
            'consist' => $p ? round(count(array_filter($p, fn ($v) => $v > 0)) / count($p) * 100, 1) : 0.0,
            'avg'     => $p ? array_sum($p) / count($p) : 0.0,
        ];
    }
}

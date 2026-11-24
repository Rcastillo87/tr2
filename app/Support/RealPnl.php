<?php

namespace App\Support;

/**
 * C5-08 (p105, D-60): un solo criterio de resultado para las operaciones Real en pantallas, filtros y KPI: el NETO
 * (después de comisiones y funding) y, solo si una operación no tiene neto, su bruto. Ganadora = resultado > 0.
 * PHP puro (sin Laravel): TradingController y DashboardController lo usan para filtrar y para los KPI.
 */
final class RealPnl
{
    /** El mismo criterio en SQL, para filtrar en la base («Ganadoras» = NET_SQL > 0, «Perdedoras» = NET_SQL <= 0). */
    public const NET_SQL = 'COALESCE(net_pnl, pnl)';

    /** Resultado de una operación: neto; si falta, bruto; si faltan los dos, 0. */
    public static function of(object|array $t): float
    {
        $net = is_array($t) ? ($t['net_pnl'] ?? null) : ($t->net_pnl ?? null);
        $gross = is_array($t) ? ($t['pnl'] ?? null) : ($t->pnl ?? null);

        return (float) ($net ?? $gross ?? 0);
    }

    /**
     * KPI de un conjunto de operaciones cerradas con ese criterio: total, ganadoras, win rate, resultado total, ganancia
     * y pérdida brutas (de los resultados) y profit factor (null sin pérdidas).
     *
     * @return array{total_closed:int, wins:int, win_rate:float, total_pnl:float, gross_profit:float, gross_loss:float, profit_factor:?float}
     */
    public static function stats(iterable $trades): array
    {
        $n = $wins = 0;
        $sum = $gp = $gl = 0.0;
        foreach ($trades as $t) {
            $v = self::of($t);
            $n++;
            $sum += $v;
            if ($v > 0) {
                $wins++;
                $gp += $v;
            } else {
                $gl += -$v;
            }
        }

        return [
            'total_closed' => $n,
            'wins' => $wins,
            'win_rate' => $n > 0 ? round($wins / $n * 100, 2) : 0.0,
            'total_pnl' => round($sum, 2),
            'gross_profit' => $gp,
            'gross_loss' => $gl,
            'profit_factor' => $gl > 0 ? round($gp / $gl, 2) : null,
        ];
    }
}

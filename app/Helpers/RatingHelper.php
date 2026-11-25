<?php

namespace App\Helpers;

/**
 * Calificación de 1 a 5 estrellas, ÚNICA para todo el sistema (backtest, historial, búsqueda, Paper y Real).
 * Dueño, 25-nov (D-70): promedio ponderado de cuatro notas de 1 a 5, calibradas con riesgo 1 % por operación:
 *   profit factor 30 % · retorno ÷ caída máxima 30 % · meses positivos 20 % · caída máxima 20 %;
 *   topes: < 30 operaciones → máx. 2; < 50 → máx. 4; retorno ≤ 0 → máx. 1,5.
 * El % de ganadas y el Sharpe se muestran, pero no cuentan (castigaban a las estrategias de tendencia).
 * Sin caída máxima (backtests guardados sin el dato): sus dos notas quedan neutras (3).
 */
class RatingHelper
{
    public const PF_CUTS       = [1.0, 1.15, 1.3, 1.5];
    public const RECOVERY_CUTS = [0.5, 1.5, 3.0, 5.0];
    public const CONSIST_CUTS  = [40.0, 50.0, 60.0, 70.0];
    public const DD_CUTS       = [5.0, 10.0, 15.0, 25.0];   // menos caída = más nota
    public const WEIGHTS       = ['pf' => 0.3, 'recovery' => 0.3, 'consist' => 0.2, 'dd' => 0.2];
    public const NEUTRAL       = 3;
    public const LABELS        = ['pf' => 'Profit factor', 'recovery' => 'Retorno ÷ caída', 'consist' => 'Meses positivos',
                                  'dd' => 'Caída máxima'];

    /**
     * @param float|null $pf      profit factor (null = sin pérdidas)
     * @param float      $retPct  retorno del período en %
     * @param float|null $ddPct   caída máxima en % (null = sin dato)
     * @param float      $consist % de meses positivos (0–100)
     * @param int        $trades  operaciones
     */
    public static function calculate(?float $pf, float $retPct, ?float $ddPct, float $consist, int $trades): float
    {
        return self::detail($pf, $retPct, $ddPct, $consist, $trades)['rating'];
    }

    /** @return array{rating: float, parts: array{pf:int, recovery:int, consist:int, dd:int}, recovery: ?float, cap: ?string} */
    public static function detail(?float $pf, float $retPct, ?float $ddPct, float $consist, int $trades): array
    {
        $pfNote = $pf === null ? ($retPct > 0 ? 5 : 1) : self::step($pf, self::PF_CUTS);
        if ($ddPct === null) {
            $recovery = null;
            $recNote = $ddNote = self::NEUTRAL;
        } else {
            $dd = abs($ddPct);
            $recovery = $dd > 0 ? $retPct / $dd : ($retPct > 0 ? INF : 0.0);
            $recNote = self::step($recovery, self::RECOVERY_CUTS);
            $ddNote = 6 - self::step($dd, self::DD_CUTS);
        }
        $parts = ['pf' => $pfNote, 'recovery' => $recNote, 'consist' => self::step($consist, self::CONSIST_CUTS), 'dd' => $ddNote];
        $r = 0.0;
        foreach (self::WEIGHTS as $k => $w) {
            $r += $w * $parts[$k];
        }
        $cap = null;
        if ($trades < 30) {
            [$r, $cap] = [min($r, 2.0), 'menos de 30 operaciones'];
        } elseif ($trades < 50) {
            [$r, $cap] = [min($r, 4.0), 'menos de 50 operaciones'];
        }
        if ($retPct <= 0) {
            [$r, $cap] = [min($r, 1.5), 'sin ganancia'];
        }

        return ['rating' => round(max(1.0, $r), 1), 'parts' => $parts,
                'recovery' => $recovery === null || is_infinite($recovery) ? $recovery : round($recovery, 2), 'cap' => $cap];
    }

    /**
     * Entradas de la fórmula desde un juego de métricas (aggregate_metrics del motor, o las guardadas de un backtest).
     * $monthly: monthly_breakdown (para los meses positivos, si las métricas no traen consist_pct).
     *
     * @return array{pf: ?float, ret: float, dd: ?float, consist: float, trades: int}
     */
    public static function inputs(array $m, array $monthly = []): array
    {
        $num = static fn ($v): ?float => is_numeric($v) ? (float) $v : null;
        $pf = $num($m['profit_factor'] ?? null);
        if ($pf !== null && $pf >= 999) {
            $pf = null;   // «sin pérdidas» guardado como 999.99
        }
        if ($monthly !== []) {
            $vals = array_map(fn ($x) => (float) ($x['total_pnl'] ?? $x['total_pnl_pct'] ?? 0), $monthly);
            $consist = count(array_filter($vals, fn ($v) => $v > 0)) / count($vals) * 100;
        } else {
            $consist = (float) ($m['consist_pct'] ?? 0);
            if ($consist > 0 && $consist <= 1) {
                $consist *= 100;   // backtests viejos: fracción
            }
        }

        return [
            'pf'      => $pf,
            'ret'     => (float) ($m['total_return_pct'] ?? 0),
            'dd'      => $num($m['max_drawdown_pct'] ?? null),
            'consist' => $consist,
            'trades'  => (int) ($m['total_trades'] ?? 0),
        ];
    }

    /** Una moneda (o un juego de métricas). */
    public static function forMetrics(array $m, array $monthly = []): array
    {
        $in = self::inputs($m, $monthly);

        return self::detail($in['pf'], $in['ret'], $in['dd'], $in['consist'], $in['trades']) + ['inputs' => $in];
    }

    /**
     * Un backtest guardado (metrics de la tabla backtests): el promedio de las estrellas de sus monedas, cada una con sus
     * propias métricas (como la fila CONSOLIDADO). Sin detalle por moneda: las métricas del backtest.
     */
    public static function fromMetrics(array $m): float
    {
        $ind = array_values(array_filter((array) ($m['individual_results'] ?? []), 'is_array'));
        if ($ind === []) {
            return self::forMetrics($m)['rating'];
        }
        $r = array_map(fn ($x) => self::forMetrics((array) ($x['aggregate_metrics'] ?? []), (array) ($x['monthly_breakdown'] ?? []))['rating'], $ind);

        return round(array_sum($r) / count($r), 1);
    }

    /**
     * Detalle para mostrar las cuatro notas de un backtest guardado: la nota de cada parte es el promedio de sus monedas
     * (redondeado) y los valores son los del backtest (PF global, peor caída de las monedas…).
     *
     * @return array{rating: float, parts: array<string,int>, values: array<string, ?float>}
     */
    public static function fromMetricsDetail(array $m): array
    {
        $ind = array_values(array_filter((array) ($m['individual_results'] ?? []), 'is_array'));
        $rows = $ind === [] ? [self::forMetrics($m)]
            : array_map(fn ($x) => self::forMetrics((array) ($x['aggregate_metrics'] ?? []), (array) ($x['monthly_breakdown'] ?? [])), $ind);
        $parts = [];
        foreach (array_keys(self::WEIGHTS) as $k) {
            $parts[$k] = (int) round(array_sum(array_map(fn ($r) => $r['parts'][$k], $rows)) / count($rows));
        }
        $dds = array_filter(array_map(fn ($r) => $r['inputs']['dd'], $rows), fn ($v) => $v !== null);
        $recs = array_filter(array_map(fn ($r) => $r['recovery'], $rows), fn ($v) => $v !== null && ! is_infinite($v));
        $in = self::inputs($m);

        return [
            'rating' => self::fromMetrics($m),
            'parts'  => $parts,
            'values' => [
                'pf'       => $in['pf'],
                'recovery' => $recs ? round(array_sum($recs) / count($recs), 2) : null,
                'consist'  => round($in['consist'] ?: (array_sum(array_map(fn ($r) => $r['inputs']['consist'], $rows)) / count($rows)), 1),
                'dd'       => $dds ? max($dds) : null,
            ],
        ];
    }

    /** Color según la calificación (igual que antes). */
    public static function getColor(float $rating): string
    {
        return $rating >= 4 ? '#F5C518' : ($rating >= 3 ? '#EF9F27' : ($rating >= 2 ? '#E8832A' : '#E24B4A'));
    }

    public static function stars(float $rating): string
    {
        $n = max(0, min(5, (int) round($rating)));

        return str_repeat('★', $n) . str_repeat('☆', 5 - $n);
    }

    private static function step(float $v, array $cuts): int
    {
        $s = 1;
        foreach ($cuts as $c) {
            if ($v >= $c) {
                $s++;
            }
        }

        return $s;
    }
}

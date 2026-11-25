<?php

namespace App\Support;

/**
 * C6-04: fechas reales del período y de cada tramo de una búsqueda, desde los cortes que guarda cada búsqueda
 * (results.period: start, split, test, end; rango semiabierto [start, end): el último día que cuenta es end − 1 día).
 * Solo rótulos: la metodología no cambia (D-58: el total ordena y filtra; los tramos dicen dónde debe ganar).
 * Puro para poder probarlo; lo usa ParamSearchController::state.
 */
final class SearchPeriodLabels
{
    private const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

    /**
     * @param array|null $period ['start' => 'AAAA-MM-DD', 'split' => …, 'test' => … (solo v4), 'end' => … exclusivo]
     * @return array{total: string, segments: ?array{0: string, 1: string, 2: string}}|null
     */
    public static function build(?array $period): ?array
    {
        $start = self::day($period['start'] ?? null);
        $end   = self::day($period['end'] ?? null);
        if ($start === null || $end === null || $end <= $start) {
            return null;
        }
        $last  = $end->modify('-1 day');
        $out   = ['total' => self::fmt($start) . ' → ' . self::fmt($last), 'segments' => null];
        $split = self::day($period['split'] ?? null);
        $test  = self::day($period['test'] ?? null);
        if ($split !== null && $test !== null && $start < $split && $split < $test && $test < $end) {
            $out['segments'] = [
                self::range($start, $split->modify('-1 day')),
                self::range($split, $test->modify('-1 day')),
                self::range($test, $last),
            ];
        }

        return $out;
    }

    private static function day(mixed $v): ?\DateTimeImmutable
    {
        if (! is_string($v) || ! preg_match('/^\d{4}-\d{2}-\d{2}$/', $v)) {
            return null;
        }
        $d = \DateTimeImmutable::createFromFormat('!Y-m-d', $v, new \DateTimeZone('UTC'));

        return $d && $d->format('Y-m-d') === $v ? $d : null;
    }

    private static function fmt(\DateTimeImmutable $d, bool $year = true): string
    {
        return (int) $d->format('j') . ' ' . self::MONTHS[(int) $d->format('n') - 1] . ($year ? ' ' . $d->format('Y') : '');
    }

    /** «13 ene – 7 jun 2026»; con años distintos, el año en las dos puntas. */
    private static function range(\DateTimeImmutable $a, \DateTimeImmutable $b): string
    {
        return self::fmt($a, $a->format('Y') !== $b->format('Y')) . ' – ' . self::fmt($b);
    }
}

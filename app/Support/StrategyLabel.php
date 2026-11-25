<?php

namespace App\Support;

/**
 * Etiqueta de una configuración desplegada: «{estrategia} — {símbolo} {intervalo}» (display_name y paper_trades.strategy).
 * Es solo texto para mostrar y filtrar: la identidad de una config es su id (N-09). Dos backtests de la misma estrategia,
 * símbolo e intervalo comparten etiqueta.
 */
final class StrategyLabel
{
    public const SEPARATOR = ' — ';

    public static function compose(string $strategyName, string $symbol, string $intervalLabel): string
    {
        return $strategyName . self::SEPARATOR . "{$symbol} {$intervalLabel}";
    }

    public const INTERVAL_LABELS = ['1' => '1m', '5' => '5m', '15' => '15m', '60' => 'H1', '120' => 'H2', '240' => 'H4', 'D' => 'D1'];

    /**
     * D-72 (dueño, 25-nov): etiqueta SIN nombre de estrategia para el inversionista: «Config #74 · DOGEUSDT · H4».
     * El número de config distingue dos configs de la misma moneda y temporalidad.
     *
     * @param int[]    $configIds
     * @param string[] $symbols
     */
    public static function anon(array $configIds, array $symbols, string $interval): string
    {
        $ids = array_values(array_unique(array_filter(array_map('intval', $configIds))));
        $who = $ids === [] ? 'Config' : (count($ids) === 1 ? 'Config #' . $ids[0] : 'Configs #' . implode(', #', $ids));

        return $who . ' · ' . implode(', ', array_values(array_unique($symbols))) . ' · ' . (self::INTERVAL_LABELS[$interval] ?? $interval);
    }

    /**
     * Patrón LIKE de las etiquetas de una estrategia: su nombre exacto (con % _ \ escapados) seguido del separador.
     * «VWAP» no abarca «VWAP Tendencia».
     */
    public static function likePrefix(string $strategyName): string
    {
        return addcslashes($strategyName, '\\%_') . self::SEPARATOR . '%';
    }
}

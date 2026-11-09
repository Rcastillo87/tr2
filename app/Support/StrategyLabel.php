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

    /**
     * Patrón LIKE de las etiquetas de una estrategia: su nombre exacto (con % _ \ escapados) seguido del separador.
     * «VWAP» no abarca «VWAP Tendencia».
     */
    public static function likePrefix(string $strategyName): string
    {
        return addcslashes($strategyName, '\\%_') . self::SEPARATOR . '%';
    }
}

<?php

namespace App\Helpers;

class RatingHelper
{
    /**
     * Calcula el rating de 1 a 5 basado en las métricas del backtest.
     * Umbrales unificados para todo el sistema.
     */
    public static function calculate(float $wr, float $sharpe, float $pf, float $retMes, float $consist): float
    {
        $sWr = $wr >= 65 ? 5 : ($wr >= 55 ? 4 : ($wr >= 45 ? 3 : ($wr >= 35 ? 2 : 1)));
        $sSharpe = $sharpe >= 4 ? 5 : ($sharpe >= 3 ? 4 : ($sharpe >= 2 ? 3 : ($sharpe >= 1 ? 2 : 1)));
        $sPf = $pf >= 2.5 ? 5 : ($pf >= 2.0 ? 4 : ($pf >= 1.5 ? 3 : ($pf >= 1.0 ? 2 : 1)));
        $sRet = $retMes >= 20 ? 5 : ($retMes >= 10 ? 4 : ($retMes >= 5 ? 3 : ($retMes >= 2 ? 2 : 1)));
        // Umbrales de Consistencia: 80/60/40/20
        $sCons = $consist >= 80 ? 5 : ($consist >= 60 ? 4 : ($consist >= 40 ? 3 : ($consist >= 20 ? 2 : 1)));

        return round(($sWr + $sSharpe + $sPf + $sRet + $sCons) / 5, 1);
    }

    /**
     * Devuelve el color HEX según el rating.
     */
    public static function getColor(float $rating): string
    {
        return $rating >= 4 ? '#F5C518' : ($rating >= 3 ? '#EF9F27' : ($rating >= 2 ? '#E8832A' : '#E24B4A'));
    }
}

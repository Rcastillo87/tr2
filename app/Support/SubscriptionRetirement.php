<?php

namespace App\Support;

/**
 * Suscripciones Real de una config que sale de Paper (Detener, moneda quitada del backtest, backtest eliminado): el
 * dueño (24-nov) las quiere fuera de Real aunque las haya seleccionado. Puro (sin base) para poder probarlo.
 * Sin operación viva se borran ya; con operación viva se pausan y se borran solas al cerrar (retire_on_close, la
 * tarea de D-04): la operación abierta sigue hasta su SL/TP (03-nov, opción A). El historial de operaciones Real se
 * conserva (real_trades.subscription_id es ON DELETE SET NULL).
 */
final class SubscriptionRetirement
{
    /**
     * @param array<int, bool> $subLive id de suscripción => tiene una operación viva (RealTrade::RECONCILE_STATUSES)
     * @return array{delete: int[], retire: int[]}
     */
    public static function split(array $subLive): array
    {
        $plan = ['delete' => [], 'retire' => []];
        foreach ($subLive as $id => $live) {
            $plan[$live ? 'retire' : 'delete'][] = (int) $id;
        }

        return $plan;
    }
}

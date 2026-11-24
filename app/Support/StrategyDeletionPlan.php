<?php

namespace App\Support;

/**
 * D-63 (C5-13): qué pasa al borrar una estrategia. Puro (sin base de datos) para poder probarlo.
 * - Con alguna config operando en Paper no se borra (como antes). Con una búsqueda en cola o en curso, tampoco
 *   (la búsqueda escribe su resultado en su fila).
 * - Si no, se borra todo lo suyo: búsquedas, backtests, configs (detenidas) y lo de Paper de esas configs. Lo de Real
 *   se conserva (registro de dinero, D-04); las operaciones Real abiertas siguen con sus parámetros congelados.
 * - Suscripciones Real de esas configs: sin operación viva se borran ya; con operación viva se pausan y se borran
 *   solas al cerrar (retire_on_close, la tarea de D-04).
 */
final class StrategyDeletionPlan
{
    public const ACTIVE_PAPER = 'No puedes eliminar esta estrategia porque tiene una variante activa en Paper Trading. Pausa el Paper primero.';

    /**
     * @param array<int, bool> $configActive    id de config => activa en Paper
     * @param bool             $legacyActive    config activa sin backtest con la etiqueta de la estrategia (legado)
     * @param int              $searchesActive  búsquedas de la estrategia en cola o en curso
     * @param array<int, bool> $subLive         id de suscripción Real => tiene una operación viva
     * @return array{error: ?string, delete_subs: int[], retire_subs: int[]}
     */
    public static function decide(array $configActive, bool $legacyActive, int $searchesActive, array $subLive): array
    {
        $plan = ['error' => null, 'delete_subs' => [], 'retire_subs' => []];
        if ($legacyActive || in_array(true, $configActive, true)) {
            return ['error' => self::ACTIVE_PAPER] + $plan;
        }
        if ($searchesActive > 0) {
            return ['error' => "No puedes eliminar esta estrategia: tiene {$searchesActive} búsqueda(s) en cola o en curso. "
                . 'Espera a que terminen o cancélalas.'] + $plan;
        }
        foreach ($subLive as $id => $live) {
            $plan[$live ? 'retire_subs' : 'delete_subs'][] = (int) $id;
        }

        return $plan;
    }

    /** @param array{backtests: int, searches: int, configs: int, paper_trades: int, subs_deleted: int, subs_retired: int} $n */
    public static function summary(string $name, array $n): string
    {
        $parts = [];
        foreach ([['backtests', 'backtest', 'backtests'], ['searches', 'búsqueda', 'búsquedas'],
                  ['configs', 'configuración', 'configuraciones'], ['paper_trades', 'operación de Paper', 'operaciones de Paper'],
                  ['subs_deleted', 'suscripción Real', 'suscripciones Real']] as [$k, $one, $many]) {
            if (($n[$k] ?? 0) > 0) {
                $parts[] = $n[$k] . ' ' . ($n[$k] === 1 ? $one : $many);
            }
        }
        $text = "Estrategia {$name} eliminada" . ($parts === [] ? '.' : ': ' . implode(', ', $parts) . '.');
        if (($n['subs_retired'] ?? 0) > 0) {
            $text .= ' ' . ($n['subs_retired'] === 1
                ? '1 suscripción Real tiene una operación abierta: se pausó y se eliminará sola al cerrar.'
                : "{$n['subs_retired']} suscripciones Real tienen una operación abierta: se pausaron y se eliminarán solas al cerrar.");
        }

        return $text;
    }
}

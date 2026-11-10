<?php

namespace App\Support;

/**
 * Origen de un backtest (RQ-01.3): cómo nació el registro, fijado una sola vez al crearlo.
 *  - manual: botón Guardar de la pantalla de backtesting.
 *  - search: «Crear en historial» desde una búsqueda de parámetros; origin_meta guarda una foto de la búsqueda
 *    (sin FK: sobrevive aunque la búsqueda se borre).
 *  - null: backtest anterior a p50 sin rastro recuperable («Origen no registrado»).
 * El origen «search» solo llega por un atributo interno de la petición (lo pone BacktestFromSearch), nunca por un
 * campo del formulario: el navegador no puede declararlo.
 */
final class BacktestOrigin
{
    public const MANUAL = 'manual';
    public const SEARCH = 'search';

    /** Clave del atributo interno de la petición (Request::$attributes, no Request::input). */
    public const REQUEST_ATTRIBUTE = 'tr2.backtest_origin';

    private const SEARCH_KEYS = ['run_id', 'row_id', 'focus', 'mode', 'symbols_mode', 'search_at'];

    /** Foto de la búsqueda para un backtest creado desde ella. */
    public static function fromSearch(int $runId, string $rowId, ?string $focus, ?string $mode, string $symbolsMode,
                                      ?string $searchAt): array
    {
        return [
            'run_id'       => $runId,
            'row_id'       => $rowId,
            'focus'        => $focus,
            'mode'         => $mode,
            'symbols_mode' => $symbolsMode,
            'search_at'    => $searchAt,
        ];
    }

    /**
     * Columnas origin/origin_meta para un backtest NUEVO a partir del atributo interno de la petición.
     * Sin atributo, o con uno que no es una foto de búsqueda válida: manual.
     *
     * @return array{origin: string, origin_meta: ?array}
     */
    public static function forNewBacktest(mixed $attribute): array
    {
        if (is_array($attribute) && is_int($attribute['run_id'] ?? null) && $attribute['run_id'] > 0
            && is_string($attribute['row_id'] ?? null) && $attribute['row_id'] !== '') {
            $meta = array_intersect_key($attribute, array_flip(self::SEARCH_KEYS));
            $meta['created_at'] = gmdate('Y-m-d\TH:i:sP');

            return ['origin' => self::SEARCH, 'origin_meta' => $meta];
        }

        return ['origin' => self::MANUAL, 'origin_meta' => null];
    }

    /** Texto para la pantalla. */
    public static function describe(?string $origin, ?array $meta): string
    {
        if ($origin === self::MANUAL) {
            return 'Manual (pantalla de backtesting)';
        }
        if ($origin !== self::SEARCH) {
            return 'Origen no registrado';
        }
        $parts = ['Búsqueda #' . ($meta['run_id'] ?? '?'), 'fila ' . ($meta['row_id'] ?? '?')];
        if (! empty($meta['focus'])) {
            $parts[] = 'foco ' . $meta['focus'];
        }
        if (! empty($meta['mode'])) {
            $parts[] = 'modo ' . $meta['mode'];
        }
        if (! empty($meta['search_at']) && strtotime((string) $meta['search_at']) !== false) {
            $parts[] = gmdate('Y-m-d', strtotime((string) $meta['search_at']));
        }

        return implode(' · ', $parts) . (! empty($meta['recovered']) ? ' (recuperado del historial de la búsqueda)' : '');
    }
}

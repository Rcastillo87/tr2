<?php

namespace App\Support;

/**
 * Interpreta los resultados por cuenta de /v1/real/tick y devuelve las líneas de log [nivel, mensaje] (R-14).
 * PHP puro (sin Laravel): RealTradingTickJob::logAccountResults solo las escribe.
 *
 * Formas de un resultado de cuenta:
 *  - ['error' => texto]                         -> la cuenta falló (claves rechazadas, excepción)
 *  - ['skipped' => texto]                       -> tick omitido: otro proceso tenía el turno de la cuenta (p61)
 *  - ['monitor' => [...], 'signals' => [...]]   -> tick normal
 *  - ['signals' => texto]                       -> tick omitido de un motor anterior a p61 (antes rompía array_filter)
 */
final class RealTickResults
{
    /** @return list<array{0: string, 1: string}> */
    public static function lines(array $results): array
    {
        $out = [];
        foreach ($results as $accountKey => $data) {
            if (! is_array($data)) {
                $out[] = ['warning', "RealTrading {$accountKey}: respuesta inesperada del motor: " . self::text($data)];
                continue;
            }
            if (isset($data['error'])) {
                $out[] = ['error', "RealTrading {$accountKey}: " . self::text($data['error'])];
                continue;
            }
            if (isset($data['skipped'])) {
                $out[] = ['warning', "RealTrading {$accountKey}: tick omitido — " . self::text($data['skipped'])];
                continue;
            }
            $signals = $data['signals'] ?? [];
            if (! is_array($signals)) {
                $out[] = ['warning', "RealTrading {$accountKey}: tick omitido — " . self::text($signals)];
                continue;
            }

            $monitor = is_array($data['monitor'] ?? null) ? $data['monitor'] : [];
            if (($monitor['closed'] ?? 0) > 0) {
                $out[] = ['info', "RealTrading {$accountKey}: {$monitor['closed']} posicion(es) cerrada(s)"];
            }
            if (($monitor['errors'] ?? 0) > 0) {
                $out[] = ['warning', "RealTrading {$accountKey}: {$monitor['errors']} error(es) al cerrar"];
            }
            $opened = array_filter($signals, fn ($r) => str_starts_with(self::text($r), 'ABIERTA'));
            $errors = array_filter($signals, fn ($r) => str_starts_with(self::text($r), 'ERROR')
                || str_starts_with(self::text($r), 'EXCEPTION'));
            foreach ($opened as $strategy => $result) {
                $out[] = ['info', "RealTrading ABIERTA: {$accountKey} | {$strategy} -> " . self::text($result)];
            }
            foreach ($errors as $strategy => $result) {
                $out[] = ['error', "RealTrading ERROR: {$accountKey} | {$strategy} -> " . self::text($result)];
            }
            $sinSenal = count(array_filter($signals, fn ($r) => str_contains(self::text($r), 'sin señal')));
            $out[] = ['debug', "RealTrading tick: {$accountKey} | monitoreadas:" . ($monitor['checked'] ?? 0)
                . ' cerradas:' . ($monitor['closed'] ?? 0) . ' nuevas:' . count($opened) . ' errores:' . count($errors)
                . " sin_senal:{$sinSenal}"];
        }
        return $out;
    }

    private static function text(mixed $v): string
    {
        return is_scalar($v) || $v === null ? (string) $v : (json_encode($v, JSON_UNESCAPED_UNICODE) ?: '');
    }
}

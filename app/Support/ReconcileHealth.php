<?php

namespace App\Support;

/**
 * C5-07 (p100): lectura de la respuesta de /v1/real/reconcile y regla del aviso. PHP puro (sin Laravel):
 * RealTradingReconcileJob solo escribe el log, guarda la hora del primer fallo en caché y abre / cierra el incidente.
 *
 * Una conciliación es «con fallos» si el motor no respondió bien (HTTP, excepción) o si su respuesta trae errores
 * (Bybit falló, cuenta ocupada, sin config, error inesperado de una cuenta). `pending` (esperando el closed-pnl de
 * Bybit) no es fallo: lo vigila `real_unresolved` del vigilante a los 15 min.
 */
final class ReconcileHealth
{
    /** Minutos seguidos con fallos antes de avisar al admin. */
    public const ALERT_AFTER_MIN = 10;

    /**
     * Errores de una respuesta del motor (lista vacía = conciliación completa).
     *
     * @return list<string>
     */
    public static function errors(?array $data): array
    {
        if ($data === null) {
            return ['respuesta del motor ilegible'];
        }
        $errors = $data['results']['errors'] ?? [];
        $out = [];
        foreach (is_array($errors) ? $errors : [] as $e) {
            $e = is_array($e) ? $e : ['error' => (string) $e];
            $ref = isset($e['trade_id']) ? "#{$e['trade_id']} " . ($e['symbol'] ?? '')
                : 'cuenta #' . ($e['account_id'] ?? '?') . (isset($e['symbol']) ? " {$e['symbol']}" : '');
            $out[] = trim($ref) . ': ' . mb_substr((string) ($e['note'] ?? $e['error'] ?? 'error'), 0, 200);
        }
        if ($out === [] && ($data['complete'] ?? true) === false) {
            $out[] = 'el motor informa la conciliación como incompleta';
        }

        return $out;
    }

    /**
     * Qué hacer tras una conciliación. $since: hora (ISO 8601) del primer fallo de la racha actual, o null.
     *
     * @return array{since: ?string, action: ?string}  action: 'open' (avisar), 'resolve' (cerrar el aviso) o null
     */
    public static function decide(?string $since, bool $failed, \DateTimeInterface $now): array
    {
        if (! $failed) {
            return ['since' => null, 'action' => 'resolve'];
        }
        $since ??= $now->format(DATE_ATOM);
        $minutes = ($now->getTimestamp() - (new \DateTimeImmutable($since))->getTimestamp()) / 60;

        return ['since' => $since, 'action' => $minutes >= self::ALERT_AFTER_MIN ? 'open' : null];
    }
}

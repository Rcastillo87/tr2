<?php

namespace App\Services;

/**
 * Texto de cada evento de broker (tabla broker_events) para el aviso del dueño de la cuenta.
 * Lógica pura, sin framework: un solo lugar para los textos y para cómo se agrupan.
 *
 * Devuelve null si el evento no genera aviso, o:
 *   level    info | success | warning | error
 *   title    título del aviso
 *   body     detalle
 *   mode     'notify'   aviso suelto
 *            'throttle' aviso suelto, como máximo uno por `key` cada N minutos (mismo problema repetido)
 *            'open'     abre un incidente `key` (avisa solo si no estaba abierto)
 *            'resolve'  cierra el incidente `key` (avisa solo si estaba abierto)
 *   key      clave del incidente / del límite de repetición (incluye la cuenta)
 */
final class BrokerEventMessages
{
    private const EXIT_REASONS = [
        'stop_loss' => 'stop loss', 'trailing_stop' => 'trailing stop', 'time_exit' => 'tiempo máximo',
        'time_exit_profit' => 'tiempo máximo', 'volatility_protection' => 'protección por volatilidad',
        'circuit_breaker_max_loss' => 'pérdida máxima', 'take_profit_1' => 'take profit',
    ];

    public static function for(string $event, array $data, string $account, int $accountId, ?int $tradeId): ?array
    {
        $sym = (string) ($data['symbol'] ?? '');
        $ref = trim($sym . ($tradeId ? " #{$tradeId}" : ''));
        $side = isset($data['side']) ? ' ' . $data['side'] : '';
        $strategy = isset($data['strategy']) && $data['strategy'] !== '' ? " · {$data['strategy']}" : '';
        $reason = self::clip((string) ($data['reason'] ?? ''));
        $exit = isset($data['exit_reason']) ? (self::EXIT_REASONS[$data['exit_reason']] ?? (string) $data['exit_reason']) : null;

        return match ($event) {
            'open_rejected' => [
                'level' => 'warning', 'mode' => 'throttle', 'key' => "open_rejected:{$accountId}:{$sym}",
                'title' => 'Orden rechazada en Bybit',
                'body'  => "{$account} · {$sym}{$side}{$strategy}: " . ($reason !== '' ? $reason : 'Bybit no aceptó la orden')
                    . '. No se abrió ninguna posición.',
            ],
            'open_unconfirmed' => [
                'level' => 'error', 'mode' => 'notify', 'key' => null,
                'title' => 'Apertura sin confirmar',
                'body'  => "{$account} · {$ref}{$side}{$strategy}: Bybit no confirmó la orden. "
                    . 'La conciliación revisa en ≤5 min si la posición existe y, si existe, la gestiona.',
            ],
            'close_failed' => [
                'level' => 'error', 'mode' => 'throttle', 'key' => "close_failed:{$accountId}:{$sym}",
                'title' => 'Cierre no ejecutado',
                'body'  => "{$account} · {$ref}" . ($exit ? " ({$exit})" : '') . ': '
                    . ($reason !== '' ? $reason : 'Bybit no confirmó la orden de cierre')
                    . '. La posición sigue abierta con su SL/TP en Bybit; el bot reintenta el cierre cada minuto.',
            ],
            'close_unconfirmed' => [
                'level' => 'error', 'mode' => 'throttle', 'key' => "close_unconfirmed:{$accountId}:{$sym}",
                'title' => 'Cierre sin confirmar',
                'body'  => "{$account} · {$ref}" . ($exit ? " ({$exit})" : '')
                    . ': no se pudo consultar a Bybit si el cierre se ejecutó. Se verifica en el próximo ciclo.',
            ],
            'account_paused' => [
                'level' => 'error', 'mode' => 'open', 'key' => "account_paused:{$accountId}",
                'title' => 'Cuenta pausada automáticamente',
                'body'  => "{$account}: " . ($reason !== '' ? $reason : 'errores críticos repetidos')
                    . '. No se abren posiciones nuevas; las abiertas se siguen gestionando (SL/TP, break-even, '
                    . 'trailing, tiempo). Revisa los errores y reactívala en Cuentas.',
            ],
            'max_loss_close' => [
                'level' => 'error', 'mode' => 'notify', 'key' => null,
                'title' => 'Cierre por pérdida máxima',
                'body'  => "{$account} · {$ref}: el precio retrocedió "
                    . (isset($data['loss_pct']) ? self::pct($data['loss_pct']) : 'más de lo tolerado')
                    . (isset($data['limit_pct']) ? ' (límite ' . self::pct($data['limit_pct']) . ')' : '')
                    . ' desde el nivel de referencia y se cerró a mercado como red de seguridad.',
            ],
            'api_auth_failed' => [
                'level' => 'error', 'mode' => 'open', 'key' => "api_auth:{$accountId}",
                'title' => 'Claves API rechazadas por Bybit',
                'body'  => "{$account}: " . ($reason !== '' ? $reason : 'clave inválida')
                    . '. No se opera esta cuenta hasta corregirlas en Cuentas (permisos: Contratos → Órdenes y Posiciones).',
            ],
            'api_auth_ok' => [
                'level' => 'success', 'mode' => 'resolve', 'key' => "api_auth:{$accountId}",
                'title' => 'Claves API funcionando de nuevo',
                'body'  => "{$account}: Bybit vuelve a aceptar las claves.",
            ],
            'reconcile_closed' => [
                'level' => 'warning', 'mode' => 'notify', 'key' => null,
                'title' => 'Cierre conciliado',
                'body'  => "{$account} · {$ref}: la posición ya estaba cerrada en Bybit; se registró con el precio y el PnL neto de Bybit.",
            ],
            'reconcile_adopted' => ($data['protected'] ?? true) ? [
                'level' => 'warning', 'mode' => 'notify', 'key' => null,
                'title' => 'Posición adoptada por conciliación',
                'body'  => "{$account} · {$ref}{$side}: "
                    . (($data['kind'] ?? '') === 'untracked' ? 'existía en Bybit sin registro en TR2' : 'la apertura no se había confirmado')
                    . '. Ahora se gestiona con el SL/TP de su estrategia.',
            ] : [
                'level' => 'error', 'mode' => 'notify', 'key' => null,
                'title' => 'Posición sin protección de estrategia',
                'body'  => "{$account} · {$ref}{$side}: existe en Bybit pero no se encontró la configuración de su estrategia. "
                    . 'Solo la protege el SL/TP provisional; revísala en Bybit.',
            ],
            'reconcile_discarded' => [
                'level' => 'info', 'mode' => 'notify', 'key' => null,
                'title' => 'Apertura descartada',
                'body'  => "{$account} · {$ref}: la orden no llegó a abrir posición en Bybit; se marcó como fallida.",
            ],
            default => null,
        };
    }

    /** Título y texto del aviso al reactivar una cuenta pausada por el circuit breaker. */
    public static function reactivated(string $account): array
    {
        return ['title' => 'Cuenta reactivada', 'body' => "{$account}: vuelve a abrir posiciones."];
    }

    private static function pct(mixed $v): string
    {
        return number_format((float) $v, 2, ',', '.') . ' %';
    }

    private static function clip(string $s): string
    {
        $s = trim(preg_replace('/\s+/', ' ', $s) ?? '');

        return mb_strlen($s) > 180 ? mb_substr($s, 0, 177) . '…' : $s;
    }
}

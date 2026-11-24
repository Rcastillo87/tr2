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
        'stop_loss' => 'stop loss', 'trailing_stop' => 'trailing stop', 'break_even' => 'break-even', 'time_exit' => 'tiempo máximo',
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
                    . '. No se abrió ninguna posición.'
                    . (self::isPositionModeError($reason)
                        ? ' La cuenta está en modo Hedge y TR2 opera en One-Way: cámbiala en Bybit (Derivados → Ajustes → Modo de posición → One-Way). TR2 no cambia ese ajuste por su cuenta.'
                        : ''),
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
                    . ' desde el nivel de referencia y se cerró a mercado como red de seguridad'
                    . (! empty($data['unresolved']) ? ' (operación sin confirmar: la conciliación anota el cierre).' : '.'),
            ],
            'unresolved_unprotected' => [   // C6-03 (D-68)
                'level' => 'error', 'mode' => 'notify', 'key' => null,
                'title' => 'Operación sin confirmar y sin poder protegerse',
                'body'  => "{$account} · {$ref}: hay una posición viva en Bybit que el bot no puede identificar con certeza"
                    . (isset($data['reason']) ? " ({$data['reason']})" : '')
                    . '. No se cierra sola: revísala en Bybit. La cuenta no abre operaciones nuevas mientras tanto.',
            ],
            'liquidation_risk' => [
                'level' => 'error', 'mode' => 'notify', 'key' => null,
                'title' => ($data['closed'] ?? false) ? 'Posición cerrada: riesgo de liquidación' : 'Riesgo de liquidación: ciérrala en Bybit',
                'body'  => "{$account} · {$ref}{$side}: el stop loss"
                    . (isset($data['sl']) ? ' (' . self::num($data['sl']) . ')' : '')
                    . ' quedaba más allá del precio de liquidación'
                    . (isset($data['liq_price']) ? ' (' . self::num($data['liq_price']) . ')' : '')
                    . (isset($data['leverage']) ? ' con apalancamiento ' . self::num($data['leverage']) . 'x' : '')
                    . (($data['closed'] ?? false) ? '; se cerró de inmediato.' : ' y no se pudo cerrar: ciérrala en Bybit.')
                    . " Baja el apalancamiento de {$sym} en Bybit antes de volver a operarlo.",
            ],
            'monthly_limit_reached' => [
                'level' => 'error', 'mode' => 'open', 'key' => "monthly_limit:{$accountId}",
                'title' => 'Pérdida máxima del mes alcanzada',
                'body'  => "{$account}: pérdida neta del mes "
                    . (isset($data['pct']) ? self::pct($data['pct']) : 'por encima del máximo')
                    . (isset($data['limit']) ? ' (máximo −' . self::num($data['limit']) . ' %)' : '')
                    . (isset($data['paused_until'])   // D-66: pausa de N días
                        ? '. Pausa de ' . (int) ($data['pause_days'] ?? 0) . " día(s): no se abren posiciones hasta el {$data['paused_until']}"
                          . ' (hora de Bogotá); las abiertas se siguen gestionando. Al reanudar, la pérdida se cuenta de cero.'
                        : '. No se abren posiciones hasta el día 1 (00:00 Bogotá); las abiertas se siguen gestionando.'),
            ],
            'loss_pause_ended' => [
                'level' => 'success', 'mode' => 'resolve', 'key' => "monthly_limit:{$accountId}",
                'title' => 'Terminó la pausa por pérdida',
                'body'  => "{$account}: vuelve a abrir posiciones; la pérdida se cuenta de cero desde el "
                    . ($data['since'] ?? 'reinicio') . ' (hora de Bogotá).',
            ],
            'monthly_limit_reset' => [
                'level' => 'success', 'mode' => 'resolve', 'key' => "monthly_limit:{$accountId}",
                'title' => 'Nuevo mes: límite de pérdida reiniciado',
                'body'  => "{$account}: vuelve a abrir posiciones.",
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
                    . match ($data['kind'] ?? '') {
                        'untracked' => 'existía en Bybit sin registro en TR2',
                        'pending'   => 'la apertura se interrumpió (reinicio del motor) pero la orden sí se ejecutó',
                        default     => 'la apertura no se había confirmado',
                    }
                    . '. Ahora se gestiona con el SL/TP de su estrategia.',
            ] : [
                'level' => 'error', 'mode' => 'notify', 'key' => null,
                'title' => 'Posición sin protección de estrategia',
                'body'  => "{$account} · {$ref}{$side}: existe en Bybit pero no se encontró la configuración de su estrategia. "
                    . 'Solo la protege el SL/TP provisional; revísala en Bybit.',
            ],
            'manual_position_ignored' => [
                'level' => 'warning', 'mode' => 'notify', 'key' => null,
                'title' => 'Posición manual ignorada',
                'body'  => "{$account} · " . ($data['symbol'] ?? '') . $side
                    . ': hay una posición abierta en Bybit que no abrió TR2. El bot no la gestiona (sin SL/TP del bot) '
                    . 'y no abre en esa moneda mientras exista.',
            ],
            'manual_position_closed' => [
                'level' => 'info', 'mode' => 'notify', 'key' => null,
                'title' => 'Posición manual cerrada',
                'body'  => "{$account} · " . ($data['symbol'] ?? '') . $side
                    . ': la posición abierta a mano en Bybit ya no está. El bot vuelve a poder abrir en esa moneda, '
                    . 'solo si la señal de apertura sigue vigente.',
            ],
            'reconcile_discarded' => [
                'level' => 'info', 'mode' => 'notify', 'key' => null,
                'title' => 'Apertura descartada',
                'body'  => "{$account} · {$ref}: la orden no llegó a abrir posición en Bybit; se marcó como fallida.",
            ],
            'api_permissions_bad' => [
                'level' => 'error', 'mode' => 'open', 'key' => "api_perms:{$accountId}",
                'title' => 'Permisos de la clave API a revisar',
                'body'  => "{$account}: la clave API " . self::permissionProblems($data['problems'] ?? [])
                    . '. La cuenta sigue operando; reemplázala en Cuentas por una con Contratos → Órdenes y Posiciones'
                    . ' y sin retiros.',
            ],
            'api_permissions_ok' => [
                'level' => 'success', 'mode' => 'resolve', 'key' => "api_perms:{$accountId}",
                'title' => 'Permisos de la clave API correctos',
                'body'  => "{$account}: la clave tiene Contratos → Órdenes y Posiciones y no tiene retiros.",
            ],
            'protection_failed' => [
                'level' => 'error', 'mode' => 'open', 'key' => "protection:{$accountId}:" . ($tradeId ?? $sym),
                'title' => 'SL/TP de la estrategia no instalado',
                'body'  => "{$account} · {$ref}{$side}{$strategy}: Bybit no aceptó el SL/TP de la estrategia"
                    . (isset($data['sl']) ? ' (SL ' . self::num($data['sl']) . (isset($data['tp']) ? ' / TP ' . self::num($data['tp']) : '') . ')' : '')
                    . '. La posición sigue protegida solo por el stop provisional'
                    . (isset($data['exchange_sl']) ? ' (SL ' . self::num($data['exchange_sl']) . ' en Bybit)' : ' de la orden (2 % / 4 %)')
                    . '; se reintenta cada minuto. Revísala en Bybit si no se corrige.',
            ],
            'protection_restored' => [
                'level' => 'success', 'mode' => 'resolve', 'key' => "protection:{$accountId}:" . ($tradeId ?? $sym),
                'title' => 'SL/TP de la estrategia instalado',
                'body'  => "{$account} · {$ref}{$side}: el SL/TP de la estrategia ya está en Bybit"
                    . (isset($data['sl']) ? ' (SL ' . self::num($data['sl']) . (isset($data['tp']) ? ' / TP ' . self::num($data['tp']) : '') . ')' : '')
                    . '.',
            ],
            'executions_mismatch' => [
                'level' => 'warning', 'mode' => 'notify', 'key' => null,
                'title' => 'Ejecuciones de Bybit que no cuadran',
                'body'  => "{$account} · {$ref}: 24 h después del cierre, lo que llenó Bybit no cuadra con lo registrado ("
                    . self::clip(implode('; ', array_map('strval', is_array($data['checks'] ?? null) ? $data['checks'] : [])))
                    . '). El neto y el saldo vienen de Bybit y no cambian; la comisión y el funding de esta operación no se'
                    . ' separan. Revísala en el historial de la operación.',
            ],
            default => null,
        };
    }

    /** Título y texto del aviso al reactivar una cuenta pausada por el circuit breaker. */
    public static function reactivated(string $account): array
    {
        return ['title' => 'Cuenta reactivada', 'body' => "{$account}: vuelve a abrir posiciones."];
    }

    /** Problemas de permisos de la clave (códigos del motor: read_only, missing_order, missing_position, withdraw). */
    private static function permissionProblems(mixed $codes): string
    {
        $texts = [
            'read_only' => 'es de solo lectura', 'missing_order' => 'no tiene Contratos → Órdenes',
            'missing_position' => 'no tiene Contratos → Posiciones', 'withdraw' => 'tiene permiso de retiro',
        ];
        $parts = array_map(fn ($c) => $texts[$c] ?? (string) $c, is_array($codes) ? $codes : []);

        return $parts === [] ? 'no tiene los permisos que TR2 necesita' : implode(', ', $parts);
    }

        /** Rechazo de Bybit porque la cuenta está en modo Hedge (TR2 envía órdenes One-Way, positionIdx=0). */
    private static function isPositionModeError(string $reason): bool
    {
        $r = mb_strtolower($reason);

        return str_contains($r, 'position idx not match position mode') || str_contains($r, 'position mode');
    }

        private static function num(mixed $v): string
    {
        return rtrim(rtrim(number_format((float) $v, 8, ',', '.'), '0'), ',');
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

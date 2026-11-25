<?php

namespace App\Support;

/**
 * Lista de suscripciones de una cuenta Real (24-nov): cada moneda con su propio estado y el aviso cuando otra config
 * de la cuenta opera la misma moneda (el motor abre una sola posición por moneda y cuenta: la que dé señal primero).
 * Puro para poder probarlo; lo usa trading/partials/subscriptions_list.
 */
final class SubscriptionRows
{
    public const LABELS = [
        'active'   => 'Activa',
        'paused'   => 'Pausada',
        'retiring' => 'Se elimina al cerrar su operación',
    ];

    /**
     * @param array<int, array{id:int, symbol:string, strategy:string, status:string, retire_on_close:bool}> $subs
     *        todas las suscripciones de la cuenta
     * @return array<int, array{state:string, label:string, shares:string[]}> por id de suscripción
     */
    public static function build(array $subs): array
    {
        $out = [];
        foreach ($subs as $s) {
            $state = ! empty($s['retire_on_close']) ? 'retiring' : ($s['status'] === 'active' ? 'active' : 'paused');
            $shares = [];
            foreach ($subs as $o) {
                if ((int) $o['id'] !== (int) $s['id'] && $o['symbol'] === $s['symbol'] && empty($o['retire_on_close'])) {
                    $shares[] = (string) $o['strategy'];
                }
            }
            $out[(int) $s['id']] = ['state' => $state, 'label' => self::LABELS[$state], 'shares' => $shares];
        }

        return $out;
    }

    public static function sharedNote(array $shares): ?string
    {
        if ($shares === []) {
            return null;
        }

        return 'Misma moneda que «' . implode('», «', $shares) . '». Si están activas a la vez, solo una opera: '
            . 'la que dé señal primero.';
    }
}

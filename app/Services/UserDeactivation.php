<?php

namespace App\Services;

use App\Models\RealStrategySubscription;
use App\Models\RealTrade;
use App\Models\User;
use Illuminate\Support\Facades\DB;

/**
 * Inactivar / reactivar un usuario (decisión del dueño, 13-nov; U-1..U-3).
 *
 * - Inactivar ELIMINA sus suscripciones Real para que, al reactivarlo, elija de nuevo cuáles opera.
 * - Las que tienen operaciones vivas (RealTrade::RECONCILE_STATUSES) quedan PAUSADAS y marcadas retire_on_close
 *   hasta que esas operaciones terminen su ciclo completo: el tick las sigue enviando al motor SIN entradas
 *   (RealStrategySubscription::windingDown) para la gestión y la salida por señal opuesta. Cuando ya no tienen
 *   operaciones vivas, purgeFinished() (cada 5 min) las elimina, aunque el usuario se haya reactivado.
 * Reglas de negocio: docs/DECISIONES_DUENO.md (D-02 a D-05).
 * - Los trades (historial) no se tocan: real_trades.subscription_id es ON DELETE SET NULL.
 * - Las entradas nuevas de un usuario inactivo están bloqueadas además por RealStrategySubscription::runnable()
 *   (aunque se inactive por SQL o una suscripción vuelva a quedar activa por error).
 */
final class UserDeactivation
{
    /** @return array{deleted: int, kept: int} */
    public function setActive(User $user, bool $active): array
    {
        return DB::transaction(function () use ($user, $active) {
            $user->is_active = $active;
            $user->save();

            return $active ? ['deleted' => 0, 'kept' => 0] : $this->releaseSubscriptions((int) $user->id);
        });
    }

    /**
     * Suscripciones de un usuario que se inactiva: sin operaciones vivas -> se eliminan; con operaciones vivas ->
     * pausadas hasta que terminen. Debe correr dentro de una transacción (setActive).
     *
     * @return array{deleted: int, kept: int}
     */
    public function releaseSubscriptions(int $userId): array
    {
        $deleted = $kept = 0;
        foreach (RealStrategySubscription::where('user_id', $userId)->orderBy('id')->lockForUpdate()->get() as $sub) {
            if (self::hasLiveTrades((int) $sub->id)) {
                $sub->update(['status' => 'paused', 'retire_on_close' => true]);
                $kept++;
            } else {
                $sub->delete();
                $deleted++;
            }
        }

        return ['deleted' => $deleted, 'kept' => $kept];
    }

    /**
     * Elimina las suscripciones marcadas retire_on_close (las que quedaron con operaciones vivas al inactivar a su
     * usuario) y las de usuarios inactivos, cuando ya no tienen operaciones vivas. Aunque el usuario se haya
     * reactivado: elige de nuevo (decisión del dueño 13-nov, D-04). Devuelve cuántas eliminó.
     */
    public function purgeFinished(): int
    {
        return DB::transaction(function () {
            $n = 0;
            $subs = RealStrategySubscription::where(fn ($q) => $q->where('retire_on_close', true)
                    ->orWhereHas('user', fn ($u) => $u->where('is_active', false)))
                ->orderBy('id')->lockForUpdate()->get();
            foreach ($subs as $sub) {
                if (! self::hasLiveTrades((int) $sub->id)) {
                    $sub->delete();
                    $n++;
                }
            }

            return $n;
        });
    }

    public static function hasLiveTrades(int $subscriptionId): bool
    {
        return RealTrade::where('subscription_id', $subscriptionId)
            ->whereIn('status', RealTrade::RECONCILE_STATUSES)->exists();
    }
}

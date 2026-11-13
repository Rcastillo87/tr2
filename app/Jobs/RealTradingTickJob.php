<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use App\Support\RealTickResults;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;

class RealTradingTickJob implements ShouldQueue, ShouldBeUnique
{
    use Queueable;

    public int $uniqueFor = 60;

    public int $tries   = 1;
    public int $timeout = 30;

    /**
     * Ya no procesa las cuentas el mismo — solo las lista y despacha un
     * RealTradingAccountTickJob por cada una a la cola (Horizon las reparte
     * entre sus workers en paralelo). Esto elimina el limite fijo de 75
     * segundos que tenia el pedido HTTP unico con todas las cuentas juntas,
     * y evita que un problema en una cuenta bloquee a las demas.
     */
    public function handle(): void
    {
        // Cuentas con suscripciones activas O con posiciones abiertas (estas se gestionan hasta cerrarse,
        // aunque se haya pausado la última suscripción).
        // Y cualquier cuenta PAUSADA con posiciones abiertas: se gestionan, pero no se abre nada.
        $accountIds = BrokerAccount::query()
            ->where(fn ($q) => $q
                ->where(fn ($a) => $a->where('status', 'active')
                    ->whereHas('subscriptions', fn ($s) => $s->runnable()))
                ->orWhereExists(fn ($e) => self::openRealTrades($e)))
            ->pluck('id');

        if ($accountIds->isEmpty()) {
            Log::debug('RealTradingTickJob: sin cuentas activas');
            return;
        }

        foreach ($accountIds as $accountId) {
            RealTradingAccountTickJob::dispatch($accountId)->onQueue('high');
        }

        Log::debug('RealTradingTickJob: despachados ' . $accountIds->count() . ' job(s) de cuenta');
    }

    /** Subconsulta: trades reales abiertos de la cuenta (broker_accounts.id). */
    public static function openRealTrades($query)
    {
        return $query->selectRaw('1')->from('real_trades')
            ->whereColumn('real_trades.broker_account_id', 'broker_accounts.id')
            ->whereIn('real_trades.status', ['open', 'pending_close']);
    }

    /**
     * Logging compartido de resultados de un tick — usado por
     * RealTradingAccountTickJob. Mantiene el mismo formato de logs de
     * siempre para no romper nada que dependa de grep-ear estas lineas.
     */
    public static function logAccountResults(array $results): void
    {
        // Interpretación pura en App\Support\RealTickResults (R-14: un tick omitido llegaba como texto y rompía array_filter)
        foreach (RealTickResults::lines($results) as [$level, $message]) {
            Log::log($level, $message);
        }
    }
}

<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;

class RealTradingTickJob implements ShouldQueue
{
    use Queueable;

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
        $accountIds = BrokerAccount::where('status', 'active')
            ->where(fn ($q) => $q
                ->whereHas('subscriptions', fn ($s) => $s->where('status', 'active'))
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
        foreach ($results as $accountKey => $accountData) {
            if (isset($accountData['error'])) {
                Log::error("RealTrading {$accountKey}: {$accountData['error']}");
                continue;
            }

            $monitor = $accountData['monitor'] ?? [];
            if (($monitor['closed'] ?? 0) > 0) {
                Log::info("RealTrading {$accountKey}: {$monitor['closed']} posicion(es) cerrada(s)");
            }
            if (($monitor['errors'] ?? 0) > 0) {
                Log::warning("RealTrading {$accountKey}: {$monitor['errors']} error(es) al cerrar");
            }

            // Loguear TODAS las señales para facilitar debugging
            $signals = $accountData['signals'] ?? [];
            $opened  = array_filter($signals, fn($r) => str_starts_with((string)$r, 'ABIERTA'));
            $errors  = array_filter($signals, fn($r) => str_starts_with((string)$r, 'ERROR') || str_starts_with((string)$r, 'EXCEPTION'));

            foreach ($opened as $strategy => $result) {
                Log::info("RealTrading ABIERTA: {$accountKey} | {$strategy} -> {$result}");
            }
            foreach ($errors as $strategy => $result) {
                Log::error("RealTrading ERROR: {$accountKey} | {$strategy} -> {$result}");
            }
            // Log resumen del tick (debug)
            $sinSenal = count(array_filter($signals, fn($r) => str_contains((string)$r, 'sin señal')));
            Log::debug("RealTrading tick: {$accountKey} | monitoreadas:" . ($monitor['checked'] ?? 0) . " cerradas:" . ($monitor['closed'] ?? 0) . " nuevas:" . count($opened) . " errores:" . count($errors) . " sin_senal:{$sinSenal}");
        }
    }
}

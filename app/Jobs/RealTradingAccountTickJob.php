<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class RealTradingAccountTickJob implements ShouldQueue, ShouldBeUnique
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 75;
    /** Vencimiento de seguridad del bloqueo (s): nunca dos ticks de la MISMA cuenta a la vez. */
    public int $uniqueFor = 120;
    /** Último tick que gestionó las posiciones de la cuenta (lo mira el vigilante). */
    public const LAST_OK_KEY = 'real_tick:ok:';

    public function __construct(public int $accountId)
    {
    }

    public function uniqueId(): string
    {
        return (string) $this->accountId;
    }

    public function handle(): void
    {
        // La cuenta se busca ACA ADENTRO, no en el constructor — asi las
        // credenciales desencriptadas nunca quedan serializadas en el
        // payload del job dentro de la cola de Redis (solo viaja el id).
        $account = BrokerAccount::where('id', $this->accountId)
            ->with(['subscriptions' => fn ($q) => $q->where('status', 'active')
                ->with('paperStrategyConfig')])
            ->first();

        if (!$account) {
            return;
        }
        // Cuenta pausada (a mano o por el circuit breaker) o sin suscripciones activas: sus posiciones abiertas
        // se siguen gestionando (SL/TP, break-even, trailing, tiempo) pero no se abre nada.
        $entriesAllowed = $account->status === 'active';
        $hasOpen = \App\Models\RealTrade::where('broker_account_id', $account->id)
            ->whereIn('status', ['open', 'pending_close'])->exists();
        if (!$hasOpen && (!$entriesAllowed || $account->subscriptions->isEmpty())) {
            return;
        }

        $url = config('trading.python_engine_url') . '/v1/real/tick';

        $payload = [
            'accounts' => [[
                'id'           => $account->id,
                'broker'       => $account->broker,
                'account_type' => $account->account_type,
                'api_key'      => $account->api_key,
                'api_secret'   => $account->api_secret,
                'entries_allowed' => $entriesAllowed,
                'subscriptions' => $account->subscriptions->map(function ($sub) {
                    $config = $sub->paperStrategyConfig;
                    return [
                        'subscription_id'          => $sub->id,
                        'user_id'                  => $sub->user_id,
                        'broker_account_id'        => $sub->broker_account_id,
                        'paper_strategy_config_id' => $sub->paper_strategy_config_id,
                        'strategy'                 => $sub->strategy,
                        'symbol'                   => $sub->symbol,
                        'interval'                 => $sub->interval,
                        'strategy_class'           => $config?->strategy_class,
                        'config_params'            => $config?->params,
                        'risk_override_pct'        => $sub->risk_override_pct,
                    ];
                })->values()->toArray(),
            ]],
        ];

        $started = microtime(true);
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(60)->post($url, $payload);

            if (!$response->successful()) {
                Log::warning('RealTradingAccountTickJob: respuesta no exitosa', [
                    'account_id' => $this->accountId,
                    'status'     => $response->status(),
                    'body'       => $response->body(),
                ]);
                return;
            }

            $data = $response->json();
            RealTradingTickJob::logAccountResults($data['results'] ?? []);
            // Solo cuenta como gestionada si el monitor de posiciones corrió (no si se omitió o falló)
            if (collect($data['results'] ?? [])->contains(fn ($r) => is_array($r) && isset($r['monitor']))) {
                \Illuminate\Support\Facades\Cache::put(self::LAST_OK_KEY . $this->accountId,
                    now()->toIso8601String(), now()->addDay());
            }

            $secs = round(microtime(true) - $started, 1);
            if ($secs > 40) {
                Log::warning("RealTradingAccountTickJob lento: cuenta {$this->accountId} {$secs}s (el tick corre cada minuto)");
            }

        } catch (\Throwable $e) {
            Log::error("RealTradingAccountTickJob: error (cuenta {$this->accountId}) — " . $e->getMessage());
        }
    }
}

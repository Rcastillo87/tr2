<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use App\Models\RealStrategySubscription;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class RealTradingTickJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 90;

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/real/tick';

        // Construir payload con credenciales desencriptadas por Laravel
        // Python NO puede leer credenciales encriptadas de la DB directamente
        $accounts = BrokerAccount::where('status', 'active')
            ->whereHas('subscriptions', fn ($q) => $q->where('status', 'active'))
            ->with(['subscriptions' => fn ($q) => $q->where('status', 'active')
                ->with('paperStrategyConfig')])
            ->get();

        if ($accounts->isEmpty()) {
            return;
        }

        $payload = [
            'accounts' => $accounts->map(function ($account) {
                return [
                    'id'           => $account->id,
                    'broker'       => $account->broker,
                    'account_type' => $account->account_type,
                    'api_key'      => $account->api_key,    // desencriptado por Laravel
                    'api_secret'   => $account->api_secret, // desencriptado por Laravel
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
                        ];
                    })->values()->toArray(),
                ];
            })->values()->toArray(),
        ];

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(75)->post($url, $payload);

            if (!$response->successful()) {
                Log::warning('RealTradingTickJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
                return;
            }

            $data = $response->json();

            foreach (($data['results'] ?? []) as $accountKey => $accountData) {
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

                foreach (($accountData['signals'] ?? []) as $strategy => $result) {
                    if (str_starts_with((string) $result, 'ABIERTA')) {
                        Log::info("RealTrading señal: {$accountKey} {$strategy} -> {$result}");
                    } elseif (str_starts_with((string) $result, 'ERROR')) {
                        Log::error("RealTrading error: {$accountKey} {$strategy} -> {$result}");
                    }
                }
            }

        } catch (\Throwable $e) {
            Log::error('RealTradingTickJob: error — ' . $e->getMessage());
        }
    }
}

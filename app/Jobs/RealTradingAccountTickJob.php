<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class RealTradingAccountTickJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 75;

    public function __construct(public int $accountId)
    {
    }

    public function handle(): void
    {
        // La cuenta se busca ACA ADENTRO, no en el constructor — asi las
        // credenciales desencriptadas nunca quedan serializadas en el
        // payload del job dentro de la cola de Redis (solo viaja el id).
        $account = BrokerAccount::where('status', 'active')
            ->where('id', $this->accountId)
            ->with(['subscriptions' => fn ($q) => $q->where('status', 'active')
                ->with('paperStrategyConfig')])
            ->first();

        if (!$account || $account->subscriptions->isEmpty()) {
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

        } catch (\Throwable $e) {
            Log::error("RealTradingAccountTickJob: error (cuenta {$this->accountId}) — " . $e->getMessage());
        }
    }
}

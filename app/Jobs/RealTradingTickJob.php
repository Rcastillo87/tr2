<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
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

        $accounts = BrokerAccount::where('status', 'active')
            ->whereHas('subscriptions', fn ($q) => $q->where('status', 'active'))
            ->with(['subscriptions' => fn ($q) => $q->where('status', 'active')
                ->with('paperStrategyConfig')])
            ->get();

        if ($accounts->isEmpty()) {
            Log::debug('RealTradingTickJob: sin cuentas activas');
            return;
        }

        $payload = [
            'accounts' => $accounts->map(function ($account) {
                return [
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
            Log::info('RealTradingTickJob: tick ejecutado', [
                'accounts' => array_keys($data['results'] ?? []),
            ]);

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
                $pausadas = count(array_filter($signals, fn($r) => str_contains((string)$r, 'pausada') || str_contains((string)$r, 'regimen')));
                Log::debug("RealTrading tick: {$accountKey} | abiertas:" . count($opened) . " errores:" . count($errors) . " sin_senal:{$sinSenal} bloqueadas:{$pausadas}");
            }

        } catch (\Throwable $e) {
            Log::error('RealTradingTickJob: error — ' . $e->getMessage());
        }
    }
}

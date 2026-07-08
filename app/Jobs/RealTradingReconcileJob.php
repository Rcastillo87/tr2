<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class RealTradingReconcileJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 120;

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/real/reconcile';

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
                    'api_key'      => $account->api_key,
                    'api_secret'   => $account->api_secret,
                    'credentials_extra' => $account->credentials_extra,
                    'subscriptions' => $account->subscriptions->map(function ($sub) {
                        return [
                            'subscription_id'          => $sub->id,
                            'user_id'                  => $sub->user_id,
                            'broker_account_id'        => $sub->broker_account_id,
                            'paper_strategy_config_id' => $sub->paper_strategy_config_id,
                            'strategy'                 => $sub->strategy,
                            'symbol'                   => $sub->symbol,
                            'interval'                 => $sub->interval,
                            'strategy_class'           => $sub->paperStrategyConfig?->strategy_class,
                            'config_params'            => $sub->paperStrategyConfig?->params,
                        ];
                    })->values()->toArray(),
                ];
            })->values()->toArray(),
        ];

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(90)->post($url, $payload);

            if (!$response->successful()) {
                Log::warning('RealTradingReconcileJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
                return;
            }

            $data = $response->json();
            $results = $data['results'] ?? [];

            if (!empty($results['reconciled'])) {
                foreach ($results['reconciled'] as $r) {
                    Log::warning("Reconciliacion: trade #{$r['trade_id']} {$r['symbol']} cerrado — {$r['reason']}");
                }
            }

            if (!empty($results['orphaned'])) {
                foreach ($results['orphaned'] as $r) {
                    Log::error("Reconciliacion: posicion huerfana en Bybit — {$r['symbol']} size={$r['size']} side={$r['side']}");
                }
            }

            $ok        = count($results['ok'] ?? []);
            $reconciled = count($results['reconciled'] ?? []);
            $orphaned   = count($results['orphaned'] ?? []);

            if ($reconciled > 0 || $orphaned > 0) {
                Log::info("Reconciliacion completada: {$ok} ok, {$reconciled} reconciliados, {$orphaned} huerfanos");
            }

        } catch (\Throwable $e) {
            Log::error('RealTradingReconcileJob: error — ' . $e->getMessage());
        }
    }
}

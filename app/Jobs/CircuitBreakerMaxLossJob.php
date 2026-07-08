<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Circuit breaker de perdida maxima — corre cada 1 minuto (mas seguido que
 * el monitoreo normal de 5 min) porque su unico proposito es detectar
 * posiciones cuya perdida no realizada ya supero un multiplo de seguridad
 * del SL nominal (ver check_max_loss_circuit_breaker en real_trader.py).
 * No reemplaza el SL/trailing nativo de Bybit — es una segunda capa de
 * defensa ante desincronizaciones (ej. activePrice mal calibrado, fallos
 * de red, bugs no descubiertos) que dejen una posicion efectivamente
 * desprotegida por mas tiempo del esperado.
 *
 * Deliberadamente NO reusa RealTradingAccountTickJob/RealTradingTickJob:
 * ese par ya despacha un job por cuenta para /real/tick (con calculo de
 * senales, mas pesado). Este job es liviano (una sola llamada a Bybit por
 * posicion abierta, sin velas ni indicadores) y corre en un ciclo aparte
 * y mas frecuente, asi que se mantiene como su propio flujo simple.
 */
class CircuitBreakerMaxLossJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 30;

    public function handle(): void
    {
        $accounts = BrokerAccount::where('status', 'active')
            ->whereHas('subscriptions', fn ($q) => $q->where('status', 'active'))
            ->get();

        if ($accounts->isEmpty()) {
            return;
        }

        $payload = [
            'accounts' => $accounts->map(fn ($account) => [
                'id'            => $account->id,
                'broker'        => $account->broker,
                'account_type'  => $account->account_type,
                'api_key'       => $account->api_key,
                'api_secret'    => $account->api_secret,
                'credentials_extra' => $account->credentials_extra,
                'subscriptions' => [],
            ])->values()->toArray(),
        ];

        $url = config('trading.python_engine_url') . '/v1/real/circuit-breaker-max-loss';

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(25)->post($url, $payload);

            if (!$response->successful()) {
                Log::warning('CircuitBreakerMaxLossJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
                return;
            }

            $data = $response->json();
            foreach ($data['results'] ?? [] as $accountKey => $result) {
                if (isset($result['error'])) {
                    Log::error("CircuitBreakerMaxLoss {$accountKey}: {$result['error']}");
                    continue;
                }
                if (($result['closed'] ?? 0) > 0) {
                    Log::error("CircuitBreakerMaxLoss {$accountKey}: {$result['closed']} posicion(es) cerrada(s) por perdida excesiva");
                }
                if (($result['errors'] ?? 0) > 0) {
                    Log::warning("CircuitBreakerMaxLoss {$accountKey}: {$result['errors']} error(es) durante el chequeo");
                }
            }

        } catch (\Throwable $e) {
            Log::error('CircuitBreakerMaxLossJob: error — ' . $e->getMessage());
        }
    }
}

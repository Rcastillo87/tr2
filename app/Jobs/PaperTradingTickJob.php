<?php

namespace App\Jobs;

use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class PaperTradingTickJob implements ShouldQueue, ShouldBeUnique
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 60;
    /** Vencimiento de seguridad del bloqueo de unicidad (s): nunca dos ticks a la vez. */
    public int $uniqueFor = 120;

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/paper/tick';
        $started = microtime(true);

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(45)->post($url);

            if (!$response->successful()) {
                Log::warning('PaperTradingTickJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
                return;
            }

            $data = $response->json();

            $secs = round(microtime(true) - $started, 1);
            if ($secs > 40) {
                Log::warning("PaperTradingTickJob lento: {$secs}s (el tick corre cada minuto)");
            }

            // Log de cierres y aperturas
            foreach (($data['monitor'] ?? []) as $key => $value) {
                if (in_array($key, ['closed', 'be_activated']) && $value > 0) {
                    Log::info("PaperTrading monitor: {$key} = {$value}");
                }
            }

            foreach (($data['signals'] ?? []) as $key => $result) {
                if (str_starts_with((string) $result, 'ABIERTA')) {
                    Log::info("PaperTrading señal: {$key} -> {$result}");
                }
            }

        } catch (\Throwable $e) {
            Log::error('PaperTradingTickJob: error — ' . $e->getMessage());
        }
    }
}

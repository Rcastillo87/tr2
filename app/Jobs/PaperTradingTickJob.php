<?php

namespace App\Jobs;

use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class PaperTradingTickJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 60;

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/paper/tick';

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

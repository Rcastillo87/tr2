<?php

namespace App\Jobs;

use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class DetectMarketRegimeJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 60;

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/regime/run';

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(45)->post($url);

            if (!$response->successful()) {
                Log::warning('DetectMarketRegimeJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
                return;
            }

            $data    = $response->json();
            $results = $data['results'] ?? [];

            foreach ($results as $symbol => $info) {
                if (isset($info['regime'])) {
                    Log::info("Régimen {$symbol}: {$info['regime']} (ADX: {$info['adx']})");
                }
            }

        } catch (\Throwable $e) {
            Log::error('DetectMarketRegimeJob: error — ' . $e->getMessage());
        }
    }
}

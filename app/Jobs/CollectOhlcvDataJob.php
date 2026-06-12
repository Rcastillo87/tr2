<?php

namespace App\Jobs;

use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class CollectOhlcvDataJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    public int $timeout = 120;

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/collector/run';

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(90)->post($url);

            if (!$response->successful()) {
                Log::warning('CollectOhlcvDataJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => $response->body(),
                ]);
                return;
            }

            $data        = $response->json();
            $totalSaved  = $data['total_saved'] ?? 0;

            if ($totalSaved > 0) {
                Log::info("CollectOhlcvDataJob: {$totalSaved} velas nuevas guardadas", $data['results'] ?? []);
            }

        } catch (\Throwable $e) {
            Log::error('CollectOhlcvDataJob: error — ' . $e->getMessage());
        }
    }
}

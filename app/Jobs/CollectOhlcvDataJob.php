<?php

namespace App\Jobs;

use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Actualiza todas las series activas del collector (cada minuto). Nunca dos a la vez: única en la cola y, además,
 * el motor rechaza ("busy") una corrida si la anterior sigue viva. timeout < retry_after de la cola (90 s) para que
 * Redis no la re-entregue mientras corre. El resultado de la última corrida queda en caché (collector:last_run)
 * para la pantalla del Data Collector.
 */
class CollectOhlcvDataJob implements ShouldQueue, ShouldBeUnique
{
    use Queueable;

    public const LAST_RUN_KEY = 'collector:last_run';

    public int $tries = 1;
    public int $timeout = 80;
    /** Vencimiento de seguridad del bloqueo de unicidad (s). */
    public int $uniqueFor = 120;

    public function handle(): void
    {
        $started = microtime(true);
        $run = ['at' => now()->toIso8601String(), 'ok' => false, 'status' => 'error', 'duration_s' => null,
                'saved' => 0, 'series' => 0, 'failed' => 0, 'errors' => []];
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(75)->post(config('trading.python_engine_url') . '/v1/collector/run');

            if (! $response->successful()) {
                Log::warning('CollectOhlcvDataJob: respuesta no exitosa', ['status' => $response->status(), 'body' => mb_substr($response->body(), 0, 500)]);
                $run['errors'] = ['motor' => 'HTTP ' . $response->status()];
            } else {
                $data = $response->json();
                $run = array_merge($run, [
                    'ok'         => ($data['status'] ?? '') === 'ok' && (int) ($data['failed'] ?? 0) === 0,
                    'status'     => $data['status'] ?? 'error',
                    'duration_s' => $data['duration_s'] ?? null,
                    'saved'      => (int) ($data['total_saved'] ?? 0),
                    'series'     => (int) ($data['series'] ?? 0),
                    'failed'     => (int) ($data['failed'] ?? 0),
                    'errors'     => $data['errors'] ?? [],
                ]);
                if ($run['failed'] > 0) {
                    Log::warning("CollectOhlcvDataJob: {$run['failed']} serie(s) fallaron", $run['errors']);
                }
            }
        } catch (\Throwable $e) {
            Log::error('CollectOhlcvDataJob: error — ' . $e->getMessage());
            $run['errors'] = ['laravel' => mb_substr($e->getMessage(), 0, 300)];
        }

        if ($run['status'] !== 'busy') {   // "busy" = la corrida anterior sigue: se conserva su registro
            $run['job_s'] = round(microtime(true) - $started, 2);
            Cache::put(self::LAST_RUN_KEY, $run, now()->addDay());
        }
    }
}

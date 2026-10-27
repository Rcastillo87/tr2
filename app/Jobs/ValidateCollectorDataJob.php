<?php

namespace App\Jobs;

use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use Throwable;

/**
 * "Validar contra Bybit" (Data Collector): corre cli/collector_validate.py en la cola research (1 proceso, prioridad
 * mínima) y guarda el resultado en caché para la pantalla. Solo lectura sobre los datos.
 */
class ValidateCollectorDataJob implements ShouldQueue, ShouldBeUnique
{
    use Queueable;

    public const RESULT_KEY = 'collector:last_validation';
    public const RUNNING_KEY = 'collector:validation_running';
    public const ERROR_KEY = 'collector:validation_error';

    public int $tries = 1;
    public int $timeout = 1200;
    public int $uniqueFor = 1500;

    public function handle(): void
    {
        $engine = base_path('python-engine');
        $out = storage_path('app/collector_validation.json');
        try {
            $result = Process::path($engine)->timeout(1100)
                ->run(['nice', '-n', '19', 'ionice', '-c3', $engine . '/venv/bin/python', 'cli/collector_validate.py',
                       '--recent', '300', '--json-out', $out, '--quiet']);
            $data = is_file($out) ? json_decode((string) file_get_contents($out), true) : null;
            // código 1 = hay series con fallas (resultado válido); otro código sin JSON = error de la herramienta
            if (! is_array($data) || ! isset($data['summary'])) {
                throw new \RuntimeException(trim($result->errorOutput()) ?: 'la validación no produjo resultado');
            }
            Cache::put(self::RESULT_KEY, $data, now()->addDays(30));
            Cache::forget(self::ERROR_KEY);
        } catch (Throwable $e) {
            Log::warning('[COLLECTOR-VALIDATE] ' . $e->getMessage());
            Cache::put(self::ERROR_KEY, mb_substr($e->getMessage(), -500), now()->addDays(1));
        } finally {
            @unlink($out);
            Cache::forget(self::RUNNING_KEY);
        }
    }

    public function failed(?Throwable $e): void
    {
        Cache::forget(self::RUNNING_KEY);
        Cache::put(self::ERROR_KEY, 'La tarea de validación falló: ' . ($e?->getMessage() ?? 'desconocido'), now()->addDay());
    }
}

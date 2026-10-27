<?php

namespace App\Jobs;

use App\Models\ParamSearchRun;
use App\Services\ParamSearchService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use Throwable;

/**
 * Corre cli/param_search.py --run-id N (cola research: 1 proceso). El script escribe estado, progreso y
 * resultados en la fila; aquí solo se lanza y, si el proceso muere sin cerrar la fila, se marca fallida.
 */
class RunParamSearchJob implements ShouldQueue
{
    use Queueable;

    public int $tries = 1;
    public int $timeout = 11100;  // 185 min > tope de la búsqueda (180) y < retry_after (11400) de redis-research

    public function __construct(public int $runId)
    {
    }

    public function handle(): void
    {
        $run = ParamSearchRun::find($this->runId);
        if (! $run || $run->status !== 'queued') {
            return;   // cancelada mientras esperaba, o ya procesada
        }
        $engine = base_path('python-engine');
        $result = Process::path($engine)
            ->timeout((ParamSearchService::MAX_MINUTES + 5) * 60)
            ->run(['nice', '-n', '19', 'ionice', '-c3', $engine . '/venv/bin/python', 'cli/param_search.py',
                   '--run-id', (string) $this->runId, '--max-minutes', (string) ParamSearchService::MAX_MINUTES]);

        if (! $result->successful()) {
            Log::warning("[PARAM-SEARCH] #{$this->runId} terminó con código {$result->exitCode()}: "
                . mb_substr(trim($result->errorOutput()), -1500));
        }
        $err = trim($result->errorOutput());
        if (in_array($result->exitCode(), [143, 137, -15, -9], true) || str_contains($err, 'signal')) {
            $err = 'Interrumpida por un reinicio del servidor, del motor o de Horizon. Vuelve a lanzarla.';
        }
        $this->closeIfOpen(mb_substr($err ?: 'El proceso terminó sin resultado.', -2000));
    }

    public function failed(?Throwable $e): void
    {
        $msg = $e?->getMessage() ?? 'desconocido';
        $this->closeIfOpen(str_contains($msg, 'signal')
            ? 'Interrumpida por un reinicio del servidor, del motor o de Horizon. Vuelve a lanzarla.'
            : 'La tarea de búsqueda falló: ' . $msg);
    }

    private function closeIfOpen(string $error): void
    {
        ParamSearchRun::whereKey($this->runId)->whereIn('status', ParamSearchRun::ACTIVE)
            ->update(['status' => 'failed', 'error' => $error, 'finished_at' => now()]);
    }
}

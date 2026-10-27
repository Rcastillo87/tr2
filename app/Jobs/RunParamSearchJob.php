<?php

namespace App\Jobs;

use App\Models\ParamSearchRun;
use App\Services\ParamSearchService;
use App\Services\SystemAlerts;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use Throwable;

/**
 * Corre cli/param_search.py --run-id N (cola research: 1 proceso). El script escribe estado, progreso y
 * resultados en la fila; aquí solo se lanza y, si el proceso muere sin cerrar la fila, se marca fallida.
 * Al terminar deja un aviso (terminada / fallida) para el admin.
 */
class RunParamSearchJob implements ShouldQueue
{
    use Queueable;

    public int $tries = 1;
    public int $timeout = 11100;  // 185 min > tope de la búsqueda (180) y < retry_after (11400) de redis-research

    private const LABELS = ['15' => '15m', '60' => '1h', '120' => '2h', '240' => '4h', 'D' => '1D'];

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
        $this->notifyResult();
    }

    public function failed(?Throwable $e): void
    {
        $msg = $e?->getMessage() ?? 'desconocido';
        $this->closeIfOpen(str_contains($msg, 'signal')
            ? 'Interrumpida por un reinicio del servidor, del motor o de Horizon. Vuelve a lanzarla.'
            : 'La tarea de búsqueda falló: ' . $msg);
        $this->notifyResult();
    }

    private function closeIfOpen(string $error): void
    {
        ParamSearchRun::whereKey($this->runId)->whereIn('status', ParamSearchRun::ACTIVE)
            ->update(['status' => 'failed', 'error' => $error, 'finished_at' => now()]);
    }

    /** Aviso para el admin: terminada (cuántas rentables y la mejor) o fallida. Las canceladas no avisan. */
    private function notifyResult(): void
    {
        try {
            $run = ParamSearchRun::with('strategy:id,name')->find($this->runId);
            if (! $run || ! in_array($run->status, ['done', 'failed'], true)) {
                return;
            }
            $ivs = implode(', ', array_map(fn ($i) => self::LABELS[$i] ?? $i, (array) $run->intervals));
            $name = ($run->strategy?->name ?? 'Estrategia eliminada') . " · {$ivs}";
            $url = route('strategies.search.show', $run->id, false);
            if ($run->status === 'done') {
                $rows = (array) ($run->results['rows'] ?? []);
                $n = (int) ($run->results['survivors'] ?? count($rows));
                $best = $rows ? max(array_map(fn ($r) => (float) ($r['ret_total'] ?? 0), $rows)) : null;
                app(SystemAlerts::class)->notify('success', 'search', "Búsqueda terminada · {$name}",
                    $n > 0 ? sprintf('%d configuración(es) rentable(s) · mejor %+.1f%%', $n, $best) : 'Ninguna configuración rentable.', $url);
            } else {
                app(SystemAlerts::class)->notify('error', 'search', "Búsqueda fallida · {$name}",
                    mb_substr((string) $run->error, 0, 200), $url);
            }
        } catch (Throwable $e) {
            Log::warning("[PARAM-SEARCH] #{$this->runId} no se pudo avisar: " . $e->getMessage());
        }
    }
}

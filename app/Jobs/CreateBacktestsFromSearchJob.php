<?php

namespace App\Jobs;

use App\Models\ParamSearchRun;
use App\Models\User;
use App\Services\BacktestFromSearch;
use App\Services\ParamSearchService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\DB;
use Throwable;

/**
 * "Crear en historial": corre y guarda, por el camino de la pantalla, las filas elegidas de una búsqueda.
 * Cola research (detrás de cualquier búsqueda en curso: nunca dos trabajos pesados a la vez).
 * Resultado por fila en results.created.<fila> = {status, backtest_id|error, symbols}.
 */
class CreateBacktestsFromSearchJob implements ShouldQueue
{
    use Queueable;

    public int $tries = 1;
    public int $timeout = 3900;

    /** @param string $symbolsMode all | search | winners */
    public function __construct(public int $runId, public array $rowIds, public string $symbolsMode, public int $userId)
    {
    }

    public function handle(BacktestFromSearch $creator, ParamSearchService $service): void
    {
        $run = ParamSearchRun::with('strategy')->find($this->runId);
        $user = User::find($this->userId);
        if (! $run || ! $user || $run->status !== 'done' || ! $run->strategy) {
            return;
        }
        $rows = collect($run->results['rows'] ?? [])->keyBy('id');

        foreach ($this->rowIds as $rowId) {
            $row = $rows->get($rowId);
            if (! $row || ! $service->creatable($run, $row)) {
                $this->mark($rowId, ['status' => 'error', 'error' => 'Esta configuración no se puede crear (no es robusta validada).']);
                continue;
            }
            $symbols = match ($this->symbolsMode) {
                'search'  => array_values(array_intersect($run->search_symbols, array_keys($row['symbols']))),
                'winners' => $service->summarize($row)['winners'],
                default   => array_keys($row['symbols']),
            };
            if ($symbols === []) {
                $this->mark($rowId, ['status' => 'error', 'error' => 'Ninguna moneda para crear.']);
                continue;
            }
            $this->mark($rowId, ['status' => 'running', 'symbols' => $symbols]);
            try {
                $out = $creator->run($user, $run->strategy, $row['cfg'], (string) $row['interval'], $symbols,
                    (int) $run->months, true);
                $this->mark($rowId, ['status' => 'done', 'backtest_id' => $out['saved']['backtest_id'] ?? null,
                                     'message' => $out['saved']['message'] ?? null, 'symbols' => $symbols]);
            } catch (Throwable $e) {
                $this->mark($rowId, ['status' => 'error', 'error' => mb_substr($e->getMessage(), 0, 500), 'symbols' => $symbols]);
            }
        }
    }

    private function mark(string $rowId, array $state): void
    {
        DB::update(
            "UPDATE param_search_runs
                SET results = jsonb_set(jsonb_set(results, '{created}', coalesce(results->'created', '{}'::jsonb)),
                                        ARRAY['created', ?], ?::jsonb),
                    updated_at = now()
              WHERE id = ?",
            [$rowId, json_encode($state + ['at' => now()->toIso8601String()], JSON_UNESCAPED_UNICODE), $this->runId]
        );
    }
}

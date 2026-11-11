<?php

namespace App\Jobs;

use App\Models\ParamSearchRun;
use App\Models\User;
use App\Services\BacktestFromSearch;
use App\Services\ParamSearchService;
use App\Support\BacktestOrigin;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
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
    /** No promovida: un job serializado antes de p51 no la trae y debe leerse como null (no como no inicializada). */
    public ?string $token = null;

    /**
     * @param string $symbolsMode survivors (monedas que sobrevivieron) | all (todas las probadas)
     * @param ?string $token reserva hecha por ParamSearchController::create (RQ-01.2); null = trabajo encolado antes de p51
     */
    public function __construct(public int $runId, public array $rowIds, public string $symbolsMode, public int $userId,
                                ?string $token = null)
    {
        $this->token = $token;
    }

    public function handle(BacktestFromSearch $creator, ParamSearchService $service): void
    {
        $run = ParamSearchRun::with('strategy')->find($this->runId);
        $user = User::find($this->userId);
        if (! $run || ! $user || $run->status !== 'done' || ! $run->strategy) {
            $this->releaseReservations($service, 'La búsqueda o el usuario ya no están disponibles.');
            return;
        }
        $rows = collect($run->results['rows'] ?? [])->keyBy('id');

        foreach ($this->rowIds as $rowId) {
            // RQ-01.2: fila ya creada (backtest existente) o reservada por otro pedido -> no se crea otra vez
            $state = $service->createdStates($run->fresh())[$rowId] ?? null;
            if (ParamSearchService::creationBlock($state) !== null && ! $this->ownsReservation($state)) {
                continue;
            }
            $row = $rows->get($rowId);
            if (! $row || ! $service->creatable($run, $row)) {
                $this->mark($rowId, ['status' => 'error', 'error' => 'Esta configuración no se puede crear.']);
                continue;
            }
            $symbols = $service->symbolsFor($run, $row, $this->symbolsMode);
            if ($symbols === []) {
                $this->mark($rowId, ['status' => 'error', 'error' => 'Ninguna moneda para crear.']);
                continue;
            }
            $this->mark($rowId, ['status' => 'running', 'symbols' => $symbols, 'token' => $this->token]);
            try {
                $origin = BacktestOrigin::fromSearch($run->id, (string) $rowId, $run->focus, $run->mode,
                    $this->symbolsMode, $run->created_at?->toIso8601String());
                $out = $creator->run($user, $run->strategy, $row['cfg'], (string) $row['interval'], $symbols,
                    (int) $run->months, true, $origin);
                $this->mark($rowId, ['status' => 'done', 'backtest_id' => $out['saved']['backtest_id'] ?? null,
                                     'message' => $out['saved']['message'] ?? null, 'symbols' => $symbols]);
            } catch (Throwable $e) {
                $this->mark($rowId, ['status' => 'error', 'error' => mb_substr($e->getMessage(), 0, 500), 'symbols' => $symbols]);
            }
        }
    }

    /** Laravel lo llama si el job muere (timeout, excepción): las filas que quedaron en curso vuelven a estar disponibles. */
    public function failed(?Throwable $e): void
    {
        $this->releaseReservations(app(ParamSearchService::class), 'Se interrumpió sin terminar; se puede volver a crear.');
    }

    /** Fila reservada o en curso por ESTE pedido (mismo token). */
    private function ownsReservation(?array $state): bool
    {
        return $this->token !== null && ($state['status'] ?? null) === 'running'
            && hash_equals($this->token, (string) ($state['token'] ?? ''));
    }

    private function releaseReservations(ParamSearchService $service, string $why): void
    {
        $run = ParamSearchRun::find($this->runId);
        if ($run === null || $this->token === null) {
            return;
        }
        $states = $service->createdStates($run);
        foreach ($this->rowIds as $rowId) {
            if ($this->ownsReservation($states[$rowId] ?? null)) {
                $this->mark((string) $rowId, ['status' => 'error', 'error' => $why]);
            }
        }
    }

    private function mark(string $rowId, array $state): void
    {
        ParamSearchService::markCreated($this->runId, (string) $rowId, $state);
    }
}

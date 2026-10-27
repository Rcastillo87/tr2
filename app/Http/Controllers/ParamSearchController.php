<?php

namespace App\Http\Controllers;

use App\Jobs\CreateBacktestsFromSearchJob;
use App\Models\ParamSearchRun;
use App\Models\Strategy;
use App\Services\ParamSearchService;
use DomainException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

/** Estrategias → 🔍 Buscar configuración (endpoints JSON; la pantalla de resultados llega en el paso de vistas). */
class ParamSearchController extends Controller
{
    public function __construct(private readonly ParamSearchService $service)
    {
    }

    /** Datos para la ventana: monedas con datos por temporalidad, búsqueda activa y estimación de tiempo. */
    public function options(Strategy $strategy): JsonResponse
    {
        $this->service->reapStale();
        $byInterval = [];
        foreach (ParamSearchService::INTERVALS as $iv) {
            $byInterval[$iv] = $this->service->availableSymbols([$iv]);
        }
        $active = ParamSearchRun::with('strategy:id,name')->whereIn('status', ParamSearchRun::ACTIVE)->first();

        return response()->json([
            'strategy'          => ['id' => $strategy->id, 'name' => $strategy->name],
            'intervals'         => ParamSearchService::INTERVALS,
            'symbols'           => $byInterval,
            'minutes'           => ParamSearchService::MINUTES_PER_INTERVAL,
            'limits'            => ['min_symbols' => ParamSearchService::MIN_SYMBOLS, 'max_symbols' => ParamSearchService::MAX_SYMBOLS,
                                    'months' => ParamSearchService::MONTHS, 'samples' => ParamSearchService::SAMPLES],
            'fixed'             => ['commission_pct' => 0.055, 'slippage_pct' => 0.05, 'risk_pct' => 1.0],
            'active'            => $active ? $this->state($active) : null,
        ]);
    }

    public function start(Request $request, Strategy $strategy): JsonResponse
    {
        $data = $request->validate([
            'intervals'   => ['required', 'array', 'min:1', 'max:5'],
            'intervals.*' => ['string'],
            'symbols'     => ['required', 'array'],
            'symbols.*'   => ['string', 'max:30'],
            'validate'    => ['sometimes', 'boolean'],
        ]);
        try {
            $run = $this->service->start($strategy, $data['intervals'], $data['symbols'],
                (bool) ($data['validate'] ?? true), $request->user()?->id);
        } catch (DomainException $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }

        return response()->json(['success' => true, 'run' => $this->state($run->fresh('strategy'))]);
    }

    /** Estado para la barra de progreso (consulta liviana: sin los resultados). */
    public function status(ParamSearchRun $run): JsonResponse
    {
        $this->service->reapStale();

        return response()->json($this->state($run->fresh('strategy')));
    }

    public function cancel(ParamSearchRun $run): JsonResponse
    {
        $this->service->cancel($run);

        return response()->json(['success' => true, 'run' => $this->state($run->fresh('strategy'))]);
    }

    /** Resultados resumidos para un conjunto de monedas (all | search | winners), con las mismas métricas que el historial. */
    public function results(Request $request, ParamSearchRun $run): JsonResponse
    {
        $mode = (string) $request->query('symbols', 'all');
        $rows = [];
        foreach ($run->results['rows'] ?? [] as $row) {
            $symbols = match ($mode) {
                'search'  => array_values(array_intersect($run->search_symbols, array_keys($row['symbols']))),
                'winners' => $this->service->summarize($row)['winners'],
                default   => null,
            };
            $rows[] = [
                'id'        => $row['id'],
                'interval'  => $row['interval'],
                'cfg'       => $row['cfg'],
                'robusta'   => $row['robusta'],
                'validada'  => $row['validada'],
                'creatable' => $this->service->creatable($run, $row),
                'is'        => $row['is'],
                'oos'       => $row['oos'],
                'val'       => $row['val'],
                'summary'   => $this->service->summarize($row, $symbols),
                'created'   => $run->results['created'][$row['id']] ?? null,
            ];
        }
        // Orden pedido: retorno total ↓, luego estrellas, luego consistencia
        usort($rows, fn ($a, $b) => [$b['summary']['total_return_pct'], $b['summary']['rating'], $b['summary']['consist_pct']]
            <=> [$a['summary']['total_return_pct'], $a['summary']['rating'], $a['summary']['consist_pct']]);

        return response()->json(['run' => $this->state($run->fresh('strategy')), 'symbols_mode' => $mode, 'rows' => $rows]);
    }

    public function create(Request $request, ParamSearchRun $run): JsonResponse
    {
        $data = $request->validate([
            'rows'    => ['required', 'array', 'min:1', 'max:5'],
            'rows.*'  => ['string', 'max:20'],
            'symbols' => ['required', 'in:all,search,winners'],
        ]);
        if ($run->status !== 'done') {
            return response()->json(['success' => false, 'error' => 'La búsqueda no ha terminado.'], 422);
        }
        if ($run->isOutdated()) {
            return response()->json(['success' => false, 'error' => 'La estrategia cambió después de esta búsqueda: vuelve a buscar.'], 422);
        }
        $rows = collect($run->results['rows'] ?? [])->keyBy('id');
        foreach ($data['rows'] as $id) {
            if (! $rows->has($id) || ! $this->service->creatable($run, $rows[$id])) {
                return response()->json(['success' => false, 'error' => "La configuración {$id} no es robusta validada."], 422);
            }
        }
        CreateBacktestsFromSearchJob::dispatch($run->id, array_values($data['rows']), $data['symbols'], $request->user()->id)
            ->onConnection(ParamSearchService::QUEUE_CONNECTION)->onQueue(ParamSearchService::QUEUE);

        return response()->json(['success' => true, 'message' => count($data['rows']) . ' configuración(es) en cola para crear en el historial.']);
    }

    private function state(ParamSearchRun $run): array
    {
        $r = $run->results ?? [];

        return [
            'id'             => $run->id,
            'strategy'       => $run->strategy?->name,
            'strategy_id'    => $run->strategy_id,
            'status'         => $run->status,
            'phase'          => $run->phase,
            'progress_done'  => $run->progress_done,
            'progress_total' => $run->progress_total,
            'progress_note'  => $run->progress_note,
            'intervals'      => $run->intervals,
            'search_symbols' => $run->search_symbols,
            'validation_symbols' => $run->validation_symbols,
            'created_at'     => $run->created_at?->toIso8601String(),
            'started_at'     => $run->started_at?->toIso8601String(),
            'finished_at'    => $run->finished_at?->toIso8601String(),
            'period'         => $r['period'] ?? null,
            'tested'         => $r['tested'] ?? null,
            'candidates'     => $r['candidates'] ?? null,
            'robust'         => $r['robust'] ?? null,
            'validated'      => $r['validated'] ?? null,
            'elapsed_s'      => $r['elapsed_s'] ?? null,
            'outdated'       => $run->isOutdated(),
            'error'          => $run->error,
        ];
    }
}

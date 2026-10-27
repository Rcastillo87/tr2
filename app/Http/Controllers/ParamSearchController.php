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

    /** Página de la búsqueda: progreso en vivo, resultados y búsquedas anteriores de la estrategia. */
    public function show(ParamSearchRun $run)
    {
        $this->service->reapStale();
        $run->load('strategy');
        $history = ParamSearchRun::where('strategy_id', $run->strategy_id)->orderByDesc('id')
            ->limit(ParamSearchService::KEEP_PER_STRATEGY)
            ->select(['id', 'status', 'intervals', 'created_at', 'strategy_code_md5'])
            ->selectRaw("results->>'tested' AS tested, coalesce(results->>'robust', results->>'survivors') AS robust, coalesce(results->>'survivors', results->>'validated') AS validated")
            ->get();

        return view('param-search.show', [
            'run'     => $run,
            'history' => $history,
            'keep'    => ParamSearchService::KEEP_PER_STRATEGY,
            'labels'  => ['15' => '15m', '60' => '1h', '120' => '2h', '240' => '4h', 'D' => '1D'],
            'codeMd5' => $run->strategy?->code !== null ? md5($run->strategy->code) : null,
        ]);
    }

    /** Datos para la ventana: monedas con datos por temporalidad, búsqueda activa y estimación de tiempo. */
    public function options(Strategy $strategy): JsonResponse
    {
        $this->service->reapStale();
        $byInterval = [];
        foreach (ParamSearchService::INTERVALS as $iv) {
            $byInterval[$iv] = $this->service->availableSymbols([$iv]);
        }
        $active = ParamSearchRun::with('strategy:id,name')->where('strategy_id', $strategy->id)
            ->whereIn('status', ParamSearchRun::ACTIVE)->first();
        $queued = ParamSearchRun::whereIn('status', ParamSearchRun::ACTIVE)->count();

        return response()->json([
            'strategy'          => ['id' => $strategy->id, 'name' => $strategy->name],
            'intervals'         => ParamSearchService::INTERVALS,
            'symbols'           => $byInterval,
            'minutes'           => ParamSearchService::MINUTES_PER_INTERVAL,
            // min_symbols/max_symbols: compatibilidad con la ventana actual (hasta las pantallas del paso 4)
            'limits'            => ['min_symbols' => 1, 'max_symbols' => max(1, ...array_values(array_map('count', $byInterval))),
                                    'max_symbols_symbol_mode' => ParamSearchService::MAX_SYMBOLS_SYMBOL_MODE,
                                    'months' => ParamSearchService::MONTHS, 'samples' => ParamSearchService::SAMPLES,
                                    'min_trades' => 30],
            'queued'            => $queued,
            'fixed'             => ['commission_pct' => 0.055, 'slippage_pct' => 0.05, 'risk_pct' => 1.0],
            'active'            => $active ? $this->state($active) : null,
        ]);
    }

    public function start(Request $request, Strategy $strategy): JsonResponse
    {
        $data = $this->validateStart($request);
        try {
            $run = $this->service->start($strategy, $data['mode'], $data['intervals'] ?? [], $data['symbols'], $request->user()?->id);
        } catch (DomainException $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }

        return response()->json(['success' => true, 'run' => $this->state($run->fresh('strategy'))]);
    }

    /** "Buscar en todas las estrategias": una búsqueda en cola por estrategia activa; corren una tras otra. */
    public function startAll(Request $request): JsonResponse
    {
        $data = $this->validateStart($request);
        $out = $this->service->startAll($data['mode'], $data['intervals'] ?? [], $data['symbols'], $request->user()?->id);

        return response()->json(['success' => $out['created'] !== [], 'created' => $out['created'], 'skipped' => $out['skipped'],
                                 'error' => $out['created'] === [] ? 'No se encoló ninguna búsqueda.' : null]);
    }

    /**
     * mode: interval (una temporalidad, 1..N monedas) | symbol (1..3 monedas, todas las temporalidades).
     * Compatibilidad: sin "mode" se deduce (1 temporalidad = interval; varias = symbol).
     */
    private function validateStart(Request $request): array
    {
        $data = $request->validate([
            'mode'        => ['sometimes', 'in:interval,symbol'],
            'intervals'   => ['sometimes', 'array', 'max:5'],
            'intervals.*' => ['string'],
            'symbols'     => ['required', 'array', 'min:1', 'max:50'],
            'symbols.*'   => ['string', 'max:30'],
        ]);
        $data['mode'] ??= count($data['intervals'] ?? []) === 1 ? 'interval' : 'symbol';

        return $data;
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

    /**
     * Resultados con las mismas métricas que el historial. symbols=survivors (por defecto: las monedas que
     * sobrevivieron) | all (todas las probadas, incluidas las descartadas).
     */
    public function results(Request $request, ParamSearchRun $run): JsonResponse
    {
        $mode = $request->query('symbols') === 'all' ? 'all' : 'survivors';
        $rows = [];
        foreach ($run->results['rows'] ?? [] as $row) {
            $rows[] = [
                'id'         => $row['id'],
                'interval'   => $row['interval'],
                'cfg'        => $row['cfg'],
                'survivors'  => $row['survivors'] ?? array_keys($row['symbols'] ?? []),
                'discarded'  => $row['discarded'] ?? [],
                'oos_ok'     => $row['oos_ok'] ?? (($row['oos']['ret'] ?? 0) > 0),
                // v2: toda fila guardada sobrevivió (compatibilidad con la pantalla actual)
                'robusta'    => $row['robusta'] ?? ! empty($row['survivors']),
                'validada'   => $row['validada'] ?? ! empty($row['survivors']),
                'creatable'  => $this->service->creatable($run, $row),
                'is'         => $row['is'],
                'oos'        => $row['oos'],
                'val'        => $row['val'] ?? null,
                'summary'    => $this->service->summarize($row, $this->service->symbolsFor($run, $row, $mode)),
                'detail'     => array_map(fn ($s) => ['role' => $s['role'] ?? 'search', 'why' => $s['why'] ?? null, 'ret' => $s['ret'] ?? null,
                                                      'pf' => $s['pf'] ?? null, 'n' => $s['n'] ?? 0, 'dd' => $s['dd'] ?? null,
                                                      'm1' => $s['m1'] ?? null], $row['symbols']),
                'created'    => $run->results['created'][$row['id']] ?? null,
            ];
        }
        // Orden pedido: retorno total ↓, luego estrellas, luego consistencia
        usort($rows, fn ($a, $b) => [$b['summary']['total_return_pct'], $b['summary']['rating'], $b['summary']['consist_pct']]
            <=> [$a['summary']['total_return_pct'], $a['summary']['rating'], $a['summary']['consist_pct']]);

        return response()->json(['run' => $this->state($run->fresh('strategy')), 'symbols_mode' => $mode,
                                 'version' => (int) ($run->results['version'] ?? 1), 'min_trades' => $run->results['min_trades'] ?? null,
                                 'months' => count($run->results['months'] ?? []), 'rows' => $rows,
                                 'near' => $run->results['near'] ?? []]);
    }

    public function create(Request $request, ParamSearchRun $run): JsonResponse
    {
        $data = $request->validate([
            'rows'    => ['required', 'array', 'min:1', 'max:5'],
            'rows.*'  => ['string', 'max:20'],
            'symbols' => ['required', 'in:survivors,all,search,winners'],
        ]);
        if (in_array($data['symbols'], ['search', 'winners'], true)) {   // valores de la ventana actual
            $data['symbols'] = 'survivors';
        }
        if ($run->status !== 'done') {
            return response()->json(['success' => false, 'error' => 'La búsqueda no ha terminado.'], 422);
        }
        if ($run->isOutdated()) {
            return response()->json(['success' => false, 'error' => 'La estrategia cambió después de esta búsqueda: vuelve a buscar.'], 422);
        }
        $rows = collect($run->results['rows'] ?? [])->keyBy('id');
        foreach ($data['rows'] as $id) {
            if (! $rows->has($id) || ! $this->service->creatable($run, $rows[$id])) {
                return response()->json(['success' => false, 'error' => "La configuración {$id} no se puede crear."], 422);
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
            'candidates'     => $r['candidates'] ?? $r['survivors'] ?? null,
            'robust'         => $r['robust'] ?? $r['survivors'] ?? null,
            'validated'      => $r['validated'] ?? $r['survivors'] ?? null,
            'survivors'      => $r['survivors'] ?? null,
            'oos_ok'         => $r['oos_ok'] ?? null,
            'elapsed_s'      => $r['elapsed_s'] ?? null,
            'outdated'       => $run->isOutdated(),
            'error'          => $run->error,
        ];
    }
}

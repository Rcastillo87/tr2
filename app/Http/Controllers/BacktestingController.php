<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\CollectorConfig;
use App\Models\PaperStrategyConfig;
use App\Models\Backtest;
use App\Services\StrategyConfigSync;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Gate;

class BacktestingController extends Controller
{
    /** Historial mínimo para que un backtest pueda operar en Paper/Real. */
    private const MIN_LIVE_MONTHS = 24;

    private function getStrategies()
    {
        return \App\Models\Strategy::where('active', true)->orderBy('name')->get();
    }

    /**
     * Vista 1: Lista de estrategias activas en Paper Trading.
     * Punto de entrada al módulo de Backtesting.
     */


    public function index()
    {
        // Redirigir al Hub unificado de Estrategias
        return redirect()->route('strategies.index');
    }

    public function executeAjax(Request $request)
    {
        \Illuminate\Support\Facades\Log::info('EXECUTE AJAX backtest_id: ' . $request->input('backtest_id'));
        Gate::authorize('viewAnalysisTools');

        $strategyId = $request->input('strategy_id');
        $strategy = \App\Models\Strategy::find($strategyId);
        $selectedSymbols = $request->input('symbols', []);

        if (!$strategy) {
            return response()->json(['success' => false, 'error' => 'Estrategia no encontrada.']);
        }
        if (empty($selectedSymbols)) {
            return response()->json(['success' => false, 'error' => 'Debes seleccionar al menos un símbolo.']);
        }

        $months = (int) $request->input('months', 6);
        $end = now()->subMonthNoOverflow()->endOfMonth();
        $start = $end->copy()->subMonths($months - 1)->startOfMonth();

        $overrideConfig = $request->input('strategy_config_override');
        $finalConfig = $strategy->config;
        if (!empty($overrideConfig)) {
            $decoded = json_decode($overrideConfig, true);
            if (json_last_error() === JSON_ERROR_NONE) $finalConfig = $decoded;
        }

        $resultsData = [];
        $warnings = [];
        $totalTrades = 0;
        $totalWins = 0;
        $totalPnl = 0;

        // 1. RESTAURAMOS LA CREACIÓN DEL PAYLOAD POR CADA MONEDA
        $payloads = [];
        foreach ($selectedSymbols as $sym) {
            $payloads[$sym] = [
                'strategy' => $strategy->name,
                'strategy_code' => $strategy->code,
                'strategy_config' => $finalConfig,
                'symbol' => $sym,
                'interval' => $request->input('interval', '60'),
                'initial_balance' => (float) $request->input('initial_balance', 10000), // FIX: Ya no está quemado
                'risk_per_trade_pct' => (float) $request->input('risk_per_trade_pct', 1.0),
                'commission_pct' => (float) $request->input('commission_pct', 0.055),
                'sl_pct' => (float) $request->input('sl_pct', 1.5),
                'tp_pct' => (float) $request->input('tp_pct', 3.0),
                'be_pct' => (float) $request->input('be_pct', 2.0),
                'max_duration' => (int) $request->input('max_duration', 24),
                'max_duration_profit' => $request->has('max_duration_profit'),
                'close_on_opposite' => $request->has('close_on_opposite'),
                'regime_filter' => $request->has('regime_filter'),
                'regime_adx_trending' => (float) $request->input('regime_adx_trending', 25),
                'regime_adx_ranging' => (float) $request->input('regime_adx_ranging', 20),
                'regime_ambiguous_as' => match(strtolower($request->input('regime_ambiguous_as', 'lateral'))) {
                    'tendencia', 'trending' => 'TRENDING',
                    'ignorar' => 'NO_OPERAR',
                    default => 'RANGING',
                },
                'walk_forward' => true, 'n_windows' => 5, 'monthly_breakdown' => true,
                
                // FIX: Parámetros de Trailing completos
                'trailing_mode' => $request->input('trailing_mode', 'none') !== 'none' ? $request->input('trailing_mode') : null,
                'trailing_distance_pct' => (float) $request->input('trailing_distance_pct', 1.0),
                'trailing_activation_buffer_pct' => (float) $request->input('trailing_activation_buffer_pct', 0.0),
                'trailing_atr_mult' => (float) $request->input('trailing_atr_mult', 2.0),
                
                // FIX: Filtros
                'macro_trend_filter' => $request->has('macro_trend_filter'),
                'volume_filter' => $request->has('volume_filter'),
                'volume_filter_period' => (int) $request->input('volume_filter_period', 20),
                'volume_filter_mult' => (float) $request->input('volume_filter_mult', 1.2),
                
                // FIX: Protección por volatilidad (Faltaban)
                'volatility_protection_mode' => $request->input('volatility_protection_mode', 'none') !== 'none' ? $request->input('volatility_protection_mode') : null,
                'volatility_atr_multiplier' => (float) $request->input('volatility_atr_multiplier', 2.5),
                'volatility_widen_pct' => (float) $request->input('volatility_widen_pct', 1.0),
                
                'start_date' => $start->format('Y-m-d'), 'end_date' => $end->format('Y-m-d'),
            ];
            // Los valores de la UI SIEMPRE sobrescriben el JSON
            $payloads[$sym]['macro_trend_filter'] = $request->has('macro_trend_filter');
            $payloads[$sym]['volume_filter'] = $request->has('volume_filter');
            if ($request->has('volume_filter')) {
                $payloads[$sym]['volume_filter_period'] = (int) $request->input('volume_filter_period', 20);
                $payloads[$sym]['volume_filter_mult'] = (float) $request->input('volume_filter_mult', 1.2);
            }
            $payloads[$sym]['regime_filter'] = $request->has('regime_filter');
        }

        // 2. EJECUCIÓN SECUENCIAL (UNA A UNA) PARA EVITAR RACE CONDITIONS
        \Illuminate\Support\Facades\Log::info('PAYLOAD FINAL ENVIADO A PYTHON:', $payloads[array_key_first($payloads)] ?? []);

        $responses = [];
        foreach ($payloads as $sym => $payload) {
            $responses[$sym] = \Illuminate\Support\Facades\Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(120)->post(config('trading.python_engine_url') . '/v1/backtest/run', $payload);
        }

        // 3. PROCESAMIENTO DE RESULTADOS
        foreach ($selectedSymbols as $sym) {
            try {
                $response = $responses[$sym] ?? null;
                if (!$response) {
                    return response()->json(['success' => false, 'error' => "No se recibió respuesta para $sym."]);
                }
                if (!$response->successful()) {
                    return response()->json(['success' => false, 'error' => "Error en $sym: " . $response->body()]);
                }

                $res = $response->json('result');
                $warnings = array_merge($warnings ?? [], $response->json('warnings') ?? []);
                $summary = [
                    'symbol' => $sym,
                    'aggregate_metrics' => $res['aggregate_metrics'] ?? [],
                    'monthly_breakdown' => $res['monthly_breakdown'] ?? [],
                    'passed' => $res['passed'] ?? false,
                ];
                $resultsData[] = $summary;

                $agg = $summary['aggregate_metrics'];
                $totalTrades += $agg['total_trades'] ?? 0;
                $totalWins += $agg['winning_trades'] ?? 0;
                $totalPnl += $agg['total_return_pct'] ?? 0;
            } catch (\Throwable $e) {
                return response()->json(['success' => false, 'error' => "Error procesando $sym: " . $e->getMessage()]);
            }
        }

        if ($totalTrades === 0) {
            $warnings[] = 'Resultado: 0 operaciones generadas. Posible causa: Filtros muy estrictos o falta de señales en el período.';
        } elseif ($totalPnl < -50) {
            $warnings[] = 'ALERTA: Retorno catastrófico (' . round($totalPnl, 2) . '%). La estrategia está sobre-operando (Overtrading) y las comisiones se están comiendo la cuenta. Prueba en una temporalidad mayor (H1 o H4).';
        }

        if (empty($resultsData)) {
            return response()->json(['success' => false, 'error' => 'No se obtuvieron resultados.']);
        }

        $winRate = $totalTrades > 0 ? round($totalWins / $totalTrades * 100, 2) : 0;

        // Calcular promedio mensual y consistencia global (igual que en results.blade.php)
        $monthlyTotals = [];
        foreach ($resultsData as $ind) {
            $monthly = $ind['monthly_breakdown'] ?? [];
            foreach ($monthly as $m) {
                $monthKey = $m['month'];
                if (!isset($monthlyTotals[$monthKey])) $monthlyTotals[$monthKey] = 0;
                $monthlyTotals[$monthKey] += (float)($m['total_pnl_pct'] ?? 0);
            }
        }
        $avgGlobal = count($monthlyTotals) > 0 ? array_sum($monthlyTotals) / count($monthlyTotals) : 0;
        $positiveGlobal = count(array_filter($monthlyTotals, fn($v) => $v > 0));
        $consistGlobal = count($monthlyTotals) > 0 ? round($positiveGlobal / count($monthlyTotals) * 100, 1) : 0;

        $totalPnl = array_sum($monthlyTotals); // Fix: El retorno consolidado es la suma de los meses

        $result = [
            'strategy' => $strategy->name,
            'interval' => $request->input('interval', '60'),
            'symbols_list' => $selectedSymbols,
            'aggregate_metrics' => [
                'total_trades' => $totalTrades,
                'winning_trades' => $totalWins,
                'win_rate' => $winRate,
                'total_return_pct' => round($totalPnl, 2),
                'sharpe_ratio' => count($resultsData) > 0 ? round(collect($resultsData)->avg('aggregate_metrics.sharpe_ratio'), 2) : 0,
                'profit_factor' => count($resultsData) > 0 ? round(collect($resultsData)->avg('aggregate_metrics.profit_factor'), 2) : 0,
            ],
            'individual_results' => $resultsData,
            'save_payload' => [
                'backtest_id' => request('backtest_id'),
                'hash' => md5($strategyId . '_' . implode(',', $selectedSymbols) . '_' . $request->input('interval', '60') . '_' . $months . '_' . $request->input('sl_pct', 1.5) . '_' . $request->input('tp_pct', 3.0)),
                'strategy_id' => $strategyId,
                'symbols' => $selectedSymbols,
                'interval' => $request->input('interval', '60'),
                'months' => $months,
                'config_params' => array_values($payloads)[0] ?? [],
                'strategy_snapshot' => ['code' => $strategy->code, 'config' => $finalConfig],
                'metrics' => [
                    'total_trades' => $totalTrades,
                    'win_rate' => $winRate,
                    'sharpe_ratio' => count($resultsData) > 0 ? round(collect($resultsData)->avg('aggregate_metrics.sharpe_ratio'), 2) : 0,
                    'profit_factor' => count($resultsData) > 0 ? round(collect($resultsData)->avg('aggregate_metrics.profit_factor'), 2) : 0,
                    'avg_monthly_pnl' => round($avgGlobal, 2),
                    'consist_pct' => $consistGlobal,
                ]
            ]
        ];

        // Firma de integridad: lo que vuelva en "Guardar" debe ser exactamente lo ejecutado.
        $result['save_payload']['signed_total_trades'] = $totalTrades;
        $result['save_payload']['signature'] = StrategyConfigSync::sign(
            self::saveSignatureFields($result['save_payload'], $totalTrades)
        );

        // Renderizar la vista parcial y devolverla como HTML
        $prevBacktest = $request->input('backtest_id') ? \App\Models\Backtest::find($request->input('backtest_id')) : null;
        
                
        
        $html = view('backtesting.partials.results', [
            'result' => $result,
            'implementParams' => array_values($payloads)[0] ?? [],
            'prevBacktest' => $prevBacktest,
            'warnings' => $warnings
        ])->render();

        return response()->json(['success' => true, 'html' => $html, 'warnings' => $warnings ?? []]);
    }

    public function run(Request $request)
    {
        Gate::authorize('viewAnalysisTools');

        $result          = null;
        $implementParams = null;
        $error           = null;
        $old_session     = null;

        $strategies = $this->getStrategies();
        $symbols   = array_values((array) CollectorConfig::activeSymbols());
        $intervals = CollectorConfig::activeIntervals();
        $symbolBrokerMap = CollectorConfig::query()->select('symbol', 'broker')->distinct()->pluck('broker', 'symbol');
        $paperConfigsForPreload = PaperStrategyConfig::active()->get(['display_name', 'strategy_class', 'symbol', 'interval', 'params'])->map(function ($c) {
            $params = is_array($c->params) ? $c->params : json_decode($c->params, true);
            return ['display_name' => $c->display_name, 'strategy_class' => $c->strategy_class, 'symbol' => $c->symbol, 'interval' => $c->interval, 'params' => $params];
        })->values();

        $backtestToLoad = null;
        $strategyToLoad = null;
        
        // Si viene backtest_id, cargar el backtest Y su estrategia
        if ($request->has('backtest_id')) {
            $backtestToLoad = \App\Models\Backtest::find($request->input('backtest_id'));
            if ($backtestToLoad) {
                $strategyToLoad = $backtestToLoad->strategy;
            }
        }
        // Si no, pero viene strategy_id, cargar solo la estrategia
        elseif ($request->has('strategy_id')) {
            $strategyToLoad = \App\Models\Strategy::find($request->input('strategy_id'));
        }

        // Inicializar los símbolos seleccionados por defecto (si venimos de editar, cargar los del backtest)
        $selectedSymbols = $backtestToLoad->symbols ?? ['BTCUSDT'];



        \Illuminate\Support\Facades\Log::info('[BACKTEST] Preparando vista. Filas de resultados: ' . count($resultsData ?? []));
        
        return view('backtesting.run', [
            'strategies' => $strategies,
            'symbols' => $symbols,
            'intervals' => $intervals,
            'symbolBrokerMap' => $symbolBrokerMap,
            'paperConfigsForPreload' => $paperConfigsForPreload,
            'result' => $result,
            'implementParams' => $implementParams,
            'error' => $error,
            'backtestToLoad' => $backtestToLoad,
            'selectedSymbols' => $selectedSymbols ?? [],
            'strategyToLoad' => $strategyToLoad,
        ]);
    }

    /**
     * Endpoint AJAX: devuelve los parametros exactos de una config activa de
     * Paper Trading, para precargar el formulario de Backtesting al re-testear.
     */





    public function approve(\App\Models\Backtest $backtest)
    {
        Gate::authorize('viewAnalysisTools');
        
        // Desmarcar cualquier otro backtest aprobado para esta estrategia
        \App\Models\Backtest::where('strategy_id', $backtest->strategy_id)
            ->where('id', '!=', $backtest->id)
            ->update(['approved' => false]);
            
        $backtest->approved = true;
        $backtest->save();
        
        return redirect()->route('backtesting.history', $backtest->strategy_id)->with('status', 'Backtest aprobado para Paper Trading.');
    }


    public function implementPaper(Backtest $backtest, StrategyConfigSync $sync)
    {
        Gate::authorize('viewAnalysisTools');

        $blocked = $this->liveBlockReason($backtest, (int) ($backtest->metrics['total_trades'] ?? 0));
        if ($blocked !== null) {
            return back()->withErrors(['error' => "No se puede implementar el backtest #{$backtest->id}: {$blocked}."]);
        }

        try {
            $summary = $sync->syncFromBacktest($backtest, StrategyConfigSync::SOURCE_IMPLEMENT, true, auth()->id());
        } catch (\Throwable $e) {
            Log::error("[IMPLEMENT] Backtest #{$backtest->id}: {$e->getMessage()}");

            return back()->withErrors(['error' => 'No se pudo implementar: ' . $e->getMessage()]);
        }

        $total = count($summary['created']) + count($summary['updated']) + count($summary['unchanged']);

        return redirect()->route('strategies.index')
            ->with('status', "Backtest #{$backtest->id} implementado: {$total} moneda(s) activas en Paper.");
    }


    public function history(\App\Models\Strategy $strategy)
    {
        Gate::authorize('viewAnalysisTools');
        $backtests = $strategy->backtests()->orderBy('created_at', 'desc')->get();

        // Buscar TODOS los backtests de esta estrategia operando en paper
        $activeBacktestIds = \App\Models\PaperStrategyConfig::whereIn('backtest_id', $backtests->pluck('id'))
            ->where('active', true)
            ->pluck('backtest_id')
            ->unique()
            ->toArray();

        return view('backtesting.history', compact('strategy', 'backtests', 'activeBacktestIds'));
    }


    public function destroyBacktest(\App\Models\Backtest $backtest)
    {
        Gate::authorize('viewAnalysisTools');

        // Verificar si está en uso ACTIVO en Paper Trading
        $inUse = \App\Models\PaperStrategyConfig::where('backtest_id', $backtest->id)
            ->where('active', true)
            ->exists();
        
        if ($inUse) {
            return back()->withErrors(['error' => 'No puedes eliminar este backtest porque está OPERANDO en Paper Trading. Detenlo primero.']);
        }
        
        // Si está inactivo, borramos también su configuración de Paper huérfana
        \App\Models\PaperStrategyConfig::where('backtest_id', $backtest->id)->delete();

        $backtest->delete();
        return back()->with('status', 'Backtest eliminado del historial.');
    }


    public function saveBacktest(Request $request, StrategyConfigSync $sync)
    {
        Gate::authorize('viewAnalysisTools');

        $data = self::decodeSavePayload($request->input('save_data'));
        if ($data === null) {
            return $this->saveResponse($request, false, 'Los datos del backtest están vacíos o corruptos.');
        }

        $signed = self::saveSignatureFields($data, (int) ($data['signed_total_trades'] ?? -1));
        if (! StrategyConfigSync::verify($signed, $data['signature'] ?? null)) {
            Log::warning('[BACKTEST-SAVE] Firma inválida (payload alterado o anterior al despliegue).', ['user' => auth()->id()]);

            return $this->saveResponse($request, false, 'El resultado no coincide con lo ejecutado en el servidor. Vuelve a correr el backtest y guarda de nuevo.');
        }

        $strategyId = $signed['strategy_id'];
        $hash = StrategyConfigSync::backtestHash(
            $strategyId, $signed['symbols'], $signed['interval'], $signed['months'], $signed['config_params']
        );

        try {
            // Guardado y auto-sync en la MISMA transacción: o queda todo, o no queda nada.
            $outcome = DB::transaction(function () use ($data, $signed, $strategyId, $hash, $sync) {
                $backtest = null;
                if (! empty($data['backtest_id'])) {
                    $backtest = Backtest::whereKey((int) $data['backtest_id'])->lockForUpdate()->first();
                    // Un re-test solo sobrescribe backtests de la MISMA estrategia.
                    if ($backtest !== null && (int) $backtest->strategy_id !== $strategyId) {
                        $backtest = null;
                    }
                }

                $duplicate = Backtest::where('hash', $hash)
                    ->when($backtest, fn ($q) => $q->whereKeyNot($backtest->id))
                    ->first(['id']);
                if ($duplicate !== null) {
                    return ['duplicate_id' => $duplicate->id];
                }

                $metrics = (array) ($data['metrics'] ?? []);
                $metrics['total_trades'] = $signed['total_trades']; // dato firmado, no el del navegador

                $backtest ??= new Backtest();
                $backtest->fill([
                    'hash'              => $hash,
                    'strategy_id'       => $strategyId,
                    'symbols'           => $signed['symbols'],
                    'interval'          => $signed['interval'],
                    'months'            => $signed['months'],
                    'config_params'     => $signed['config_params'],
                    'strategy_snapshot' => (array) ($data['strategy_snapshot'] ?? []),
                    'metrics'           => $metrics,
                    'approved'          => false,
                ]);
                $backtest->save();

                // Auto-sync: solo backtests ya implementados (tienen configs en Paper).
                $syncResult = null;
                $blocked = null;
                if (PaperStrategyConfig::where('backtest_id', $backtest->id)->exists()) {
                    $blocked = $this->liveBlockReason($backtest, $signed['total_trades']);
                    if ($blocked === null) {
                        $syncResult = $sync->syncFromBacktest(
                            $backtest, StrategyConfigSync::SOURCE_BACKTEST_SAVE, null, auth()->id()
                        );
                    } else {
                        Log::warning("[CONFIG-SYNC] Backtest #{$backtest->id} guardado SIN sincronizar: {$blocked}");
                    }
                }

                return ['backtest' => $backtest, 'sync' => $syncResult, 'blocked' => $blocked];
            });
        } catch (\Throwable $e) {
            Log::error('[BACKTEST-SAVE] ' . $e->getMessage());

            return $this->saveResponse($request, false, 'Error guardando el backtest: ' . $e->getMessage());
        }

        if (isset($outcome['duplicate_id'])) {
            return $this->saveResponse($request, false, "Ya existe el backtest #{$outcome['duplicate_id']} con exactamente esta configuración.");
        }

        $backtest = $outcome['backtest'];
        $message  = 'Backtest guardado correctamente.';
        if ($outcome['blocked'] !== null) {
            $message .= " NO se sincronizó con Paper/Real: {$outcome['blocked']}.";
        } elseif ($outcome['sync'] !== null) {
            $s = $outcome['sync'];
            $message .= sprintf(
                ' Paper/Real sincronizados: %d actualizada(s), %d sin cambios, %d nueva(s), %d desactivada(s).',
                count($s['updated']), count($s['unchanged']), count($s['created']), count($s['deactivated'])
            );
        }

        return $this->saveResponse($request, true, $message, [
            'backtest_id' => $backtest->id,
            'sync'        => $outcome['sync'],
            'sync_blocked'=> $outcome['blocked'],
        ]);
    }


    public function stopPaper(Backtest $backtest, StrategyConfigSync $sync)
    {
        Gate::authorize('viewAnalysisTools');

        $count = $sync->deactivateBacktest($backtest, auth()->id());

        return back()->with('status', "Estrategia detenida: {$count} configuración(es) desactivadas (sin nuevas entradas en Paper ni Real).");
    }

    /** Motivo por el que un backtest NO puede operar en vivo, o null si es apto. */
    private function liveBlockReason(Backtest $backtest, int $totalTrades): ?string
    {
        if ($totalTrades <= 0) {
            return 'el backtest no generó operaciones';
        }
        if ((int) $backtest->months < self::MIN_LIVE_MONTHS) {
            return "historial de {$backtest->months} meses (mínimo " . self::MIN_LIVE_MONTHS . ')';
        }

        return null;
    }

    /** Campos cubiertos por la firma HMAC del guardado (tipos normalizados). */
    private static function saveSignatureFields(array $payload, int $totalTrades): array
    {
        return [
            'strategy_id'   => (int) ($payload['strategy_id'] ?? 0),
            'symbols'       => array_values(array_map('strval', (array) ($payload['symbols'] ?? []))),
            'interval'      => (string) ($payload['interval'] ?? ''),
            'months'        => (int) ($payload['months'] ?? 0),
            'config_params' => (array) ($payload['config_params'] ?? []),
            'total_trades'  => $totalTrades,
        ];
    }

    private static function decodeSavePayload(mixed $raw): ?array
    {
        if (! is_string($raw) || $raw === '') {
            return null;
        }
        $decoded = base64_decode($raw, true);
        $data = json_decode($decoded === false ? $raw : $decoded, true);

        return is_array($data) ? $data : null;
    }

    private function saveResponse(Request $request, bool $ok, string $message, array $extra = [])
    {
        if ($request->ajax() || $request->wantsJson()) {
            return response()->json(['success' => $ok, 'message' => $message] + $extra, $ok ? 200 : 422);
        }

        return $ok
            ? redirect()->route('backtesting.run', ['backtest_id' => $extra['backtest_id'] ?? null])->with('status', $message)
            : back()->withErrors(['error' => $message]);
    }

    public function retest(PaperStrategyConfig $config)
    {
        Gate::authorize('viewAnalysisTools');

        $strategyName = PaperStrategyConfig::classAndModeToStrategyName(
            $config->strategy_class,
            $config->params['mode'] ?? null
        );

        return response()->json([
            'strategy_name' => $strategyName,
            'symbol'        => $config->symbol,
            'interval'      => $config->interval,
            'audited_months'  => $config->audited_months,
            'avg_win_rate'    => $config->avg_win_rate,
            'avg_monthly_pnl' => $config->avg_monthly_pnl,
            'params'        => $config->params,
        ]);
    }

    /**
     * Endpoint AJAX: devuelve el rango de fechas disponible para un simbolo/intervalo,
     * usado para calibrar el selector de meses en el formulario.
     */
    public function dataRange(string $symbol, string $interval)
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(
                config('trading.python_engine_url') . "/v1/backtest/data-range/{$symbol}/{$interval}"
            );

            if ($response->successful()) {
                return response()->json($response->json('data'));
            }
        } catch (\Throwable $e) {
            Log::warning('Backtesting: error obteniendo rango de fechas — ' . $e->getMessage());
        }

        return response()->json(null);
    }

    /**
     * Exporta el ultimo resultado de backtest (desglose mensual) a Excel.
     * Recibe el resultado completo como JSON en el request (enviado por el formulario
     * tras correr el backtest, para no tener que re-ejecutar el backtest).
     */
    public function exportExcel(Request $request)
    {
        $request->validate([
            'result' => ['required', 'string'],
        ]);

        $result = json_decode($request->input('result'), true);

        if (!$result || empty($result['monthly_breakdown'])) {
            return back()->withErrors(['result' => 'No hay datos de desglose mensual para exportar.']);
        }

        $strategy = $result['strategy'] ?? 'backtest';
        $symbol   = $result['symbol'] ?? '';
        $filename = 'backtest_' . str_replace(' ', '_', $strategy) . '_' . $symbol . '_' . now()->format('Ymd_His') . '.xlsx';

        return \App\Exports\BacktestMonthlyExport::download($result, $filename);
    }
}

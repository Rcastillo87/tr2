<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\CollectorConfig;
use App\Models\PaperStrategyConfig;
use Illuminate\Support\Facades\Gate;

class BacktestingController extends Controller
{
    private function getStrategies()
    {
        return \App\Models\Strategy::where('active', true)->orderBy('name')->get();
    }

    /**
     * Vista 1: Lista de estrategias activas en Paper Trading.
     * Punto de entrada al módulo de Backtesting.
     */
    private function calcularEstrellas(float $wr, float $sharpe, float $retMes, float $consistencia, float $pf): array
    {
        $starWr = match(true) {
            $wr >= 65  => 5, $wr >= 55 => 4, $wr >= 45 => 3, $wr >= 35 => 2, default => 1,
        };
        $starSharpe = match(true) {
            $sharpe >= 4 => 5, $sharpe >= 3 => 4, $sharpe >= 2 => 3, $sharpe >= 1 => 2, default => 1,
        };
        $starRet = match(true) {
            $retMes >= 20 => 5, $retMes >= 10 => 4, $retMes >= 5 => 3, $retMes >= 2 => 2, default => 1,
        };
        $starConsistency = match(true) {
            $consistencia >= 95 => 5, $consistencia >= 85 => 4, $consistencia >= 65 => 3, $consistencia >= 40 => 2, default => 1,
        };
        $starPf = match(true) {
            $pf >= 2.5 => 5, $pf >= 2.0 => 4, $pf >= 1.5 => 3, $pf >= 1.0 => 2, default => 1,
        };
        // Entero, redondeado SIEMPRE hacia arriba al próximo valor de estrella
        // Entero, redondeado al más cercano (4.1 -> 4, 4.5 -> 5)
        $starRating = round(($starWr + $starSharpe + $starRet + $starConsistency + $starPf) / 5, 1);
        return compact('starWr','starSharpe','starRet','starConsistency','starPf','starRating');
    }

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
                'initial_balance' => 10000,
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
                'trailing_mode' => $request->input('trailing_mode', 'none') !== 'none' ? $request->input('trailing_mode') : null,
                'trailing_distance_pct' => (float) $request->input('trailing_distance_pct', 1.0),
                'trailing_atr_mult' => (float) $request->input('trailing_atr_mult', 2.0),
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
            $payloads[$sym]['use_max_duration'] = $request->has('use_max_duration');
            $payloads[$sym]['use_trailing'] = $request->has('use_trailing');
        }

        // 2. EJECUCIÓN SECUENCIAL (UNA A UNA) PARA EVITAR RACE CONDITIONS
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

        // Renderizar la vista parcial y devolverla como HTML
        $prevBacktest = $request->input('backtest_id') ? \App\Models\Backtest::find($request->input('backtest_id')) : null;
        
                
        $prevBacktest = $request->input('backtest_id') ? \App\Models\Backtest::find($request->input('backtest_id')) : null;
        
        $html = view('backtesting.partials.results', [
            'result' => $result,
            'implementParams' => array_values($payloads)[0] ?? [],
             // <-- FORZAMOS EL PASE DEL ID
            'prevBacktest' => $prevBacktest
        ])->render();

        return response()->json(['success' => true, 'html' => $html]);
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

        if ($request->isMethod('post')) {
            \Illuminate\Support\Facades\Log::info('[BACKTEST] POST iniciado');
            $selectedSymbols = $request->input('symbols', []);
            $strategyId = $request->input('strategy_id');
            $strategy = \App\Models\Strategy::find($strategyId);
            $selectedSymbols = $request->input('symbols', []);

            if (!$strategy) {
                $error = "Estrategia no encontrada.";
            } elseif (empty($selectedSymbols)) {
                $error = "Debes seleccionar al menos un símbolo.";
            } else {
                $months = (int) $request->input('months', 6);
                $end = now()->subMonthNoOverflow()->endOfMonth();
                $start = $end->copy()->subMonths($months - 1)->startOfMonth();

                // Configuración Base
                $overrideConfig = $request->input('strategy_config_override');
                $finalConfig = $strategy->config;
                if (!empty($overrideConfig)) {
                    $decoded = json_decode($overrideConfig, true);
                    if (json_last_error() === JSON_ERROR_NONE) $finalConfig = $decoded;
                }

                $resultsData = [];
                $totalTrades = 0;
                $totalWins = 0;
                $totalPnl = 0;

                \Illuminate\Support\Facades\Log::info('[BACKTEST] Símbolos seleccionados: ' . implode(', ', $selectedSymbols));
                
                // Bucle por cada símbolo seleccionado
                foreach ($selectedSymbols as $sym) {
                    \Illuminate\Support\Facades\Log::info("[BACKTEST] Procesando símbolo: $sym");
                    $payload = [
                        'strategy' => $strategy->name,
                        'strategy_code' => $strategy->code,
                        'strategy_config' => $finalConfig,
                        'symbol' => $sym,
                        'interval' => $request->input('interval', '60'),
                        'initial_balance' => 10000,
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
                        'trailing_mode' => $request->input('trailing_mode', 'none') !== 'none' ? $request->input('trailing_mode') : null,
                        'trailing_distance_pct' => (float) $request->input('trailing_distance_pct', 1.0),
                        'trailing_atr_mult' => (float) $request->input('trailing_atr_mult', 2.0),
                        'start_date' => $start->format('Y-m-d'), 'end_date' => $end->format('Y-m-d'),
                    ];
                    
                    if ($request->has('macro_trend_filter')) $payload['macro_trend_filter'] = true;
                    if ($request->has('volume_filter')) {
                        $payload['volume_filter'] = true;
                        $payload['volume_filter_period'] = (int) $request->input('volume_filter_period', 20);
                        $payload['volume_filter_mult'] = (float) $request->input('volume_filter_mult', 1.2);
                    }
                    if ($request->has('volatility_protection_mode') && $request->input('volatility_protection_mode') !== 'none') {
                        $payload['volatility_protection_mode'] = $request->input('volatility_protection_mode');
                        $payload['volatility_atr_multiplier'] = (float) $request->input('volatility_atr_multiplier', 2.5);
                    }

                    try {
                        $response = Http::withHeaders(['X-Internal-API-Key' => config('trading.python_internal_api_key')])
                            ->timeout(90)->post(config('trading.python_engine_url') . '/v1/backtest/run', $payload);
                            
                        \Illuminate\Support\Facades\Log::info("[BACKTEST] Response status para $sym: " . $response->status());
                        if ($response->successful()) {
                            \Illuminate\Support\Facades\Log::info("[BACKTEST] Procesando respuesta JSON para $sym...");
                            
                            $res = $response->json('result');
                            
                            // CRITICAL: eliminar los trades individuales (pueden ser miles de registros)
                            // Solo guardamos los agregados que la vista necesita
                            $summary = [
                                'symbol' => $sym,
                                'aggregate_metrics' => $res['aggregate_metrics'] ?? [],
                                'monthly_breakdown' => $res['monthly_breakdown'] ?? [],
                                'passed' => $res['passed'] ?? false,
                                'stars' => $res['stars'] ?? [],
                                'consist_pct' => $res['consist_pct'] ?? 0,
                                'range_from' => $res['range_from'] ?? null,
                                'range_to' => $res['range_to'] ?? null,
                            ];
                            
                            $resultsData[] = $summary;
                            unset($res); // liberar memoria
                            
                            \Illuminate\Support\Facades\Log::info("[BACKTEST] Resumen de $sym añadido correctamente");
                            
                            $agg = $summary['aggregate_metrics'];
                            $totalTrades += $agg['total_trades'] ?? 0;
                            $totalWins += $agg['winning_trades'] ?? 0;
                            $totalPnl += $agg['total_return_pct'] ?? 0;
                        } else {
                            $error .= "Error en $sym: " . $response->body() . "\n";
                            \Illuminate\Support\Facades\Log::error("[BACKTEST] Error de Python para $sym: " . $response->body());
                        }
                    } catch (\Throwable $e) {
                        $error .= "Error de conexión en $sym: " . $e->getMessage() . "\n";
                    }
                }

                if (!empty($resultsData)) {
                    // Consolidar resultados
                    $winRate = $totalTrades > 0 ? round($totalWins / $totalTrades * 100, 2) : 0;
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
                        'config_used' => $finalConfig,
                        'save_payload' => [
                            'hash' => md5(json_encode(['strat' => $strategyId, 'syms' => $selectedSymbols, 'cfg' => $payload])),
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
                                'avg_monthly_pnl' => round($totalPnl / max(1, count($selectedSymbols) * $months), 2),
                                'consist_pct' => $consistGlobal, // Placeholder
                            ]
                        ]
                    ];
                    $implementParams = $payload;
                }
            }
        }

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
    public function runAjax(Request $request)
    {
        Gate::authorize('viewAnalysisTools');
        // Misma logica que run() pero devuelve JSON
        $symbols   = array_values((array) CollectorConfig::activeSymbols());
        $intervals = CollectorConfig::activeIntervals();
        $payload   = $this->buildPayload($request);

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(90)->post(
                config('trading.python_engine_url') . '/v1/backtest/run',
                $payload
            );
            if ($response->successful()) {
                $result = $response->json('result');
                $implementParams = collect($payload)->except([
                    'strategy', 'symbol', 'interval', 'walk_forward', 'n_windows',
                    'train_pct', 'monthly_breakdown', 'initial_balance',
                ])->filter(fn ($v) => $v !== null)->toArray();

                // Calcular estrellas
                $agg      = $result['aggregate_metrics'] ?? [];
                $monthly  = $result['monthly_breakdown'] ?? [];
                $pnls     = collect($monthly)->pluck('total_pnl_pct')->map(fn($v) => (float)$v);
                $avgRet   = $pnls->count() > 0 ? round($pnls->average(), 2) : 0;
                $mesesPos = $pnls->filter(fn($p) => $p > 0)->count();
                $consist  = $pnls->count() > 0 ? round($mesesPos / $pnls->count() * 100, 1) : 0;
                $rangeFrom = $monthly ? $monthly[0]['month'] : null;
                $rangeTo   = $monthly ? $monthly[count($monthly)-1]['month'] : null;
                $stars = $this->calcularEstrellas(
                    (float) ($agg['win_rate'] ?? 0),
                    (float) ($agg['sharpe_ratio'] ?? 0),
                    (float) $avgRet,
                    (float) $consist,
                    (float) ($agg['profit_factor'] ?? 0)
                );
                $result['stars']       = $stars;
                $result['consist_pct'] = $consist;
                $result['range_from']  = $rangeFrom;
                $result['range_to']    = $rangeTo;

                return response()->json([
                    'success'        => true,
                    'result'         => $result,
                    'implementParams'=> $implementParams,
                ]);
            } else {
                return response()->json(['success' => false, 'error' => 'Error del motor: ' . $response->body()], 500);
            }
        } catch (\Throwable $e) {
            return response()->json(['success' => false, 'error' => 'No se pudo conectar al motor.'], 500);
        }
    }

    private function buildPayload(Request $request): array
    {
        $strategy  = $request->input('strategy', 'VWAP Tendencia');
        $symbol    = $request->input('symbol', 'BTCUSDT');
        $interval  = $request->input('interval', '60');
        $options   = self::STRATEGY_OPTIONS[$strategy] ?? self::STRATEGY_OPTIONS['VWAP Tendencia'];

        $payload = [
            'strategy'           => $options['class'],
            'symbol'             => $symbol,
            'interval'           => $interval,
            'initial_balance'    => 10000,
            'sl_pct'             => (float) $request->input('sl_pct', 1.5),
            'tp_pct'             => (float) $request->input('tp_pct', 3.0),
            'be_pct'             => (float) $request->input('be_pct', 2.0),
            'max_duration'       => (int) $request->input('max_duration', 24),
            'risk_per_trade_pct' => (float) $request->input('risk_per_trade_pct', 1.0),
'commission_pct'     => (float) $request->input('commission_pct', 0.055),
            'max_leverage'       => (float) $request->input('max_leverage', 1.0),
            'monthly_breakdown'  => true,
            'mode'               => $options['mode'] ?? null,
        ];

        // TPs opcionales
        foreach (['tp2_pct','tp3_pct','tp4_pct'] as $tp) {
            $val = $request->input($tp);
            if ($val !== null && $val !== '') $payload[$tp] = (float)$val;
        }

        // Filtros
        if ($request->has('regime_filter')) {
            $payload['regime_filter']       = true;
            $payload['regime_adx_trending'] = (float) $request->input('regime_adx_trending', 25);
            $payload['regime_adx_ranging']  = (float) $request->input('regime_adx_ranging', 20);
            $payload['regime_ambiguous_as'] = $request->input('regime_ambiguous_as', 'RANGING');
        }
        if ($request->has('macro_trend_filter')) $payload['macro_trend_filter'] = true;
        if ($request->has('volume_filter')) {
            $payload['volume_filter']        = true;
            $payload['volume_filter_period'] = (int) $request->input('volume_filter_period', 20);
            $payload['volume_filter_mult']   = (float) $request->input('volume_filter_mult', 1.2);
        }
        // Horas y dias bloqueados
        if ($request->has('blocked_hours_active')) {
            $payload['blocked_hours'] = array_map('intval', $request->input('blocked_hours', [10, 11]));
        }
        if ($request->has('blocked_days_active')) {
            $payload['blocked_days'] = array_map('intval', $request->input('blocked_days', [0]));
        }

        // Trailing
        $trailingMode = $request->input('trailing_mode');
        if ($trailingMode && $trailingMode !== 'none') {
            $payload['trailing_mode'] = $trailingMode;
            if ($trailingMode === 'fixed') {
                $payload['trailing_distance_pct'] = (float) $request->input('trailing_distance_pct', 1.0);
                $payload['trailing_activation_buffer_pct'] = (float) $request->input('trailing_activation_buffer_pct', 0.3);
            } elseif ($trailingMode === 'stepped') {
                $gains = $request->input('trailing_step_gain', []);
                $sls   = $request->input('trailing_step_sl', []);
                $steps = [];
                foreach ($gains as $i => $g) {
                    if ($g !== null && isset($sls[$i])) $steps[] = [(float)$g, (float)$sls[$i]];
                }
                if (!empty($steps)) $payload['trailing_steps'] = $steps;
            }
        }

        // Volatilidad
        $volMode = $request->input('volatility_protection_mode');
        if ($volMode && $volMode !== 'none') {
            $payload['volatility_protection_mode'] = $volMode;
            $payload['volatility_atr_multiplier']  = (float) $request->input('volatility_atr_multiplier', 2.5);
            if ($volMode === 'widen') {
                $payload['volatility_widen_pct'] = (float) $request->input('volatility_widen_pct', 1.0);
            }
        }

        return $payload;
    }


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


    public function implementPaper(\App\Models\Backtest $backtest)
    {
        Gate::authorize('viewAnalysisTools');
        


        $strategy = $backtest->strategy;
        $configParams = $backtest->config_params;
        $metrics = $backtest->metrics;
        
        // 1. Desactivar cualquier OTRA config de Paper para esta misma estrategia
        $strategyBacktestIds = $strategy->backtests->pluck('id')->toArray();
        if (count($strategyBacktestIds) > 0) {
            \App\Models\PaperStrategyConfig::whereIn('backtest_id', $strategyBacktestIds)
                ->where('backtest_id', '!=', $backtest->id)
                ->update(['active' => false]);
        }

        // 2. Crear o activar el nuevo (para CADA moneda)
        foreach ($backtest->symbols as $sym) {
            \App\Models\PaperStrategyConfig::updateOrCreate(
                [
                    'strategy_class' => 'DynamicStrategy',
                    'symbol' => $sym,
                    'interval' => $backtest->interval,
                ],
                [
                    'display_name' => $strategy->name . ' — ' . $sym . ' ' . $backtest->interval,
                    'params' => $configParams,
                    'backtest_id' => $backtest->id,
                    'active' => true,
                    'avg_win_rate' => $metrics['win_rate'] ?? null,
                    'sharpe_ratio' => $metrics['sharpe_ratio'] ?? null,
                    'profit_factor' => $metrics['profit_factor'] ?? null,
                    'total_return_pct' => $metrics['total_return_pct'] ?? null,
                ]
            );
        }

        return redirect()->route('strategies.index')->with('status', 'Backtest implementado en Paper Trading correctamente.');
    }


    public function history(\App\Models\Strategy $strategy)
    {
        Gate::authorize('viewAnalysisTools');
        $backtests = $strategy->backtests()->orderBy('created_at', 'desc')->get();
        
        // Buscar si hay un backtest de esta estrategia operando en paper
        $activeConfig = \App\Models\PaperStrategyConfig::whereIn('backtest_id', $backtests->pluck('id'))
            ->where('active', true)
            ->first();
            
        $activeBacktestId = $activeConfig ? $activeConfig->backtest_id : null;
        
        return view('backtesting.history', compact('strategy', 'backtests', 'activeBacktestId'));
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


    public function saveBacktest(Request $request)
    {
        Gate::authorize('viewAnalysisTools');
        
        $jsonStr = $request->input('save_data');
        if (!$jsonStr) {
            return back()->withErrors(['error' => 'No hay datos para guardar.']);
        }

        // Decodificar el JSON (viene en Base64 para evitar problemas de HTML)
        $decoded = base64_decode($jsonStr, true);
        if ($decoded === false) {
            $decoded = $jsonStr; // Fallback si no viene en base64
        }

        $data = json_decode($decoded, true);
        
        // DEBUG: Vamos a detener la ejecución y ver qué está llegando exactamente
         
        
        if (json_last_error() !== JSON_ERROR_NONE) {
            \Illuminate\Support\Facades\Log::error('Error JSON saveBacktest: ' . json_last_error_msg());
            return back()->withErrors(['error' => 'Los datos del backtest están corruptos.']);
        }

        try {
            $backtest = null;

            // Si viene un backtest_id (al darle a 'Probar de nuevo'), actualizamos ese registro
            if (!empty($data['backtest_id'])) {
                $backtest = \App\Models\Backtest::find($data['backtest_id']);
            }

            // Si no existe el ID, buscamos por configuración para evitar duplicados
            if (!$backtest) {
                $symbolsJson = json_encode($data['symbols']);
                $backtest = \App\Models\Backtest::where('strategy_id', $data['strategy_id'])
                    ->where('interval', $data['interval'])
                    ->where('months', $data['months'])
                    ->whereRaw("symbols::text = ?", [$symbolsJson])
                    ->first();
            }

            if (!$backtest) {
                $backtest = new \App\Models\Backtest();
                $backtest->hash = $data['hash']; // Se guarda el hash que venga del frontend
            }
            
            // Asignar los datos
            $backtest->strategy_id = $data['strategy_id'];
            $backtest->symbols = $data['symbols'];
            $backtest->interval = $data['interval'];
            $backtest->months = $data['months'];
            $backtest->config_params = $data['config_params'];
            $backtest->strategy_snapshot = $data['strategy_snapshot'];
            $backtest->metrics = $data['metrics'];
            $backtest->approved = false;
            
            // Si es un registro existente, forzamos que la fecha de actualización sea AHORA
            if ($backtest->exists) {
                $backtest->updated_at = now('America/Bogota');
            }
            
            $backtest->save();

            // Si es una petición AJAX, devolvemos JSON para que el SweetAlert no recargue la página
            if ($request->ajax() || $request->wantsJson()) {
                return response()->json([
                    'success' => true,
                    'backtest_id' => $backtest->id,
                    'message' => 'Backtest guardado correctamente.'
                ]);
            }

            // Fallback por si se envía el formulario de forma tradicional
            return redirect()->route('backtesting.run', ['strategy_id' => $data['strategy_id'], 'backtest_id' => $backtest->id])
                ->with('status', 'Backtest guardado en el historial correctamente.');
                
        } catch (\Throwable $e) {
            \Illuminate\Support\Facades\Log::error('Error guardando backtest: ' . $e->getMessage());
            return back()->withErrors(['error' => 'Error de Base de Datos: ' . $e->getMessage()]);
        }
    }


    public function stopPaper(\App\Models\Backtest $backtest)
    {
        Gate::authorize('viewAnalysisTools');
        
        // Desactivar la configuración de Paper vinculada a este backtest
        \App\Models\PaperStrategyConfig::where('backtest_id', $backtest->id)
            ->update(['active' => false]);

        return back()->with('status', 'Estrategia detenida en Paper Trading correctamente.');
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

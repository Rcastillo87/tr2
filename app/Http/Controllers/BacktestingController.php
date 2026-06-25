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
    const STRATEGY_OPTIONS = [
        'VWAP Tendencia'         => ['class' => 'VwapStrategy',          'mode' => 'trend_follow', 'label' => 'VWAP Tendencia (trend follow)'],
        'VWAP Reversión'         => ['class' => 'VwapStrategy',          'mode' => 'reversion',    'label' => 'VWAP Reversión (E-13)'],
        'Reversión a la Media'   => ['class' => 'MeanReversionStrategy', 'mode' => null,           'label' => 'Reversión a la Media'],
        'Tendencia EMA/Donchian' => ['class' => 'EmaDonchianStrategy',   'mode' => null,           'label' => 'Tendencia EMA/Donchian'],
    ];

    /**
     * Vista 1: Lista de estrategias activas en Paper Trading.
     * Punto de entrada al módulo de Backtesting.
     */
    public function index()
    {
        Gate::authorize('viewAnalysisTools');

        $paperConfigs = PaperStrategyConfig::orderBy('strategy_class')->orderBy('symbol')->get();

        return view('backtesting.index', compact('paperConfigs'));
    }

    /**
     * Vista 2: Formulario de configuración + resultados del backtest.
     * GET: muestra el formulario vacío.
     * POST: ejecuta el backtest y muestra resultados.
     */
    public function run(Request $request)
    {
        Gate::authorize('viewAnalysisTools');

        $result          = null;
        $error           = null;
        $implementParams = null;

        $symbols   = CollectorConfig::activeSymbols();
        $intervals = CollectorConfig::activeIntervals();

        $paperConfigsForPreload = PaperStrategyConfig::active()
            ->get(['display_name', 'strategy_class', 'symbol', 'interval', 'params'])
            ->map(function ($c) {
                $params = is_array($c->params) ? $c->params : json_decode($c->params, true);
                return [
                    'display_name'   => $c->display_name,
                    'strategy_class' => $c->strategy_class,
                    'symbol'         => $c->symbol,
                    'interval'       => $c->interval,
                    'params'         => $params,
                ];
            })->values();

        if ($request->isMethod('post')) {
            $strategyKey = $request->input('strategy');
            $strategyDef = self::STRATEGY_OPTIONS[$strategyKey] ?? null;

            if (!$strategyDef) {
                $error = "Estrategia no reconocida: {$strategyKey}";
            } else {
                $strategyName = match($strategyDef['class']) {
                    'VwapStrategy' => $strategyDef['mode'] === 'trend_follow'
                        ? 'VWAP Tendencia'
                        : 'VWAP Reversión',
                    'MeanReversionStrategy' => 'Reversión a la Media',
                    'EmaDonchianStrategy'   => 'Tendencia EMA/Donchian',
                    default => $strategyKey,
                };

                $payload = [
                    'strategy'           => $strategyName,
                    'symbol'             => $request->input('symbol'),
                    'interval'           => $request->input('interval', '60'),
                    'initial_balance'    => 10000,
                    'risk_per_trade_pct' => (float) $request->input('risk_per_trade_pct', 1.0),
                    'sl_pct'             => (float) $request->input('sl_pct', 1.5),
                    'tp_pct'             => (float) $request->input('tp_pct', 3.0),
                    'be_pct'             => (float) $request->input('be_pct', 2.0),
                    'max_duration'       => (int) $request->input('max_duration', 24),
                    'regime_filter'      => $request->has('regime_filter'), // fix: checkbox desmarcado = false
                    'walk_forward'       => true,
                    'n_windows'          => 5,
                    'monthly_breakdown'  => true,
                ];

                if ($strategyDef['mode']) {
                    $payload['mode'] = $strategyDef['mode'];
                }

                if ($request->has('macro_trend_filter')) {
                    $payload['macro_trend_filter'] = true;
                }

                foreach (['tp2_pct', 'tp3_pct', 'tp4_pct'] as $tpField) {
                    $value = $request->input($tpField);
                    if ($value !== null && $value !== '') {
                        $payload[$tpField] = (float) $value;
                    }
                }

                if ($request->filled('start_date')) $payload['start_date'] = $request->input('start_date');
                if ($request->filled('end_date'))   $payload['end_date']   = $request->input('end_date');

                $trailingMode = $request->input('trailing_mode');
                if ($trailingMode && $trailingMode !== 'none') {
                    $payload['trailing_mode'] = $trailingMode;
                    if ($trailingMode === 'fixed') {
                        $payload['trailing_distance_pct'] = (float) $request->input('trailing_distance_pct', 1.0);
                    }
                    if ($trailingMode === 'stepped') {
                        $steps = [];
                        $gains = $request->input('trailing_step_gain', []);
                        $sls   = $request->input('trailing_step_sl', []);
                        foreach ($gains as $idx => $gain) {
                            if ($gain !== '' && isset($sls[$idx]) && $sls[$idx] !== '') {
                                $steps[] = [(float) $gain, (float) $sls[$idx]];
                            }
                        }
                        $payload['trailing_steps'] = $steps;
                    }
                }

                $volMode = $request->input('volatility_protection_mode');
                if ($volMode && $volMode !== 'none') {
                    $payload['volatility_protection_mode'] = $volMode;
                    $payload['volatility_atr_multiplier']  = (float) $request->input('volatility_atr_multiplier', 2.5);
                    if ($volMode === 'widen') {
                        $payload['volatility_widen_pct'] = (float) $request->input('volatility_widen_pct', 1.0);
                    }
                }

                try {
                    $response = Http::withHeaders([
                        'X-Internal-API-Key' => config('trading.python_internal_api_key'),
                    ])->timeout(180)->post(
                        config('trading.python_engine_url') . '/v1/backtest/run',
                        $payload
                    );

                    if ($response->successful()) {
                        $result = $response->json('result');
                        $implementParams = collect($payload)->except([
                            'strategy', 'symbol', 'interval', 'walk_forward', 'n_windows',
                            'train_pct', 'monthly_breakdown', 'initial_balance',
                        ])->filter(fn ($v) => $v !== null)->toArray();
                    } else {
                        $error = 'Error del motor: ' . $response->body();
                    }
                } catch (\Throwable $e) {
                    Log::error('Backtesting: error — ' . $e->getMessage());
                    $error = 'No se pudo conectar al motor de backtesting.';
                }
            }
        }

        return view('backtesting.run', [
            'strategies'             => self::STRATEGY_OPTIONS,
            'symbols'                => $symbols,
            'intervals'              => $intervals,
            'paperConfigsForPreload' => $paperConfigsForPreload,
            'result'                 => $result,
            'implementParams'        => $implementParams,
            'error'                  => $error,
            'old'                    => $request->all(),
        ]);
    }

    /**
     * Endpoint AJAX: devuelve los parametros exactos de una config activa de
     * Paper Trading, para precargar el formulario de Backtesting al re-testear.
     */
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

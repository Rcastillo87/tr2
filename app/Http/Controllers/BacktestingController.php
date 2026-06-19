<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\CollectorConfig;
use App\Models\PaperStrategyConfig;

class BacktestingController extends Controller
{
    // Clases genericas de estrategia disponibles para backtesting
    // Cada una mapea al nombre que el motor Python reconoce en backtest.py
    const STRATEGY_OPTIONS = [
        'VWAP Tendencia'         => ['class' => 'VwapStrategy',          'mode' => 'trend_follow', 'label' => 'VWAP Tendencia (trend follow)'],
        'VWAP Reversión'         => ['class' => 'VwapStrategy',          'mode' => 'reversion',    'label' => 'VWAP Reversión (E-13)'],
        'Reversión a la Media'   => ['class' => 'MeanReversionStrategy', 'mode' => null,           'label' => 'Reversión a la Media'],
        'Tendencia EMA/Donchian' => ['class' => 'EmaDonchianStrategy',   'mode' => null,           'label' => 'Tendencia EMA/Donchian'],
    ];

    public function index(Request $request)
    {
        $result = null;
        $error  = null;

        // Simbolos e intervalos activos desde DB
        $symbols   = CollectorConfig::activeSymbols();
        $intervals = CollectorConfig::activeIntervals();

        // Configs activas de paper trading para precarga de params via JS
        $paperConfigs = PaperStrategyConfig::active()
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
            });

        if ($request->isMethod('post')) {
            $strategyKey = $request->input('strategy');
            $strategyDef = self::STRATEGY_OPTIONS[$strategyKey] ?? null;

            if (!$strategyDef) {
                $error = "Estrategia no reconocida: {$strategyKey}";
            } else {
                // Nombre que el motor Python reconoce en su strategy_map
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
                    'risk_per_trade_pct' => 1.0,
                    'sl_pct'             => (float) $request->input('sl_pct', 1.5),
                    'tp_pct'             => (float) $request->input('tp_pct', 3.0),
                    'be_pct'             => (float) $request->input('be_pct', 2.0),
                    'max_duration'       => (int) $request->input('max_duration', 24),
                    'regime_filter'      => $request->boolean('regime_filter', true),
                    'walk_forward'       => true,
                    'n_windows'          => 5,
                ];

                // Si la estrategia tiene modo (VwapStrategy), incluirlo en extra_params
                if ($strategyDef['mode']) {
                    $payload['mode'] = $strategyDef['mode'];
                }

                try {
                    $response = Http::withHeaders([
                        'X-Internal-API-Key' => config('trading.python_internal_api_key'),
                    ])->timeout(120)->post(
                        config('trading.python_engine_url') . '/v1/backtest/run',
                        $payload
                    );

                    if ($response->successful()) {
                        $result = $response->json('result');
                    } else {
                        $error = 'Error del motor: ' . $response->body();
                    }
                } catch (\Throwable $e) {
                    Log::error('Backtesting: error — ' . $e->getMessage());
                    $error = 'No se pudo conectar al motor de backtesting.';
                }
            }
        }

        return view('backtesting.index', [
            'strategies'   => self::STRATEGY_OPTIONS,
            'symbols'      => $symbols,
            'intervals'    => $intervals,
            'paperConfigs' => $paperConfigs,
            'result'       => $result,
            'error'        => $error,
            'old'          => $request->all(),
        ]);
    }
}

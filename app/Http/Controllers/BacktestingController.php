<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class BacktestingController extends Controller
{
    private array $strategies = [
        'Tendencia EMA/Donchian',
        'Reversión a la Media',
        'VWAP Intradía',
    ];

    private array $symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];

    public function index(Request $request)
    {
        $result = null;
        $error  = null;

        if ($request->isMethod('post')) {
            $payload = [
                'strategy'           => $request->input('strategy'),
                'symbol'             => $request->input('symbol'),
                'interval'           => '60',
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

        return view('backtesting.index', [
            'strategies' => $this->strategies,
            'symbols'    => $this->symbols,
            'result'     => $result,
            'error'      => $error,
            'old'        => $request->all(),
        ]);
    }
}

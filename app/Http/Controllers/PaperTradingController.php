<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\PaperTrade;

class PaperTradingController extends Controller
{
    public function index()
    {
        $summary = $this->getPaperSummary();

        // Si no hay datos del API (por ejemplo aún sin trades), construir desde DB
        if (empty($summary)) {
            $strategies = ['Tendencia EMA/Donchian', 'Reversión a la Media', 'VWAP Intradía'];
            $summary = [];

            foreach ($strategies as $strategy) {
                $closed  = PaperTrade::forStrategy($strategy)->closed();
                $total   = $closed->count();
                $wins    = PaperTrade::forStrategy($strategy)->closed()->where('pnl', '>', 0)->count();

                $summary[] = [
                    'strategy'     => $strategy,
                    'total_trades' => $total,
                    'wins'         => $wins,
                    'losses'       => $total - $wins,
                    'win_rate'     => $total > 0 ? round($wins / $total * 100, 2) : 0,
                    'open_trades'  => PaperTrade::forStrategy($strategy)->open()->count(),
                    'total_pnl'    => (float) PaperTrade::forStrategy($strategy)->closed()->sum('pnl'),
                ];
            }
        }

        return view('paper-trading.index', ['summary' => $summary]);
    }

    public function show(string $strategy)
    {
        $openTrades   = PaperTrade::forStrategy($strategy)->open()->orderBy('entry_time', 'desc')->get();
        $closedTrades = PaperTrade::forStrategy($strategy)->closed()->orderBy('exit_time', 'desc')->limit(100)->get();

        $totalClosed = $closedTrades->count();
        $wins        = $closedTrades->where('pnl', '>', 0)->count();
        $winRate     = $totalClosed > 0 ? round($wins / $totalClosed * 100, 2) : 0;
        $totalPnl    = $closedTrades->sum('pnl');

        $grossProfit = $closedTrades->where('pnl', '>', 0)->sum('pnl');
        $grossLoss   = abs($closedTrades->where('pnl', '<=', 0)->sum('pnl'));
        $profitFactor = $grossLoss > 0 ? round($grossProfit / $grossLoss, 2) : null;

        // Equity curve para el gráfico
        $equityCurve = [10000];
        foreach ($closedTrades->sortBy('exit_time') as $trade) {
            $equityCurve[] = round(end($equityCurve) + (float) $trade->pnl, 2);
        }

        return view('paper-trading.show', [
            'strategy'      => $strategy,
            'openTrades'    => $openTrades,
            'closedTrades'  => $closedTrades,
            'totalClosed'   => $totalClosed,
            'winRate'       => $winRate,
            'totalPnl'      => $totalPnl,
            'profitFactor'  => $profitFactor,
            'equityCurve'   => $equityCurve,
        ]);
    }

    private function getPaperSummary(): array
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(config('trading.python_engine_url') . '/v1/paper/summary');

            if ($response->successful()) {
                return $response->json('data') ?? [];
            }
        } catch (\Throwable $e) {
            Log::warning('PaperTrading: error obteniendo resumen — ' . $e->getMessage());
        }

        return [];
    }
}

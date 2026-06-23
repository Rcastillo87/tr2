<?php
namespace App\Http\Controllers;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\PaperTrade;
use App\Models\PaperStrategyConfig;

class DashboardController extends Controller
{
    public function index()
    {
        $regimes = $this->getRegimes();

        // Resumen consolidado por grupo de estrategia (igual que paper-trading/index)
        $groups = [
            'VWAP Tendencia'         => ['VWAP Tendencia'],
            'VWAP Reversión'         => ['VWAP Reversión'],
            'Reversión a la Media'   => ['Reversión a la Media'],
            'Tendencia EMA/Donchian' => ['Tendencia EMA/Donchian'],
        ];

        $startOfMonth = now()->startOfMonth();
        $endOfMonth   = now()->endOfMonth();
        $legacyMap = [
            'VWAP Tendencia'         => ['VWAP Intradía'],
            'VWAP Reversión'         => [],
            'Reversión a la Media'   => ['Reversión a la Media'],
            'Tendencia EMA/Donchian' => ['Tendencia EMA/Donchian'],
        ];

        $summary = [];

        foreach ($groups as $groupName => $prefixes) {
            $displayNames = PaperStrategyConfig::active()
                ->get('display_name')
                ->pluck('display_name')
                ->filter(function ($name) use ($prefixes) {
                    foreach ($prefixes as $prefix) {
                        if (str_starts_with($name, $prefix)) return true;
                    }
                    return false;
                })->values()->toArray();

            $legacyNames = $legacyMap[$groupName] ?? [];
            $allNames    = array_unique(array_merge($displayNames, $legacyNames));

            if (empty($allNames)) continue;

            $closedMonth = PaperTrade::whereIn('strategy', $allNames)
                ->closed()
                ->whereBetween('entry_time', [$startOfMonth, $endOfMonth]);

            $total      = $closedMonth->count();
            $wins       = (clone $closedMonth)->where('pnl', '>', 0)->count();
            $openCount  = PaperTrade::whereIn('strategy', $allNames)->open()->count();

            $summary[] = [
                'group'         => $groupName,
                'total_trades'  => $total,
                'wins'          => $wins,
                'losses'        => $total - $wins,
                'win_rate'      => $total > 0 ? round($wins / $total * 100, 2) : 0,
                'open_trades'   => $openCount,
                'total_pnl_pct' => (float) (clone $closedMonth)->sum('pnl_pct'),
            ];
        }

        $collectorStatus = auth()->user()?->canViewAnalysisTools()
            ? $this->getCollectorStatus()
            : [];

        $closedThisMonth = PaperTrade::closed()->whereBetween('entry_time', [$startOfMonth, $endOfMonth]);

        $openTrades    = PaperTrade::open()->count();
        $totalPnlPct   = (float) (clone $closedThisMonth)->sum('pnl_pct');
        $totalTrades   = (clone $closedThisMonth)->count();
        $winningTrades = (clone $closedThisMonth)->where('pnl', '>', 0)->count();
        $winRate       = $totalTrades > 0 ? round($winningTrades / $totalTrades * 100, 2) : 0;
        $recentTrades  = PaperTrade::orderBy('updated_at', 'desc')->limit(10)->get();

        return view('dashboard.index', [
            'regimes'     => $regimes,
            'summary'     => $summary,
            'collector'   => $collectorStatus,
            'openTrades'  => $openTrades,
            'totalPnlPct' => $totalPnlPct,
            'totalTrades' => $totalTrades,
            'winRate'     => $winRate,
            'recentTrades'=> $recentTrades,
        ]);
    }

    private function getRegimes(): array
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(config('trading.python_engine_url') . '/v1/regime/status');
            if ($response->successful()) {
                return $response->json('data') ?? [];
            }
        } catch (\Throwable $e) {
            Log::warning('Dashboard: error obteniendo régimen — ' . $e->getMessage());
        }
        return [];
    }

    private function getCollectorStatus(): array
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(config('trading.python_engine_url') . '/v1/collector/status');
            if ($response->successful()) {
                return $response->json('data') ?? [];
            }
        } catch (\Throwable $e) {
            Log::warning('Dashboard: error obteniendo estado collector — ' . $e->getMessage());
        }
        return [];
    }
}

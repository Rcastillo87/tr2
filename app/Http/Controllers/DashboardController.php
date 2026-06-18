<?php
namespace App\Http\Controllers;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\PaperTrade;
class DashboardController extends Controller
{
    public function index()
    {
        $regimes = $this->getRegimes();
        $summary = $this->getPaperSummary();
        $collectorStatus = auth()->user()?->canViewAnalysisTools()
            ? $this->getCollectorStatus()
            : [];

        $startOfMonth = now()->startOfMonth();
        $endOfMonth   = now()->endOfMonth();

        $closedThisMonth = PaperTrade::closed()->whereBetween('entry_time', [$startOfMonth, $endOfMonth]);

        $openTrades = PaperTrade::open()->count();
        $totalPnlPct = (float) (clone $closedThisMonth)->sum('pnl_pct');
        $totalTrades = (clone $closedThisMonth)->count();
        $winningTrades = (clone $closedThisMonth)->where('pnl', '>', 0)->count();
        $winRate = $totalTrades > 0 ? round($winningTrades / $totalTrades * 100, 2) : 0;
        $recentTrades = PaperTrade::orderBy('updated_at', 'desc')->limit(10)->get();
        return view('dashboard.index', [
            'regimes'       => $regimes,
            'summary'       => $summary,
            'collector'     => $collectorStatus,
            'openTrades'    => $openTrades,
            'totalPnlPct'   => $totalPnlPct,
            'totalTrades'   => $totalTrades,
            'winRate'       => $winRate,
            'recentTrades'  => $recentTrades,
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
            Log::warning('Dashboard: error obteniendo resumen paper — ' . $e->getMessage());
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
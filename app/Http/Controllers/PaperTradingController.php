<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\PaperTrade;
use App\Models\PaperStrategyConfig;

class PaperTradingController extends Controller
{
    public function index(Request $request)
    {
        $month    = $this->resolveMonth($request);
        $start    = $month->copy()->startOfMonth();
        $end      = $month->copy()->endOfMonth();

        // Filtros
        $filterStrategy = $request->query('strategy', 'all');
        $filterSymbol   = $request->query('symbol', 'all');
        $filterInterval = $request->query('interval', 'all');
        $filterResult   = $request->query('result', 'all');

        // Posiciones abiertas (sin filtro de mes, siempre se muestran)
        $openQuery = PaperTrade::open()->orderBy('entry_time', 'desc');
        if ($filterStrategy !== 'all') $openQuery->where('strategy', 'like', $filterStrategy . '%');
        if ($filterSymbol   !== 'all') $openQuery->where('symbol', $filterSymbol);
        if ($filterInterval !== 'all') $openQuery->where('interval', $filterInterval);
        $openTrades = $openQuery->get();

        // Precios en vivo para posiciones abiertas
        $livePrices = $this->getLiveOpenTrades();
        foreach ($openTrades as $trade) {
            $live = $livePrices[$trade->id] ?? null;
            $trade->current_price    = $live['current_price'] ?? null;
            $trade->floating_pnl_pct = $live['floating_pnl_pct'] ?? null;
        }

        // Operaciones cerradas del mes con filtros
        $closedQuery = PaperTrade::closed()
            ->whereBetween('entry_time', [$start, $end]);
        if ($filterStrategy !== 'all') $closedQuery->where('strategy', 'like', $filterStrategy . '%');
        if ($filterSymbol   !== 'all') $closedQuery->where('symbol', $filterSymbol);
        if ($filterInterval !== 'all') $closedQuery->where('interval', $filterInterval);
        if ($filterResult === 'win')  $closedQuery->where('pnl', '>', 0);
        if ($filterResult === 'loss') $closedQuery->where('pnl', '<=', 0);
        $closedTrades = $closedQuery->orderBy('exit_time', 'desc')->get();

        // KPIs consolidados
        $totalClosed  = $closedTrades->count();
        $wins         = $closedTrades->where('pnl', '>', 0)->count();
        $winRate      = $totalClosed > 0 ? round($wins / $totalClosed * 100, 2) : 0;
        $totalPnlPct  = round($closedTrades->sum('pnl_pct'), 4);
        $grossProfit  = $closedTrades->where('pnl', '>', 0)->sum('pnl');
        $grossLoss    = abs($closedTrades->where('pnl', '<=', 0)->sum('pnl'));
        $profitFactor = $grossLoss > 0 ? round($grossProfit / $grossLoss, 2) : null;

        // Equity curve en %
        $equityCurvePct = [0];
        foreach ($closedTrades->sortBy('exit_time') as $trade) {
            $equityCurvePct[] = round(end($equityCurvePct) + (float) $trade->pnl_pct, 4);
        }

        // Opciones para los filtros
        $filterOptions = [
            'strategies' => PaperTrade::distinct()->pluck('strategy')->sort()->values()->toArray(),
            'symbols'    => PaperTrade::distinct()->pluck('symbol')->sort()->values()->toArray(),
            'intervals'  => PaperTrade::distinct()->pluck('interval')->sort()->values()->toArray(),
        ];

        return view('paper-trading.index', [
            'openTrades'      => $openTrades,
            'closedTrades'    => $closedTrades,
            'totalClosed'     => $totalClosed,
            'wins'            => $wins,
            'winRate'         => $winRate,
            'totalPnlPct'     => $totalPnlPct,
            'profitFactor'    => $profitFactor,
            'equityCurvePct'  => $equityCurvePct,
            'selectedMonth'   => $month,
            'availableMonths' => $this->availableMonths(),
            'filterOptions'   => $filterOptions,
            'filterStrategy'  => $filterStrategy,
            'filterSymbol'    => $filterSymbol,
            'filterInterval'  => $filterInterval,
            'filterResult'    => $filterResult,
        ]);
    }

    public function live(Request $request)
    {
        $openTrades = PaperTrade::open()->get(['id']);
        $livePrices = $this->getLiveOpenTrades();

        $data = $openTrades->map(function ($trade) use ($livePrices) {
            $live = $livePrices[$trade->id] ?? null;
            return [
                'id'               => $trade->id,
                'current_price'    => $live['current_price'] ?? null,
                'floating_pnl_pct' => $live['floating_pnl_pct'] ?? null,
            ];
        });

        return response()->json(['status' => 'ok', 'data' => $data]);
    }

    private function getLiveOpenTrades(): array
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(config('trading.python_engine_url') . '/v1/paper/open');

            if ($response->successful()) {
                return collect($response->json('data') ?? [])->keyBy('id')->toArray();
            }
        } catch (\Throwable $e) {
            Log::warning('PaperTrading: error obteniendo precios en vivo — ' . $e->getMessage());
        }
        return [];
    }

    private function resolveMonth(Request $request): Carbon
    {
        $requested = $request->query('mes');
        $month = $requested
            ? Carbon::createFromFormat('Y-m', $requested)->startOfMonth()
            : now()->startOfMonth();

        $earliestAllowed = $this->earliestAllowedMonth();
        if ($month->lessThan($earliestAllowed))          $month = $earliestAllowed->copy();
        if ($month->greaterThan(now()->startOfMonth()))  $month = now()->startOfMonth();
        return $month;
    }

    private function earliestAllowedMonth(): Carbon
    {
        $user = auth()->user();
        if ($user && $user->isInversionista()) {
            return now()->startOfMonth()->subMonths(8);
        }
        $firstTrade = PaperTrade::orderBy('entry_time', 'asc')->first();
        return $firstTrade
            ? Carbon::parse($firstTrade->entry_time)->startOfMonth()
            : now()->startOfMonth()->subYears(2);
    }

    private function availableMonths(): array
    {
        $earliest = $this->earliestAllowedMonth();
        $current  = now()->startOfMonth();
        $months   = [];
        $cursor   = $current->copy();
        while ($cursor->greaterThanOrEqualTo($earliest)) {
            $months[] = [
                'value' => $cursor->format('Y-m'),
                'label' => ucfirst($cursor->translatedFormat('F Y')),
            ];
            $cursor->subMonth();
        }
        return $months;
    }
}

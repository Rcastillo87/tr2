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
    // Nombres legacy (sistema anterior) mapeados a cada grupo
const LEGACY_NAMES = [
    'VWAP Tendencia'         => ['VWAP Intradía'],
    'VWAP Reversión'         => [],
    'Reversión a la Media'   => ['Reversión a la Media'],
    'Tendencia EMA/Donchian' => ['Tendencia EMA/Donchian'],
];
const STRATEGY_GROUPS = [
    'VWAP Tendencia'         => ['VWAP Tendencia'],
    'VWAP Reversión'         => ['VWAP Reversión'],
    'Reversión a la Media'   => ['Reversión a la Media'],
    'Tendencia EMA/Donchian' => ['Tendencia EMA/Donchian'],
];

    public function index(Request $request)
    {
        $month = $this->resolveMonth($request);
        $start = $month->copy()->startOfMonth();
        $end   = $month->copy()->endOfMonth();

        $summary = [];

        foreach (self::STRATEGY_GROUPS as $groupName => $prefixes) {
            // Buscar todos los display_names que pertenecen a este grupo
            $displayNames = PaperStrategyConfig::active()
                ->get('display_name')
                ->pluck('display_name')
                ->filter(function ($name) use ($prefixes) {
                    foreach ($prefixes as $prefix) {
                        if (str_starts_with($name, $prefix)) return true;
                    }
                    return false;
                })->values()->toArray();

            // Agregar nombres legacy para compatibilidad con trades historicos
            $legacyNames  = self::LEGACY_NAMES[$groupName] ?? [];
            $allNames     = array_unique(array_merge($displayNames, $legacyNames));

            if (empty($allNames)) continue;

            $closedQuery = PaperTrade::whereIn('strategy', $allNames)
                ->closed()
                ->whereBetween('entry_time', [$start, $end]);

            $total      = $closedQuery->count();
            $wins       = (clone $closedQuery)->where('pnl', '>', 0)->count();
            $openTrades = PaperTrade::whereIn('strategy', $allNames)->open()->count();

            if ($total === 0 && $openTrades === 0) continue;

            // Stats por config individual (para mostrar sub-filas en la card)
            $configStats = [];
            foreach ($displayNames as $dn) {
                $q     = PaperTrade::where('strategy', $dn)->closed()->whereBetween('entry_time', [$start, $end]);
                $qOpen = PaperTrade::where('strategy', $dn)->open()->count();
                $t     = $q->count();
                $w     = (clone $q)->where('pnl', '>', 0)->count();
                $configStats[] = [
                    'name'          => $dn,
                    'total_trades'  => $t,
                    'wins'          => $w,
                    'open_trades'   => $qOpen,
                    'total_pnl_pct' => (float)(clone $q)->sum('pnl_pct'),
                ];
            }

            $summary[] = [
                'group'         => $groupName,
                'display_names' => $displayNames,
                'config_stats'  => $configStats,
                'total_trades'  => $total,
                'wins'          => $wins,
                'losses'        => $total - $wins,
                'win_rate'      => $total > 0 ? round($wins / $total * 100, 2) : 0,
                'open_trades'   => $openTrades,
                'total_pnl_pct' => (float) (clone $closedQuery)->sum('pnl_pct'),
            ];
        }

        return view('paper-trading.index', [
            'summary'         => $summary,
            'selectedMonth'   => $month,
            'availableMonths' => $this->availableMonths(),
        ]);
    }

    public function show(string $strategy, Request $request)
    {
        $month  = $this->resolveMonth($request);
        $symbol = $request->query('symbol', 'all');

        // Posiciones abiertas — sin filtro de mes ni símbolo (estado actual)
        $openTrades = PaperTrade::forStrategy($strategy)->open()->orderBy('entry_time', 'desc')->get();
        $livePrices = $this->getLiveOpenTrades();

        foreach ($openTrades as $trade) {
            $live = $livePrices[$trade->id] ?? null;
            $trade->current_price    = $live['current_price'] ?? null;
            $trade->floating_pnl_pct = $live['floating_pnl_pct'] ?? null;
        }

        // Trades cerrados — filtro de mes + filtro de símbolo
        $closedQuery = PaperTrade::forStrategy($strategy)->closed()
            ->whereBetween('entry_time', [
                $month->copy()->startOfMonth(),
                $month->copy()->endOfMonth(),
            ]);

        if ($symbol !== 'all') {
            $closedQuery->where('symbol', $symbol);
        }

        $closedTrades = $closedQuery->orderBy('exit_time', 'desc')->limit(200)->get();

        // Símbolos disponibles para el selector (todos los que tiene esta estrategia)
        $availableSymbols = PaperTrade::forStrategy($strategy)
            ->closed()
            ->distinct()
            ->pluck('symbol')
            ->sort()
            ->values()
            ->toArray();

        // KPIs
        $totalClosed  = $closedTrades->count();
        $wins         = $closedTrades->where('pnl', '>', 0)->count();
        $winRate      = $totalClosed > 0 ? round($wins / $totalClosed * 100, 2) : 0;
        $totalPnlPct  = $closedTrades->sum('pnl_pct');
        $grossProfit  = $closedTrades->where('pnl', '>', 0)->sum('pnl');
        $grossLoss    = abs($closedTrades->where('pnl', '<=', 0)->sum('pnl'));
        $profitFactor = $grossLoss > 0 ? round($grossProfit / $grossLoss, 2) : null;

        // Equity curve en %
        $equityCurvePct = [0];
        foreach ($closedTrades->sortBy('exit_time') as $trade) {
            $equityCurvePct[] = round(end($equityCurvePct) + (float) $trade->pnl_pct, 4);
        }

        // Subtotales por símbolo
        $symbolTotals = [];
        foreach ($closedTrades->groupBy('symbol') as $sym => $trades) {
            $symWins = $trades->where('pnl', '>', 0)->count();
            $symbolTotals[$sym] = [
                'symbol'        => $sym,
                'total'         => $trades->count(),
                'wins'          => $symWins,
                'losses'        => $trades->count() - $symWins,
                'win_rate'      => $trades->count() > 0 ? round($symWins / $trades->count() * 100, 2) : 0,
                'total_pnl_pct' => round($trades->sum('pnl_pct'), 2),
            ];
        }

        // Config de la estrategia (para mostrar en show — inversionista puede ver, admin puede editar)
        $strategyConfig = PaperStrategyConfig::where('display_name', $strategy)->first();

        return view('paper-trading.show', [
            'strategy'        => $strategy,
            'openTrades'      => $openTrades,
            'closedTrades'    => $closedTrades,
            'totalClosed'     => $totalClosed,
            'winRate'         => $winRate,
            'totalPnlPct'     => $totalPnlPct,
            'profitFactor'    => $profitFactor,
            'equityCurvePct'  => $equityCurvePct,
            'selectedMonth'   => $month,
            'availableMonths' => $this->availableMonths(),
            'availableSymbols'=> $availableSymbols,
            'selectedSymbol'  => $symbol,
            'symbolTotals'    => $symbolTotals,
            'strategyConfig'  => $strategyConfig,
        ]);
    }

    public function live(string $strategy)
    {
        $openTrades = PaperTrade::forStrategy($strategy)->open()->get(['id']);
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
        if ($month->lessThan($earliestAllowed)) $month = $earliestAllowed->copy();
        if ($month->greaterThan(now()->startOfMonth())) $month = now()->startOfMonth();
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

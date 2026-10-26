<?php

namespace App\Http\Controllers;

use App\Models\BrokerAccount;
use App\Models\PaperStrategyConfig;
use App\Models\RealTrade;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Http;

class TradingController extends Controller
{
    public function index(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $user  = auth()->user();
        $month = $request->input('month')
            ? Carbon::createFromFormat('Y-m', $request->input('month'))->startOfMonth()
            : now('America/Bogota')->startOfMonth();

        $start = $month->copy()->startOfMonth();
        $end   = $month->copy()->endOfMonth();

        // Filtros
        $filterStrategy = $request->query('strategy', 'all');
        $filterSymbol   = $request->query('symbol', 'all');
        $filterInterval = $request->query('interval', 'all');
        $filterResult   = $request->query('result', 'all');
        $filterAccount  = $request->query('account', 'all');
        
        
        
        

        // IDs de cuentas del usuario
        $accountIds = BrokerAccount::where('user_id', $user->id)->pluck('id');

        // Posiciones abiertas (sin filtro de mes)
        $openQuery = RealTrade::whereIn('broker_account_id', $accountIds)->open()
            ->orderBy('entry_time', 'desc');
        if ($filterStrategy !== 'all') $openQuery->where('strategy', 'LIKE', $filterStrategy . ' —%');
        if ($filterSymbol   !== 'all') $openQuery->where('symbol', $filterSymbol);
        if ($filterInterval !== 'all') $openQuery->where('interval', $filterInterval);
        if ($filterAccount  !== 'all') $openQuery->where('broker_account_id', $filterAccount);
        $openTrades = $openQuery->get();

        // Precios en vivo para posiciones abiertas
        $prices = $this->getLivePrices($openTrades->pluck('symbol')->unique()->toArray());
        foreach ($openTrades as $trade) {
            $currentPrice = $prices[$trade->symbol] ?? null;
            $trade->current_price = $currentPrice;
            if ($currentPrice) {
                $trade->floating_pnl_pct = round(
                    $trade->side === 'long'
                        ? (($currentPrice - $trade->entry_price) / $trade->entry_price) * 100
                        : (($trade->entry_price - $currentPrice) / $trade->entry_price) * 100,
                    4
                );
            } else {
                $trade->floating_pnl_pct = null;
            }
        }

        // Operaciones cerradas del mes con filtros
        $closedQuery = RealTrade::whereIn('broker_account_id', $accountIds)
            ->closed()
            ->whereBetween('entry_time', [$start, $end]);
        if ($filterStrategy !== 'all') $closedQuery->where('strategy', 'LIKE', $filterStrategy . ' —%');
        if ($filterSymbol   !== 'all') $closedQuery->where('symbol', $filterSymbol);
        if ($filterInterval !== 'all') $closedQuery->where('interval', $filterInterval);
        if ($filterResult === 'win')   $closedQuery->where('pnl', '>', 0);
        if ($filterResult === 'loss')  $closedQuery->where('pnl', '<=', 0);
        if ($filterAccount  !== 'all') $closedQuery->where('broker_account_id', $filterAccount);
        $closedTrades = $closedQuery->orderBy('exit_time', 'desc')->get();

        // KPIs consolidados
        $totalClosed  = $closedTrades->count();
        $wins         = $closedTrades->filter(fn ($t) => ($t->net_pnl ?? $t->pnl) > 0)->count();
        $winRate      = $totalClosed > 0 ? round($wins / $totalClosed * 100, 2) : 0;
        $totalNetPnl  = round((float) $closedTrades->sum('net_pnl') ?: $closedTrades->sum('pnl'), 2);
        $grossProfit  = $closedTrades->filter(fn ($t) => ($t->net_pnl ?? $t->pnl) > 0)->sum('net_pnl');
        $grossLoss    = abs($closedTrades->filter(fn ($t) => ($t->net_pnl ?? $t->pnl) <= 0)->sum('net_pnl'));
        $profitFactor = $grossLoss > 0 ? round($grossProfit / $grossLoss, 2) : null;

        // Equity curve en USDT (net_pnl acumulado)
        $equityCurve = [0];
        foreach ($closedTrades->sortBy('exit_time') as $trade) {
            $equityCurve[] = round(end($equityCurve) + (float) ($trade->net_pnl ?? $trade->pnl), 2);
        }

        // Opciones para filtros — dinamicas desde DB
        $allTrades    = RealTrade::whereIn('broker_account_id', $accountIds);
        $userAccounts = BrokerAccount::where('user_id', $user->id)
            ->orderBy('created_at')
            ->get(['id', 'label', 'account_type', 'broker']);

        // 1. Estrategias con suscripciones REALES activas en las cuentas del usuario
        $subscriptionStrategies = \App\Models\RealStrategySubscription::whereIn('broker_account_id', $accountIds)
            ->where('status', 'active')
            ->pluck('strategy')
            ->map(fn($s) => trim(explode('—', $s)[0]))
            ->filter()
            ->toArray();

        // 2. Estrategias con trades históricos (para no perder las que ya operaron)
        $tradeStrategies = (clone $allTrades)->pluck('strategy')
            ->map(fn($s) => trim(explode('—', $s)[0]))
            ->filter()
            ->toArray();

        // 3. Combinar ambas fuentes, limpiar duplicados y ordenar
        $allStrategyNames = collect(array_merge($subscriptionStrategies, $tradeStrategies))
            ->unique()
            ->sort()
            ->values()
            ->toArray();

        // Estrategias de suscripciones activas
        $subStrategies = \App\Models\RealStrategySubscription::whereIn('broker_account_id', $accountIds)
            ->where('status', 'active')
            ->pluck('strategy')
            ->map(fn($s) => trim(explode('—', $s)[0]))
            ->filter()
            ->toArray();
        
        // Símbolos de suscripciones activas
        $subSymbols = \App\Models\RealStrategySubscription::whereIn('broker_account_id', $accountIds)
            ->where('status', 'active')
            ->pluck('symbol')
            ->filter()
            ->toArray();

        // Combinar con los trades históricos
        $tradeStrategies = (clone $allTrades)->pluck('strategy')
            ->map(fn($s) => trim(explode('—', $s)[0]))
            ->filter()
            ->toArray();
        $tradeSymbols = (clone $allTrades)->pluck('symbol')->filter()->toArray();

        // Estrategias activas en Paper (las que están listas para operar)
        $paperStrategies = \App\Models\PaperStrategyConfig::where('active', true)
            ->get(['display_name', 'symbol', 'interval']);
        
        $paperStrategyNames = $paperStrategies->pluck('display_name')
            ->map(fn($s) => trim(explode('—', $s)[0]))
            ->filter()
            ->toArray();
        
        $paperSymbols = $paperStrategies->pluck('symbol')->filter()->toArray();
        $paperIntervals = $paperStrategies->pluck('interval')->filter()->toArray();

        // Estrategias con trades históricos en Real (para no perder las que ya operaron)
        $tradeStrategies = (clone $allTrades)->pluck('strategy')
            ->map(fn($s) => trim(explode('—', $s)[0]))
            ->filter()
            ->toArray();
        
        $tradeSymbols = (clone $allTrades)->pluck('symbol')->filter()->toArray();
        $tradeIntervals = (clone $allTrades)->distinct()->pluck('interval')->filter()->toArray();

        $filterOptions = [
            'strategies' => collect(array_merge($paperStrategyNames, $tradeStrategies))->unique()->sort()->values()->toArray(),
            'symbols'    => collect(array_merge($paperSymbols, $tradeSymbols))->unique()->sort()->values()->toArray(),
            'intervals'  => collect(array_merge($paperIntervals, $tradeIntervals))->unique()->sort()->values()->toArray(),
            'accounts'   => $userAccounts,
        ];

        // Meses disponibles
        $availableMonths = $this->availableMonths($accountIds->toArray());

        return view('trading.index', [
            'openTrades'      => $openTrades,
            'closedTrades'    => $closedTrades,
            'totalClosed'     => $totalClosed,
            'wins'            => $wins,
            'winRate'         => $winRate,
            'totalNetPnl'     => $totalNetPnl,
            'profitFactor'    => $profitFactor,
            'equityCurve'     => $equityCurve,
            'month'           => $month,
            'availableMonths' => $availableMonths,
            'filterOptions'   => $filterOptions,
            'filterStrategy'  => $filterStrategy,
            'filterSymbol'    => $filterSymbol,
            'filterInterval'  => $filterInterval,
            'filterResult'    => $filterResult,
            'filterAccount'   => $filterAccount,
            
            
            
            
        ]);
    }

    private function getLivePrices(array $symbols): array
    {
        $prices = [];
        foreach ($symbols as $symbol) {
            try {
                $price = \Illuminate\Support\Facades\Redis::get("price:{$symbol}");
                if ($price) $prices[$symbol] = (float) $price;
            } catch (\Throwable $e) {}
        }

        if (empty($prices) && !empty($symbols)) {
            try {
                $response = Http::withHeaders([
                    'X-Internal-API-Key' => config('trading.python_internal_api_key'),
                ])->timeout(5)->get(config('trading.python_engine_url') . '/v1/prices', [
                    'symbols' => implode(',', $symbols),
                ]);
                if ($response->successful()) {
                    $prices = $response->json('prices', []);
                }
            } catch (\Throwable $e) {}
        }

        return $prices;
    }

    private function availableMonths(array $accountIds): array
    {
        $first = RealTrade::whereIn('broker_account_id', $accountIds)
            ->orderBy('entry_time')->first();
        $earliest = $first
            ? Carbon::parse($first->entry_time)->startOfMonth()
            : now('America/Bogota')->startOfMonth();

        $current = now('America/Bogota')->startOfMonth();
        $months  = [];
        $cursor  = $current->copy();
        while ($cursor->greaterThanOrEqualTo($earliest)) {
            $months[] = [
                'value' => $cursor->format('Y-m'),
                'label' => ucfirst($cursor->translatedFormat('F Y')),
            ];
            $cursor->subMonth();
        }
        return $months;
    }

    private function getAccountInfo(BrokerAccount $account): ?array
    {
        return Cache::remember("broker_account_info:{$account->id}", 3600, function () use ($account) {
            try {
                $response = Http::withHeaders([
                    'X-Internal-API-Key' => config('trading.python_internal_api_key'),
                ])->timeout(10)->post(
                    config('trading.python_engine_url') . '/v1/broker/account-info',
                    [
                        'broker'       => $account->broker,
                        'account_type' => $account->account_type,
                        'api_key'      => $account->api_key,
                        'api_secret'   => $account->api_secret,
                    ]
                );
                if ($response->successful()) return $response->json();
            } catch (\Throwable $e) {}
            return null;
        });
    }

    public function accounts(Request $request)
    {
        Gate::authorize('viewRealTrading');
        $user = auth()->user();

        $accounts = BrokerAccount::where('user_id', $user->id)
            ->withCount('subscriptions')
            ->with(['subscriptions' => fn ($q) => $q->with('paperStrategyConfig.backtest')->orderBy('created_at')])
            ->orderBy('created_at', 'desc')
            ->get();

        // Agrupar configuraciones activas por backtest_id
        $allActiveConfigs = PaperStrategyConfig::active()->with('backtest')->get();
        
        $groupedConfigs = $allActiveConfigs->groupBy(function($config) {
            return $config->backtest_id ?? 'config_' . $config->id;
        })->map(function($group) {
            $first = $group->first();
            $backtest = $first->backtest;
            
            // Símbolos del backtest
            $symbols = $backtest 
                ? (is_array($backtest->symbols) ? $backtest->symbols : json_decode($backtest->symbols, true))
                : [$first->symbol];
            
            $interval = $backtest ? $backtest->interval : $first->interval;
            $baseName = trim(explode(' — ', $first->display_name)[0]);
            $displayName = $baseName . ' — ' . implode(', ', $symbols) . ' (' . $interval . ')';
            
            // Extraer métricas del backtest de forma segura
            $m = $backtest->metrics ?? [];
            
            return [
                'id' => $first->id,
                'config_ids' => $group->pluck('id')->toArray(),
                'display_name' => $displayName,
                'backtest' => $backtest,
                'symbols' => $symbols,
                'interval' => $interval,
                'months' => $backtest->months ?? 0,
                'params' => $backtest->config_params ?? [],
                'metrics' => [
                    'win_rate' => (float)($m['win_rate'] ?? 0),
                    'sharpe_ratio' => (float)($m['sharpe_ratio'] ?? 0),
                    'profit_factor' => (float)($m['profit_factor'] ?? 0),
                    'avg_monthly_pnl' => (float)($m['avg_monthly_pnl'] ?? 0),
                    'consist_pct' => (float)($m['consist_pct'] ?? 0),
                    'total_trades' => (int)($m['total_trades'] ?? 0),
                ],
            ];
        })->values();

        $availableConfigsByAccount = [];
        $subscribedByAccount = $accounts->mapWithKeys(fn ($a) => [
            $a->id => $a->subscriptions->pluck('paper_strategy_config_id')->filter()->toArray(),
        ]);

        foreach ($accounts as $account) {
            $subscribedIds = $subscribedByAccount[$account->id];
            $availableConfigsByAccount[$account->id] = $groupedConfigs->filter(function($group) use ($subscribedIds) {
                $intersect = array_intersect($group['config_ids'], $subscribedIds);
                return empty($intersect);
            })->values();
        }

        $accountInfos = $accounts->mapWithKeys(fn ($a) => [$a->id => $this->getAccountInfo($a)]);

        return view('trading.accounts', [
            'accounts' => $accounts,
            'availableConfigsByAccount' => $availableConfigsByAccount,
            'accountInfos' => $accountInfos,
            'canCreateDemo' => $user->canCreateDemoAccounts(),
        ]);
    }

    public function livePrices(Request $request)
    {
        Gate::authorize('viewRealTrading');
        $accountIds = BrokerAccount::where('user_id', auth()->id())->pluck('id');
        $openTrades = RealTrade::whereIn('broker_account_id', $accountIds)
            ->open()
            ->with('brokerAccount')
            ->get(['id', 'symbol', 'side', 'entry_price', 'sl', 'tp', 'size', 'broker_account_id']);
        $symbols = $openTrades->pluck('symbol')->unique()->toArray();
        // Demo Trading de Bybit usa los precios reales del mercado: misma fuente para demo y real
        $prices = $this->getLivePrices($symbols);

        $result = $openTrades->map(function ($trade) use ($prices) {
            $currentPrice   = $prices[$trade->symbol] ?? null;
            $floatingPnlPct = null;
            if ($currentPrice) {
                $floatingPnlPct = round(
                    $trade->side === 'long'
                        ? (($currentPrice - $trade->entry_price) / $trade->entry_price) * 100
                        : (($trade->entry_price - $currentPrice) / $trade->entry_price) * 100,
                    4
                );
            }
            return [
                'id'               => $trade->id,
                'symbol'           => $trade->symbol,
                'current_price'    => $currentPrice,
                'floating_pnl_pct' => $floatingPnlPct,
            ];
        });

        return response()->json($result);
    }
}

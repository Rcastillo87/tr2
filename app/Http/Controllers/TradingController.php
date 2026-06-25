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
        if ($filterStrategy !== 'all') $openQuery->where('strategy', $filterStrategy);
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
        if ($filterStrategy !== 'all') $closedQuery->where('strategy', $filterStrategy);
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

        $filterOptions = [
            'strategies' => (clone $allTrades)->distinct()->pluck('strategy')->sort()->values()->toArray(),
            'symbols'    => (clone $allTrades)->distinct()->pluck('symbol')->sort()->values()->toArray(),
            'intervals'  => (clone $allTrades)->distinct()->pluck('interval')->filter()->sort()->values()->toArray(),
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
            ->with(['subscriptions' => fn ($q) => $q->with('paperStrategyConfig')->orderBy('created_at')])
            ->orderBy('created_at', 'desc')
            ->get();

        $availableConfigs    = PaperStrategyConfig::active()->orderBy('display_name')->get();
        $subscribedByAccount = $accounts->mapWithKeys(fn ($a) => [
            $a->id => $a->subscriptions->pluck('paper_strategy_config_id')->filter()->values()->toArray(),
        ]);
        $accountInfos = $accounts->mapWithKeys(fn ($a) => [$a->id => $this->getAccountInfo($a)]);

        return view('trading.accounts', [
            'accounts'            => $accounts,
            'availableConfigs'    => $availableConfigs,
            'subscribedByAccount' => $subscribedByAccount,
            'accountInfos'        => $accountInfos,
            'canCreateDemo'       => $user->canCreateDemoAccounts(),
        ]);
    }

    public function livePrices(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $accountIds = BrokerAccount::where('user_id', auth()->id())->pluck('id');
        $openTrades = RealTrade::whereIn('broker_account_id', $accountIds)
            ->open()
            ->get(['id', 'symbol', 'side', 'entry_price', 'sl', 'tp', 'size']);

        $symbols = $openTrades->pluck('symbol')->unique()->toArray();
        $prices  = $this->getLivePrices($symbols);

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

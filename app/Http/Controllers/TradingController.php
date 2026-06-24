<?php

namespace App\Http\Controllers;

use App\Models\BrokerAccount;
use App\Models\PaperStrategyConfig;
use App\Models\RealStrategySubscription;
use App\Models\RealTrade;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Gate;

class TradingController extends Controller
{
    /**
     * Vista principal: operaciones del mes por broker.
     */
    public function index(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $user  = auth()->user();
        $month = $request->input('month')
            ? Carbon::createFromFormat('Y-m', $request->input('month'))->startOfMonth()
            : now()->startOfMonth();

        $start = $month->copy()->startOfMonth();
        $end   = $month->copy()->endOfMonth();

        $accounts = BrokerAccount::where('user_id', $user->id)
            ->with(['subscriptions.paperStrategyConfig'])
            ->orderBy('created_at')
            ->get();

        // Operaciones por cuenta
        $accountData = $accounts->map(function ($account) use ($start, $end) {
            $closed = RealTrade::forAccount($account->id)
                ->closed()
                ->whereBetween('entry_time', [$start, $end])
                ->orderBy('entry_time', 'desc')
                ->get();

            $open = RealTrade::forAccount($account->id)
                ->open()
                ->orderBy('entry_time', 'desc')
                ->get();

            $totalTrades = $closed->count();
            $wins        = $closed->filter(fn ($t) => $t->isWinner())->count();
            $totalNetPnl = $closed->sum('net_pnl') ?? $closed->sum('pnl');
            $bestTrade   = $closed->sortByDesc('net_pnl')->first();
            $worstTrade  = $closed->sortBy('net_pnl')->first();

            // Balance inicial y final del mes
            $firstTrade = RealTrade::forAccount($account->id)
                ->closed()
                ->whereBetween('entry_time', [$start, $end])
                ->orderBy('entry_time')
                ->first();
            $lastTrade = RealTrade::forAccount($account->id)
                ->closed()
                ->whereBetween('entry_time', [$start, $end])
                ->orderBy('entry_time', 'desc')
                ->first();

            return [
                'account'      => $account,
                'closed'       => $closed,
                'open'         => $open,
                'total_trades' => $totalTrades,
                'wins'         => $wins,
                'losses'       => $totalTrades - $wins,
                'win_rate'     => $totalTrades > 0 ? round($wins / $totalTrades * 100, 2) : 0,
                'total_net_pnl' => round((float) $totalNetPnl, 2),
                'best_trade'   => $bestTrade,
                'worst_trade'  => $worstTrade,
                'balance_start' => $firstTrade?->balance_before,
                'balance_end'   => $lastTrade?->balance_after,
            ];
        });

        // Consolidado global del mes
        $globalTrades  = $accountData->sum('total_trades');
        $globalWins    = $accountData->sum('wins');
        $globalNetPnl  = $accountData->sum('total_net_pnl');

        return view('trading.index', [
            'accountData'   => $accountData,
            'month'         => $month,
            'globalTrades'  => $globalTrades,
            'globalWins'    => $globalWins,
            'globalWinRate' => $globalTrades > 0 ? round($globalWins / $globalTrades * 100, 2) : 0,
            'globalNetPnl'  => $globalNetPnl,
        ]);
    }

    /**
     * Vista de gestión de cuentas y suscripciones.
     */
    public function accounts(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $user = auth()->user();

        $accounts = BrokerAccount::where('user_id', $user->id)
            ->withCount('subscriptions')
            ->with([
                'subscriptions' => fn ($q) => $q->with('paperStrategyConfig')->orderBy('created_at'),
            ])
            ->orderBy('created_at', 'desc')
            ->get();

        // Configs activas disponibles para suscribir
        $availableConfigs = PaperStrategyConfig::active()
            ->orderBy('display_name')
            ->get();

        // IDs suscritos por cuenta (para excluirlos del modal)
        $subscribedByAccount = $accounts->mapWithKeys(function ($account) {
            return [
                $account->id => $account->subscriptions
                    ->pluck('paper_strategy_config_id')
                    ->filter()
                    ->values()
                    ->toArray(),
            ];
        });

        return view('trading.accounts', [
            'accounts'         => $accounts,
            'availableConfigs'    => $availableConfigs,
            'subscribedByAccount' => $subscribedByAccount,
            'canCreateDemo'       => $user->canCreateDemoAccounts(),
        ]);
    }

    /**
     * AJAX: precio actual para actualizar trades abiertos cada 30s.
     */
    public function livePrices(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $accountIds = BrokerAccount::where('user_id', auth()->id())->pluck('id');

        $openTrades = RealTrade::whereIn('broker_account_id', $accountIds)
            ->open()
            ->get(['id', 'symbol', 'side', 'entry_price', 'sl', 'tp', 'size', 'entry_time']);

        // Obtener precios actuales desde Redis (igual que paper trading)
        $prices = [];
        foreach ($openTrades->pluck('symbol')->unique() as $symbol) {
            try {
                $price = \Illuminate\Support\Facades\Redis::get("price:{$symbol}");
                if ($price) $prices[$symbol] = (float) $price;
            } catch (\Throwable $e) {
                // Si no hay precio en Redis, omitir
            }
        }

        $result = $openTrades->map(function ($trade) use ($prices) {
            $currentPrice = $prices[$trade->symbol] ?? null;
            $floatingPnlPct = null;

            if ($currentPrice) {
                $floatingPnlPct = $trade->side === 'long'
                    ? (($currentPrice - $trade->entry_price) / $trade->entry_price) * 100
                    : (($trade->entry_price - $currentPrice) / $trade->entry_price) * 100;
                $floatingPnlPct = round($floatingPnlPct, 4);
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

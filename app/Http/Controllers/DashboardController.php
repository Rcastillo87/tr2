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
        $startOfMonth = now()->startOfMonth();
        $endOfMonth   = now()->endOfMonth();

        $summary = [];
        $activeConfigs = PaperStrategyConfig::where('active', true)->get();
        $groupedConfigs = $activeConfigs->groupBy(function($config) {
            return trim(explode(' — ', $config->display_name)[0]);
        });

        foreach ($groupedConfigs as $groupName => $configs) {
            $displayNames = $configs->pluck('display_name')->toArray();
            
            $closedMonth = PaperTrade::whereIn('strategy', $displayNames)
                ->closed()
                ->whereBetween('entry_time', [$startOfMonth, $endOfMonth]);

            $total      = $closedMonth->count();
            $wins       = (clone $closedMonth)->where('pnl', '>', 0)->count();
            $openCount  = PaperTrade::whereIn('strategy', $displayNames)->open()->count();

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


        $closedThisMonth = PaperTrade::closed()->whereBetween('entry_time', [$startOfMonth, $endOfMonth]);

        $openTrades    = PaperTrade::open()->count();
        $totalPnlPct   = (float) (clone $closedThisMonth)->sum('pnl_pct');
        $totalTrades   = (clone $closedThisMonth)->count();
        $winningTrades = (clone $closedThisMonth)->where('pnl', '>', 0)->count();
        $winRate       = $totalTrades > 0 ? round($winningTrades / $totalTrades * 100, 2) : 0;
        $recentTrades  = PaperTrade::orderBy('updated_at', 'desc')->limit(10)->get();
        $initialPrices = [];

        // Resumen del mes — real trading (todas las cuentas del usuario)
        $realAccountIds = \App\Models\BrokerAccount::where('user_id', auth()->id())->pluck('id');
        $closedRealMonth = \App\Models\RealTrade::whereIn('broker_account_id', $realAccountIds)
            ->closed()
            ->whereBetween('entry_time', [$startOfMonth, $endOfMonth]);
        $openRealTrades    = \App\Models\RealTrade::whereIn('broker_account_id', $realAccountIds)->open()->count();
        $totalRealPnl = (float) (clone $closedRealMonth)->get()->sum(fn ($t) => $t->net_pnl ?? $t->pnl);

        $totalRealTrades   = (clone $closedRealMonth)->count();
        $winningRealTrades = (clone $closedRealMonth)->where('pnl', '>', 0)->count();
        $realWinRate       = $totalRealTrades > 0 ? round($winningRealTrades / $totalRealTrades * 100, 2) : 0;
        // Carga inicial de precios (Desde la base de datos, ultra rápido)
        $activeConfigs = PaperStrategyConfig::where('active', true)->get();
        $activeSymbols = $activeConfigs->pluck('symbol')->unique()->values()->toArray();

        $initialPrices = [];
        if (!empty($activeSymbols)) {
            $initialCacheKey = 'initial_prices_' . md5(implode(',', $activeSymbols));
            
            // Caché de 30 segundos para la tendencia inicial
            $initialPrices = \Illuminate\Support\Facades\Cache::remember($initialCacheKey, 30, function () use ($activeSymbols) {
                $prices = [];
                foreach ($activeSymbols as $sym) {
                    $candles = self::lastTwoMinuteCloses($sym);

                    if (count($candles) >= 2) {
                        $curr = (float) $candles[0]->close;
                        $prev = (float) $candles[1]->close;
                        $prices[$sym] = ['price' => $curr, 'change_pct' => $prev > 0 ? (($curr - $prev) / $prev) * 100 : 0];
                    } elseif (count($candles) == 1) {
                        $prices[$sym] = ['price' => (float) $candles[0]->close, 'change_pct' => 0];
                    }
                }
                return $prices;
            });
        }

        return view('dashboard.index', [
            'regimes'         => $regimes,
            'summary'         => $summary,
            'openTrades'      => $openTrades,
            'totalPnlPct'     => $totalPnlPct,
            'totalTrades'     => $totalTrades,
            'winRate'         => $winRate,
            'recentTrades'    => $recentTrades,
            'openRealTrades'  => $openRealTrades,
            'totalRealPnl'    => $totalRealPnl,
            'totalRealTrades' => $totalRealTrades,
            'realWinRate'     => $realWinRate,
            'initialPrices'   => $initialPrices,
            'activeSymbols'   => $activeSymbols,
            
        ]);
    }

    /**
     * Cierres de las 2 últimas velas de 1m del símbolo (la más reciente primero), fuente en vivo bybit (D-22).
     * R-03 (13-nov): antes, ROW_NUMBER() recorría TODA la serie de 1m (≈1,1 M velas comprimidas por moneda) para
     * quedarse con 2 filas: ~0,39 s por moneda en producción. Acotada al último día usa el último fragmento (~6 ms).
     * Con menos de 2 velas en el último día (collector detenido o recién reanudado) usa la consulta sin límite de
     * tiempo: el resultado es SIEMPRE el mismo que antes (mismas 2 filas, mismo orden).
     */
    private static function lastTwoMinuteCloses(string $symbol): array
    {
        $sql = "SELECT close FROM ohlcv_data WHERE broker = 'bybit' AND symbol = ? AND interval = '1'%s ORDER BY time DESC LIMIT 2";
        $rows = \DB::select(sprintf($sql, " AND time > now() - interval '1 day'"), [$symbol]);

        // Menos de 2 en el último día (collector detenido o recién reanudado): sin límite, como antes
        return count($rows) >= 2 ? $rows : \DB::select(sprintf($sql, ''), [$symbol]);
    }

    public function livePrices()
    {
        $symbols = \App\Models\PaperStrategyConfig::where('active', true)
            ->pluck('symbol')->unique()->values()->toArray();

        if (empty($symbols)) return response()->json(['prices' => []]);

        $cacheKey = 'live_prices_' . md5(implode(',', $symbols));

        // Caché de 60 segundos (antes 10s)
        $prices = \Illuminate\Support\Facades\Cache::remember($cacheKey, 60, function () use ($symbols) {
            try {
                $response = \Illuminate\Support\Facades\Http::withHeaders([
                    'X-Internal-API-Key' => config('trading.python_internal_api_key'),
                ])->timeout(3)->get(config('trading.python_engine_url') . '/v1/prices', [
                    'symbols' => implode(',', $symbols),
                ]);
                if ($response->successful()) return $response->json('prices', []);
            } catch (\Throwable $e) {
                \Illuminate\Support\Facades\Log::warning('Dashboard livePrices: ' . $e->getMessage());
            }
            return [];
        });

        return response()->json(['prices' => $prices]);
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

}

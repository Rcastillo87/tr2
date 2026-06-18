<?php
namespace App\Http\Controllers;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\PaperTrade;
class PaperTradingController extends Controller
{
    public function index(Request $request)
    {
        $month = $this->resolveMonth($request);

        $strategies = ['Tendencia EMA/Donchian', 'Reversión a la Media', 'VWAP Intradía'];
        $summary = [];

        foreach ($strategies as $strategy) {
            $closedQuery = PaperTrade::forStrategy($strategy)->closed()->whereBetween('entry_time', [
                $month->copy()->startOfMonth(),
                $month->copy()->endOfMonth(),
            ]);

            $total = $closedQuery->count();
            $wins  = (clone $closedQuery)->where('pnl', '>', 0)->count();

            $summary[] = [
                'strategy'     => $strategy,
                'total_trades' => $total,
                'wins'         => $wins,
                'losses'       => $total - $wins,
                'win_rate'     => $total > 0 ? round($wins / $total * 100, 2) : 0,
                'open_trades'  => PaperTrade::forStrategy($strategy)->open()->count(),
                'total_pnl'    => (float) (clone $closedQuery)->sum('pnl'),
                'total_pnl_pct'=> (float) (clone $closedQuery)->sum('pnl_pct'),
            ];
        }

        $summary = array_values(array_filter($summary, function ($s) {
            return $s['total_trades'] > 0 || $s['open_trades'] > 0;
        }));

        return view('paper-trading.index', [
            'summary'         => $summary,
            'selectedMonth'   => $month,
            'availableMonths' => $this->availableMonths(),
        ]);
    }

    public function show(string $strategy, Request $request)
    {
        $month = $this->resolveMonth($request);

        // Las posiciones abiertas no se filtran por mes: son el estado actual.
        $openTrades = PaperTrade::forStrategy($strategy)->open()->orderBy('entry_time', 'desc')->get();
        $livePrices = $this->getLiveOpenTrades();

        foreach ($openTrades as $trade) {
            $live = $livePrices[$trade->id] ?? null;
            $trade->current_price    = $live['current_price'] ?? null;
            $trade->floating_pnl_pct = $live['floating_pnl_pct'] ?? null;
        }

        $closedTrades = PaperTrade::forStrategy($strategy)->closed()
            ->whereBetween('entry_time', [
                $month->copy()->startOfMonth(),
                $month->copy()->endOfMonth(),
            ])
            ->orderBy('exit_time', 'desc')
            ->limit(200)
            ->get();

        $totalClosed = $closedTrades->count();
        $wins        = $closedTrades->where('pnl', '>', 0)->count();
        $winRate     = $totalClosed > 0 ? round($wins / $totalClosed * 100, 2) : 0;
        $totalPnl    = $closedTrades->sum('pnl');
        $totalPnlPct = $closedTrades->sum('pnl_pct');
        $grossProfit = $closedTrades->where('pnl', '>', 0)->sum('pnl');
        $grossLoss   = abs($closedTrades->where('pnl', '<=', 0)->sum('pnl'));
        $profitFactor = $grossLoss > 0 ? round($grossProfit / $grossLoss, 2) : null;

        // Equity curve en % acumulado (sobre balance virtual de referencia)
        $equityCurvePct = [0];
        foreach ($closedTrades->sortBy('exit_time') as $trade) {
            $equityCurvePct[] = round(end($equityCurvePct) + (float) $trade->pnl_pct, 4);
        }

        return view('paper-trading.show', [
            'strategy'        => $strategy,
            'openTrades'      => $openTrades,
            'closedTrades'    => $closedTrades,
            'totalClosed'     => $totalClosed,
            'winRate'         => $winRate,
            'totalPnl'        => $totalPnl,
            'totalPnlPct'     => $totalPnlPct,
            'profitFactor'    => $profitFactor,
            'equityCurvePct'  => $equityCurvePct,
            'selectedMonth'   => $month,
            'availableMonths' => $this->availableMonths(),
        ]);
    }

    /**
     * Consulta el motor Python para obtener el precio actual de mercado y el
     * PnL flotante de cada posicion abierta. Devuelve un mapa [trade_id => datos],
     * o un array vacio si el motor no responde (la vista debe degradar con gracia).
     */
    private function getLiveOpenTrades(): array
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(config('trading.python_engine_url') . '/v1/paper/open');

            if ($response->successful()) {
                $data = $response->json('data') ?? [];

                return collect($data)->keyBy('id')->toArray();
            }
        } catch (\Throwable $e) {
            Log::warning('PaperTrading: error obteniendo precios en vivo — ' . $e->getMessage());
        }

        return [];
    }

    /**
     * Resuelve el mes seleccionado a partir del parametro 'mes' (formato YYYY-MM),
     * por defecto el mes actual. Si el usuario es inversionista y pide un mes
     * mas antiguo que el limite permitido, se cae al limite (no al actual),
     * para no ocultar silenciosamente la intencion del usuario mas de lo necesario.
     */
    private function resolveMonth(Request $request): Carbon
    {
        $requested = $request->query('mes');

        $month = $requested
            ? Carbon::createFromFormat('Y-m', $requested)->startOfMonth()
            : now()->startOfMonth();

        $earliestAllowed = $this->earliestAllowedMonth();

        if ($month->lessThan($earliestAllowed)) {
            $month = $earliestAllowed->copy();
        }

        if ($month->greaterThan(now()->startOfMonth())) {
            $month = now()->startOfMonth();
        }

        return $month;
    }

    private function earliestAllowedMonth(): Carbon
    {
        $user = auth()->user();

        if ($user && $user->isInversionista()) {
            return now()->startOfMonth()->subMonths(8);
        }

        // Admin/consultor: sin limite practico, se usa la fecha del primer trade conocido
        // o un limite amplio de respaldo.
        $firstTrade = PaperTrade::orderBy('entry_time', 'asc')->first();

        return $firstTrade
            ? Carbon::parse($firstTrade->entry_time)->startOfMonth()
            : now()->startOfMonth()->subYears(2);
    }

    /**
     * Lista de meses disponibles para el selector, mas reciente primero,
     * respetando el limite de 8 meses para inversionista.
     */
    private function availableMonths(): array
    {
        $earliest = $this->earliestAllowedMonth();
        $current  = now()->startOfMonth();

        $months = [];
        $cursor = $current->copy();

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
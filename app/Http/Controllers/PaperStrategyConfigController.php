<?php
namespace App\Http\Controllers;
use App\Models\BrokerAccount;
use App\Models\PaperStrategyConfig;
use App\Models\RealStrategySubscription;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;

class PaperStrategyConfigController extends Controller
{
    /**
     * Cuando una config de paper trading se activa, crea (si no existe ya)
     * una suscripcion PAUSADA en cada cuenta broker activa — asi la seccion
     * del simbolo aparece automaticamente en /trading/accounts sin que el
     * usuario tenga que agregarla a mano, pero sin operar en real hasta que
     * el usuario mismo decida activarla.
     */
    protected function ensurePausedSubscriptions(PaperStrategyConfig $config): void
    {
        $accounts = BrokerAccount::where('status', 'active')->get();
        foreach ($accounts as $account) {
            RealStrategySubscription::firstOrCreate(
                [
                    'broker_account_id'        => $account->id,
                    'paper_strategy_config_id' => $config->id,
                ],
                [
                    'user_id'  => $account->user_id,
                    'strategy' => $config->display_name,
                    'symbol'   => $config->symbol,
                    'interval' => $config->interval,
                    'status'   => 'paused',
                ]
            );
        }
    }

    public function toggleActive(PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');
        $config->active = !$config->active;
        $config->save();
        if ($config->active) {
            $this->ensurePausedSubscriptions($config);
        }
        return back()->with('status', $config->active
            ? "Configuración \"{$config->display_name}\" activada."
            : "Configuración \"{$config->display_name}\" desactivada.");
    }

    public function store(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'config_id'          => ['nullable', 'integer'],
            'strategy_name'      => ['required', 'string'],
            'symbol'             => ['required', 'string', 'max:20'],
            'interval'           => ['required', 'string', 'max:10'],
            'params'             => ['required', 'string'],
            'audited_months'     => ['nullable', 'integer', 'min:1'],
            'avg_win_rate'       => ['nullable', 'numeric'],
            'avg_monthly_pnl'    => ['nullable', 'numeric'],
            'avg_monthly_trades' => ['nullable', 'numeric'],
            'total_return_pct'   => ['nullable', 'numeric'],
            'star_wr'            => ['nullable', 'numeric'],
            'star_sharpe'        => ['nullable', 'numeric'],
            'star_ret'           => ['nullable', 'numeric'],
            'star_consistency'   => ['nullable', 'numeric'],
            'star_pf'            => ['nullable', 'numeric'],
            'star_rating'        => ['nullable', 'numeric'],
            'backtest_range_from'=> ['nullable', 'string'],
            'backtest_range_to'  => ['nullable', 'string'],
            'sharpe_ratio'       => ['nullable', 'numeric'],
            'consistency_pct'    => ['nullable', 'numeric'],
            'profit_factor'      => ['nullable', 'numeric'],
        ]);

        $params = json_decode($validated['params'], true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return back()->withErrors(['params' => 'Los parámetros no son JSON válido.']);
        }

        try {
            // Si viene config_id — actualizar config existente directamente
            if (!empty($validated['config_id'])) {
                $config = PaperStrategyConfig::findOrFail($validated['config_id']);
                // No tocar 'active' al editar - se mantiene el estado que ya tenia
                $config->update(['params' => $params]);
            } else {
                $config = PaperStrategyConfig::implementFromBacktest(
                    $validated['strategy_name'],
                    $validated['symbol'],
                    $validated['interval'],
                    $params
                );
            }
            $config->update([
                'audited_months'     => $validated['audited_months'] ?? null,
                'avg_win_rate'       => $validated['avg_win_rate'] ?? null,
                'avg_monthly_pnl'    => $validated['avg_monthly_pnl'] ?? null,
                'avg_monthly_trades' => $validated['avg_monthly_trades'] ?? null,
                'total_return_pct'   => $validated['total_return_pct'] ?? null,
                'star_wr'            => $validated['star_wr'] ?? null,
                'star_sharpe'        => $validated['star_sharpe'] ?? null,
                'star_ret'           => $validated['star_ret'] ?? null,
                'star_consistency'   => $validated['star_consistency'] ?? null,
                'star_pf'            => $validated['star_pf'] ?? null,
                'star_rating'        => $validated['star_rating'] ?? null,
                'backtest_range_from'=> $validated['backtest_range_from'] ?? null,
                'backtest_range_to'  => $validated['backtest_range_to'] ?? null,
                'sharpe_ratio'       => $validated['sharpe_ratio'] ?? null,
                'consistency_pct'    => $validated['consistency_pct'] ?? null,
                'profit_factor'      => $validated['profit_factor'] ?? null,
            ]);
        } catch (\InvalidArgumentException $e) {
            return back()->withErrors(['strategy_name' => $e->getMessage()]);
        }

        $this->ensurePausedSubscriptions($config);

        return redirect()->route('backtesting.index')
            ->with('status', "Configuración \"{$config->display_name}\" creada.");
    }

    public function implement(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'config_id'          => ['nullable', 'integer'],
            'strategy_name'      => ['required', 'string'],
            'symbol'             => ['required', 'string', 'max:20'],
            'interval'           => ['required', 'string', 'max:10'],
            'params'             => ['required', 'string'],
            'audited_months'     => ['nullable', 'integer', 'min:1'],
            'avg_win_rate'       => ['nullable', 'numeric'],
            'avg_monthly_pnl'    => ['nullable', 'numeric'],
            'avg_monthly_trades' => ['nullable', 'numeric'],
            'total_return_pct'   => ['nullable', 'numeric'],
            'star_wr'            => ['nullable', 'numeric'],
            'star_sharpe'        => ['nullable', 'numeric'],
            'star_ret'           => ['nullable', 'numeric'],
            'star_consistency'   => ['nullable', 'numeric'],
            'star_pf'            => ['nullable', 'numeric'],
            'star_rating'        => ['nullable', 'numeric'],
            'backtest_range_from'=> ['nullable', 'string'],
            'backtest_range_to'  => ['nullable', 'string'],
            'sharpe_ratio'       => ['nullable', 'numeric'],
            'consistency_pct'    => ['nullable', 'numeric'],
            'profit_factor'      => ['nullable', 'numeric'],
        ]);

        $params = json_decode($validated['params'], true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return back()->withErrors(['params' => 'Los parámetros no son JSON válido.']);
        }

        try {
            // Si viene config_id — actualizar config existente directamente
            if (!empty($validated['config_id'])) {
                $config = PaperStrategyConfig::findOrFail($validated['config_id']);
                // No tocar 'active' al editar - se mantiene el estado que ya tenia
                $config->update(['params' => $params]);
            } else {
                $config = PaperStrategyConfig::implementFromBacktest(
                    $validated['strategy_name'],
                    $validated['symbol'],
                    $validated['interval'],
                    $params
                );
            }
            $config->update([
                'audited_months'     => $validated['audited_months'] ?? null,
                'avg_win_rate'       => $validated['avg_win_rate'] ?? null,
                'avg_monthly_pnl'    => $validated['avg_monthly_pnl'] ?? null,
                'avg_monthly_trades' => $validated['avg_monthly_trades'] ?? null,
                'total_return_pct'   => $validated['total_return_pct'] ?? null,
                'star_wr'            => $validated['star_wr'] ?? null,
                'star_sharpe'        => $validated['star_sharpe'] ?? null,
                'star_ret'           => $validated['star_ret'] ?? null,
                'star_consistency'   => $validated['star_consistency'] ?? null,
                'star_pf'            => $validated['star_pf'] ?? null,
                'star_rating'        => $validated['star_rating'] ?? null,
                'backtest_range_from'=> $validated['backtest_range_from'] ?? null,
                'backtest_range_to'  => $validated['backtest_range_to'] ?? null,
                'sharpe_ratio'       => $validated['sharpe_ratio'] ?? null,
                'consistency_pct'    => $validated['consistency_pct'] ?? null,
                'profit_factor'      => $validated['profit_factor'] ?? null,
            ]);
        } catch (\InvalidArgumentException $e) {
            return back()->withErrors(['strategy_name' => $e->getMessage()]);
        }

        $this->ensurePausedSubscriptions($config);

        return redirect()->route('backtesting.index')
            ->with('status', "✓ Configuración \"{$config->display_name}\" implementada en Paper Trading.");
    }

    public function destroy(PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');
        $name = $config->display_name;
        $config->delete();
        return back()->with('status', "Configuración \"{$name}\" eliminada.");
    }
}

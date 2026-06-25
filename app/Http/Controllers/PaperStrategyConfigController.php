<?php
namespace App\Http\Controllers;
use App\Models\PaperStrategyConfig;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;

class PaperStrategyConfigController extends Controller
{
    public function index()
    {
        Gate::authorize('manageUsers');
        $configs = PaperStrategyConfig::orderBy('strategy_class')->orderBy('symbol')->get();
        return view('paper-trading.configs.index', compact('configs'));
    }

    public function toggleActive(PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');
        $config->active = !$config->active;
        $config->save();
        return back()->with('status', $config->active
            ? "Configuración \"{$config->display_name}\" activada."
            : "Configuración \"{$config->display_name}\" desactivada.");
    }

    public function edit(PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');
        return view('paper-trading.configs.edit', compact('config'));
    }

    public function update(Request $request, PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');
        $validated = $request->validate([
            'display_name' => ['required', 'string', 'max:100'],
            'interval'     => ['required', 'string', 'max:10'],
            'params'       => ['required', 'string'],
        ]);

        $params = json_decode($validated['params'], true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return back()->withErrors(['params' => 'Los parámetros no son JSON válido.']);
        }

        $config->update([
            'display_name' => $validated['display_name'],
            'interval'     => $validated['interval'],
            'params'       => $params,
        ]);

        return redirect()->route('paper-trading.configs.index')
            ->with('status', "Configuración \"{$config->display_name}\" actualizada.");
    }

    public function store(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'strategy_name'   => ['required', 'string'],
            'symbol'          => ['required', 'string', 'max:20'],
            'interval'        => ['required', 'string', 'max:10'],
            'params'          => ['required', 'string'],
            'audited_months'  => ['nullable', 'integer', 'min:1'],
            'avg_win_rate'    => ['nullable', 'numeric'],
            'avg_monthly_pnl' => ['nullable', 'numeric'],
        ]);

        $params = json_decode($validated['params'], true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return back()->withErrors(['params' => 'Los parámetros no son JSON válido.']);
        }

        try {
            $config = PaperStrategyConfig::implementFromBacktest(
                $validated['strategy_name'],
                $validated['symbol'],
                $validated['interval'],
                $params
            );

            // Guardar estadísticas del backtest
            $config->update([
                'audited_months'  => $validated['audited_months'] ?? null,
                'avg_win_rate'    => $validated['avg_win_rate'] ?? null,
                'avg_monthly_pnl' => $validated['avg_monthly_pnl'] ?? null,
            ]);

        } catch (\InvalidArgumentException $e) {
            return back()->withErrors(['strategy_name' => $e->getMessage()]);
        }

        return redirect()->route('backtesting.index')
            ->with('status', "Configuración \"{$config->display_name}\" creada.");
    }

    public function implement(Request $request)
    {
        Gate::authorize('manageUsers');
\Log::info('implement payload', $request->all());
        $validated = $request->validate([
            'strategy_name'   => ['required', 'string'],
            'symbol'          => ['required', 'string', 'max:20'],
            'interval'        => ['required', 'string', 'max:10'],
            'params'          => ['required', 'string'],
            'audited_months'  => ['nullable', 'integer', 'min:1'],
            'avg_win_rate'    => ['nullable', 'numeric'],
            'avg_monthly_pnl' => ['nullable', 'numeric'],
        ]);

        $params = json_decode($validated['params'], true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return back()->withErrors(['params' => 'Los parámetros no son JSON válido.']);
        }

        try {
            $config = PaperStrategyConfig::implementFromBacktest(
                $validated['strategy_name'],
                $validated['symbol'],
                $validated['interval'],
                $params
            );

            // Guardar estadísticas del backtest
            $config->update([
                'audited_months'  => $validated['audited_months'] ?? null,
                'avg_win_rate'    => $validated['avg_win_rate'] ?? null,
                'avg_monthly_pnl' => $validated['avg_monthly_pnl'] ?? null,
            ]);

        } catch (\InvalidArgumentException $e) {
            return back()->withErrors(['strategy_name' => $e->getMessage()]);
        }

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

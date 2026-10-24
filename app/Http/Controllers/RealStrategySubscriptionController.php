<?php

namespace App\Http\Controllers;

use App\Models\BrokerAccount;
use App\Models\PaperStrategyConfig;
use App\Models\RealStrategySubscription;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;

class RealStrategySubscriptionController extends Controller
{
    /**
     * Si la cuenta exige una sola posicion por simbolo (regla configurable
     * via broker_accounts.single_position_per_symbol, pensada para el limite
     * real de Bybit en modo One-Way), pausa cualquier OTRA suscripcion activa
     * del mismo simbolo en esta cuenta, dejando como unica activa a
     * $keepSubscriptionId. Si el flag esta en false (broker/modo que permite
     * varias posiciones simultaneas del mismo simbolo), no hace nada.
     */
    protected function enforceSingleActivePerSymbol(BrokerAccount $account, string $symbol, int $keepSubscriptionId): void
    {
        if (!$account->single_position_per_symbol) {
            return;
        }

        RealStrategySubscription::where('broker_account_id', $account->id)
            ->where('symbol', $symbol)
            ->where('id', '!=', $keepSubscriptionId)
            ->where('status', 'active')
            ->update(['status' => 'paused']);
    }

    /**
     * Suscribir una estrategia activa de paper_strategy_configs a una cuenta.
     */
    public function store(Request $request, BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');
        if ($account->user_id !== auth()->id()) abort(403);

        $validated = $request->validate([
            'paper_strategy_config_ids' => ['required', 'array'],
            'paper_strategy_config_ids.*' => ['exists:paper_strategy_configs,id'],
        ]);

        $added = 0;
        foreach ($validated['paper_strategy_config_ids'] as $configId) {
            $config = PaperStrategyConfig::findOrFail($configId);
            if (!$config->active) continue;

            $exists = RealStrategySubscription::where('broker_account_id', $account->id)
                ->where('paper_strategy_config_id', $config->id)->exists();

            if (!$exists) {
                RealStrategySubscription::create([
                    'user_id' => auth()->id(),
                    'broker_account_id' => $account->id,
                    'paper_strategy_config_id' => $config->id,
                    'strategy' => $config->display_name,
                    'symbol' => $config->symbol,
                    'interval' => $config->interval,
                    'status' => 'active',
                ]);
                $added++;
            }
        }

        if ($request->wantsJson() || $request->ajax()) {
            $account->refresh();
            $account->load('subscriptions.paperStrategyConfig');
            $html = view('trading.partials.subscriptions_list', compact('account'))->render();
            return response()->json([
                'success' => true,
                'added' => $added,
                'message' => $added > 0 ? "Configuración agregada correctamente." : "La configuración ya estaba agregada.",
                'html' => $html,
                'count' => $account->subscriptions->count()
            ]);
        }

        return back()->with('status', "Configuración agregada correctamente.");
    }

    /**
     * Suscribir TODAS las estrategias activas de paper_strategy_configs a una cuenta.
     */
    public function storeAll(Request $request, BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');
        if ($account->user_id !== auth()->id()) abort(403);

        $configs = PaperStrategyConfig::active()->get();
        $added = 0;

        foreach ($configs as $config) {
            $exists = RealStrategySubscription::where('broker_account_id', $account->id)
                ->where('paper_strategy_config_id', $config->id)->exists();

            if (!$exists) {
                RealStrategySubscription::create([
                    'user_id' => auth()->id(),
                    'broker_account_id' => $account->id,
                    'paper_strategy_config_id' => $config->id,
                    'strategy' => $config->display_name,
                    'symbol' => $config->symbol,
                    'interval' => $config->interval,
                    'status' => 'active',
                ]);
                $added++;
            }
        }

        if ($request->wantsJson() || $request->ajax()) {
            $account->refresh();
            $account->load('subscriptions.paperStrategyConfig');
            $html = view('trading.partials.subscriptions_list', compact('account'))->render();
            return response()->json([
                'success' => true,
                'added' => $added,
                'message' => $added > 0 ? "Todas las configuraciones agregadas." : "Todas ya estaban agregadas.",
                'html' => $html,
                'count' => $account->subscriptions->count()
            ]);
        }

        return back()->with('status', "Todas las configuraciones agregadas.");
    }
    public function toggle(BrokerAccount $account, RealStrategySubscription $subscription)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id() || $subscription->broker_account_id !== $account->id) {
            abort(403);
        }

        $activating = $subscription->status !== 'active';

        $subscription->status = $activating ? 'active' : 'paused';
        $subscription->save();

        if ($activating) {
            $this->enforceSingleActivePerSymbol($account, $subscription->symbol, $subscription->id);
        }

        return back()->with('status', $subscription->status === 'active'
            ? "Estrategia \"{$subscription->strategy}\" activada."
            : "Estrategia \"{$subscription->strategy}\" pausada.");
    }

    /**
     * Eliminar una suscripcion (solo si no tiene trades abiertos).
     */
    public function destroy(BrokerAccount $account, RealStrategySubscription $subscription)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id() || $subscription->broker_account_id !== $account->id) {
            abort(403);
        }

        if ($subscription->openTrades()->exists()) {
            return back()->withErrors([
                'subscription' => 'No puedes eliminar una suscripción con operaciones abiertas. Espera a que se cierren primero.',
            ]);
        }

        $name = $subscription->strategy;
        $subscription->delete();

        return back()->with('status', "Suscripción \"{$name}\" eliminada.");
    }
}

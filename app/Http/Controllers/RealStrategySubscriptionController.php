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

        if ($account->user_id !== auth()->id()) {
            abort(403);
        }

        $validated = $request->validate([
            'paper_strategy_config_id' => ['required', 'exists:paper_strategy_configs,id'],
        ]);

        $config = PaperStrategyConfig::findOrFail($validated['paper_strategy_config_id']);

        if (!$config->active) {
            return back()->withErrors(['config' => 'Esta estrategia no está activa en Paper Trading.']);
        }

        // Verificar que no existe ya esta suscripcion en esta cuenta
        $exists = RealStrategySubscription::where('broker_account_id', $account->id)
            ->where('paper_strategy_config_id', $config->id)
            ->exists();

        if ($exists) {
            return back()->withErrors(['config' => 'Esta estrategia ya está suscrita a esta cuenta.']);
        }

        $subscription = RealStrategySubscription::create([
            'user_id'                  => auth()->id(),
            'broker_account_id'        => $account->id,
            'paper_strategy_config_id' => $config->id,
            'strategy'                 => $config->display_name,
            'symbol'                   => $config->symbol,
            'interval'                 => $config->interval,
            'status'                   => 'active',
        ]);

        $this->enforceSingleActivePerSymbol($account, $config->symbol, $subscription->id);

        return back()->with('status', "Estrategia \"{$config->display_name}\" suscrita a {$account->label}.");
    }

    /**
     * Suscribir TODAS las estrategias activas de paper_strategy_configs a una cuenta.
     */
    public function storeAll(Request $request, BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id()) {
            abort(403);
        }

        $configs = PaperStrategyConfig::active()->get();
        $added   = 0;

        foreach ($configs as $config) {
            $exists = RealStrategySubscription::where('broker_account_id', $account->id)
                ->where('paper_strategy_config_id', $config->id)
                ->exists();

            if (!$exists) {
                RealStrategySubscription::create([
                    'user_id'                  => auth()->id(),
                    'broker_account_id'        => $account->id,
                    'paper_strategy_config_id' => $config->id,
                    'strategy'                 => $config->display_name,
                    'symbol'                   => $config->symbol,
                    'interval'                 => $config->interval,
                    'status'                   => 'active',
                ]);
                $added++;
            }
        }

        if ($account->single_position_per_symbol && $added > 0) {
            // Tras agregar todas, dejar activa solo la de mejor rating por
            // simbolo (evita quedar con varias activas a la vez cuando el
            // broker/modo no lo permite).
            $account->load(['subscriptions.paperStrategyConfig']);
            $account->subscriptions
                ->groupBy('symbol')
                ->each(function ($subsForSymbol, $symbol) use ($account) {
                    $best = $subsForSymbol
                        ->sortByDesc(fn ($s) => $s->paperStrategyConfig->star_rating ?? 0)
                        ->first();
                    if ($best) {
                        $this->enforceSingleActivePerSymbol($account, $symbol, $best->id);
                    }
                });
        }

        return back()->with('status', $added > 0
            ? "{$added} estrategia(s) añadidas a {$account->label}."
            : "Todas las estrategias ya estaban suscritas a {$account->label}.");
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

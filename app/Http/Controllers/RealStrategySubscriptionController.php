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
        if ($activating && $subscription->retire_on_close) {
            // D-04 (usuario inactivado) y D-63 (estrategia eliminada): se elimina al cerrar su operación abierta
            return back()->withErrors(['subscription' => 'Esta suscripción se eliminará cuando cierre su operación abierta'
                . ' (su usuario fue inactivado, o su configuración salió de Paper o fue eliminada). Después podrás agregarla de nuevo.']);
        }

        // 24-nov: ya no se pausa en silencio otra suscripción de la misma moneda (parecía que el botón no cambiaba
        // nada); el motor abre una sola posición por moneda y cuenta (real_trader: has_open_trade + Bybit).
        $subscription->status = $activating ? 'active' : 'paused';
        $subscription->save();

        $name = $this->label($subscription);

        return back()->with('status', $subscription->status === 'active'
            ? "Estrategia \"{$name}\" activada."
            : "Estrategia \"{$name}\" pausada.");
    }

    /**
     * Eliminar una suscripcion (solo sin operaciones vivas ni sin confirmar: openTrades(), R-04).
     */
    public function destroy(BrokerAccount $account, RealStrategySubscription $subscription)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id() || $subscription->broker_account_id !== $account->id) {
            abort(403);
        }

        if ($subscription->openTrades()->exists()) {
            return back()->withErrors([
                'subscription' => 'No puedes eliminar una suscripción con operaciones abiertas o sin confirmar con el broker. Espera a que se cierren o se concilien.',
            ]);
        }

        $name = $this->label($subscription);
        $subscription->delete();

        return back()->with('status', "Suscripción \"{$name}\" eliminada.");
    }

    /** D-72: el inversionista no ve nombres de estrategias (Config #N · moneda · temporalidad). */
    private function label(RealStrategySubscription $subscription): string
    {
        return auth()->user()?->isInversionista()
            ? \App\Support\StrategyLabel::anon([(int) $subscription->paper_strategy_config_id], [(string) $subscription->symbol], (string) $subscription->interval)
            : (string) $subscription->strategy;
    }
}

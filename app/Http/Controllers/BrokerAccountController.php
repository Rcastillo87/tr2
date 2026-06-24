<?php

namespace App\Http\Controllers;

use App\Models\BrokerAccount;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Illuminate\Validation\Rule;

class BrokerAccountController extends Controller
{
    public function store(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $user = auth()->user();

        $allowedTypes = $user->canCreateDemoAccounts() ? ['real', 'demo'] : ['real'];

        $validated = $request->validate([
            'broker'       => ['required', 'string', 'max:50'],
            'account_type' => ['required', Rule::in($allowedTypes)],
            'api_key'      => ['required', 'string', 'min:10'],
            'api_secret'   => ['required', 'string', 'min:10'],
        ]);

        // Verificar unicidad broker + tipo con mensaje claro
        $exists = BrokerAccount::where('user_id', $user->id)
            ->where('broker', $validated['broker'])
            ->where('account_type', $validated['account_type'])
            ->exists();

        if ($exists) {
            return back()->withErrors([
                'account_type' => 'Ya tienes una cuenta ' . ucfirst($validated['account_type']) . ' de ' . ucfirst($validated['broker']) . '. Solo se permite una por tipo.',
            ]);
        }

        // Label autogenerado: "Bybit Real" o "Bybit Demo"
        $label = ucfirst($validated['broker']) . ' ' . ucfirst($validated['account_type']);

        $user->brokerAccounts()->create([
            'broker'       => $validated['broker'],
            'account_type' => $validated['account_type'],
            'label'        => $label,
            'api_key'      => $validated['api_key'],
            'api_secret'   => $validated['api_secret'],
            'status'       => 'active',
        ]);

        return redirect()->route('trading.accounts')
            ->with('status', "Cuenta {$label} agregada correctamente.");
    }

    public function toggleStatus(BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id()) {
            abort(403);
        }

        $account->status = $account->status === 'active' ? 'paused' : 'active';
        $account->save();

        if ($account->status === 'paused') {
            $account->subscriptions()->where('status', 'active')->update(['status' => 'paused']);
        }

        return back()->with('status', $account->status === 'active'
            ? "Cuenta {$account->label} activada."
            : "Cuenta {$account->label} pausada. Sus suscripciones fueron pausadas.");
    }

    public function destroy(BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id()) {
            abort(403);
        }

        if ($account->subscriptions()->exists()) {
            return back()->withErrors([
                'account' => 'No puedes eliminar una cuenta con suscripciones. Elimínalas primero.',
            ]);
        }

        $label = $account->label;
        $account->delete();

        return redirect()->route('trading.accounts')
            ->with('status', "Cuenta {$label} eliminada.");
    }
}

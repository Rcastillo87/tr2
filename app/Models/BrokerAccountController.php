<?php

namespace App\Http\Controllers;

use App\Models\BrokerAccount;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Illuminate\Validation\Rule;

class BrokerAccountController extends Controller
{
    public function index()
    {
        Gate::authorize('viewRealTrading');

        $accounts = auth()->user()
            ->brokerAccounts()
            ->withCount('subscriptions')
            ->orderBy('created_at', 'desc')
            ->get();

        return view('real-trading.accounts.index', [
            'accounts' => $accounts,
        ]);
    }

    public function create()
    {
        Gate::authorize('viewRealTrading');

        return view('real-trading.accounts.create');
    }

    public function store(Request $request)
    {
        Gate::authorize('viewRealTrading');

        $user = auth()->user();

        $allowedTypes = $user->canCreateDemoAccounts() ? ['real', 'demo'] : ['real'];

        $validated = $request->validate([
            'broker' => ['required', 'string', 'max:50'],
            'account_type' => ['required', Rule::in($allowedTypes)],
            'label' => ['required', 'string', 'max:100'],
            'api_key' => ['required', 'string', 'min:10'],
            'api_secret' => ['required', 'string', 'min:10'],
        ]);

        $user->brokerAccounts()->create([
            'broker' => $validated['broker'],
            'account_type' => $validated['account_type'],
            'label' => $validated['label'],
            'api_key' => $validated['api_key'],
            'api_secret' => $validated['api_secret'],
            'status' => 'active',
        ]);

        return redirect()->route('real-trading.accounts.index')
            ->with('status', 'Cuenta agregada correctamente.');
    }

    public function toggleStatus(BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id()) {
            abort(403);
        }

        $account->status = $account->status === 'active' ? 'paused' : 'active';
        $account->save();

        // Si se pausa la cuenta, pausar tambien sus suscripciones activas
        if ($account->status === 'paused') {
            $account->subscriptions()->where('status', 'active')->update(['status' => 'paused']);
        }

        return back()->with('status', $account->status === 'active'
            ? 'Cuenta activada.'
            : 'Cuenta pausada. Sus suscripciones fueron pausadas.');
    }

    public function destroy(BrokerAccount $account)
    {
        Gate::authorize('viewRealTrading');

        if ($account->user_id !== auth()->id()) {
            abort(403);
        }

        if ($account->subscriptions()->exists()) {
            return back()->withErrors(['account' => 'No puedes eliminar una cuenta con suscripciones asociadas. Elimina o pausa las suscripciones primero.']);
        }

        $account->delete();

        return redirect()->route('real-trading.accounts.index')
            ->with('status', 'Cuenta eliminada.');
    }
}

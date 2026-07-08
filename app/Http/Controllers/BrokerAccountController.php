<?php

namespace App\Http\Controllers;

use App\Models\BrokerAccount;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Http;
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
            'api_secret'   => ['required_if:broker,bybit', 'nullable', 'string', 'min:10'],
            'ig_username'  => ['required_if:broker,ig', 'nullable', 'string'],
            'ig_password'  => ['required_if:broker,ig', 'nullable', 'string'],
        ]);

        // Para IG armamos credentials_extra como JSON; api_secret no aplica (queda vacio)
        $credentialsExtra = null;
        if ($validated['broker'] === 'ig') {
            $credentialsExtra = json_encode([
                'username' => $validated['ig_username'],
                'password' => $validated['ig_password'],
            ]);
            $validated['api_secret'] = '';
        }

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

        // Validar credenciales con el motor Python antes de guardar
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(15)->post(
                config('trading.python_engine_url') . '/v1/broker/validate-credentials',
                [
                    'broker'            => $validated['broker'],
                    'account_type'      => $validated['account_type'],
                    'api_key'           => $validated['api_key'],
                    'api_secret'        => $validated['api_secret'],
                    'credentials_extra' => $credentialsExtra,
                ]
            );

            if (!$response->successful()) {
                return back()->withErrors(['api_key' => 'No se pudo conectar al motor para validar las credenciales. Intenta de nuevo.']);
            }

            $result = $response->json();

            if (!($result['valid'] ?? false)) {
                return back()->withErrors([
                    'api_key' => $result['message'] ?? 'Credenciales inválidas.',
                ]);
            }

        } catch (\Throwable $e) {
            return back()->withErrors(['api_key' => 'Error validando credenciales: ' . $e->getMessage()]);
        }

        // Label autogenerado: "Bybit Real" o "Bybit Demo"
        $label = ucfirst($validated['broker']) . ' ' . ucfirst($validated['account_type']);

        $user->brokerAccounts()->create([
            'broker'            => $validated['broker'],
            'account_type'      => $validated['account_type'],
            'label'             => $label,
            'api_key'           => $validated['api_key'],
            'api_secret'        => $validated['api_secret'],
            'credentials_extra' => $credentialsExtra,
            'status'            => 'active',
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

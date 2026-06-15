<?php

namespace App\Http\Controllers;

use App\Models\RealStrategySubscription;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;

class UserManagementController extends Controller
{
    public function index()
    {
        Gate::authorize('manageUsers');

        $users = User::orderBy('created_at', 'desc')->paginate(10);

        return view('users.index', [
            'users' => $users,
        ]);
    }

    public function toggleActive(Request $request, User $user)
    {
        Gate::authorize('manageUsers');

        if ($user->id === auth()->id()) {
            return back()->withErrors(['user' => 'No puedes inactivar tu propia cuenta.']);
        }

        $user->is_active = ! $user->is_active;
        $user->save();

        // Al inactivar: pausar todas sus suscripciones de trading real,
        // de modo que el motor de ejecucion deje de abrir nuevas posiciones
        // para esa cuenta. Las posiciones abiertas no se tocan.
        if (! $user->is_active) {
            RealStrategySubscription::where('user_id', $user->id)
                ->where('status', 'active')
                ->update(['status' => 'paused']);
        }

        return back()->with('status', $user->is_active
            ? 'Usuario activado correctamente.'
            : 'Usuario inactivado. Sus estrategias en real fueron pausadas.');
    }
}

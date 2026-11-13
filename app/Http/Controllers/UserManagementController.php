<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\UserDeactivation;
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

        // Una transacción: estado del usuario y sus suscripciones Real (UserDeactivation; decisión del dueño 13-nov)
        $r = app(UserDeactivation::class)->setActive($user, ! $user->is_active);

        return back()->with('status', $user->is_active
            ? 'Usuario activado. Debe elegir de nuevo sus estrategias en real.'
            : "Usuario inactivado. Suscripciones en real eliminadas: {$r['deleted']}"
              . ($r['kept'] ? "; {$r['kept']} con operaciones vivas siguen hasta que terminen su ciclo y luego se eliminan." : '.'));
    }
}

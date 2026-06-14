<?php

namespace App\Http\Middleware;

use Carbon\Carbon;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Symfony\Component\HttpFoundation\Response;

class ExpireSessionAtMidnightColombia
{
    /**
     * Expira la sesion en la primera medianoche (America/Bogota) que ocurra
     * despues del momento del login, con un tope maximo de 24 horas.
     */
    public function handle(Request $request, Closure $next): Response
    {
        if (Auth::check()) {
            $loginAt = $request->session()->get('login_at');

            if ($loginAt === null) {
                // Primer request autenticado de esta sesion: registrar el momento de login
                $request->session()->put('login_at', now()->toIso8601String());
            } else {
                $loginAt = Carbon::parse($loginAt);
                $loginColombia = $loginAt->copy()->setTimezone('America/Bogota');

                // Proxima medianoche en Colombia despues del login
                $expiresAt = $loginColombia->copy()->startOfDay()->addDay();

                // Tope maximo de 24 horas desde el login, lo que ocurra primero
                $hardLimit = $loginAt->copy()->addHours(24);

                $effectiveExpiry = $expiresAt->lessThan($hardLimit) ? $expiresAt : $hardLimit;

                if (now()->greaterThanOrEqualTo($effectiveExpiry)) {
                    Auth::logout();

                    $request->session()->invalidate();
                    $request->session()->regenerateToken();

                    return redirect()->route('login')
                        ->withErrors(['email' => 'Tu sesión ha expirado, por favor inicia sesión de nuevo.']);
                }
            }
        }

        return $next($request);
    }
}

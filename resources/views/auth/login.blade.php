<x-guest-layout>
    <div class="mb-5">
        <h1 class="text-lg font-semibold" style="color:var(--color-text-primary);">Iniciar sesión</h1>
        <p class="text-[11px] mt-1" style="color:var(--color-text-muted);">Ingresa tus credenciales para acceder al dashboard</p>
    </div>

    <x-auth-session-status class="mb-4" :status="session('status')" />

    <form method="POST" action="{{ route('login') }}" class="space-y-4">
        @csrf

        <div>
            <x-input-label for="email" :value="__('Email')" />
            <x-text-input id="email" type="email" name="email" :value="old('email')" required autofocus autocomplete="username" placeholder="tu@email.com" />
            <x-input-error :messages="$errors->get('email')" />
        </div>

        <div>
            <x-input-label for="password" :value="__('Contraseña')" />
            <x-text-input id="password"
                            type="password"
                            name="password"
                            required autocomplete="current-password" placeholder="••••••••" />
            <x-input-error :messages="$errors->get('password')" />
        </div>

        <div class="flex items-center justify-between">
            <label for="remember_me" class="inline-flex items-center gap-2 cursor-pointer">
                <input id="remember_me" type="checkbox" name="remember"
                       class="rounded border w-4 h-4"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); accent-color:var(--color-info);">
                <span class="text-[11px]" style="color:var(--color-text-secondary);">{{ __('Recordarme') }}</span>
            </label>

            @if (Route::has('password.request'))
                <a class="text-[11px] hover:underline" style="color:var(--color-info);" href="{{ route('password.request') }}">
                    {{ __('¿Olvidaste tu contraseña?') }}
                </a>
            @endif
        </div>

        <x-primary-button class="w-full justify-center py-2.5">
            {{ __('Iniciar sesión') }}
        </x-primary-button>
    </form>
</x-guest-layout>

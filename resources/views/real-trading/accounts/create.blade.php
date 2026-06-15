@extends('layouts.app')

@section('title', 'Nueva cuenta — Trading Real')
@section('header', 'Trading real — Nueva cuenta')

@section('content')

    <div class="mb-4">
        <a href="{{ route('real-trading.accounts.index') }}" class="text-[11px]" style="color:var(--color-info);">← Volver a cuentas</a>
    </div>

    @if ($errors->any())
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
            {{ $errors->first() }}
        </div>
    @endif

    <div class="rounded-lg border p-4 sm:p-5 max-w-lg" style="background:var(--color-surface); border-color:var(--color-border-soft);">

        <form method="POST" action="{{ route('real-trading.accounts.store') }}" class="space-y-4">
            @csrf

            <div>
                <x-input-label for="broker" value="Broker" />
                <select name="broker" id="broker" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="bybit" {{ old('broker') === 'bybit' ? 'selected' : '' }}>Bybit</option>
                </select>
                <x-input-error :messages="$errors->get('broker')" />
            </div>

            @if (auth()->user()->canCreateDemoAccounts())
                <div>
                    <x-input-label for="account_type" value="Tipo de cuenta" />
                    <select name="account_type" id="account_type" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        <option value="real" {{ old('account_type', 'real') === 'real' ? 'selected' : '' }}>Real</option>
                        <option value="demo" {{ old('account_type') === 'demo' ? 'selected' : '' }}>Demo</option>
                    </select>
                    <x-input-error :messages="$errors->get('account_type')" />
                </div>
            @else
                <input type="hidden" name="account_type" value="real">
                <div class="rounded-lg p-3 text-[11px]" style="background:var(--color-surface-raised); color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
                    Tipo de cuenta: <span style="color:var(--color-text-primary);">Real</span>
                </div>
            @endif

            <div>
                <x-input-label for="label" value="Nombre de la cuenta" />
                <x-text-input id="label" type="text" name="label" :value="old('label')" required placeholder="Ej: Mi cuenta principal" />
                <x-input-error :messages="$errors->get('label')" />
            </div>

            <div>
                <x-input-label for="api_key" value="API Key" />
                <x-text-input id="api_key" type="text" name="api_key" :value="old('api_key')" required placeholder="Clave API del broker" autocomplete="off" />
                <x-input-error :messages="$errors->get('api_key')" />
            </div>

            <div>
                <x-input-label for="api_secret" value="API Secret" />
                <x-text-input id="api_secret" type="password" name="api_secret" required placeholder="Secreto API del broker" autocomplete="off" />
                <x-input-error :messages="$errors->get('api_secret')" />
                <p class="text-[10px] mt-1" style="color:var(--color-text-muted);">Tus credenciales se almacenan cifradas y nunca se muestran de nuevo.</p>
            </div>

            <x-primary-button class="w-full justify-center py-2.5">
                Guardar cuenta
            </x-primary-button>
        </form>
    </div>

@endsection

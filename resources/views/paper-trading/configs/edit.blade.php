@extends('layouts.app')

@section('title', 'Editar configuración')
@section('header', 'Paper Trading — Editar configuración')

@section('content')

    <div class="mb-4">
        <a href="{{ route('paper-trading.configs.index') }}" class="text-[11px]" style="color:var(--color-info);">← Volver a configuraciones</a>
    </div>

    @if ($errors->any())
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
            {{ $errors->first() }}
        </div>
    @endif

    <div class="rounded-lg border p-4 sm:p-5 max-w-2xl" style="background:var(--color-surface); border-color:var(--color-border-soft);">

        <div class="mb-4 p-3 rounded-lg" style="background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
            <p class="text-[11px]" style="color:var(--color-text-muted);">Clase Python</p>
            <p class="text-sm font-mono" style="color:var(--color-text-primary);">{{ $config->strategy_class }}</p>
            <p class="text-[11px] mt-1" style="color:var(--color-text-muted);">Símbolo</p>
            <p class="text-sm font-mono" style="color:var(--color-text-primary);">{{ $config->symbol }}</p>
            <p class="text-[10px] mt-2" style="color:var(--color-text-muted);">La clase y el símbolo no son editables para evitar inconsistencias con trades abiertos.</p>
        </div>

        <form method="POST" action="{{ route('paper-trading.configs.update', $config) }}" class="space-y-4">
            @csrf
            @method('PATCH')

            <div>
                <x-input-label for="display_name" value="Nombre de la configuración" />
                <x-text-input id="display_name" name="display_name" type="text"
                              :value="old('display_name', $config->display_name)" required />
                <x-input-error :messages="$errors->get('display_name')" />
            </div>

            <div>
                <x-input-label for="interval" value="Intervalo" />
                <select name="interval" id="interval"
                        class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    @foreach (['60' => 'H1 (60 min)', '120' => 'H2 (120 min)', '240' => 'H4 (240 min)', 'D' => 'D1 (Diario)'] as $val => $label)
                        <option value="{{ $val }}" {{ old('interval', $config->interval) === $val ? 'selected' : '' }}>
                            {{ $label }}
                        </option>
                    @endforeach
                </select>
                <x-input-error :messages="$errors->get('interval')" />
            </div>

            <div>
                <x-input-label for="params" value="Parámetros (JSON)" />
                <textarea id="params" name="params" rows="14" required
                          class="w-full rounded-lg px-3 py-2 text-sm border font-mono focus:outline-none"
                          style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">{{ old('params', json_encode($config->params, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)) }}</textarea>
                <x-input-error :messages="$errors->get('params')" />
                <p class="text-[10px] mt-1" style="color:var(--color-text-muted);">
                    Parámetros clave: sl_pct, tp_pct, be_pct, max_duration, regime_filter, allowed_regimes, risk_per_trade_pct.
                    Parámetros específicos según la clase: mode (VwapStrategy), bb_std/rsi_ob (MeanReversionStrategy), ema_fast/donchian_period (EmaDonchianStrategy).
                </p>
            </div>

            <x-primary-button class="w-full justify-center py-2.5">
                Guardar cambios
            </x-primary-button>
        </form>
    </div>

@endsection

@extends('layouts.app')
@section('title', 'Configurar Backtest')
@section('header', 'Configurar Backtest')

@section('content')
<style>
    .multi-select-container { position: relative; }
    .multi-select-dropdown {
        position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
        max-height: 200px; overflow-y: auto; border-radius: 0.5rem;
        border: 1px solid var(--color-border-strong); background: var(--color-surface-raised); margin-top: 4px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5); display: none;
    }
    .multi-select-option { padding: 8px 12px; cursor: pointer; font-size: 11px; color: var(--color-text-muted); }
    .multi-select-option:hover { background: var(--color-surface); color: var(--color-text-primary); }
    .tag { background: var(--color-info); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; display: flex; align-items: center; gap: 4px; }
    .tag-close { cursor: pointer; font-weight: bold; }
    .tab-btn { transition: all 0.15s ease-in-out; }
    .tab-btn.active { background: var(--color-surface); border-bottom: 2px solid var(--color-info); color: var(--color-text-primary); }
    select option { background-color: var(--color-surface-raised) !important; color: var(--color-text-primary) !important; }
    select option:checked { background-color: var(--color-info) !important; color: #fff !important; }
</style>

<div class="mb-3 flex justify-between items-center">
    @php
        // El controlador envía $strategyToLoad y $backtestToLoad
        $stratId = request('strategy_id') ?? ($strategyToLoad->id ?? ($backtestToLoad->strategy_id ?? null));
        if ($stratId) {
            $returnUrl = route('backtesting.history', $stratId);
            $returnLabel = '← Volver al Historial';
        } else {
            $returnUrl = route('strategies.index');
            $returnLabel = '← Volver a Estrategias';
        }
    @endphp
    <a href="{{ $returnUrl }}" class="text-[11px] transition-colors" style="color:var(--color-text-muted);">{{ $returnLabel }}</a>
    
    @php
        $activeStrategy = $backtestToLoad->strategy ?? $strategyToLoad ?? null;
    @endphp
    @if($activeStrategy)
    <div class="flex items-center gap-2 px-2.5 py-1 rounded border" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
        <span class="text-[11px] font-medium" style="color:var(--color-text-primary);">{{ $activeStrategy->name }}</span>
    </div>
    @endif
</div>

@if ($error)
    <div class="rounded-lg border p-3 mb-3 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">{{ $error }}</div>
@endif

<div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    
    <!-- Pestañas -->
    <div class="flex border-b" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
        <button type="button" onclick="switchTab('config')" id="tab-btn-config" class="tab-btn active px-4 py-2.5 text-[11px] font-medium w-1/3 text-center" style="color:var(--color-text-muted);">1. Configuración Base</button>
        <button type="button" onclick="switchTab('apertura')" id="tab-btn-apertura" class="tab-btn px-4 py-2.5 text-[11px] font-medium w-1/3 text-center border-l border-r" style="color:var(--color-text-muted); border-color:var(--color-border-soft);">2. Filtros de Apertura</button>
        <button type="button" onclick="switchTab('cierre')" id="tab-btn-cierre" class="tab-btn px-4 py-2.5 text-[11px] font-medium w-1/3 text-center" style="color:var(--color-text-muted);">3. Filtros de Cierre</button>
    </div>

    <form method="POST" action="#" onsubmit="return false" id="backtestForm" class="p-4 space-y-4">
        @csrf
        
        <!-- Inputs ocultos limpios -->
        <input type="hidden" id="current_backtest_id" name="backtest_id" value="{{ request('backtest_id', $backtestToLoad->id ?? '') }}">
        <input type="hidden" name="strategy_id" value="{{ request('strategy_id', $backtestToLoad->strategy_id ?? '') }}">

        <!-- PESTAÑA 1 -->
        <div id="tab-config" class="space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Símbolos (Selección Múltiple)</label>
                    <div class="multi-select-container">
                        <div onclick="event.stopPropagation(); toggleSymbolsDropdown()" id="symbols-input" class="w-full rounded-lg px-3 py-2 text-sm border min-h-[38px] flex flex-wrap gap-1 items-center cursor-pointer" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                            <span id="symbols-placeholder" class="text-sm" style="color:var(--color-text-muted);">Seleccionar monedas...</span>
                        </div>
                        <div id="symbols-dropdown" class="multi-select-dropdown" onclick="event.stopPropagation()">
                            <div class="p-2 border-b" style="border-color:var(--color-border-soft);">
                                <input type="text" id="symbols-search" onkeyup="filterSymbols()" placeholder="Buscar moneda..." class="w-full rounded px-2 py-1 text-[11px] border outline-none" style="background:var(--color-surface); border-color:var(--color-border-soft); color:var(--color-text-primary);">
                            </div>
                            <div id="symbols-list"></div>
                        </div>
                    </div>
                    <div id="hidden-symbols-inputs"></div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Intervalo</label>
                        <select name="interval" class="w-full rounded-lg px-3 py-2 text-sm border outline-none" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                            @foreach ($intervals as $iv)
                                @php
                                    $intervalLabels = ['1' => '1m', '5' => '5m', '15' => '15m', '30' => '30m', '60' => 'H1', '120' => 'H2', '240' => 'H4', 'D' => 'D1'];
                                    $label = $intervalLabels[$iv] ?? $iv;
                                @endphp
                                <option value="{{ $iv }}" {{ old('interval', $backtestToLoad->interval ?? '60') == $iv ? 'selected' : '' }}>{{ $label }}</option>
                            @endforeach
                        </select>
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Meses a probar</label>
                        <select name="months" class="w-full rounded-lg px-3 py-2 text-sm border outline-none" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                            @foreach ([1, 3, 6, 12, 18, 24] as $m)
                                <option value="{{ $m }}" {{ old('months', $backtestToLoad->months ?? 6) == $m ? 'selected' : '' }}>{{ $m }} meses</option>
                            @endforeach
                        </select>
                    </div>
                </div>
            </div>

            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-3" style="color:var(--color-text-secondary);">Configuración de Riesgo y Operación</h4>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Stop Loss %</label>
                        <input type="number" step="0.1" name="sl_pct" value="{{ old('sl_pct', $backtestToLoad->config_params['sl_pct'] ?? '1.5') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit 1 %</label>
                        <input type="number" step="0.1" name="tp_pct" value="{{ old('tp_pct', $backtestToLoad->config_params['tp_pct'] ?? '3.0') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Balance Inicial ($)</label>
                        <input type="number" step="100" name="initial_balance" value="{{ old('initial_balance', $backtestToLoad->config_params['initial_balance'] ?? '10000') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Riesgo / Trade %</label>
                        <input type="number" step="0.1" name="risk_per_trade_pct" value="{{ old('risk_per_trade_pct', $backtestToLoad->config_params['risk_per_trade_pct'] ?? '1.0') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Comisión % (Auto)</label>
                        <input type="number" step="0.001" name="commission_pct" value="{{ old('commission_pct', $backtestToLoad->config_params['commission_pct'] ?? '0.055') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                </div>
            </div>

            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Parámetros de la Estrategia (JSON)</label>
                                    @php
                        // Limpiamos los filtros del JSON para que no se mezclen con la UI
                        $cleanConfig = $backtestToLoad ? ($backtestToLoad->strategy_snapshot['config'] ?? []) : ($strategyToLoad->config ?? []);
                        $keysToRemove = ['sl_pct', 'tp_pct', 'tp2_pct', 'tp3_pct', 'tp4_pct', 'be_pct', 'max_duration',
                              'commission_pct', 'risk_per_trade_pct', 'regime_filter', 'regime_adx_trending',
                              'regime_adx_ranging', 'regime_ambiguous_as', 'volume_filter', 'volume_filter_period',
                              'volume_filter_mult', 'macro_trend_filter', 'trailing_mode', 'trailing_distance_pct', 'trailing_atr_mult'];
                        foreach ($keysToRemove as $k) {
                            unset($cleanConfig[$k]);
                        }
                        $jsonString = json_encode($cleanConfig, JSON_PRETTY_PRINT);
                    @endphp
                    <textarea name="strategy_config_override" rows="8" class="w-full rounded-lg px-3 py-1.5 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-profit); resize: vertical;" placeholder='{"fast_period": 9}'>{{ old('strategy_config_override', $jsonString) }}</textarea>
            </div>
        </div>

        <!-- PESTAÑA 2 -->
        <div id="tab-apertura" class="space-y-4" style="display: none;">
            <div class="rounded-lg p-3 border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                <label class="flex items-center gap-2 cursor-pointer text-[12px]" style="color:var(--color-text-primary);">
                    <input type="checkbox" name="regime_filter" value="1" class="w-4 h-4 rounded" style="accent-color:var(--color-info);" {{ old('regime_filter', !empty($backtestToLoad->config_params['regime_filter'])) ? 'checked' : '' }}>
                    Régimen de Mercado (ADX)
                </label>
                <div class="grid grid-cols-3 gap-2 mt-3 pl-6">
                    <div>
                        <label class="block text-[10px] mb-1" style="color:var(--color-text-muted);">ADX Tendencia (Mayor a)</label>
                        <input type="number" name="regime_adx_trending" value="{{ old('regime_adx_trending', $backtestToLoad->config_params['regime_adx_trending'] ?? '25') }}" class="w-full rounded px-2 py-1 text-[11px] border outline-none font-mono" style="background:var(--color-surface); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[10px] mb-1" style="color:var(--color-text-muted);">ADX Lateral (Menor a)</label>
                        <input type="number" name="regime_adx_ranging" value="{{ old('regime_adx_ranging', $backtestToLoad->config_params['regime_adx_ranging'] ?? '20') }}" class="w-full rounded px-2 py-1 text-[11px] border outline-none font-mono" style="background:var(--color-surface); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[10px] mb-1" style="color:var(--color-text-muted);">Caso Ambiguo</label>
                        <select name="regime_ambiguous_as" class="w-full rounded px-2 py-1 text-[11px] border outline-none" style="background:var(--color-surface); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                            <option value="RANGING" {{ old('regime_ambiguous_as', $backtestToLoad->config_params['regime_ambiguous_as'] ?? 'RANGING') == 'RANGING' ? 'selected' : '' }}>Lateral (Asumir Rango)</option>
                            <option value="TRENDING" {{ old('regime_ambiguous_as', $backtestToLoad->config_params['regime_ambiguous_as'] ?? 'RANGING') == 'TRENDING' ? 'selected' : '' }}>Tendencia (Asumir Tendencia)</option>
                            <option value="ignorar" {{ old('regime_ambiguous_as', $backtestToLoad->config_params['regime_ambiguous_as'] ?? 'RANGING') == 'ignorar' ? 'selected' : '' }}>No Operar (Filtrar)</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="rounded-lg p-3 border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                <label class="flex items-center gap-2 cursor-pointer text-[12px]" style="color:var(--color-text-primary);">
                    <input type="checkbox" name="volume_filter" value="1" class="w-4 h-4 rounded" style="accent-color:var(--color-info);" {{ old('volume_filter', !empty($backtestToLoad->config_params['volume_filter'])) ? 'checked' : '' }}>
                    Filtro de Volumen Mínimo
                </label>
                <div class="grid grid-cols-2 gap-2 mt-3 pl-6">
                    <div>
                        <label class="block text-[10px] mb-1" style="color:var(--color-text-muted);">Período Promedio</label>
                        <input type="number" name="volume_filter_period" value="{{ old('volume_filter_period', $backtestToLoad->config_params['volume_filter_period'] ?? '20') }}" class="w-full rounded px-2 py-1 text-[11px] border outline-none font-mono" style="background:var(--color-surface); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[10px] mb-1" style="color:var(--color-text-muted);">Multiplicador (Ej: 1.2x)</label>
                        <input type="number" step="0.1" name="volume_filter_mult" value="{{ old('volume_filter_mult', $backtestToLoad->config_params['volume_filter_mult'] ?? '1.2') }}" class="w-full rounded px-2 py-1 text-[11px] border outline-none font-mono" style="background:var(--color-surface); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                </div>
            </div>

            <div class="rounded-lg p-3 border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                <label class="flex items-center gap-2 cursor-pointer text-[12px]" style="color:var(--color-text-primary);">
                    <input type="checkbox" name="macro_trend_filter" value="1" class="w-4 h-4 rounded" style="accent-color:var(--color-info);" {{ old('macro_trend_filter', !empty($backtestToLoad->config_params['macro_trend_filter'])) ? 'checked' : '' }}>
                    Tendencia Macro H4 (EMA 50)
                </label>
            </div>
        </div>

        <!-- PESTAÑA 3 -->
        <div id="tab-cierre" class="space-y-4" style="display: none;">
            <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Duración máxima (velas)</label>
                    <input type="number" name="max_duration" value="{{ old('max_duration', $backtestToLoad->config_params['max_duration'] ?? '24') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>
                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Break-even %</label>
                    <input type="number" step="0.1" name="be_pct" value="{{ old('be_pct', $backtestToLoad->config_params['be_pct'] ?? '2.0') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>
                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Modo Trailing Stop</label>
                    <select name="trailing_mode" id="trailing_mode_select" onchange="toggleTrailingInputs()" class="w-full rounded-lg px-3 py-2 text-sm border outline-none" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        <option value="none" {{ old('trailing_mode', $backtestToLoad->config_params['trailing_mode'] ?? '') == 'none' ? 'selected' : '' }}>Ninguno</option>
                        <option value="fixed" {{ old('trailing_mode', $backtestToLoad->config_params['trailing_mode'] ?? '') == 'fixed' ? 'selected' : '' }}>Fijo (%)</option>
                        <option value="atr" {{ old('trailing_mode', $backtestToLoad->config_params['trailing_mode'] ?? '') == 'atr' ? 'selected' : '' }}>Dinámico (ATR)</option>
                    </select>
                </div>

                <!-- Inputs ocultos para Trailing -->
                <div id="div_trailing_fixed" style="display: none;">
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Distancia Trailing Fijo (%)</label>
                    <input type="number" step="0.1" name="trailing_distance_pct" value="{{ old('trailing_distance_pct', $backtestToLoad->config_params['trailing_distance_pct'] ?? '1.0') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>

                <div id="div_trailing_atr" style="display: none;">
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Multiplicador ATR</label>
                    <input type="number" step="0.1" name="trailing_atr_mult" value="{{ old('trailing_atr_mult', $backtestToLoad->config_params['trailing_atr_mult'] ?? '2.0') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>

                <div id="div_trailing_buffer" style="display: none;">
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Activación Trailing (%)</label>
                    <input type="number" step="0.1" name="trailing_activation_buffer_pct" value="{{ old('trailing_activation_buffer_pct', $backtestToLoad->config_params['trailing_activation_buffer_pct'] ?? '0.5') }}" class="w-full rounded-lg px-3 py-2 text-sm border outline-none font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>
            </div>

            {{-- Checkboxes de cierre --}}
            <div class="rounded-lg p-3 border space-y-3" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                <label class="flex items-start gap-2 cursor-pointer">
                    <input type="checkbox" name="max_duration_profit" value="1" class="w-4 h-4 rounded mt-0.5" style="accent-color:var(--color-info);" {{ old('max_duration_profit', !empty($backtestToLoad->config_params['max_duration_profit'])) ? 'checked' : '' }}>
                    <div>
                        <span class="text-[12px] font-medium block" style="color:var(--color-text-primary);">Cierre por tiempo inteligente</span>
                        <span class="text-[10px] block" style="color:var(--color-text-muted);">Cierra al llegar al tiempo máximo solo si está en ganancia.</span>
                    </div>
                </label>

                <label class="flex items-start gap-2 cursor-pointer">
                    <input type="checkbox" name="close_on_opposite" value="1" class="w-4 h-4 rounded mt-0.5" style="accent-color:var(--color-info);" {{ old('close_on_opposite', !empty($backtestToLoad->config_params['close_on_opposite'])) ? 'checked' : '' }}>
                    <div>
                        <span class="text-[12px] font-medium block" style="color:var(--color-text-primary);">Cierre por Señal Opuesta</span>
                        <span class="text-[10px] block" style="color:var(--color-text-muted);">Si la estrategia emite una señal contraria, cierra la posición al instante.</span>
                    </div>
                </label>
            </div>
        </div> <!-- Cierre de la Tarjeta Oscura -->

        <!-- Footer con Botones (DENTRO de la tarjeta) -->
        <div class="border-t pt-4 mt-6 flex justify-between items-center" style="border-color:var(--color-border-soft);">
            <button type="button" onclick="nextTab()" id="btn-next" class="text-[11px] px-3 py-1.5 rounded border transition-colors" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-info);">
                Siguiente paso →
            </button>
            <button type="submit" onclick="showLoading()" class="text-sm font-medium px-6 py-2 rounded-lg transition-colors" style="background:var(--color-info); color:#fff;">
                🚀 Ejecutar Backtest
            </button>
        </div>
    </form>


{{-- RESULTADOS (Bloque único, sin duplicados) --}}
<div id="results-container"></div>

<script>
    // Esta función se define aquí para que esté disponible cuando los resultados carguen por AJAX
    function confirmSaveBacktest() {
        Swal.fire({
            title: '¿Guardar Backtest?',
            text: "Se guardará esta configuración en el historial.",
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#10B981',
            cancelButtonColor: '#374151',
            confirmButtonText: 'Sí, guardar',
            cancelButtonText: 'Cancelar',
            background: '#1f2937',
            color: '#f3f4f6'
        }).then((result) => {
            if (result.isConfirmed) {
                Swal.fire({
                    title: 'Guardando...',
                    allowOutsideClick: false,
                    didOpen: () => { Swal.showLoading(); }
                });
                
                // Envío por AJAX
                const form = document.getElementById('saveBacktestForm');
                const formData = new FormData(form);
                
                fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRF-TOKEN': '{{ csrf_token() }}',
                        'Accept': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Guardamos el ID en un input oculto para el próximo backtest
                        let hiddenId = document.getElementById('current_backtest_id');
                        if (!hiddenId) {
                            hiddenId = document.createElement('input');
                            hiddenId.type = 'hidden';
                            hiddenId.id = 'current_backtest_id';
                            hiddenId.name = 'backtest_id';
                            document.getElementById('backtestForm').appendChild(hiddenId);
                        }
                        hiddenId.value = data.backtest_id;
                        console.log('--- BACKTEST GUARDADO --- ID asignado al input oculto:', data.backtest_id);

                        Swal.fire({
                            title: data.sync_blocked ? 'Guardado sin sincronizar' : '¡Guardado!',
                            text: data.message || 'El backtest se guardó en el historial.',
                            icon: data.sync_blocked ? 'warning' : 'success',
                            confirmButtonColor: '#10B981',
                            background: '#1f2937',
                            color: '#f3f4f6'
                        });
                    } else {
                        throw new Error(data.message || 'Error al guardar');
                    }
                })
                .catch(error => {
                    Swal.fire({
                        title: 'Error',
                        text: error.message,
                        icon: 'error',
                        background: '#1f2937',
                        color: '#f3f4f6'
                    });
                });
            }
        });
    }
</script>

<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>


<script>
    function toggleTrailingInputs() {
        const mode = document.getElementById('trailing_mode_select').value;
        const divFixed = document.getElementById('div_trailing_fixed');
        const divAtr = document.getElementById('div_trailing_atr');
        
        const divBuffer = document.getElementById('div_trailing_buffer');
        if (mode === 'fixed') {
            divFixed.style.display = 'block';
            divAtr.style.display = 'none';
            divBuffer.style.display = 'block';
        } else if (mode === 'atr') {
            divFixed.style.display = 'none';
            divAtr.style.display = 'block';
            divBuffer.style.display = 'block';
        } else {
            divFixed.style.display = 'none';
            divAtr.style.display = 'none';
            divBuffer.style.display = 'none';
        }
    }
    
    // Ejecutar al cargar la página para mostrar el campo correcto si ya estaba seleccionado
    document.addEventListener('DOMContentLoaded', function() {
        toggleTrailingInputs();
    });
</script>
@endsection




@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
// ═══════════════════════════════════════════════════════════
// LÓGICA DE TABS
// ═══════════════════════════════════════════════════════════
let currentTab = 'config';
const tabs = ['config', 'apertura', 'cierre'];

function switchTab(tabName) {
    currentTab = tabName;
    tabs.forEach(t => {
        document.getElementById('tab-' + t).style.display = 'none';
        document.getElementById('tab-btn-' + t).classList.remove('active');
    });
    document.getElementById('tab-' + tabName).style.display = 'block';
    document.getElementById('tab-btn-' + tabName).classList.add('active');
    
    const btnNext = document.getElementById('btn-next');
    if (tabName === 'cierre') { btnNext.style.display = 'none'; } 
    else { btnNext.style.display = 'inline-block'; }
}

function nextTab() {
    const idx = tabs.indexOf(currentTab);
    if (idx < tabs.length - 1) { switchTab(tabs[idx + 1]); }
}

// ═══════════════════════════════════════════════════════════
// LÓGICA DE MULTISELECT
// ═══════════════════════════════════════════════════════════
let rawSymbols = @json($symbols);
let allSymbols = Array.isArray(rawSymbols) ? rawSymbols : Object.values(rawSymbols || {});

let rawSelected = @json(old('symbols', $selectedSymbols));
let selectedSymbols = Array.isArray(rawSelected) ? rawSelected : Object.values(rawSelected || {});

function renderSymbols() {
    const input = document.getElementById('symbols-input');
    const list = document.getElementById('symbols-list');
    const hiddenInputs = document.getElementById('hidden-symbols-inputs');
    
    if (!input || !list || !hiddenInputs) return;

    input.innerHTML = '';
    list.innerHTML = '';
    hiddenInputs.innerHTML = '';

    if (selectedSymbols.length === 0) {
        input.innerHTML = '<span class="text-sm" style="color:var(--color-text-muted);">Seleccionar monedas...</span>';
    } else {
        selectedSymbols.forEach(sym => {
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.innerHTML = `<span>${sym}</span><span class="tag-close" onclick="removeSymbol('${sym}', event)">×</span>`;
            input.appendChild(tag);

            const inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'symbols[]';
            inp.value = sym;
            hiddenInputs.appendChild(inp);
        });
    }

    const searchInput = document.getElementById('symbols-search');
    const search = searchInput ? searchInput.value.toLowerCase() : '';
    const available = allSymbols.filter(s => !selectedSymbols.includes(s) && s.toLowerCase().includes(search));

    if (available.length === 0) {
        list.innerHTML = '<div class="p-3 text-center text-[11px]" style="color:var(--color-text-muted);">No hay resultados</div>';
    } else {
        available.forEach(sym => {
            const div = document.createElement('div');
            div.className = 'multi-select-option';
            div.textContent = sym;
            div.onclick = () => { addSymbol(sym); };
            list.appendChild(div);
        });
    }
}

function addSymbol(sym) {
    if (!selectedSymbols.includes(sym)) {
        selectedSymbols.push(sym);
        renderSymbols();
    }
}

function removeSymbol(sym, event) {
    if (event) event.stopPropagation();
    selectedSymbols = selectedSymbols.filter(s => s !== sym);
    renderSymbols();
}

function toggleSymbolsDropdown() {
    const dd = document.getElementById('symbols-dropdown');
    if (!dd) return;
    const isHidden = dd.style.display === 'none' || dd.style.display === '';
    dd.style.display = isHidden ? 'block' : 'none';
    if (isHidden) {
        setTimeout(() => {
            const search = document.getElementById('symbols-search');
            if (search) search.focus();
        }, 50);
    }
}

function filterSymbols() { renderSymbols(); }

document.addEventListener('click', function(e) {
    const dropdown = document.getElementById('symbols-dropdown');
    const input = document.getElementById('symbols-input');
    if (!dropdown || !input) return;
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
    }
});

document.addEventListener('DOMContentLoaded', () => { renderSymbols(); });

// ═══════════════════════════════════════════════════════════
// LOADING OVERLAY
// ═══════════════════════════════════════════════════════════
function showLoading() {
    Swal.fire({
        title: 'Ejecutando Backtest...',
        html: 'Procesando símbolos. Esto puede tardar unos segundos por moneda.',
        allowOutsideClick: false, allowEscapeKey: false,
        background: '#11161F', color: '#E5E9F0',
        didOpen: () => Swal.showLoading()
    });
}
document.getElementById('backtestForm').addEventListener('submit', function(e) {
    e.preventDefault(); // Evita que la página se recargue
    
    showLoading();
    
    const form = e.target;
    const formData = new FormData(form);
    
    fetch('{{ route("backtesting.execute-ajax") }}', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRF-TOKEN': '{{ csrf_token() }}',
            'Accept': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        Swal.close();
        
        if (data.success) {
            document.getElementById('results-container').innerHTML = data.html;
            window.currentWarnings = data.warnings || [];
            document.getElementById('results-container').scrollIntoView({ behavior: 'smooth' });
        } else {
            Swal.fire({
                title: 'Error',
                text: data.error || 'Hubo un problema al ejecutar el backtest.',
                icon: 'error',
                background: '#11161F', color: '#E5E9F0'
            });
        }
    })
    .catch(error => {
        Swal.close();
        Swal.fire({
            title: 'Error de conexión',
            text: 'No se pudo conectar con el servidor.',
            icon: 'error',
            background: '#11161F', color: '#E5E9F0'
        });
    });
});

    // Función para el Modal de Errores
    window.showBacktestLog = function() {
        if (!window.currentWarnings || window.currentWarnings.length === 0) {
            Swal.fire({ title: 'Sin errores', text: 'No hay advertencias para este backtest.', icon: 'info', background: '#11161F', color: '#E5E9F0' });
            return;
        }
        
        let logHtml = '<div style="text-align:left; font-family:monospace; font-size:12px; background:#0D1117; padding:15px; border-radius:5px; border:1px solid #30363D; max-height:400px; overflow-y:auto;">';
        window.currentWarnings.forEach(w => {
            logHtml += `<div style="margin-bottom:10px; color:#F2545B;">- ${w}</div>`;
        });
        logHtml += '</div>';

        Swal.fire({
            title: 'Log de Errores del Backtest',
            html: logHtml,
            icon: 'warning',
            background: '#11161F', 
            color: '#E5E9F0',
            confirmButtonColor: '#374151',
            confirmButtonText: 'Cerrar',
            showDenyButton: true,
            denyButtonText: '📥 Descargar .txt',
            denyButtonColor: '#3b82f6',
            width: '85%',          /* 🔥 AQUÍ ESTÁ LA MAGIA: 85% DEL ANCHO DE LA PANTALLA */
            maxWidth: '1200px'     /* Límite máximo para pantallas muy grandes */
        }).then((result) => {
            if (result.isDenied) {
                let textContent = `LOG DE ERRORES - Backtest\nFecha: ${new Date().toLocaleString()}\n\n`;
                window.currentWarnings.forEach((w, i) => {
                    textContent += `${i + 1}. ${w}\n`;
                });
                
                const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Log_Backtest.txt`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
        });
    };

</script>
@endpush

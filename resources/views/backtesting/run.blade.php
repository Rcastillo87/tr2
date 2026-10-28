@extends('layouts.app')
@section('title', 'Configurar Backtest')
@section('header', 'Configurar Backtest')

@section('content')
{{-- Estilos propios de la página: no dependen del build de Tailwind (Vite). Misma paleta que el resto de módulos. --}}
<style>
    button, a[href] { cursor: pointer; }
    .bt-card { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: .5rem; overflow: hidden; }
    .bt-body { padding: 1rem; }
    .bt-body > * + * { margin-top: 1.25rem; }
    .bt-section + .bt-section { border-top: 1px solid var(--color-border-soft); padding-top: 1rem; margin-top: 1.25rem; }
    .bt-section-title { font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; color: var(--color-info); margin: 0 0 .75rem; }
    .bt-section-head { display: flex; justify-content: space-between; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: .75rem; }
    .bt-section-head .bt-section-title { margin: 0; }
    .bt-label { display: block; font-size: 11px; margin-bottom: .25rem; color: var(--color-text-muted); }
    .bt-hint { display: block; font-size: 10px; margin-top: .25rem; color: var(--color-text-muted); }
    .bt-input { width: 100%; border-radius: .5rem; padding: .5rem .75rem; font-size: .875rem; line-height: 1.25rem; border: 1px solid var(--color-border-strong);
                background: var(--color-surface-raised); color: var(--color-text-primary); outline: none; transition: border-color .15s; }
    .bt-input:focus { border-color: var(--color-info); }
    .bt-input.num { font-family: var(--font-mono, 'JetBrains Mono', monospace); }
    textarea.bt-input { resize: vertical; color: var(--color-profit); }
    select option { background-color: var(--color-surface-raised) !important; color: var(--color-text-primary) !important; }
    select option:checked { background-color: var(--color-info) !important; color: #fff !important; }

    /* Grillas responsive (móvil primero) */
    .bt-grid { display: grid; gap: .75rem; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .bt-grid-1 { display: grid; gap: .75rem; grid-template-columns: minmax(0, 1fr); }
    .bt-span-2 { grid-column: span 2 / span 2; }
    .bt-market { display: grid; gap: .75rem; grid-template-columns: minmax(0, 1fr); }
    .bt-pair { display: grid; gap: .75rem; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    @media (min-width: 640px) {
        .bt-grid-1.sm-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .bt-grid-1.sm-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .bt-filter-sub { padding-left: 1.5rem; }
    }
    @media (min-width: 768px) {
        .bt-market { grid-template-columns: minmax(0, 1fr) 280px; }
    }
    @media (min-width: 1024px) {
        .bt-grid.lg-5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
        .bt-grid.lg-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .bt-grid .bt-span-2 { grid-column: auto; }
    }

    /* Filtros (tarjeta con checkbox) */
    .bt-filter { background: var(--color-surface-raised); border: 1px solid var(--color-border-soft); border-radius: .5rem; padding: .75rem; }
    .bt-filter + .bt-filter { margin-top: .75rem; }
    .bt-filter .bt-input { background: var(--color-surface); }
    .bt-filter-sub { margin-top: .75rem; transition: opacity .15s; }
    .bt-filter.is-off .bt-filter-sub { opacity: .4; }
    .bt-filter-stack > * + * { margin-top: .75rem; }
    .bt-regimes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .5rem; }
    .bt-chip { display: flex; align-items: center; justify-content: center; gap: .375rem; min-height: 40px; padding: .375rem .75rem; border-radius: 999px;
               font-size: 12px; border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-text-secondary); cursor: pointer; user-select: none; }
    .bt-chip input { position: absolute; opacity: 0; width: 1px; height: 1px; pointer-events: none; }
    .bt-chip .dot { width: 8px; height: 8px; border-radius: 999px; background: #3A4454; }
    .bt-chip.on { border-color: var(--color-info); background: rgba(77,143,232,.15); color: var(--color-text-primary); }
    .bt-chip.on[data-regime=TRENDING] .dot { background: var(--color-profit); }
    .bt-chip.on[data-regime=RANGING] .dot { background: var(--color-info); }
    .bt-chip.on[data-regime=VOLATILE] .dot { background: var(--color-neutral); }
    .bt-chip:focus-within { outline: 2px solid var(--color-info); outline-offset: 2px; }
    .bt-note { display: flex; gap: .5rem; align-items: flex-start; border-radius: .5rem; padding: .5rem .625rem; font-size: 11px; line-height: 1.45; }
    .bt-note.warn { background: rgba(232,179,57,.10); border: 1px solid rgba(232,179,57,.35); color: var(--color-neutral); }
    .bt-note.err { background: rgba(242,84,91,.10); border: 1px solid rgba(242,84,91,.35); color: var(--color-loss); }
    .bt-badge-new { font-size: 9px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: #fff; background: var(--color-info);
                    border-radius: 4px; padding: 2px 6px; margin-left: .375rem; vertical-align: middle; }
    .bt-filter.is-new { border-color: var(--color-info); }
    .bt-check-row { display: flex; align-items: flex-start; gap: .5rem; cursor: pointer; }
    .bt-check { width: 1rem; height: 1rem; accent-color: var(--color-info); margin-top: .125rem; flex-shrink: 0; }
    .bt-check-title { display: block; font-size: 12px; font-weight: 500; color: var(--color-text-primary); }
    .bt-check-desc { display: block; font-size: 10px; color: var(--color-text-muted); }

    /* Pestañas */
    .bt-tabs { display: flex; border-bottom: 1px solid var(--color-border-soft); background: var(--color-surface-raised); }
    .bt-tab { flex: 1 1 0; padding: .625rem .5rem; font-size: 11px; font-weight: 500; color: var(--color-text-muted); border-bottom: 2px solid transparent;
              transition: all .15s; display: inline-flex; align-items: center; justify-content: center; white-space: nowrap; }
    .bt-tab.active { color: var(--color-text-primary); border-bottom-color: var(--color-info); background: var(--color-surface); }
    .bt-tab .n { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 9999px; font-size: 9px;
                 margin-right: 6px; background: var(--color-border-strong); color: var(--color-text-secondary); }
    .bt-tab.active .n { background: var(--color-info); color: #fff; }
    .bt-tab .long { display: none; }
    @media (min-width: 640px) { .bt-tab .long { display: inline; } .bt-tab .short { display: none; } }

    /* Pie y botones */
    .bt-footer { border-top: 1px solid var(--color-border-soft); padding-top: 1rem; display: flex; flex-direction: column-reverse; gap: .5rem; }
    .bt-nav { display: flex; gap: .5rem; }
    .bt-nav .btn-sec { flex: 1 1 0; }
    @media (min-width: 640px) {
        .bt-footer { flex-direction: row; justify-content: space-between; align-items: center; }
        .bt-nav .btn-sec { flex: none; }
    }
    .btn-sec { font-size: 11px; padding: .5rem .75rem; border-radius: .5rem; border: 1px solid var(--color-border-strong); background: var(--color-surface-raised);
               color: var(--color-text-secondary); transition: border-color .15s; }
    .btn-sec:hover { border-color: var(--color-info); }
    .btn-pri { font-size: .875rem; font-weight: 500; padding: .5rem 1.5rem; border-radius: .5rem; background: var(--color-info); color: #fff; width: 100%; }
    @media (min-width: 640px) { .btn-pri { width: auto; } }

    /* Selector múltiple de símbolos */
    .multi-select-container { position: relative; }
    .multi-select-dropdown { position: absolute; top: 100%; left: 0; right: 0; z-index: 50; max-height: 200px; overflow-y: auto; border-radius: .5rem;
        border: 1px solid var(--color-border-strong); background: var(--color-surface-raised); margin-top: 4px; box-shadow: 0 10px 25px rgba(0,0,0,.5); display: none; }
    .multi-select-option { padding: 8px 12px; cursor: pointer; font-size: 11px; color: var(--color-text-muted); }
    .multi-select-option:hover { background: var(--color-surface); color: var(--color-text-primary); }
    .symbols-box { min-height: 38px; display: flex; flex-wrap: wrap; gap: .25rem; align-items: center; cursor: pointer; }
    .tag { background: var(--color-info); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; display: flex; align-items: center; gap: 4px; }
    .tag-close { cursor: pointer; font-weight: bold; }

    /* Guía de campos (modal) */
    .bt-help { text-align: left; font-size: 12px; line-height: 1.5; color: var(--color-text-secondary); max-height: 65vh; overflow-y: auto; padding-right: .25rem; }
    .bt-help h4 { font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; color: var(--color-info); margin: 1rem 0 .5rem; }
    .bt-help h4:first-child { margin-top: 0; }
    .bt-help dt { color: var(--color-text-primary); font-weight: 500; margin-top: .5rem; }
    .bt-help dd { margin: 0; }
    .bt-help .warn { color: var(--color-neutral); }
</style>

<div class="mb-3 flex justify-between items-center gap-2 flex-wrap">
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
        $activeStrategy = $backtestToLoad->strategy ?? $strategyToLoad ?? null;
    @endphp
    <a href="{{ $returnUrl }}" class="text-[11px] transition-colors" style="color:var(--color-text-muted);">{{ $returnLabel }}</a>

    <div class="flex items-center gap-2">
        <button type="button" onclick="showFieldGuide()" class="btn-sec" style="color:var(--color-info);">? Guía de campos</button>
        @if($activeStrategy)
        <div class="flex items-center gap-2 px-2.5 py-1 rounded border" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
            <span class="text-[10px]" style="color:var(--color-text-muted);">Estrategia</span>
            <span class="text-[11px] font-medium" style="color:var(--color-text-primary);">{{ $activeStrategy->name }}</span>
        </div>
        @endif
    </div>
</div>

@if ($error)
    <div class="rounded-lg border p-3 mb-3 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">{{ $error }}</div>
@endif

<div class="bt-card">
    <!-- Pestañas -->
    <div class="bt-tabs">
        <button type="button" onclick="switchTab('config')" id="tab-btn-config" class="bt-tab active"><span class="n">1</span><span class="short">Configuración</span><span class="long">Configuración base</span></button>
        <button type="button" onclick="switchTab('apertura')" id="tab-btn-apertura" class="bt-tab"><span class="n">2</span><span class="short">Apertura</span><span class="long">Filtros de apertura</span></button>
        <button type="button" onclick="switchTab('cierre')" id="tab-btn-cierre" class="bt-tab"><span class="n">3</span><span class="short">Cierre</span><span class="long">Reglas de cierre</span></button>
    </div>

    <form method="POST" action="#" onsubmit="return false" id="backtestForm" class="bt-body">
        @csrf

        <input type="hidden" id="current_backtest_id" name="backtest_id" value="{{ request('backtest_id', $backtestToLoad->id ?? '') }}">
        <input type="hidden" name="strategy_id" value="{{ request('strategy_id', $backtestToLoad->strategy_id ?? '') }}">
        {{-- Balance oculto: los resultados en % no dependen de él (tamaño, comisión y slippage son proporcionales). Sigue viajando al motor. --}}
        <input type="hidden" name="initial_balance" value="{{ old('initial_balance', $backtestToLoad->config_params['initial_balance'] ?? '10000') }}">

        <!-- ═══ PESTAÑA 1: CONFIGURACIÓN BASE ═══ -->
        <div id="tab-config">
            <section class="bt-section">
                <p class="bt-section-title">Mercado y periodo</p>
                <div class="bt-market">
                    <div>
                        <label class="bt-label">Símbolos</label>
                        <div class="multi-select-container">
                            <div onclick="event.stopPropagation(); toggleSymbolsDropdown()" id="symbols-input" class="bt-input symbols-box">
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
                    <div class="bt-pair">
                        <div>
                            <label class="bt-label">Intervalo</label>
                            <select name="interval" class="bt-input">
                                @php $intervalLabels = ['1' => '1m', '5' => '5m', '15' => '15m', '30' => '30m', '60' => 'H1', '120' => 'H2', '240' => 'H4', 'D' => 'D1']; @endphp
                                @foreach ($intervals as $iv)
                                    <option value="{{ $iv }}" {{ old('interval', $backtestToLoad->interval ?? '60') == $iv ? 'selected' : '' }}>{{ $intervalLabels[$iv] ?? $iv }}</option>
                                @endforeach
                            </select>
                        </div>
                        <div>
                            <label class="bt-label">Meses a probar</label>
                            <select name="months" class="bt-input">
                                @foreach ([1, 3, 6, 12, 18, 24] as $m)
                                    <option value="{{ $m }}" {{ old('months', $backtestToLoad->months ?? 6) == $m ? 'selected' : '' }}>{{ $m }} meses</option>
                                @endforeach
                            </select>
                        </div>
                    </div>
                </div>
            </section>

            <section class="bt-section">
                <p class="bt-section-title">Riesgo y costos</p>
                <div class="bt-grid lg-5">
                    <div>
                        <label class="bt-label">Stop Loss %</label>
                        <input type="number" step="0.1" name="sl_pct" value="{{ old('sl_pct', $backtestToLoad->config_params['sl_pct'] ?? '1.5') }}" class="bt-input num">
                    </div>
                    <div>
                        <label class="bt-label">Take Profit %</label>
                        <input type="number" step="0.1" name="tp_pct" value="{{ old('tp_pct', $backtestToLoad->config_params['tp_pct'] ?? '3.0') }}" class="bt-input num">
                    </div>
                    <div>
                        <label class="bt-label">Riesgo / trade %</label>
                        <input type="number" step="0.1" name="risk_per_trade_pct" value="{{ old('risk_per_trade_pct', $backtestToLoad->config_params['risk_per_trade_pct'] ?? '1.0') }}" class="bt-input num">
                        <span class="bt-hint">% del balance que se pierde en el SL</span>
                    </div>
                    <div>
                        <label class="bt-label">Comisión % / lado</label>
                        <input type="number" step="0.001" name="commission_pct" value="{{ old('commission_pct', $backtestToLoad->config_params['commission_pct'] ?? '0.055') }}" class="bt-input num">
                        <span class="bt-hint">Bybit taker: 0.055</span>
                    </div>
                    <div class="bt-span-2">
                        <label class="bt-label">Slippage % / lado</label>
                        <input type="number" step="0.01" min="0" max="1" name="slippage_pct" value="{{ old('slippage_pct', $backtestToLoad->config_params['slippage_pct'] ?? '0.05') }}" class="bt-input num">
                        <span class="bt-hint">Precio peor al llenar la orden</span>
                    </div>
                </div>
            </section>

            <section class="bt-section">
                <div class="bt-section-head">
                    <p class="bt-section-title">Parámetros de la estrategia</p>
                    <span class="text-[10px]" style="color:var(--color-text-muted);">JSON · sobrescribe los valores por defecto</span>
                </div>
                @php
                    // Limpiamos los filtros del JSON para que no se mezclen con la UI
                    $cleanConfig = $backtestToLoad ? ($backtestToLoad->strategy_snapshot['config'] ?? []) : ($strategyToLoad->config ?? []);
                    $keysToRemove = ['sl_pct', 'tp_pct', 'tp2_pct', 'tp3_pct', 'tp4_pct', 'be_pct', 'max_duration',
                          'commission_pct', 'slippage_pct', 'risk_per_trade_pct', 'regime_filter', 'regime_adx_trending',
                          'regime_adx_ranging', 'regime_ambiguous_as', 'volume_filter', 'volume_filter_period',
                          'volume_filter_mult', 'macro_trend_filter', 'trailing_mode', 'trailing_distance_pct', 'trailing_atr_mult'];
                    foreach ($keysToRemove as $k) {
                        unset($cleanConfig[$k]);
                    }
                    $jsonString = json_encode($cleanConfig, JSON_PRETTY_PRINT);
                @endphp
                <textarea name="strategy_config_override" rows="8" class="bt-input num" placeholder='{"fast_period": 9}'>{{ old('strategy_config_override', $jsonString) }}</textarea>
            </section>
        </div>

        <!-- ═══ PESTAÑA 2: FILTROS DE APERTURA ═══ -->
        <div id="tab-apertura" style="display: none;">
            <p class="bt-section-title">Filtros que deben cumplirse para abrir</p>

            <div class="bt-filter" data-filter>
                <label class="bt-check-row">
                    <input type="checkbox" name="regime_filter" value="1" class="bt-check" onchange="dimFilter(this)" {{ old('regime_filter', !empty($backtestToLoad->config_params['regime_filter'])) ? 'checked' : '' }}>
                    <span><span class="bt-check-title">Régimen de mercado (ADX)</span>
                    <span class="bt-check-desc">Solo abre si el régimen de la vela está entre los permitidos.</span></span>
                </label>
                @php
                    $regimeLabels = ['TRENDING' => 'Tendencia', 'RANGING' => 'Lateral', 'VOLATILE' => 'Volátil'];
                    $strategyRegimes = $activeStrategy ? $activeStrategy->allowedRegimes() : \App\Models\Strategy::REGIMES;
                    $checkedRegimes = old('allowed_regimes_present')
                        ? (array) old('allowed_regimes', [])
                        : (array) ($backtestToLoad->config_params['allowed_regimes'] ?? $strategyRegimes);
                    $ambiguousSel = strtoupper((string) old('regime_ambiguous_as', $backtestToLoad->config_params['regime_ambiguous_as'] ?? 'RANGING'));
                    $ambiguousSel = in_array($ambiguousSel, ['IGNORAR', 'NO_OPERAR'], true) ? 'ignorar' : $ambiguousSel;
                @endphp
                <div class="bt-filter-sub" style="display:flex; flex-direction:column; gap:.75rem;">
                    <div>
                        <span class="bt-label">Regímenes permitidos</span>
                        <input type="hidden" name="allowed_regimes_present" value="1">
                        <div class="bt-regimes">
                            @foreach($regimeLabels as $code => $label)
                            <label class="bt-chip{{ in_array($code, $checkedRegimes, true) ? ' on' : '' }}" data-regime="{{ $code }}">
                                <input type="checkbox" name="allowed_regimes[]" value="{{ $code }}" onchange="toggleRegimeChip(this)" {{ in_array($code, $checkedRegimes, true) ? 'checked' : '' }}>
                                <span class="dot" aria-hidden="true"></span>{{ $label }}
                            </label>
                            @endforeach
                        </div>
                        <span class="bt-hint">Por defecto, los de la estrategia{{ $activeStrategy ? ' (' . $activeStrategy->name . ': ' . implode(', ', array_map(fn ($r) => $regimeLabels[$r], $strategyRegimes)) . ')' : '' }}.</span>
                    </div>
                <div class="bt-grid-1 sm-3">
                    <div>
                        <label class="bt-label">ADX tendencia (mayor a)</label>
                        <input type="number" name="regime_adx_trending" value="{{ old('regime_adx_trending', $backtestToLoad->config_params['regime_adx_trending'] ?? '25') }}" class="bt-input num">
                    </div>
                    <div>
                        <label class="bt-label">ADX lateral (menor a)</label>
                        <input type="number" name="regime_adx_ranging" value="{{ old('regime_adx_ranging', $backtestToLoad->config_params['regime_adx_ranging'] ?? '20') }}" class="bt-input num">
                    </div>
                    <div>
                        <label class="bt-label">Caso ambiguo</label>
                        <select name="regime_ambiguous_as" class="bt-input" onchange="updateRegimeNotes()">
                            <option value="RANGING" {{ $ambiguousSel == 'RANGING' ? 'selected' : '' }}>Lateral (asumir rango)</option>
                            <option value="TRENDING" {{ $ambiguousSel == 'TRENDING' ? 'selected' : '' }}>Tendencia (asumir tendencia)</option>
                            <option value="ignorar" {{ $ambiguousSel == 'ignorar' ? 'selected' : '' }}>No operar (filtrar)</option>
                        </select>
                    </div>
                </div>
                <div id="regime-note-noeffect" class="bt-note warn" role="status" style="display:none;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" style="flex-shrink:0; margin-top:1px;"><path d="M12 9v4M12 17h.01"></path><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path></svg>
                    <span>Con los 3 regímenes permitidos este filtro no bloquea ninguna operación. Quita alguno o elige "No operar" en el caso ambiguo.</span>
                </div>
                <div id="regime-note-none" class="bt-note err" role="alert" style="display:none;">Elige al menos un régimen: sin ninguno no se abriría ninguna operación.</div>
                </div>
            </div>

            <div class="bt-filter" data-filter>
                <label class="bt-check-row">
                    <input type="checkbox" name="volume_filter" value="1" class="bt-check" onchange="dimFilter(this)" {{ old('volume_filter', !empty($backtestToLoad->config_params['volume_filter'])) ? 'checked' : '' }}>
                    <span><span class="bt-check-title">Volumen mínimo</span>
                    <span class="bt-check-desc">Volumen de la vela mayor o igual al promedio × multiplicador.</span></span>
                </label>
                <div class="bt-filter-sub bt-grid-1 sm-2">
                    <div>
                        <label class="bt-label">Período del promedio (velas)</label>
                        <input type="number" name="volume_filter_period" value="{{ old('volume_filter_period', $backtestToLoad->config_params['volume_filter_period'] ?? '20') }}" class="bt-input num">
                    </div>
                    <div>
                        <label class="bt-label">Multiplicador</label>
                        <input type="number" step="0.1" name="volume_filter_mult" value="{{ old('volume_filter_mult', $backtestToLoad->config_params['volume_filter_mult'] ?? '1.2') }}" class="bt-input num">
                    </div>
                </div>
            </div>

            <div class="bt-filter" data-filter>
                <label class="bt-check-row">
                    <input type="checkbox" name="macro_trend_filter" value="1" class="bt-check" onchange="dimFilter(this)" {{ old('macro_trend_filter', !empty($backtestToLoad->config_params['macro_trend_filter'])) ? 'checked' : '' }}>
                    <span><span class="bt-check-title">Tendencia macro H4 (EMA 50)</span>
                    <span class="bt-check-desc">Sin largos con H4 bajista ni cortos con H4 alcista.</span></span>
                </label>
            </div>

            <div class="bt-filter is-new" data-filter>
                <label class="bt-check-row">
                    <input type="checkbox" name="btc_trend_filter" value="1" class="bt-check" onchange="dimFilter(this)" {{ old('btc_trend_filter', !empty($backtestToLoad->config_params['btc_trend_filter'])) ? 'checked' : '' }}>
                    <span><span class="bt-check-title">Tendencia de BTC (EMA 50 H4)<span class="bt-badge-new">Nuevo</span></span>
                    <span class="bt-check-desc">Solo altcoins: sin largos con BTC bajista ni cortos con BTC alcista. En BTC no aplica (usa el macro H4).</span></span>
                </label>
            </div>
        </div>

        <!-- ═══ PESTAÑA 3: REGLAS DE CIERRE ═══ -->
        <div id="tab-cierre" style="display: none;">
            <section class="bt-section">
                <p class="bt-section-title">Gestión de la posición</p>
                <div class="bt-grid lg-3">
                    <div>
                        <label class="bt-label">Duración máxima (velas)</label>
                        <input type="number" name="max_duration" value="{{ old('max_duration', $backtestToLoad->config_params['max_duration'] ?? '24') }}" class="bt-input num">
                    </div>
                    <div>
                        <label class="bt-label">Break-even %</label>
                        <input type="number" step="0.1" name="be_pct" value="{{ old('be_pct', $backtestToLoad->config_params['be_pct'] ?? '2.0') }}" class="bt-input num">
                        <span class="bt-hint">Debe ser menor que el TP</span>
                    </div>
                    <div class="bt-span-2">
                        <label class="bt-label">Trailing stop</label>
                        <select name="trailing_mode" id="trailing_mode_select" onchange="toggleTrailingInputs()" class="bt-input">
                            <option value="none" {{ old('trailing_mode', $backtestToLoad->config_params['trailing_mode'] ?? '') == 'none' ? 'selected' : '' }}>Ninguno</option>
                            <option value="fixed" {{ old('trailing_mode', $backtestToLoad->config_params['trailing_mode'] ?? '') == 'fixed' ? 'selected' : '' }}>Fijo (%)</option>
                            <option value="atr" {{ old('trailing_mode', $backtestToLoad->config_params['trailing_mode'] ?? '') == 'atr' ? 'selected' : '' }}>Dinámico (ATR)</option>
                        </select>
                    </div>

                    <div id="div_trailing_fixed" style="display: none;">
                        <label class="bt-label">Distancia fija %</label>
                        <input type="number" step="0.1" name="trailing_distance_pct" value="{{ old('trailing_distance_pct', $backtestToLoad->config_params['trailing_distance_pct'] ?? '1.0') }}" class="bt-input num">
                        <span class="bt-hint">Mínimo 1.0%</span>
                    </div>
                    <div id="div_trailing_atr" style="display: none;">
                        <label class="bt-label">Multiplicador ATR</label>
                        <input type="number" step="0.1" name="trailing_atr_mult" value="{{ old('trailing_atr_mult', $backtestToLoad->config_params['trailing_atr_mult'] ?? '2.0') }}" class="bt-input num">
                    </div>
                    <div id="div_trailing_buffer" style="display: none;">
                        <label class="bt-label">Activación trailing %</label>
                        <input type="number" step="0.1" name="trailing_activation_buffer_pct" value="{{ old('trailing_activation_buffer_pct', $backtestToLoad->config_params['trailing_activation_buffer_pct'] ?? '0.5') }}" class="bt-input num">
                    </div>
                </div>
            </section>

            <section class="bt-section">
                <p class="bt-section-title">Cierres adicionales</p>
                <div class="bt-filter bt-filter-stack">
                    <label class="bt-check-row">
                        <input type="checkbox" name="max_duration_profit" value="1" class="bt-check" {{ old('max_duration_profit', !empty($backtestToLoad->config_params['max_duration_profit'])) ? 'checked' : '' }}>
                        <span><span class="bt-check-title">Cierre por tiempo solo en ganancia</span>
                        <span class="bt-check-desc">Al cumplir la duración máxima cierra solo si va ganando.</span></span>
                    </label>
                    <label class="bt-check-row">
                        <input type="checkbox" name="close_on_opposite" value="1" class="bt-check" {{ old('close_on_opposite', !empty($backtestToLoad->config_params['close_on_opposite'])) ? 'checked' : '' }}>
                        <span><span class="bt-check-title">Cierre por señal opuesta</span>
                        <span class="bt-check-desc">Si la estrategia da la señal contraria, cierra la posición.</span></span>
                    </label>
                </div>
            </section>
        </div>

        <!-- Pie: navegación + ejecutar -->
        <div class="bt-footer">
            <div class="bt-nav">
                <button type="button" onclick="prevTab()" id="btn-prev" class="btn-sec" style="display:none;">← Anterior</button>
                <button type="button" onclick="nextTab()" id="btn-next" class="btn-sec" style="color:var(--color-info);">Siguiente →</button>
            </div>
            <button type="submit" class="btn-pri">Ejecutar backtest</button>
        </div>
    </form>
</div>

{{-- RESULTADOS: fuera de la tarjeta del formulario --}}
<div id="results-container" class="mt-4"></div>

{{-- Guía de campos (se muestra en un modal con "? Guía de campos") --}}
<template id="field-guide">
    <div class="bt-help">
        <h4>1 · Configuración base</h4>
        <dl>
            <dt>Símbolos</dt><dd>Monedas a probar. Cada una se simula por separado con los mismos parámetros y el resultado se suma.</dd>
            <dt>Intervalo</dt><dd>Temporalidad de las velas con las que la estrategia busca señales. El SL, TP, BE y trailing se revisan con velas de 1 minuto cuando hay datos de 1m para todo el periodo (más realista).</dd>
            <dt>Meses a probar</dt><dd>Cuánta historia se simula. Más meses = resultado más confiable (más operaciones y más tipos de mercado).</dd>
            <dt>Stop Loss %</dt><dd>Distancia desde la entrada a la que se corta la pérdida. Ej.: 1.5 en un largo a 100 → SL en 98.5.</dd>
            <dt>Take Profit %</dt><dd>Distancia del objetivo. Al tocarlo se cierra el 100% de la posición.</dd>
            <dt>Riesgo / trade %</dt><dd>Lo que se pierde del balance si salta el SL. Define el tamaño: balance × riesgo ÷ distancia al SL. El tamaño nunca supera el balance (sin apalancamiento), así que con SL muy cortos el riesgo real puede ser menor.</dd>
            <dt>Comisión % / lado</dt><dd>Se cobra al entrar y al salir sobre el valor de la posición. Bybit taker: 0.055%.</dd>
            <dt>Slippage % / lado</dt><dd>Diferencia entre el precio de la vela y el precio real de llenado. Se aplica en contra al entrar y al salir (0.05% ≈ 0.10% por operación completa). Se calibrará con la cuenta demo.</dd>
            <dt>Parámetros de la estrategia (JSON)</dt><dd>Valores propios de la estrategia (periodos, multiplicadores…). Lo que no escribas usa el valor por defecto de la estrategia. Debe ser JSON válido.</dd>
        </dl>
        <h4>2 · Filtros de apertura</h4>
        <dl>
            <dt>Régimen de mercado (ADX)</dt><dd>Cada vela se clasifica: <b>Volátil</b> si el ATR supera 1.8× su promedio de 50 velas; <b>Tendencia</b> si el ADX supera "ADX tendencia"; <b>Lateral</b> si el ADX está bajo "ADX lateral" y las Bandas de Bollinger están estrechas. Solo se abre en los <b>regímenes permitidos</b> (por defecto, los de la estrategia). Con los 3 permitidos solo filtra si el caso ambiguo es "No operar".</dd>
            <dt>Caso ambiguo</dt><dd>Qué hacer con las velas que no encajan en ningún régimen: tratarlas como lateral, como tendencia, o no operar.</dd>
            <dt>Volumen mínimo</dt><dd>Solo abre si el volumen de la vela de la señal es ≥ promedio de N velas × multiplicador. Ej.: 20 y 1.2 → al menos 20% sobre el promedio.</dd>
            <dt>Tendencia macro H4 (EMA 50)</dt><dd>No abre largos si el H4 es bajista (cierre H4 bajo su EMA 50) ni cortos si es alcista. Usa la última vela H4 ya cerrada al cerrar la vela de la señal (sin mirar al futuro). Si no hay velas H4 suficientes, no opera.</dd>
            <dt>Tendencia de BTC (EMA 50 H4)</dt><dd>Solo en altcoins: no abre largos si BTC está bajo su EMA 50 en H4 ni cortos si está sobre ella. Misma regla sin mirar al futuro que la macro H4. En BTC no hace nada. Si no hay velas H4 de BTC, no opera.</dd>
        </dl>
        <h4>3 · Reglas de cierre</h4>
        <dl>
            <dt>Duración máxima (velas)</dt><dd>Cierra al cierre de la vela N contada desde la entrada (velas del intervalo elegido). 0 = sin límite.</dd>
            <dt>Break-even %</dt><dd>Cuando el precio avanza ese % a favor, el SL se mueve al precio de entrada. Debe ser menor que el TP; si no, nunca se activa. Con 0 se activa apenas el precio pasa la entrada. Al cerrar en break-even se pierde la comisión y el slippage.</dd>
            <dt>Trailing stop · Fijo</dt><dd>El SL persigue al precio a una distancia fija (% de la entrada) y solo se mueve a favor. Mínimo 1.0% para evitar cierres por ruido.</dd>
            <dt>Trailing stop · Dinámico (ATR)</dt><dd>La distancia es ATR × multiplicador: se abre en mercados volátiles y se cierra en mercados tranquilos.</dd>
            <dt>Activación trailing %</dt><dd>El trailing solo empieza a mover el SL cuando la ganancia supera este %.</dd>
            <dt>Cierre por tiempo solo en ganancia</dt><dd>Al cumplir la duración máxima cierra solo si va ganando; si va perdiendo sigue abierta hasta SL, TP, BE o trailing.</dd>
            <dt>Cierre por señal opuesta</dt><dd>Si la estrategia da la señal contraria con una posición abierta, la cierra al abrir la vela siguiente y abre la contraria si pasa los filtros. Sin esta opción, las señales contrarias se ignoran mientras hay posición.</dd>
        </dl>
    </div>
</template>
@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
// Tema único de SweetAlert (misma paleta que la app)
const SWAL_THEME = { background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#4D8FE8', cancelButtonColor: '#232B38' };

// ═══════════════════════════════════════════════════════════
// PESTAÑAS
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

    const idx = tabs.indexOf(tabName);
    document.getElementById('btn-prev').style.display = idx === 0 ? 'none' : '';
    document.getElementById('btn-next').style.display = idx === tabs.length - 1 ? 'none' : '';
}
function nextTab() { const i = tabs.indexOf(currentTab); if (i < tabs.length - 1) switchTab(tabs[i + 1]); }
function prevTab() { const i = tabs.indexOf(currentTab); if (i > 0) switchTab(tabs[i - 1]); }

// Filtro apagado: sus campos se atenúan (solo visual; los valores se envían igual que siempre)
function dimFilter(checkbox) {
    checkbox.closest('[data-filter]').classList.toggle('is-off', !checkbox.checked);
    if (checkbox.name === 'regime_filter') updateRegimeNotes();
}

// Régimen: casillas de regímenes permitidos + avisos (sin efecto / ninguno elegido)
function toggleRegimeChip(input) { input.closest('.bt-chip').classList.toggle('on', input.checked); updateRegimeNotes(); }
function updateRegimeNotes() {
    const on = document.querySelector('input[name=regime_filter]')?.checked;
    const n = document.querySelectorAll('input[name="allowed_regimes[]"]:checked').length;
    const amb = document.querySelector('select[name=regime_ambiguous_as]')?.value;
    document.getElementById('regime-note-noeffect').style.display = on && n === 3 && amb !== 'ignorar' ? 'flex' : 'none';
    document.getElementById('regime-note-none').style.display = on && n === 0 ? 'flex' : 'none';
}

function toggleTrailingInputs() {
    const mode = document.getElementById('trailing_mode_select').value;
    document.getElementById('div_trailing_fixed').style.display  = mode === 'fixed' ? 'block' : 'none';
    document.getElementById('div_trailing_atr').style.display    = mode === 'atr' ? 'block' : 'none';
    document.getElementById('div_trailing_buffer').style.display = (mode === 'fixed' || mode === 'atr') ? 'block' : 'none';
}

function showFieldGuide() {
    Swal.fire({
        ...SWAL_THEME,
        title: 'Guía de campos',
        html: document.getElementById('field-guide').innerHTML,
        width: '760px',
        confirmButtonText: 'Entendido',
    });
}

// ═══════════════════════════════════════════════════════════
// SELECTOR MÚLTIPLE DE SÍMBOLOS
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
function addSymbol(sym) { if (!selectedSymbols.includes(sym)) { selectedSymbols.push(sym); renderSymbols(); } }
function removeSymbol(sym, event) { if (event) event.stopPropagation(); selectedSymbols = selectedSymbols.filter(s => s !== sym); renderSymbols(); }
function toggleSymbolsDropdown() {
    const dd = document.getElementById('symbols-dropdown');
    if (!dd) return;
    const isHidden = dd.style.display === 'none' || dd.style.display === '';
    dd.style.display = isHidden ? 'block' : 'none';
    if (isHidden) setTimeout(() => { const s = document.getElementById('symbols-search'); if (s) s.focus(); }, 50);
}
function filterSymbols() { renderSymbols(); }

document.addEventListener('click', function (e) {
    const dropdown = document.getElementById('symbols-dropdown');
    const input = document.getElementById('symbols-input');
    if (!dropdown || !input) return;
    if (!input.contains(e.target) && !dropdown.contains(e.target)) dropdown.style.display = 'none';
});

document.addEventListener('DOMContentLoaded', () => {
    renderSymbols();
    toggleTrailingInputs();
    document.querySelectorAll('[data-filter] .bt-check').forEach(dimFilter);
    updateRegimeNotes();
});

// ═══════════════════════════════════════════════════════════
// EJECUTAR BACKTEST (AJAX)
// ═══════════════════════════════════════════════════════════
function showLoading() {
    Swal.fire({
        ...SWAL_THEME,
        title: 'Ejecutando Backtest...',
        html: 'Procesando símbolos. Esto puede tardar unos segundos por moneda.',
        allowOutsideClick: false, allowEscapeKey: false,
        didOpen: () => Swal.showLoading()
    });
}

document.getElementById('backtestForm').addEventListener('submit', function (e) {
    e.preventDefault();
    showLoading();

    fetch('{{ route("backtesting.execute-ajax") }}', {
        method: 'POST',
        body: new FormData(e.target),
        headers: { 'X-CSRF-TOKEN': '{{ csrf_token() }}', 'Accept': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        Swal.close();
        if (data.success) {
            document.getElementById('results-container').innerHTML = data.html;
            window.currentWarnings = data.warnings || [];
            document.getElementById('results-container').scrollIntoView({ behavior: 'smooth' });
        } else {
            Swal.fire({ ...SWAL_THEME, title: 'Error', text: data.error || 'Hubo un problema al ejecutar el backtest.', icon: 'error' });
        }
    })
    .catch(() => {
        Swal.close();
        Swal.fire({ ...SWAL_THEME, title: 'Error de conexión', text: 'No se pudo conectar con el servidor.', icon: 'error' });
    });
});

// ═══════════════════════════════════════════════════════════
// GUARDAR BACKTEST (botón del panel de resultados)
// ═══════════════════════════════════════════════════════════
function confirmSaveBacktest() {
    Swal.fire({
        ...SWAL_THEME,
        title: '¿Guardar Backtest?',
        text: 'Se guardará esta configuración en el historial.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#3DD68C',
        confirmButtonText: 'Sí, guardar',
        cancelButtonText: 'Cancelar',
    }).then((result) => {
        if (!result.isConfirmed) return;
        Swal.fire({ ...SWAL_THEME, title: 'Guardando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

        const form = document.getElementById('saveBacktestForm');
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-CSRF-TOKEN': '{{ csrf_token() }}', 'Accept': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) throw new Error(data.message || 'Error al guardar');
            // El id guardado viaja en el próximo backtest (edición del mismo registro)
            let hiddenId = document.getElementById('current_backtest_id');
            if (!hiddenId) {
                hiddenId = document.createElement('input');
                hiddenId.type = 'hidden';
                hiddenId.id = 'current_backtest_id';
                hiddenId.name = 'backtest_id';
                document.getElementById('backtestForm').appendChild(hiddenId);
            }
            hiddenId.value = data.backtest_id;

            Swal.fire({
                ...SWAL_THEME,
                title: data.sync_blocked ? 'Guardado sin sincronizar' : '¡Guardado!',
                text: data.message || 'El backtest se guardó en el historial.',
                icon: data.sync_blocked ? 'warning' : 'success',
            });
        })
        .catch(error => Swal.fire({ ...SWAL_THEME, title: 'Error', text: error.message, icon: 'error' }));
    });
}

// ═══════════════════════════════════════════════════════════
// LOG DE ADVERTENCIAS (botón del panel de resultados)
// ═══════════════════════════════════════════════════════════
window.showBacktestLog = function () {
    if (!window.currentWarnings || window.currentWarnings.length === 0) {
        Swal.fire({ ...SWAL_THEME, title: 'Sin advertencias', text: 'No hay advertencias para este backtest.', icon: 'info' });
        return;
    }
    const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    let logHtml = '<div style="text-align:left; font-family:monospace; font-size:12px; background:#0A0E14; padding:15px; border-radius:5px; border:1px solid #232B38; max-height:400px; overflow-y:auto;">';
    window.currentWarnings.forEach(w => { logHtml += `<div style="margin-bottom:10px; color:#F2545B;">- ${esc(w)}</div>`; });
    logHtml += '</div>';

    Swal.fire({
        ...SWAL_THEME,
        title: 'Log de advertencias del backtest',
        html: logHtml,
        icon: 'warning',
        confirmButtonColor: '#232B38',
        confirmButtonText: 'Cerrar',
        showDenyButton: true,
        denyButtonText: 'Descargar .txt',
        denyButtonColor: '#4D8FE8',
        width: 'min(1200px, 95vw)',
    }).then((result) => {
        if (!result.isDenied) return;
        let textContent = `LOG DE ADVERTENCIAS - Backtest\nFecha: ${new Date().toLocaleString()}\n\n`;
        window.currentWarnings.forEach((w, i) => { textContent += `${i + 1}. ${w}\n`; });
        const url = URL.createObjectURL(new Blob([textContent], { type: 'text/plain;charset=utf-8' }));
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Log_Backtest.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
};
</script>
@endpush

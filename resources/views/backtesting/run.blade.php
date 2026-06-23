@extends('layouts.app')

@section('title', 'Nuevo Backtest')
@section('header', 'Configurar Backtest')

@section('content')

<style>button, a[href] { cursor: pointer; }</style>

    <div class="mb-3">
        <a href="{{ route('backtesting.index') }}" class="text-[11px] transition-colors" style="color:var(--color-text-muted);">
            ← Volver a estrategias
        </a>
    </div>

    {{-- ── Guía de campos ──────────────────────────────────────────────── --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Guía de parámetros</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-[11px]" style="color:var(--color-text-muted);">
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Stop Loss %</span> —
                Pérdida máxima permitida por operación (ej. 1.5% = cierra si el precio cae 1.5% en tu contra).
                Menor valor = más operaciones cerradas por SL, más seguro pero menos margen al precio.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Take Profit 1-4 %</span> —
                Niveles de ganancia para cerrar la posición. El motor cierra en el nivel más favorable alcanzado
                (TP4 > TP3 > TP2 > TP1). Deja en blanco los que no quieras usar.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Break-even %</span> —
                Cuando la ganancia flotante llega a este %, el Stop Loss se mueve al precio de entrada
                (ya no puedes perder en esa operación). Ej. BE=1.5% → al llegar a +1.5%, SL sube a entrada.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Máx. duración (velas)</span> —
                Si la operación no toca SL ni TP después de este número de velas, se cierra al precio actual.
                En H1, 24 velas = 24 horas. Evita dejar operaciones abiertas indefinidamente.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Riesgo/trade %</span> —
                Porcentaje del capital total a arriesgar en cada operación (ej. 1% de $10,000 = $100 de riesgo por trade).
                Determina el tamaño de la posición (más riesgo = posición más grande).
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Filtro de régimen</span> —
                Solo opera cuando el mercado está en el régimen correcto para la estrategia (TRENDING para estrategias de tendencia,
                RANGING para reversión). Desactívalo para ver el comportamiento sin este filtro.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Filtro macro H4</span> —
                Bloquea señales contra la tendencia de largo plazo (EMA50 en H4). Reduce el retorno total
                pero elimina operaciones en contra de la marea — suaviza significativamente los meses de pérdida.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Trailing Stop</span> —
                El Stop Loss se mueve automáticamente siguiendo al precio cuando va a tu favor.
                Fijo: mantiene siempre la misma distancia % del precio actual.
                Por pasos: el SL salta a niveles definidos conforme aumenta la ganancia.
            </div>
            <div>
                <span class="font-medium" style="color:var(--color-text-primary);">Protección por volatilidad</span> —
                Se activa cuando el ATR actual supera X veces su promedio (mercado errático).
                "Cerrar": sale de la posición inmediatamente.
                "Ampliar SL": da más espacio para evitar cierres prematuros por ruido.
            </div>
        </div>
    </div>

    {{-- ── Formulario ──────────────────────────────────────────────────── --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Configurar backtest</h3>

        @if ($old && isset($old['preload_from']))
            <div class="rounded-md p-2.5 mb-3 text-[11px]" style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                ✓ Parámetros precargados desde: <span class="font-medium">{{ $old['preload_from'] }}</span>
            </div>
        @endif

        @if ($error)
            <div class="rounded-lg border p-3 mb-3 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
                {{ $error }}
            </div>
        @endif

        <form method="POST" action="{{ route('backtesting.execute') }}" id="backtestForm" class="space-y-4">
            @csrf
            <input type="hidden" name="preload_from" value="{{ request('preload_from') ?: ($old['preload_from'] ?? '') }}">

            {{-- Estrategia / símbolo / intervalo / fechas --}}
            @php $isEditing = (bool) (request('preload_from') ?: ($old['preload_from'] ?? '')); @endphp
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">
                        Estrategia @if($isEditing) <span style="color:var(--color-text-muted);">(bloqueado al editar)</span> @endif
                    </label>
                    <select name="strategy" id="strategy" onchange="loadParams()"
                            @if($isEditing) disabled @endif
                            class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary); @if($isEditing) opacity:0.6;cursor:not-allowed; @endif">
                        @foreach ($strategies as $key => $def)
                            <option value="{{ $key }}" {{ ($old['strategy'] ?? request('strategy', '')) === $key ? 'selected' : '' }}>{{ $def['label'] }}</option>
                        @endforeach
                    </select>
                    @if($isEditing)
                        <input type="hidden" name="strategy" value="{{ request('strategy') }}">
                    @endif
                </div>

                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Símbolo</label>
                    <select name="symbol" id="symbol" onchange="loadParams(); loadDataRange();"
                            @if($isEditing) disabled @endif
                            class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary); @if($isEditing) opacity:0.6;cursor:not-allowed; @endif">
                        @foreach ($symbols as $sym)
                            <option value="{{ $sym }}" {{ ($old['symbol'] ?? request('symbol', '')) === $sym ? 'selected' : '' }}>{{ $sym }}</option>
                        @endforeach
                    </select>
                    @if($isEditing)
                        <input type="hidden" name="symbol" value="{{ request('symbol') }}">
                    @endif
                </div>

                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Intervalo</label>
                    <select name="interval" id="interval" onchange="loadDataRange()"
                            @if($isEditing) disabled @endif
                            class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary); @if($isEditing) opacity:0.6;cursor:not-allowed; @endif">
                        @foreach ($intervals as $iv)
                            @php $lbs = ['1'=>'1m','5'=>'5m','15'=>'15m','60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1']; @endphp
                            <option value="{{ $iv }}" {{ ($old['interval'] ?? request('interval', '60')) === $iv ? 'selected' : '' }}>{{ $lbs[$iv] ?? $iv }}</option>
                        @endforeach
                    </select>
                    @if($isEditing)
                        <input type="hidden" name="interval" value="{{ request('interval') }}">
                    @endif
                </div>

                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Desde (opcional)</label>
                    <input type="date" name="start_date" id="start_date" value="{{ $old['start_date'] ?? '' }}"
                           class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                           style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>

                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Hasta (opcional)</label>
                    <input type="date" name="end_date" id="end_date" value="{{ $old['end_date'] ?? '' }}"
                           class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                           style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>
            </div>

            <p id="dataRangeInfo" class="text-[11px]" style="color:var(--color-text-muted);"></p>

            {{-- Parámetros comunes --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">Parámetros comunes</h4>
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                    @foreach ([
                        ['sl_pct',             'Stop Loss %',          '1.5'],
                        ['tp_pct',             'Take Profit 1 %',      '3.0'],
                        ['be_pct',             'Break-even %',         '2.0'],
                        ['max_duration',       'Máx. duración (velas)','24'],
                        ['risk_per_trade_pct', 'Riesgo/trade %',       '1.0'],
                    ] as [$name, $label, $default])
                        <div>
                            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">{{ $label }}</label>
                            <input type="number" step="0.1" name="{{ $name }}" id="{{ $name }}"
                                   value="{{ $old[$name] ?? request($name, $default) }}"
                                   class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        </div>
                    @endforeach

                    <div class="flex flex-col justify-end gap-1.5 pb-1">
                        <label class="flex items-center gap-2 text-sm" style="color:var(--color-text-secondary);">
                            <input type="checkbox" name="regime_filter" id="regime_filter" value="1"
                                   {{ ($old ? isset($old['regime_filter']) : true) ? 'checked' : '' }}
                                   class="w-4 h-4 rounded" style="accent-color:var(--color-info);">
                            Filtro de régimen
                        </label>
                        <label class="flex items-center gap-2 text-sm" style="color:var(--color-text-secondary);">
                            <input type="checkbox" name="macro_trend_filter" value="1"
                                   {{ ($old['macro_trend_filter'] ?? '') ? 'checked' : '' }}
                                   class="w-4 h-4 rounded" style="accent-color:var(--color-info);">
                            Filtro macro H4
                        </label>
                    </div>
                </div>
            </div>

            {{-- TP escalonado --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-1" style="color:var(--color-text-secondary);">Take Profit escalonado (opcional)</h4>
                <p class="text-[10px] mb-2" style="color:var(--color-text-muted);">Deja en blanco los niveles que no quieras usar. El motor cierra en el nivel más favorable alcanzado (prioridad TP4 > TP3 > TP2 > TP1).</p>
                <div class="grid grid-cols-3 gap-3">
                    @foreach ([['tp2_pct','Take Profit 2 %'],['tp3_pct','Take Profit 3 %'],['tp4_pct','Take Profit 4 %']] as [$name,$label])
                        <div>
                            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">{{ $label }}</label>
                            <input type="number" step="0.1" name="{{ $name }}" id="{{ $name }}"
                                   value="{{ $old[$name] ?? request($name, '') }}" placeholder="—"
                                   class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        </div>
                    @endforeach
                </div>
            </div>

            {{-- Trailing Stop --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">Trailing Stop (opcional)</h4>
                <select name="trailing_mode" id="trailing_mode" onchange="toggleTrailingFields()"
                        class="w-full sm:w-64 rounded-lg px-3 py-2 text-sm border focus:outline-none mb-3"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="none" {{ ($old['trailing_mode'] ?? 'none') === 'none' ? 'selected' : '' }}>Ninguno</option>
                    <option value="fixed" {{ ($old['trailing_mode'] ?? '') === 'fixed' ? 'selected' : '' }}>Fijo (distancia constante)</option>
                    <option value="stepped" {{ ($old['trailing_mode'] ?? '') === 'stepped' ? 'selected' : '' }}>Por pasos (escalonado)</option>
                </select>
                <div id="trailingFixedFields" class="hidden">
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Distancia trailing %</label>
                    <input type="number" step="0.1" name="trailing_distance_pct" value="{{ $old['trailing_distance_pct'] ?? '1.0' }}"
                           class="w-48 rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                           style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>
                <div id="trailingSteppedFields" class="hidden">
                    <p class="text-[10px] mb-2" style="color:var(--color-text-muted);">Cuando la ganancia alcance el % indicado, el SL salta al % indicado (desde la entrada).</p>
                    <div id="trailingStepsContainer" class="space-y-2">
                        <div class="flex items-center gap-2">
                            <input type="number" step="0.1" name="trailing_step_gain[]" placeholder="Ganancia %"
                                   class="w-32 rounded-lg px-3 py-2 text-sm border font-mono"
                                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                            <span class="text-[11px]" style="color:var(--color-text-muted);">→ SL a</span>
                            <input type="number" step="0.1" name="trailing_step_sl[]" placeholder="SL %"
                                   class="w-32 rounded-lg px-3 py-2 text-sm border font-mono"
                                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        </div>
                    </div>
                    <button type="button" onclick="addTrailingStep()" class="text-[11px] mt-2" style="color:var(--color-info);">+ Agregar escalón</button>
                </div>
            </div>

            {{-- Protección por volatilidad --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">Protección por volatilidad (opcional)</h4>
                <select name="volatility_protection_mode" id="volatility_protection_mode" onchange="toggleVolatilityFields()"
                        class="w-full sm:w-72 rounded-lg px-3 py-2 text-sm border focus:outline-none mb-3"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="none" {{ ($old['volatility_protection_mode'] ?? 'none') === 'none' ? 'selected' : '' }}>Ninguna</option>
                    <option value="close" {{ ($old['volatility_protection_mode'] ?? '') === 'close' ? 'selected' : '' }}>Cerrar si la volatilidad se dispara</option>
                    <option value="widen" {{ ($old['volatility_protection_mode'] ?? '') === 'widen' ? 'selected' : '' }}>Ampliar SL si la volatilidad se dispara</option>
                </select>
                <div id="volatilityFields" class="hidden grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Multiplicador ATR (umbral)</label>
                        <input type="number" step="0.1" name="volatility_atr_multiplier" value="{{ $old['volatility_atr_multiplier'] ?? '2.5' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        <p class="text-[10px] mt-1" style="color:var(--color-text-muted);">Se activa si ATR actual &gt; ATR promedio × este valor</p>
                    </div>
                    <div id="volatilityWidenField" class="hidden">
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Ampliación de SL (puntos %)</label>
                        <input type="number" step="0.1" name="volatility_widen_pct" value="{{ $old['volatility_widen_pct'] ?? '1.0' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                </div>
            </div>

            <div class="border-t pt-4 flex justify-end" style="border-color:var(--color-border-soft);">
                <button type="submit" class="text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
                        style="background:var(--color-info); color:#fff;">
                    Ejecutar backtest (walk-forward)
                </button>
            </div>
        </form>
    </div>

    {{-- ── Resultados ───────────────────────────────────────────────────── --}}
    @if ($result)
        @php $agg = $result['aggregate_metrics']; @endphp

        <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                    {{ $result['strategy'] }} — {{ $result['symbol'] }} / {{ $result['interval'] }}
                </h3>
                <div class="flex items-center gap-2 flex-wrap">
                    @if ($result['passed'])
                        <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium" style="background:#16331F; color:var(--color-profit); border:1px solid #1E4A2E;">✓ Aprobada para paper trading</span>
                    @else
                        <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium" style="background:#3A1A1C; color:var(--color-loss); border:1px solid #5A2226;">✗ No aprobada</span>
                    @endif

                    @if (!empty($result['monthly_breakdown']))
                        <form method="POST" action="{{ route('backtesting.export-excel') }}" id="exportExcelForm">
                            @csrf
                            <input type="hidden" name="result" value='{{ json_encode(array_merge($result, ["_implement_params" => $implementParams ?? []])) }}'>
                            <button type="submit" class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium transition-colors" style="background:var(--color-surface-raised); color:var(--color-info); border:1px solid var(--color-border-strong);">
                                ⬇ Exportar a Excel
                            </button>
                        </form>
                    @endif

                    @can('manageUsers')
                        <button type="button" onclick="confirmImplement()" class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium transition-colors" style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                            ⚡ Implementar en Paper Trading
                        </button>
                        <form method="POST" action="{{ route('paper-trading.configs.implement') }}" id="implementForm" class="hidden">
                            @csrf
@php
    $strategyDisplayName = $result['strategy'];
    if ($result['strategy'] === 'VWAP') {
        $strategyDisplayName = ($implementParams['mode'] ?? '') === 'reversion' ? 'VWAP Reversión' : 'VWAP Tendencia';
    }
@endphp
<input type="hidden" name="strategy_name" value="{{ $strategyDisplayName }}">
                            <input type="hidden" name="symbol" value="{{ $result['symbol'] }}">
                            <input type="hidden" name="interval" value="{{ $result['interval'] }}">
                            <input type="hidden" name="params" id="implementParams" value="{{ json_encode($implementParams ?? []) }}">
                        </form>
                    @endcan
                </div>
            </div>

            {{-- Resumen de config usada --}}
            @if (!empty($implementParams))
                <div class="rounded-md p-2.5 mb-4 font-mono text-[11px]" style="background:var(--color-surface-raised); border:1px solid var(--color-border-soft); color:var(--color-text-muted);">
                    <span style="color:var(--color-text-secondary);">Configuración:</span>
                    sl={{ $implementParams['sl_pct'] ?? '—' }}%
                    tp1={{ $implementParams['tp_pct'] ?? '—' }}%
                    @if (!empty($implementParams['tp2_pct'])) tp2={{ $implementParams['tp2_pct'] }}% @endif
                    @if (!empty($implementParams['tp3_pct'])) tp3={{ $implementParams['tp3_pct'] }}% @endif
                    @if (!empty($implementParams['tp4_pct'])) tp4={{ $implementParams['tp4_pct'] }}% @endif
                    be={{ $implementParams['be_pct'] ?? '—' }}%
                    dur={{ $implementParams['max_duration'] ?? '—' }}
                    riesgo={{ $implementParams['risk_per_trade_pct'] ?? '—' }}%
                    régimen={{ $implementParams['regime_filter'] ? 'sí' : 'no' }}
                    @if (!empty($implementParams['macro_trend_filter'])) <span style="color:var(--color-info);">+macro H4</span> @endif
                    @if (!empty($implementParams['trailing_mode'])) <span style="color:var(--color-info);">+trailing:{{ $implementParams['trailing_mode'] }}</span> @endif
                    @if (!empty($implementParams['volatility_protection_mode'])) <span style="color:var(--color-info);">+vol:{{ $implementParams['volatility_protection_mode'] }}</span> @endif
                </div>
            @endif

            {{-- Métricas --}}
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                @foreach ([
                    'total_trades'=>'Total trades','win_rate'=>'Win rate','profit_factor'=>'Profit factor',
                    'sharpe_ratio'=>'Sharpe ratio','max_drawdown_pct'=>'Max drawdown',
                    'total_return_pct'=>'Return total','expectancy'=>'Expectancy','total_pnl'=>'P&L total',
                ] as $key => $label)
                    <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">{{ $label }}</p>
                        <p class="font-mono text-base font-medium"
                           style="color: {{ in_array($key, ['total_return_pct','total_pnl']) ? ($agg[$key] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)') : 'var(--color-text-primary)' }};">
                            {{ isset($agg[$key]) ? (in_array($key,['win_rate','max_drawdown_pct','total_return_pct']) ? $agg[$key].'%' : (in_array($key,['total_pnl']) ? number_format($agg[$key],2) : $agg[$key])) : '—' }}
                        </p>
                    </div>
                @endforeach
            </div>

            @if (!empty($result['pass_reasons']))
                <div class="mb-4">
                    <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-muted);">Criterios de evaluación</h4>
                    <ul class="space-y-1">
                        @foreach ($result['pass_reasons'] as $reason)
                            <li class="text-sm" style="color: {{ str_contains($reason, 'aprobada') ? 'var(--color-profit)' : 'var(--color-loss)' }};">• {{ $reason }}</li>
                        @endforeach
                    </ul>
                </div>
            @endif

            <details>
                <summary class="text-[11px] font-medium cursor-pointer" style="color:var(--color-text-muted);">Resultados por ventana (walk-forward)</summary>
                <div class="overflow-x-auto mt-2">
                    <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-2 font-normal">Ventana</th>
                                <th class="py-2 px-2 font-normal">Trades</th>
                                <th class="py-2 px-2 font-normal">Win rate</th>
                                <th class="py-2 px-2 font-normal">P. factor</th>
                                <th class="py-2 px-2 font-normal">Sharpe</th>
                                <th class="py-2 px-2 font-normal">Drawdown</th>
                                <th class="py-2 px-2 font-normal">Return</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($result['window_results'] as $w)
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $w['window'] }}</td>
                                    <td class="py-2 px-2">{{ $w['total_trades'] }}</td>
                                    <td class="py-2 px-2">{{ $w['win_rate'] }}%</td>
                                    <td class="py-2 px-2">{{ $w['profit_factor'] ?? '—' }}</td>
                                    <td class="py-2 px-2">{{ $w['sharpe_ratio'] }}</td>
                                    <td class="py-2 px-2">{{ $w['max_drawdown_pct'] }}%</td>
                                    <td class="py-2 px-2" style="color: {{ $w['total_return_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ $w['total_return_pct'] }}%</td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </details>
        </div>

        @if (!empty($result['monthly_breakdown']))
            <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <h3 class="text-sm font-medium mb-3" style="color:var(--color-text-secondary);">Desglose mes a mes</h3>
                <div class="overflow-x-auto">
                    <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-2 font-normal">Mes</th>
                                <th class="py-2 px-2 font-normal">Trades</th>
                                <th class="py-2 px-2 font-normal">G/P</th>
                                <th class="py-2 px-2 font-normal">Win rate</th>
                                <th class="py-2 px-2 font-normal">P&amp;L %</th>
                                <th class="py-2 px-2 font-normal">P&amp;L USDT</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($result['monthly_breakdown'] as $m)
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $m['month'] }}</td>
                                    <td class="py-2 px-2">{{ $m['total_trades'] }}</td>
                                    <td class="py-2 px-2">{{ $m['wins'] }}/{{ $m['losses'] }}</td>
                                    <td class="py-2 px-2">{{ $m['win_rate'] }}%</td>
                                    <td class="py-2 px-2" style="color: {{ $m['total_pnl_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ $m['total_pnl_pct'] >= 0 ? '+' : '' }}{{ $m['total_pnl_pct'] }}%
                                    </td>
                                    <td class="py-2 px-2" style="color: {{ $m['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ number_format($m['total_pnl'], 2) }}
                                    </td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        @endif
    @endif

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
const paperConfigs = {!! $paperConfigsForPreload->toJson() !!};

const strategyClassMap = {
    'VwapStrategy_trend_follow': 'VWAP Tendencia',
    'VwapStrategy_reversion':    'VWAP Reversión',
    'MeanReversionStrategy_':    'Reversión a la Media',
    'EmaDonchianStrategy_':      'Tendencia EMA/Donchian',
};

function loadParams() {
    const strategy = document.getElementById('strategy').value;
    const symbol   = document.getElementById('symbol').value;

    const config = paperConfigs.find(c => {
        const mode = c.params?.mode || '';
        const key  = c.strategy_class + '_' + mode;
        return strategyClassMap[key] === strategy && c.symbol === symbol;
    });

    if (config) {
        const p = config.params;
        if (p.sl_pct !== undefined) document.getElementById('sl_pct').value = p.sl_pct;
        if (p.tp_pct !== undefined) document.getElementById('tp_pct').value = p.tp_pct;
        if (p.be_pct !== undefined) document.getElementById('be_pct').value = p.be_pct;
        if (p.max_duration !== undefined) document.getElementById('max_duration').value = p.max_duration;
        if (p.tp2_pct !== undefined) document.getElementById('tp2_pct').value = p.tp2_pct;
        if (p.tp3_pct !== undefined) document.getElementById('tp3_pct').value = p.tp3_pct ?? '';
        if (p.tp4_pct !== undefined) document.getElementById('tp4_pct').value = p.tp4_pct ?? '';
        const iv = document.getElementById('interval');
        if (config.interval) for (let o of iv.options) if (o.value === config.interval) { o.selected = true; break; }
    }
}

async function loadDataRange() {
    const symbol = document.getElementById('symbol').value;
    const interval = document.getElementById('interval').value;
    const info = document.getElementById('dataRangeInfo');
    try {
        const res = await fetch(`/backtesting/data-range/${symbol}/${interval}`);
        const data = await res.json();
        if (data) {
            const first = new Date(data.first_date).toLocaleDateString('es-ES');
            const last  = new Date(data.last_date).toLocaleDateString('es-ES');
            info.textContent = `Datos disponibles: ${first} — ${last} (${data.total_bars} velas)`;
            document.getElementById('start_date').min = data.first_date.split('T')[0];
            document.getElementById('end_date').max   = data.last_date.split('T')[0];
        }
    } catch (e) {}
}

function toggleTrailingFields() {
    const mode = document.getElementById('trailing_mode').value;
    document.getElementById('trailingFixedFields').classList.toggle('hidden', mode !== 'fixed');
    document.getElementById('trailingSteppedFields').classList.toggle('hidden', mode !== 'stepped');
}

function addTrailingStep() {
    const c = document.getElementById('trailingStepsContainer');
    const d = document.createElement('div'); d.className = 'flex items-center gap-2';
    d.innerHTML = `<input type="number" step="0.1" name="trailing_step_gain[]" placeholder="Ganancia %" class="w-32 rounded-lg px-3 py-2 text-sm border font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);"><span class="text-[11px]" style="color:var(--color-text-muted);">→ SL a</span><input type="number" step="0.1" name="trailing_step_sl[]" placeholder="SL %" class="w-32 rounded-lg px-3 py-2 text-sm border font-mono" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);"><button type="button" onclick="this.parentElement.remove()" style="color:var(--color-loss);">✕</button>`;
    c.appendChild(d);
}

function toggleVolatilityFields() {
    const mode = document.getElementById('volatility_protection_mode').value;
    document.getElementById('volatilityFields').classList.toggle('hidden', mode === 'none');
    document.getElementById('volatilityWidenField').classList.toggle('hidden', mode !== 'widen');
}

document.addEventListener('DOMContentLoaded', () => {
    toggleTrailingFields();
    toggleVolatilityFields();
    loadDataRange();

    // Si no vienen de un POST (old vacío) y no hay preload desde query string, precargar desde config activa
    @if (empty($old) && !request('preload_from'))
        loadParams();
    @endif
});

document.getElementById('backtestForm').addEventListener('submit', function () {
    Swal.fire({
        title: 'Ejecutando backtest...',
        html: 'Procesando walk-forward, esto puede tardar unos segundos.',
        allowOutsideClick: false, allowEscapeKey: false,
        background: '#11161F', color: '#E5E9F0',
        didOpen: () => Swal.showLoading(),
    });
});

const exportForm = document.getElementById('exportExcelForm');
if (exportForm) {
    exportForm.addEventListener('submit', function () {
        Swal.fire({ title: 'Generando Excel...', allowOutsideClick: false, allowEscapeKey: false, background: '#11161F', color: '#E5E9F0', didOpen: () => Swal.showLoading(), timer: 3000, timerProgressBar: true });
    });
}

function confirmImplement() {
    const strategyName = document.getElementById('implementForm').elements['strategy_name'].value;
    const symbol = document.getElementById('implementForm').elements['symbol'].value;
    const interval = document.getElementById('implementForm').elements['interval'].value;

    Swal.fire({
        title: 'Implementar en Paper Trading',
        html: `¿Implementar <b>${strategyName}</b> para <b>${symbol}</b> (${interval})?<br><br>Esto creará o actualizará la configuración activa en producción.`,
        icon: 'question', showCancelButton: true,
        confirmButtonText: 'Implementar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#4D8FE8', cancelButtonColor: '#232B38',
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'Implementando...', allowOutsideClick: false, allowEscapeKey: false, background: '#11161F', color: '#E5E9F0', didOpen: () => Swal.showLoading() });
            document.getElementById('implementForm').submit();
        }
    });
}
</script>
@endpush

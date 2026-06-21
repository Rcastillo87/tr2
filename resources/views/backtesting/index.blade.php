@extends('layouts.app')

@section('title', 'Backtesting')
@section('header', 'Backtesting')

@section('content')

    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Configurar backtest</h3>
            <span class="text-[11px]" style="color:var(--color-text-muted);">Parámetros precargados desde la config activa al cambiar estrategia/símbolo</span>
        </div>

        <form method="POST" action="{{ route('backtesting.run') }}" id="backtestForm" class="space-y-4">
            @csrf

            {{-- Bloque 1: estrategia/simbolo/intervalo/rango fechas --}}
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Estrategia</label>
                    <select name="strategy" id="strategy" onchange="loadParams()"
                            class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        @foreach ($strategies as $key => $def)
                            <option value="{{ $key }}" {{ ($old['strategy'] ?? '') === $key ? 'selected' : '' }}>{{ $def['label'] }}</option>
                        @endforeach
                    </select>
                </div>

                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Símbolo</label>
                    <select name="symbol" id="symbol" onchange="loadParams(); loadDataRange();"
                            class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        @foreach ($symbols as $sym)
                            <option value="{{ $sym }}" {{ ($old['symbol'] ?? '') === $sym ? 'selected' : '' }}>{{ $sym }}</option>
                        @endforeach
                    </select>
                </div>

                <div>
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Intervalo</label>
                    <select name="interval" id="interval" onchange="loadDataRange()"
                            class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                            style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        @foreach ($intervals as $iv)
                            @php $labels = ['1'=>'1m','5'=>'5m','15'=>'15m','60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1']; @endphp
                            <option value="{{ $iv }}" {{ ($old['interval'] ?? '60') === $iv ? 'selected' : '' }}>{{ $labels[$iv] ?? $iv }}</option>
                        @endforeach
                    </select>
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
            <div id="preloadIndicator" class="hidden">
                <p class="text-[11px] px-2 py-1.5 rounded" style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                    ✓ Parámetros precargados desde: <span id="preloadSource" class="font-medium"></span>
                </p>
            </div>

            {{-- Bloque 2: parametros comunes --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">Parámetros comunes</h4>
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Stop Loss %</label>
                        <input type="number" step="0.1" name="sl_pct" id="sl_pct" value="{{ $old['sl_pct'] ?? '1.5' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit 1 %</label>
                        <input type="number" step="0.1" name="tp_pct" id="tp_pct" value="{{ $old['tp_pct'] ?? '3.0' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Break-even %</label>
                        <input type="number" step="0.1" name="be_pct" id="be_pct" value="{{ $old['be_pct'] ?? '2.0' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Máx. duración (velas)</label>
                        <input type="number" step="1" name="max_duration" id="max_duration" value="{{ $old['max_duration'] ?? '24' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Riesgo/trade %</label>
                        <input type="number" step="0.1" name="risk_per_trade_pct" id="risk_per_trade_pct" value="{{ $old['risk_per_trade_pct'] ?? '1.0' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div class="flex items-end pb-2">
                        <label class="flex items-center gap-2 text-sm" style="color:var(--color-text-secondary);">
                            <input type="checkbox" name="regime_filter" value="1" {{ ($old['regime_filter'] ?? '1') ? 'checked' : '' }}
                                   class="w-4 h-4 rounded" style="accent-color:var(--color-info);">
                            Filtro de régimen
                        </label>
                    </div>
                    <div class="flex items-end pb-2">
                        <label class="flex items-center gap-2 text-sm" style="color:var(--color-text-secondary);">
                            <input type="checkbox" name="macro_trend_filter" value="1" {{ ($old['macro_trend_filter'] ?? '') ? 'checked' : '' }}
                                   class="w-4 h-4 rounded" style="accent-color:var(--color-info);">
                            Filtro de tendencia macro H4
                        </label>
                    </div>
                </div>
                <p class="text-[10px] mt-2" style="color:var(--color-text-muted);">
                    El filtro macro H4 bloquea señales contra la tendencia mayor (EMA50 en H4): reduce el retorno total
                    pero suaviza significativamente los meses de pérdida — útil si priorizas menor drawdown sobre retorno máximo.
                </p>
            </div>

            {{-- Bloque 3: Take Profit escalonado TP2-TP4 --}}
            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">Take Profit escalonado (opcional)</h4>
                <p class="text-[10px] mb-2" style="color:var(--color-text-muted);">Deja en blanco los niveles que no quieras usar. El motor cierra en el nivel más favorable alcanzado (prioridad TP4 &gt; TP3 &gt; TP2 &gt; TP1).</p>
                <div class="grid grid-cols-3 gap-3">
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit 2 %</label>
                        <input type="number" step="0.1" name="tp2_pct" id="tp2_pct" value="{{ $old['tp2_pct'] ?? '' }}" placeholder="—"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit 3 %</label>
                        <input type="number" step="0.1" name="tp3_pct" id="tp3_pct" value="{{ $old['tp3_pct'] ?? '' }}" placeholder="—"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                    <div>
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit 4 %</label>
                        <input type="number" step="0.1" name="tp4_pct" id="tp4_pct" value="{{ $old['tp4_pct'] ?? '' }}" placeholder="—"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                </div>
            </div>

            {{-- Bloque 4: Trailing Stop --}}
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
                    <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Distancia del trailing %</label>
                    <input type="number" step="0.1" name="trailing_distance_pct" value="{{ $old['trailing_distance_pct'] ?? '1.0' }}"
                           class="w-full sm:w-48 rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                           style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                </div>

                <div id="trailingSteppedFields" class="hidden">
                    <p class="text-[10px] mb-2" style="color:var(--color-text-muted);">Define escalones: cuando la ganancia alcance el % indicado, el SL salta al % indicado (desde la entrada).</p>
                    <div id="trailingStepsContainer" class="space-y-2">
                        <div class="flex items-center gap-2">
                            <input type="number" step="0.1" name="trailing_step_gain[]" placeholder="Ganancia %"
                                   class="w-32 rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                            <span class="text-[11px]" style="color:var(--color-text-muted);">→ SL a</span>
                            <input type="number" step="0.1" name="trailing_step_sl[]" placeholder="SL %"
                                   class="w-32 rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        </div>
                    </div>
                    <button type="button" onclick="addTrailingStep()" class="text-[11px] mt-2" style="color:var(--color-info);">+ Agregar escalón</button>
                </div>
            </div>

            {{-- Bloque 5: Proteccion por volatilidad --}}
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
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        <p class="text-[10px] mt-1" style="color:var(--color-text-muted);">Se activa si ATR actual &gt; ATR promedio × este valor</p>
                    </div>
                    <div id="volatilityWidenField" class="hidden">
                        <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Ampliación de SL (puntos %)</label>
                        <input type="number" step="0.1" name="volatility_widen_pct" value="{{ $old['volatility_widen_pct'] ?? '1.0' }}"
                               class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    </div>
                </div>
            </div>

            <div class="border-t pt-4" style="border-color:var(--color-border-soft);">
                <button type="submit" class="w-full sm:w-auto text-sm font-medium px-6 py-2.5 rounded-lg transition-colors"
                        style="background:var(--color-info); color:#fff;">
                    Ejecutar backtest (walk-forward)
                </button>
            </div>
        </form>
    </div>

    {{-- Error --}}
    @if ($error)
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
            {{ $error }}
        </div>
    @endif

    {{-- Resultado --}}
    @if ($result)
        @php $agg = $result['aggregate_metrics']; @endphp

        <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                    {{ $result['strategy'] }} — {{ $result['symbol'] }} / {{ $result['interval'] }}
                </h3>
                <div class="flex items-center gap-2">
                    @if ($result['passed'])
                        <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium" style="background:#16331F; color:var(--color-profit); border:1px solid #1E4A2E;">
                            ✓ Aprobada para paper trading
                        </span>
                    @else
                        <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium" style="background:#3A1A1C; color:var(--color-loss); border:1px solid #5A2226;">
                            ✗ No aprobada
                        </span>
                    @endif

                    @if (!empty($result['monthly_breakdown']))
                        <form method="POST" action="{{ route('backtesting.export-excel') }}">
                            @csrf
                            <input type="hidden" name="result" value='{{ json_encode($result) }}'>
                            <button type="submit" class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium" style="background:var(--color-surface-raised); color:var(--color-info); border:1px solid var(--color-border-strong);">
                                ⬇ Exportar a Excel
                            </button>
                        </form>
                    @endif
                </div>
            </div>

            {{-- Métricas agregadas --}}
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                @foreach ([
                    'total_trades'     => 'Total trades',
                    'win_rate'         => 'Win rate',
                    'profit_factor'    => 'Profit factor',
                    'sharpe_ratio'     => 'Sharpe ratio',
                    'max_drawdown_pct' => 'Max drawdown',
                    'total_return_pct' => 'Return total',
                    'expectancy'       => 'Expectancy',
                    'total_pnl'        => 'P&L total',
                ] as $key => $label)
                    <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">{{ $label }}</p>
                        <p class="font-mono text-base font-medium"
                           style="color: {{ in_array($key, ['total_return_pct', 'total_pnl']) ? ($agg[$key] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)') : 'var(--color-text-primary)' }};">
                            {{ isset($agg[$key]) ? (in_array($key, ['win_rate', 'max_drawdown_pct', 'total_return_pct']) ? $agg[$key] . '%' : (in_array($key, ['total_pnl']) ? number_format($agg[$key], 2) : $agg[$key])) : '—' }}
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

            <div>
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-muted);">Resultados por ventana (walk-forward)</h4>
                <div class="overflow-x-auto">
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
            </div>
        </div>

        {{-- Desglose mes a mes --}}
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
<script>
const paperConfigs = {!! $paperConfigs->toJson() !!};

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

    const indicator = document.getElementById('preloadIndicator');
    const source    = document.getElementById('preloadSource');

    if (config) {
        const p = config.params;
        if (p.sl_pct !== undefined) document.getElementById('sl_pct').value = p.sl_pct;
        if (p.tp_pct !== undefined) document.getElementById('tp_pct').value = p.tp_pct;
        if (p.be_pct !== undefined) document.getElementById('be_pct').value = p.be_pct;
        if (p.max_duration !== undefined) document.getElementById('max_duration').value = p.max_duration;
        if (p.tp2_pct !== undefined) document.getElementById('tp2_pct').value = p.tp2_pct;

        const intervalSelect = document.getElementById('interval');
        if (config.interval) {
            for (let opt of intervalSelect.options) {
                if (opt.value === config.interval) { opt.selected = true; break; }
            }
        }

        indicator.classList.remove('hidden');
        source.textContent = config.display_name;
    } else {
        indicator.classList.add('hidden');
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
            document.getElementById('start_date').max = data.last_date.split('T')[0];
            document.getElementById('end_date').min = data.first_date.split('T')[0];
            document.getElementById('end_date').max = data.last_date.split('T')[0];
        } else {
            info.textContent = 'Sin datos disponibles para esta combinación.';
        }
    } catch (e) {
        info.textContent = '';
    }
}

function toggleTrailingFields() {
    const mode = document.getElementById('trailing_mode').value;
    document.getElementById('trailingFixedFields').classList.toggle('hidden', mode !== 'fixed');
    document.getElementById('trailingSteppedFields').classList.toggle('hidden', mode !== 'stepped');
}

function addTrailingStep() {
    const container = document.getElementById('trailingStepsContainer');
    const div = document.createElement('div');
    div.className = 'flex items-center gap-2';
    div.innerHTML = `
        <input type="number" step="0.1" name="trailing_step_gain[]" placeholder="Ganancia %"
               class="w-32 rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
        <span class="text-[11px]" style="color:var(--color-text-muted);">→ SL a</span>
        <input type="number" step="0.1" name="trailing_step_sl[]" placeholder="SL %"
               class="w-32 rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
        <button type="button" onclick="this.parentElement.remove()" class="text-[11px]" style="color:var(--color-loss);">✕</button>
    `;
    container.appendChild(div);
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

    @if (empty($old['strategy']) || empty($old['sl_pct']))
        loadParams();
    @endif
});
</script>
@endpush

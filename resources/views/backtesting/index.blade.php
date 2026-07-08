@extends('layouts.app')
@section('title', 'Backtesting')
@section('header', 'Backtesting')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    <div class="flex items-center justify-between mb-4">
        <p class="text-[11px]" style="color:var(--color-text-muted);">
            Gestiona las estrategias activas en Paper Trading y ejecuta backtests para validar configuraciones antes de implementarlas.
        </p>
        <a href="{{ route('backtesting.run') }}"
           class="inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
           style="background:var(--color-info); color:#fff;">
            + Nuevo backtest
        </a>
    </div>

    @can('manageUsers')
        <div class="rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
                <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">Estrategias en Paper Trading</h3>
                <span class="text-[11px]" style="color:var(--color-text-muted);">Parámetros idénticos a los que corren en producción ahora mismo</span>
            </div>

            {{-- Filtros --}}
            <div class="flex items-center gap-3 px-4 py-3 border-b flex-wrap" style="border-color:var(--color-border-soft);">
                <select id="filterStrategy" onchange="applyFilters()"
                        class="rounded-lg px-3 py-1.5 text-[11px] border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="">Todas las estrategias</option>
                    @foreach (['VWAP Tendencia', 'VWAP Reversión', 'Reversión a la Media', 'Tendencia EMA/Donchian'] as $s)
                        <option value="{{ $s }}">{{ $s }}</option>
                    @endforeach
                </select>

                <select id="filterSymbol" onchange="applyFilters()"
                        class="rounded-lg px-3 py-1.5 text-[11px] border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="">Todos los símbolos</option>
                    @foreach ($paperConfigs->pluck('symbol')->unique()->sort() as $sym)
                        <option value="{{ $sym }}">{{ $sym }}</option>
                    @endforeach
                </select>

                <select id="filterInterval" onchange="applyFilters()"
                        class="rounded-lg px-3 py-1.5 text-[11px] border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="">Todos los intervalos</option>
                    <option value="H1">H1</option>
                    <option value="H2">H2</option>
                </select>

                {{-- Filtro estado --}}
                <select id="filterState" onchange="applyFilters()"
                        class="rounded-lg px-3 py-1.5 text-[11px] border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    <option value="">Todos los estados</option>
                    <option value="activa">Activa</option>
                    <option value="inactiva">Inactiva</option>
                </select>
                {{-- Filtro estrellas (multiselect) --}}
                <div class="flex items-center gap-1">
                    @foreach ([1,2,3,4,5] as $star)
                    <label class="flex items-center gap-0.5 cursor-pointer text-[11px]" title="{{ $star }} estrella(s)">
                        <input type="checkbox" class="star-filter w-3 h-3" value="{{ $star }}" onchange="applyFilters()"
                               style="accent-color:#EF9F27;">
                        <span style="color:#EF9F27;">{{ str_repeat('★', $star) }}</span>
                    </label>
                    @endforeach
                </div>
                <button type="button" onclick="clearFilters()" class="text-[11px] transition-colors" style="color:var(--color-text-muted);">
                    Limpiar filtros
                </button>
                <span id="filterCount" class="text-[11px] ml-auto" style="color:var(--color-text-muted);"></span>
            </div>

            @if ($paperConfigs->isEmpty())
                <div class="p-6 text-center">
                    <p class="text-sm mb-3" style="color:var(--color-text-muted);">Aún no hay configuraciones activas.</p>
                    <a href="{{ route('backtesting.run') }}" class="text-sm" style="color:var(--color-info);">
                        Corre un backtest y usa "Implementar en Paper Trading" para crear la primera →
                    </a>
                </div>
            @else
                <div class="space-y-3">
                    @foreach ($paperConfigs as $config)
                    @php
                        $iLabel  = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m'][$config->interval] ?? $config->interval;
                        $params  = is_array($config->params) ? $config->params : json_decode($config->params, true);
                        $rating  = (float)($config->star_rating ?? 0);
                        $fullR   = (int)round($rating);
                        $emptyR  = 5 - $fullR;
                        $starColor = $rating >= 4 ? '#F5C518' : ($rating >= 3 ? '#EF9F27' : ($rating >= 2 ? '#E8832A' : ($rating > 0 ? '#E24B4A' : '#374151')));
                        $metrics = [
                            ['Win Rate',      $config->star_wr,          $config->avg_win_rate ? $config->avg_win_rate.'%' : '—',        $config->avg_win_rate ? ($config->avg_win_rate >= 50 ? 'var(--color-profit)' : 'var(--color-neutral)') : 'var(--color-text-muted)'],
                            ['Sharpe',        $config->star_sharpe,      $config->sharpe_ratio ?? '—',                                    'var(--color-text-secondary)'],
                            ['Ret. prom/mes', $config->star_ret,         $config->avg_monthly_pnl !== null ? ($config->avg_monthly_pnl >= 0 ? '+' : '').$config->avg_monthly_pnl.'%' : '—', $config->avg_monthly_pnl !== null ? ($config->avg_monthly_pnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)') : 'var(--color-text-muted)'],
                            ['Consistencia',  $config->star_consistency, $config->consistency_pct !== null ? $config->consistency_pct.'%' : '—', 'var(--color-text-secondary)'],
                            ['Profit Factor', $config->star_pf,          $config->profit_factor ?? '—',                                  'var(--color-text-secondary)'],
                        ];
                    @endphp
                    @php
                        $strategyPrefix = str_contains($config->display_name, 'VWAP Tendencia') ? 'VWAP Tendencia' :
                            (str_contains($config->display_name, 'VWAP Reversión') ? 'VWAP Reversión' :
                            (str_contains($config->display_name, 'Reversión a la Media') ? 'Reversión a la Media' : 'Tendencia EMA/Donchian'));
                    @endphp
                    <div class="rounded-lg border config-row"
                         data-strategy="{{ $strategyPrefix }}"
                         data-symbol="{{ $config->symbol }}"
                         data-interval="{{ $iLabel }}"
                         data-star="{{ $config->star_rating ?? '0' }}"
                         data-state="{{ $config->active ? 'activa' : 'inactiva' }}">
                        {{-- Cabecera: nombre + estado + acciones --}}
                        <div class="flex items-center justify-between px-4 py-2.5 border-b" style="border-color:var(--color-border-soft);">
                            <div class="flex items-center gap-2">
                                <span class="text-[12px] font-medium" style="color:var(--color-text-primary);">{{ $config->display_name }}</span>
                            </div>
                            <div class="flex items-center gap-3">
                                <span class="px-1.5 py-0.5 rounded text-[10px]"
                                      style="background:{{ $config->active ? '#16331F' : '#3A1A1C' }}; color:{{ $config->active ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ $config->active ? 'ACTIVA' : 'INACTIVA' }}
                                </span>
                                <a href="{{ route('backtesting.retest', $config) }}"
                                   onclick="return loadConfigAndRun(event, {{ $config->id }})"
                                   class="text-[11px]" style="color:var(--color-info);">Editar</a>
                                <form method="POST" action="{{ route('paper-trading.configs.toggle', $config) }}"
                                      onsubmit="return confirmToggle(event, '{{ $config->display_name }}', {{ $config->active ? 'true' : 'false' }})">
                                    @csrf @method('PATCH')
                                    <button type="submit" class="text-[11px]"
                                            style="color:{{ $config->active ? 'var(--color-loss)' : 'var(--color-profit)' }};">
                                        {{ $config->active ? 'Deshabilitar' : 'Activar' }}
                                    </button>
                                </form>
                            </div>
                        </div>
                        {{-- Parámetros --}}
                        <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:0; border-bottom:1px solid var(--color-border-soft);">
                            @foreach([
                                ['Stop Loss',    ($params['sl_pct'] ?? '—').'%'],
                                ['Take Profit',  ($params['tp_pct'] ?? '—').'%'],
                                ['Break-even',   ($params['be_pct'] ?? '—').'%'],
                                ['Duración',     ($params['max_duration'] ?? '—').' velas'],
                                ['Riesgo/trade', ($params['risk_per_trade_pct'] ?? '—').'%'],
                            ] as [$label, $value])
                            <div class="px-2 py-2 text-center" style="border-right:1px solid var(--color-border-soft);">
                                <p class="text-[9px] mb-0.5" style="color:var(--color-text-muted);">{{ $label }}</p>
                                <p class="text-[9px] font-mono font-medium" style="color:var(--color-text-primary);">{{ $value }}</p>
                            </div>
                            @endforeach
                        </div>
                        {{-- Calificación + 5 métricas --}}
                        <div class="px-4 py-2.5">
                            <div class="flex items-center justify-between mb-2">
                                <div style="display:inline-flex; align-items:center; gap:6px; background:var(--color-surface-raised); border-radius:5px; padding:4px 10px;">
                                    <span style="font-size:20px; line-height:1; color:{{ $starColor }};">{{ str_repeat('★',$fullR).str_repeat('☆',$emptyR) }}</span>
                                    <span style="font-size:16px; font-weight:700; color:{{ $starColor }};">{{ $rating > 0 ? $rating : '—' }}</span>
                                </div>
                                @if($config->backtest_range_from)
                                <span class="text-[11px]" style="color:var(--color-text-muted);">📅 {{ $config->backtest_range_from }} → {{ $config->backtest_range_to }}</span>
                                @endif
                                @if($config->avg_monthly_trades !== null)
                                <span class="text-[11px]" style="color:var(--color-text-muted);">🔁 {{ number_format($config->avg_monthly_trades, 1) }} op./mes</span>
                                @endif
                            </div>
                            <div style="display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:4px;">
                                @foreach($metrics as [$mlabel, $mstar, $mval, $mcolor])
                                @php
                                    $mFull  = (int)($mstar ?? 0);
                                    $mEmpty = 5 - $mFull;
                                @endphp
                                <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                                    <p style="font-size:11px; color:var(--color-text-muted); margin:0 0 3px;">{{ $mlabel }}</p>
                                    <p class="hidden sm:block" style="font-size:15px; color:{{ $mFull > 0 ? $starColor : '#374151' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★',$mFull).str_repeat('☆',$mEmpty) }}</p>
                                    <p class="sm:hidden" style="font-size:13px; font-weight:700; color:{{ $mFull > 0 ? $starColor : '#374151' }}; margin:0 0 3px; line-height:1;">{{ $mFull }}★</p>
                                    <p style="font-size:11px; font-family:monospace; color:{{ $mcolor }}; margin:0;">{{ $mval }}</p>
                                </div>
                                @endforeach
                            </div>
                        </div>
                    </div>
                    @endforeach
                </div>
            @endif
        </div>
    @endcan

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
async function loadConfigAndRun(event, configId) {
    event.preventDefault();
    Swal.fire({ title: 'Cargando configuración...', allowOutsideClick: false, background: '#11161F', color: '#E5E9F0', didOpen: () => Swal.showLoading() });
    try {
        const res  = await fetch(`/backtesting/retest/${configId}`, { headers: { 'Accept': 'application/json' } });
        const data = await res.json();
        Swal.close();
        const params = new URLSearchParams({
            strategy:           data.strategy_name,
            symbol:             data.symbol,
            interval:           data.interval,
            sl_pct:             data.params.sl_pct ?? '',
            tp_pct:             data.params.tp_pct ?? '',
            tp2_pct:            data.params.tp2_pct ?? '',
            tp3_pct:            data.params.tp3_pct ?? '',
            tp4_pct:            data.params.tp4_pct ?? '',
            be_pct:             data.params.be_pct ?? '',
            max_duration:       data.params.max_duration ?? '',
            risk_per_trade_pct: data.params.risk_per_trade_pct ?? '',
            regime_filter:      data.params.regime_filter ? '1' : '',
            macro_trend_filter: data.params.macro_trend_filter ? '1' : '',
            volume_filter:      data.params.volume_filter ? '1' : '',
            volume_filter_period: data.params.volume_filter_period ?? '',
            volume_filter_mult:   data.params.volume_filter_mult ?? '',
            blocked_hours_active: data.params.blocked_hours?.length ? '1' : '',
            blocked_days_active:  data.params.blocked_days?.length ? '1' : '',
            trailing_mode:        data.params.trailing_mode ?? 'none',
            trailing_distance_pct: data.params.trailing_distance_pct ?? '',
            volatility_protection_mode: data.params.volatility_protection_mode ?? 'none',
            volatility_atr_multiplier:  data.params.volatility_atr_multiplier ?? '',
            preload_from:       data.strategy_name,
            config_id:          configId,
        });
        // Agregar blocked_hours y blocked_days como arrays
        if (data.params.blocked_hours?.length) {
            data.params.blocked_hours.forEach(h => params.append('blocked_hours[]', h));
        }
        if (data.params.blocked_days?.length) {
            data.params.blocked_days.forEach(d => params.append('blocked_days[]', d));
        }
        window.location.href = `/backtesting/run?${params.toString()}`;
    } catch (e) {
        Swal.fire({ title: 'Error', text: 'No se pudo cargar la configuración.', icon: 'error', background: '#11161F', color: '#E5E9F0' });
    }
}

function applyFilters() {
    const strategy   = document.getElementById('filterStrategy').value;
    const symbol     = document.getElementById('filterSymbol').value;
    const interval   = document.getElementById('filterInterval').value;
    const state      = document.getElementById('filterState').value;
    const starChecks = [...document.querySelectorAll('.star-filter:checked')].map(cb => parseInt(cb.value));
    const rows       = document.querySelectorAll('.config-row');
    let visible = 0;
    rows.forEach(row => {
        const rowStar  = parseFloat(row.dataset.star || '0');
        const rowState = row.dataset.state || '';
        const starOk   = starChecks.length === 0 || starChecks.includes(Math.round(rowStar));
        const stateOk  = !state || rowState === state;
        const ok = (!strategy || row.dataset.strategy === strategy)
                && (!symbol   || row.dataset.symbol   === symbol)
                && (!interval || row.dataset.interval === interval)
                && stateOk && starOk;
        row.style.display = ok ? '' : 'none';
        if (ok) visible++;
    });
    const counter = document.getElementById('filterCount');
    counter.textContent = visible === rows.length ? '' : `${visible} de ${rows.length} estrategias`;

    // Persistir filtros para que sobrevivan la navegacion a /backtesting/run y "Volver"
    sessionStorage.setItem('backtestingFilters', JSON.stringify({
        strategy, symbol, interval, state, starChecks,
    }));
}

function clearFilters() {
    document.getElementById('filterStrategy').value = '';
    document.getElementById('filterSymbol').value   = '';
    document.getElementById('filterInterval').value = '';
    document.getElementById('filterState').value    = '';
    document.querySelectorAll('.star-filter').forEach(cb => cb.checked = false);
    sessionStorage.removeItem('backtestingFilters');
    applyFilters();
}

function restoreFilters() {
    const saved = sessionStorage.getItem('backtestingFilters');
    if (!saved) return;
    try {
        const f = JSON.parse(saved);
        if (f.strategy) document.getElementById('filterStrategy').value = f.strategy;
        if (f.symbol)   document.getElementById('filterSymbol').value   = f.symbol;
        if (f.interval) document.getElementById('filterInterval').value = f.interval;
        if (f.state)    document.getElementById('filterState').value    = f.state;
        if (Array.isArray(f.starChecks)) {
            f.starChecks.forEach(v => {
                const cb = document.querySelector(`.star-filter[value="${v}"]`);
                if (cb) cb.checked = true;
            });
        }
        applyFilters();
    } catch (e) {
        sessionStorage.removeItem('backtestingFilters');
    }
}

document.addEventListener('DOMContentLoaded', restoreFilters);

function confirmToggle(event, name, isActive) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: isActive ? 'Deshabilitar estrategia' : 'Activar estrategia',
        html: isActive
            ? `¿Deshabilitar <b>${name}</b>? Dejará de operar en Paper Trading inmediatamente.`
            : `¿Activar <b>${name}</b> en Paper Trading?`,
        icon: 'warning', showCancelButton: true,
        confirmButtonText: isActive ? 'Deshabilitar' : 'Activar',
        cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: isActive ? '#F2545B' : '#3DD68C',
        cancelButtonColor: '#232B38',
    }).then((result) => { if (result.isConfirmed) form.submit(); });
    return false;
}
</script>
@endpush

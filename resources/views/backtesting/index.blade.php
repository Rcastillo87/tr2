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
                    @foreach (['BTCUSDT', 'ETHUSDT', 'SOLUSDT'] as $sym)
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
                <div class="overflow-x-auto">
                    <table class="w-full text-[11px] text-left" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
                                <th class="py-2.5 px-4 font-medium">Estrategia</th>
                                <th class="py-2.5 px-3 font-medium">Símbolo</th>
                                <th class="py-2.5 px-3 font-medium">Int.</th>
                                <th class="py-2.5 px-3 font-medium">SL</th>
                                <th class="py-2.5 px-3 font-medium">TP1</th>
                                <th class="py-2.5 px-3 font-medium">TP2</th>
                                <th class="py-2.5 px-3 font-medium">TP3</th>
                                <th class="py-2.5 px-3 font-medium">TP4</th>
                                <th class="py-2.5 px-3 font-medium">BE</th>
                                <th class="py-2.5 px-3 font-medium">Dur.</th>
                                <th class="py-2.5 px-3 font-medium">Estado</th>
                                <th class="py-2.5 px-4 font-medium">Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($paperConfigs as $config)
                                @php
                                    $strategyPrefix = str_contains($config->display_name, 'VWAP Tendencia') ? 'VWAP Tendencia' :
                                        (str_contains($config->display_name, 'VWAP Reversión') ? 'VWAP Reversión' :
                                        (str_contains($config->display_name, 'Reversión a la Media') ? 'Reversión a la Media' : 'Tendencia EMA/Donchian'));
                                    $iLabel = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m'][$config->interval] ?? $config->interval;
                                @endphp
                                <tr class="config-row border-b transition-colors"
                                    data-strategy="{{ $strategyPrefix }}"
                                    data-symbol="{{ $config->symbol }}"
                                    data-interval="{{ $iLabel }}"
                                    style="border-color:var(--color-border-soft);"
                                    onmouseover="this.style.background='var(--color-surface-raised)'"
                                    onmouseout="this.style.background='transparent'">
                                    <td class="py-2.5 px-4 font-medium" style="color:var(--color-text-primary);">{{ $config->display_name }}</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->symbol }}</td>
                                    <td class="py-2.5 px-3 font-mono">
                                        @php $iLabels = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                                        {{ $iLabels[$config->interval] ?? $config->interval }}
                                    </td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['sl_pct'] ?? '—' }}%</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['tp_pct'] ?? '—' }}%</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['tp2_pct'] ?? '—' }}</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['tp3_pct'] ?? '—' }}</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['tp4_pct'] ?? '—' }}</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['be_pct'] ?? '—' }}%</td>
                                    <td class="py-2.5 px-3 font-mono">{{ $config->params['max_duration'] ?? '—' }}h</td>
                                    <td class="py-2.5 px-3">
                                        <span class="px-1.5 py-0.5 rounded text-[10px]"
                                              style="background: {{ $config->active ? '#16331F' : '#3A1A1C' }}; color: {{ $config->active ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                            {{ $config->active ? 'ACTIVA' : 'INACTIVA' }}
                                        </span>
                                    </td>
                                    <td class="py-2.5 px-4">
                                        <div class="flex items-center gap-3">
                                            <a href="{{ route('backtesting.retest', $config) }}"
                                               onclick="return loadConfigAndRun(event, {{ $config->id }})"
                                               class="transition-colors" style="color:var(--color-info);">Editar</a>
                                            <form method="POST" action="{{ route('paper-trading.configs.toggle', $config) }}"
                                                  onsubmit="return confirmToggle(event, '{{ $config->display_name }}', {{ $config->active ? 'true' : 'false' }})">
                                                @csrf @method('PATCH')
                                                <button type="submit" class="transition-colors"
                                                        style="color: {{ $config->active ? 'var(--color-loss)' : 'var(--color-profit)' }};">
                                                    {{ $config->active ? 'Deshabilitar' : 'Activar' }}
                                                </button>
                                            </form>
                                        </div>
                                    </td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
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
    Swal.fire({
        title: 'Cargando configuración...',
        allowOutsideClick: false,
        background: '#11161F',
        color: '#E5E9F0',
        didOpen: () => Swal.showLoading(),
    });
    try {
        const res = await fetch(`/backtesting/retest/${configId}`, { headers: { 'Accept': 'application/json' } });
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
            preload_from:       data.strategy_name,
        });
        window.location.href = `/backtesting/run?${params.toString()}`;
    } catch (e) {
        Swal.fire({ title: 'Error', text: 'No se pudo cargar la configuración.', icon: 'error', background: '#11161F', color: '#E5E9F0' });
    }
}

function applyFilters() {
    const strategy = document.getElementById('filterStrategy').value;
    const symbol   = document.getElementById('filterSymbol').value;
    const interval = document.getElementById('filterInterval').value;
    const rows     = document.querySelectorAll('.config-row');
    let visible    = 0;
    rows.forEach(row => {
        const ok = (!strategy || row.dataset.strategy === strategy)
                && (!symbol   || row.dataset.symbol   === symbol)
                && (!interval || row.dataset.interval === interval);
        row.style.display = ok ? '' : 'none';
        if (ok) visible++;
    });
    const counter = document.getElementById('filterCount');
    counter.textContent = visible === rows.length ? '' : `${visible} de ${rows.length} estrategias`;
}

function clearFilters() {
    document.getElementById('filterStrategy').value = '';
    document.getElementById('filterSymbol').value   = '';
    document.getElementById('filterInterval').value = '';
    applyFilters();
}

function confirmToggle(event, name, isActive) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: isActive ? 'Deshabilitar estrategia' : 'Activar estrategia',
        html: isActive
            ? `¿Deshabilitar <b>${name}</b>? Dejará de operar en Paper Trading inmediatamente.`
            : `¿Activar <b>${name}</b> en Paper Trading?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: isActive ? 'Deshabilitar' : 'Activar',
        cancelButtonText: 'Cancelar',
        background: '#11161F',
        color: '#E5E9F0',
        confirmButtonColor: isActive ? '#F2545B' : '#3DD68C',
        cancelButtonColor: '#232B38',
    }).then((result) => {
        if (result.isConfirmed) form.submit();
    });
    return false;
}
</script>
@endpush

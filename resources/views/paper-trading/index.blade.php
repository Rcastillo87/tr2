@extends('layouts.app')
@section('title', 'Paper Trading')
@section('header', 'Paper Trading')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

{{-- Filtros --}}
<form method="GET" action="{{ route('paper-trading.index') }}" id="filterForm">
    <div class="flex items-center gap-2 mb-4 flex-wrap">

        {{-- Selector de mes --}}
        <select name="mes" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            @foreach ($availableMonths as $m)
                <option value="{{ $m['value'] }}" {{ $selectedMonth->format('Y-m') === $m['value'] ? 'selected' : '' }}>
                    {{ $m['label'] }}
                </option>
            @endforeach
        </select>

        {{-- Filtro por estrategia --}}
        <select name="strategy" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterStrategy === 'all' ? 'selected' : '' }}>Todas las estrategias</option>
            @foreach ($filterOptions['strategies'] as $s)
                <option value="{{ $s }}" {{ $filterStrategy === $s ? 'selected' : '' }}>{{ $s }}</option>
            @endforeach
        </select>

        {{-- Filtro por símbolo --}}
        <select name="symbol" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterSymbol === 'all' ? 'selected' : '' }}>Todos los símbolos</option>
            @foreach ($filterOptions['symbols'] as $sym)
                <option value="{{ $sym }}" {{ $filterSymbol === $sym ? 'selected' : '' }}>{{ $sym }}</option>
            @endforeach
        </select>

        {{-- Filtro por intervalo --}}
        @php $iLabels = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
        <select name="interval" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterInterval === 'all' ? 'selected' : '' }}>Todos los intervalos</option>
            @foreach ($filterOptions['intervals'] as $iv)
                <option value="{{ $iv }}" {{ $filterInterval === $iv ? 'selected' : '' }}>{{ $iLabels[$iv] ?? $iv }}</option>
            @endforeach
        </select>

        {{-- Filtro resultado --}}
        <select name="result" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all"  {{ $filterResult === 'all'  ? 'selected' : '' }}>Todos los resultados</option>
            <option value="win"  {{ $filterResult === 'win'  ? 'selected' : '' }}>Ganadoras</option>
            <option value="loss" {{ $filterResult === 'loss' ? 'selected' : '' }}>Perdedoras</option>
        </select>

        @if ($filterStrategy !== 'all' || $filterSymbol !== 'all' || $filterInterval !== 'all' || $filterResult !== 'all')
            <a href="{{ route('paper-trading.index', ['mes' => $selectedMonth->format('Y-m')]) }}"
               class="text-xs px-2 py-1 rounded transition-colors"
               style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
               Limpiar filtros
            </a>
        @endif
    </div>
</form>

{{-- KPIs consolidados --}}
<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">P&L del mes</p>
        <p class="font-mono text-xl font-medium" style="color: {{ $totalPnlPct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
            {{ $totalPnlPct >= 0 ? '+' : '' }}{{ number_format($totalPnlPct, 2) }}%
        </p>
    </div>
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Win rate</p>
        <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">{{ $winRate }}%</p>
    </div>
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Profit factor</p>
        <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">
            {{ $profitFactor ?? '—' }}
        </p>
    </div>
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Trades cerrados</p>
        <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">
            {{ $totalClosed }} <span class="text-sm font-normal" style="color:var(--color-text-muted);">({{ $wins }}G / {{ $totalClosed - $wins }}P)</span>
        </p>
    </div>
</div>

{{-- Curva de equity --}}
@if (count($equityCurvePct) > 1)
<div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <p class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Curva de equity (%)</p>
    <canvas id="equityChart" height="80"></canvas>
</div>
@endif

{{-- Simulador de capital --}}
<div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <p class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Simulador de capital</p>
    <div class="flex items-center gap-3 flex-wrap">
        <div>
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Capital inicial (USDT)</label>
            <input type="number" id="simCapital" value="10000" min="100" step="100"
                   oninput="updateSimulator()"
                   class="rounded-lg px-3 py-2 text-sm border font-mono focus:outline-none w-36"
                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
        </div>
        <div class="mt-4">
            <p class="text-[11px] mb-1" style="color:var(--color-text-muted);">Capital final estimado</p>
            <p id="simResult" class="font-mono text-lg font-medium" style="color:var(--color-profit);">—</p>
        </div>
        <div class="mt-4">
            <p class="text-[11px] mb-1" style="color:var(--color-text-muted);">Ganancia / Pérdida</p>
            <p id="simPnl" class="font-mono text-lg font-medium">—</p>
        </div>
    </div>
</div>

{{-- Posiciones abiertas --}}
@if ($openTrades->isNotEmpty())
<div class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">
            Posiciones abiertas ({{ $openTrades->count() }})
        </h3>
        <span class="text-[10px]" style="color:var(--color-text-muted);">Precio actualizado cada 30s</span>
    </div>
    <div class="overflow-x-auto">
        <table class="w-full font-mono text-[11px]" style="color:var(--color-text-muted);">
            <thead>
                <tr class="border-b" style="border-color:var(--color-border-soft);">
                    <th class="py-2 px-3 text-left font-normal">Estrategia</th>
                    <th class="py-2 px-3 text-left font-normal">Símbolo</th>
                    <th class="py-2 px-3 text-left font-normal">Int.</th>
                    <th class="py-2 px-3 text-left font-normal">Dir.</th>
                    <th class="py-2 px-3 text-left font-normal">Entrada</th>
                    <th class="py-2 px-3 text-left font-normal">Precio actual</th>
                    <th class="py-2 px-3 text-left font-normal">SL</th>
                    <th class="py-2 px-3 text-left font-normal">TP</th>
                    <th class="py-2 px-3 text-left font-normal">P&L flotante</th>
                    <th class="py-2 px-3 text-left font-normal">Hora entrada</th>
                </tr>
            </thead>
            <tbody>
                @foreach ($openTrades as $trade)
                    @php $lbs = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                    <tr class="border-b" style="border-color:var(--color-border-soft);">
                        <td class="py-2 px-3" style="color:var(--color-text-primary);">{{ trim(explode('—', $trade->strategy)[0]) }}</td>
                        <td class="py-2 px-3">{{ $trade->symbol }}</td>
                        <td class="py-2 px-3">{{ $lbs[$trade->interval] ?? $trade->interval }}</td>
                        <td class="py-2 px-3">
                            <span style="color: {{ $trade->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ strtoupper($trade->side) }}
                            </span>
                        </td>
                        <td class="py-2 px-3">{{ number_format($trade->entry_price, 2) }}</td>
                        <td class="py-2 px-3 font-mono" id="price_{{ $trade->id }}"
                            data-entry="{{ $trade->entry_price }}"
                            data-side="{{ $trade->side }}"
                            style="color:var(--color-text-muted);">
                            {{ $trade->current_price ? number_format($trade->current_price, 2) : '—' }}
                        </td>
                        <td class="py-2 px-3" style="color:var(--color-loss);">{{ number_format($trade->sl, 2) }}</td>
                        <td class="py-2 px-3" style="color:var(--color-profit);">{{ number_format($trade->tp, 2) }}</td>
                        <td class="py-2 px-3" id="pnl_{{ $trade->id }}"
                            style="color: {{ ($trade->floating_pnl_pct ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                            {{ $trade->floating_pnl_pct !== null ? ($trade->floating_pnl_pct >= 0 ? '+' : '') . number_format($trade->floating_pnl_pct, 3) . '%' : '—' }}
                        </td>
                        <td class="py-2 px-3">{{ \Carbon\Carbon::parse($trade->entry_time)->timezone('America/Bogota')->format('d/m H:i') }}</td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    </div>
</div>
@endif

{{-- Historial de operaciones --}}
<div class="rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">
            Historial de operaciones — {{ ucfirst($selectedMonth->translatedFormat('F Y')) }}
            @if ($filterStrategy !== 'all' || $filterSymbol !== 'all' || $filterInterval !== 'all' || $filterResult !== 'all')
                <span class="text-[10px] ml-2" style="color:var(--color-info);">(filtrado)</span>
            @endif
        </h3>
    </div>

    @if ($closedTrades->isEmpty())
        <div class="p-6 text-center">
            <p class="text-sm" style="color:var(--color-text-muted);">Sin operaciones cerradas en este período.</p>
        </div>
    @else
        <div class="overflow-x-auto">
            <table class="w-full font-mono text-[11px]" style="color:var(--color-text-muted);">
                <thead>
                    <tr class="border-b" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
                        <th class="py-2 px-3 text-left font-normal">Estrategia</th>
                        <th class="py-2 px-3 text-left font-normal">Símbolo</th>
                        <th class="py-2 px-3 text-left font-normal">Int.</th>
                        <th class="py-2 px-3 text-left font-normal">Dir.</th>
                        <th class="py-2 px-3 text-left font-normal">Entrada</th>
                        <th class="py-2 px-3 text-left font-normal">Salida</th>
                        <th class="py-2 px-3 text-left font-normal">Razón</th>
                        <th class="py-2 px-3 text-left font-normal">P&L %</th>
                        <th class="py-2 px-3 text-left font-normal">Hora entrada</th>
                        <th class="py-2 px-3 text-left font-normal">Hora salida</th>
                                <th class="py-2 px-3 text-left font-normal">Duración</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($closedTrades as $trade)
                        @php $lbs = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <td class="py-2 px-3" style="color:var(--color-text-primary);">{{ trim(explode('—', $trade->strategy)[0]) }}</td>
                            <td class="py-2 px-3">{{ $trade->symbol }}</td>
                            <td class="py-2 px-3">{{ $lbs[$trade->interval] ?? $trade->interval }}</td>
                            <td class="py-2 px-3">
                                <span style="color: {{ $trade->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ strtoupper($trade->side) }}
                                </span>
                            </td>
                            <td class="py-2 px-3">{{ number_format($trade->entry_price, 2) }}</td>
                            <td class="py-2 px-3">{{ number_format($trade->exit_price, 2) }}</td>
                            <td class="py-2 px-3">{{ str_replace('_', ' ', $trade->exit_reason ?? '—') }}</td>
                            <td class="py-2 px-3 font-medium"
                                style="color: {{ $trade->pnl_pct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ $trade->pnl_pct >= 0 ? '+' : '' }}{{ number_format($trade->pnl_pct, 2) }}%
                            </td>
                            <td class="py-2 px-3">{{ \Carbon\Carbon::parse($trade->entry_time)->timezone('America/Bogota')->format('d/m H:i') }}</td>
                            <td class="py-2 px-3">{{ $trade->exit_time ? \Carbon\Carbon::parse($trade->exit_time)->timezone('America/Bogota')->format('d/m H:i') : '—' }}</td>
                            <td class="py-2 px-3">
                                @if ($trade->exit_time && $trade->entry_time)
                                    @php
                                        $mins = \Carbon\Carbon::parse($trade->entry_time)->diffInMinutes(\Carbon\Carbon::parse($trade->exit_time));
                                        $h = intdiv($mins, 60);
                                        $m = $mins % 60;
                                    @endphp
                                    {{ $h > 0 ? $h . 'h ' : '' }}{{ $m }}m
                                @else
                                    —
                                @endif
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    @endif
</div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const equityData = {!! json_encode($equityCurvePct) !!};
const totalPnlPct = {{ $totalPnlPct }};

// Curva de equity
@if (count($equityCurvePct) > 1)
const ctx = document.getElementById('equityChart').getContext('2d');
const finalColor = equityData[equityData.length - 1] >= 0
    ? 'rgba(61, 214, 140, 1)'
    : 'rgba(242, 84, 91, 1)';
const finalColorAlpha = equityData[equityData.length - 1] >= 0
    ? 'rgba(61, 214, 140, 0.1)'
    : 'rgba(242, 84, 91, 0.1)';

new Chart(ctx, {
    type: 'line',
    data: {
        labels: equityData.map((_, i) => i),
        datasets: [{
            data: equityData,
            borderColor: finalColor,
            backgroundColor: finalColorAlpha,
            borderWidth: 1.5,
            pointRadius: 0,
            fill: true,
            tension: 0.3,
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: {
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#6B7280', font: { size: 10 }, callback: v => v + '%' }
            }
        }
    }
});
@endif

// Simulador de capital
function updateSimulator() {
    const capital = parseFloat(document.getElementById('simCapital').value) || 0;
    const final   = capital * (1 + totalPnlPct / 100);
    const pnl     = final - capital;

    document.getElementById('simResult').textContent = final.toLocaleString('es-CO', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }) + ' USDT';
    document.getElementById('simResult').style.color = pnl >= 0
        ? 'var(--color-profit)' : 'var(--color-loss)';

    document.getElementById('simPnl').textContent = (pnl >= 0 ? '+' : '') + pnl.toLocaleString('es-CO', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }) + ' USDT';
    document.getElementById('simPnl').style.color = pnl >= 0
        ? 'var(--color-profit)' : 'var(--color-loss)';
}
updateSimulator();

// Precio en tiempo real - posiciones abiertas (cada 30s)
async function refreshLivePrices() {
    try {
        const res = await fetch('{{ route("paper-trading.live") }}');
        const data = await res.json();

        (data.data || []).forEach(trade => {
            const priceEl = document.getElementById('price_' + trade.id);
            const pnlEl   = document.getElementById('pnl_' + trade.id);

            if (priceEl && trade.current_price) {
                const current  = parseFloat(trade.current_price);
                const entry    = parseFloat(priceEl.dataset.entry);
                const side     = priceEl.dataset.side;
                const up       = current >= entry;
                // Para LONG: verde si sube, rojo si baja. Para SHORT: al reves
                const isGood   = side === 'long' ? up : !up;
                const arrow    = up ? '▲ ' : '▼ ';
                priceEl.textContent = arrow + current.toLocaleString('es-CO', {
                    minimumFractionDigits: 2, maximumFractionDigits: 2
                });
                priceEl.style.color = isGood ? 'var(--color-profit)' : 'var(--color-loss)';
            }
            if (pnlEl && trade.floating_pnl_pct !== null) {
                const pct = parseFloat(trade.floating_pnl_pct);
                pnlEl.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(3) + '%';
                pnlEl.style.color = pct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
            }
        });
    } catch (e) {
        console.warn('Error actualizando precios:', e);
    }
}

@if ($openTrades->isNotEmpty())
refreshLivePrices();
setInterval(refreshLivePrices, 20000);
@endif
</script>
@endpush

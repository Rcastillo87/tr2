@extends('layouts.app')

@section('title', 'Vista General')
@section('header', 'Vista general')

@section('content')

    {{-- 1. Precios en vivo --}}
    <div class="rounded-lg border p-3 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between mb-2">
            <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Precios en vivo</h3>
            <span class="text-[10px]" style="color:var(--color-text-muted);">Actualización cada 15s</span>
        </div>
        <div id="livePricesContainer" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2">
            @foreach($activeSymbols as $sym)
                @php
                    $data = $initialPrices[$sym] ?? null;
                    $price = $data['price'] ?? null;
                    $change = $data['change_pct'] ?? 0;
                @endphp
                <div class="rounded border px-3 py-2 flex flex-col" id="price-card-{{ $sym }}" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <span class="font-bold text-xs" style="color:var(--color-text-primary);">{{ $sym }}</span>
                    <div class="flex items-center justify-between mt-1">
                        <span class="font-mono text-xs price-val" style="color:var(--color-text-secondary);">
                            {{ $price ? '$' . number_format($price, 2) : 'Cargando...' }}
                        </span>
                        <span class="text-[10px] font-medium price-trend" style="color: {{ $price ? ($change >= 0 ? 'var(--color-profit)' : 'var(--color-loss)') : 'var(--color-text-muted)' }};">
                            @if($price)
                                {{ $change >= 0 ? '↑' : '↓' }} {{ number_format(abs($change), 2) }}%
                            @else
                                —
                            @endif
                        </span>
                    </div>
                </div>
            @endforeach
        </div>
    </div>

    @can('viewRealTrading')
    {{-- 2. Resumen del mes — real trading --}}
    <div class="flex items-center justify-between mb-2">
        <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Resumen de {{ ucfirst(now()->translatedFormat('F Y')) }} — real trading</h3>
    </div>
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">P&amp;L del mes</p>
            <p class="font-mono text-lg font-medium" style="color: {{ $totalRealPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                {{ $totalRealPnl >= 0 ? '+' : '' }}{{ number_format($totalRealPnl, 2) }} USDT
            </p>
        </div>
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Win rate del mes</p>
            <p class="font-mono text-lg font-medium">{{ $realWinRate }}%</p>
        </div>
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Cerradas en el mes</p>
            <p class="font-mono text-lg font-medium">{{ $totalRealTrades }}</p>
        </div>
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Posiciones abiertas</p>
            <p class="font-mono text-lg font-medium" style="color:var(--color-info);">{{ $openRealTrades }}</p>
        </div>
    </div>
    @endcan

    {{-- 2b. Resumen del mes — paper trading --}}
    <div class="flex items-center justify-between mb-2">
        <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Resumen de {{ ucfirst(now()->translatedFormat('F Y')) }} — paper trading</h3>
    </div>
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">P&amp;L del mes</p>
            <p class="font-mono text-lg font-medium" style="color: {{ $totalPnlPct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                {{ $totalPnlPct >= 0 ? '+' : '' }}{{ number_format($totalPnlPct, 2) }}%
            </p>
        </div>
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Win rate del mes</p>
            <p class="font-mono text-lg font-medium">{{ $winRate }}%</p>
        </div>
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Cerradas en el mes</p>
            <p class="font-mono text-lg font-medium">{{ $totalTrades }}</p>
        </div>
        <div class="rounded-lg border p-2.5" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Posiciones abiertas</p>
            <p class="font-mono text-lg font-medium" style="color:var(--color-info);">{{ $openTrades }}</p>
        </div>
    </div>

    {{-- 3. Estrategias — consolidado por grupo --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Estrategias — paper trading</h3>
            @can('viewPaperTrading')
                <a href="{{ route('paper-trading.index') }}" class="text-xs" style="color:var(--color-info);">Ver detalle →</a>
            @endcan
        </div>

        @if (count($summary) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Aún no hay operaciones registradas.</p>
        @else
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                @foreach ($summary as $s)
                    <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <div class="flex items-start justify-between mb-1 gap-1">
                            <p class="text-sm font-medium" style="color:var(--color-text-primary);">{{ $s['group'] }}</p>
                            @if ($s['open_trades'] > 0)
                                <span class="text-[10px] px-1 py-0.5 rounded shrink-0" style="background:#13233D; color:var(--color-info);">
                                    {{ $s['open_trades'] }} ab.
                                </span>
                            @endif
                        </div>
                        <p class="text-[10px] mb-2" style="color:var(--color-text-muted);">{{ ucfirst(now()->translatedFormat('F Y')) }}</p>
                        <p class="font-mono text-lg font-medium mb-2" style="color: {{ $s['total_pnl_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                            {{ $s['total_pnl_pct'] >= 0 ? '+' : '' }}{{ number_format($s['total_pnl_pct'], 2) }}%
                        </p>
                        <div class="grid grid-cols-3 gap-1 font-mono text-[10px]" style="color:var(--color-text-muted);">
                            <span>WR {{ $s['win_rate'] }}%</span>
                            <span>{{ $s['total_trades'] }} tr</span>
                            <span>{{ $s['wins'] }}/{{ $s['losses'] }}</span>
                        </div>
                    </div>
                @endforeach
            </div>
        @endif
    </div>

    {{-- 4. Data Collector: el detalle (estado, validación, historial) vive en /collector --}}
    @can('manageUsers')
        <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <h3 class="text-xs font-medium mb-2" style="color:var(--color-text-secondary);">Data collector</h3>
            <a href="{{ route('collector.unified') }}" class="text-xs" style="color:var(--color-info);">Ver estado de los datos y configurar →</a>
        </div>
    @endcan


<script>
    const livePricesData = @json($initialPrices);
    
    function updateLivePrices() {
        fetch('{{ route("dashboard.live-prices") }}')
            .then(res => res.json())
            .then(data => {
                if (!data.prices) return;
                for (const [sym, newPrice] of Object.entries(data.prices)) {
                    const card = document.getElementById('price-card-' + sym);
                    if (!card) continue;
                    
                    const priceEl = card.querySelector('.price-val');
                    const trendEl = card.querySelector('.price-trend');
                    
                    const oldPrice = livePricesData[sym] ? livePricesData[sym].price : newPrice;
                    const changePct = oldPrice > 0 ? ((newPrice - oldPrice) / oldPrice) * 100 : 0;
                    
                    if (priceEl) priceEl.textContent = '$' + newPrice.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    if (trendEl) {
                        trendEl.textContent = (changePct >= 0 ? '↑ ' : '↓ ') + Math.abs(changePct).toFixed(2) + '%';
                        trendEl.style.color = changePct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
                    }
                    livePricesData[sym] = { price: newPrice, change_pct: changePct };
                }
            })
            .catch(err => console.error('Error updating prices:', err));
    }

    // Carga inmediata
    document.addEventListener('DOMContentLoaded', function() {
        updateLivePrices();
        setInterval(updateLivePrices, 15000);
    });
</script>
@endsection


@push('scripts')
<script>
let lastPrices = {};

async function refreshLivePrices() {
    try {
        const res = await fetch("{{ route('dashboard.live-prices') }}");
        const data = await res.json();
        const prices = data.prices || {};
        const symbols = Object.keys(prices).sort();
        const grid = document.getElementById('livePricesGrid');
        if (!grid) return;

        if (symbols.length === 0) {
            grid.innerHTML = '<p class="text-sm" style="color:var(--color-text-muted);">Sin datos de precio disponibles.</p>';
            return;
        }

        grid.innerHTML = symbols.map(symbol => {
            const price = prices[symbol];
            const prev  = lastPrices[symbol];
            let arrow = '—', color = 'var(--color-text-muted)';
            if (prev !== undefined && price !== prev) {
                if (price > prev) { arrow = '▲'; color = 'var(--color-profit)'; }
                else              { arrow = '▼'; color = 'var(--color-loss)'; }
            }
            const decimals = price >= 100 ? 2 : 4;
            const priceStr = price.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
            return `
                <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <div class="flex items-center justify-between mb-1">
                        <span class="text-sm font-medium">${symbol}</span>
                        <span style="color:${color}; font-size:13px;">${arrow}</span>
                    </div>
                    <p class="font-mono text-sm" style="color:${color};">${priceStr}</p>
                </div>
            `;
        }).join('');

        lastPrices = { ...prices };
    } catch (e) {
        console.error('Error actualizando precios en vivo', e);
    }
}

refreshLivePrices();
setInterval(refreshLivePrices, 10000);
</script>
@endpush

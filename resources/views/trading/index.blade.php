@extends('layouts.app')
@section('title', 'Trading')
@section('header', 'Trading')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

{{-- Selector de mes + link a cuentas --}}
<div class="flex items-center justify-between mb-4 flex-wrap gap-2">
    <div class="flex items-center gap-2">
        <a href="{{ route('trading.index', ['month' => $month->copy()->subMonth()->format('Y-m')]) }}"
           class="px-2 py-1 rounded text-sm transition-colors" style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">‹</a>
        <span class="text-sm font-medium" style="color:var(--color-text-primary);">{{ $month->translatedFormat('F Y') }}</span>
        @if (!$month->isCurrentMonth())
            <a href="{{ route('trading.index', ['month' => $month->copy()->addMonth()->format('Y-m')]) }}"
               class="px-2 py-1 rounded text-sm transition-colors" style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">›</a>
        @endif
    </div>
    <a href="{{ route('trading.accounts') }}"
       class="text-[11px] px-3 py-1.5 rounded transition-colors"
       style="background:var(--color-surface-raised); color:var(--color-info); border:1px solid var(--color-border-soft);">
        ⚙ Gestionar cuentas y estrategias
    </a>
</div>

{{-- Consolidado global --}}
@if ($globalTrades > 0)
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-[11px] font-medium mb-3" style="color:var(--color-text-muted);">Consolidado global — {{ $month->translatedFormat('F Y') }}</h3>
        <div class="grid grid-cols-3 gap-3">
            <div>
                <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">P&L neto total</p>
                <p class="font-mono text-lg font-medium" style="color: {{ $globalNetPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                    {{ $globalNetPnl >= 0 ? '+' : '' }}{{ number_format($globalNetPnl, 2) }} USDT
                </p>
            </div>
            <div>
                <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Win rate global</p>
                <p class="font-mono text-lg font-medium" style="color:var(--color-text-primary);">{{ $globalWinRate }}%</p>
            </div>
            <div>
                <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Total trades cerrados</p>
                <p class="font-mono text-lg font-medium" style="color:var(--color-text-primary);">{{ $globalTrades }}</p>
            </div>
        </div>
    </div>
@endif

{{-- Por cuenta/broker --}}
@forelse ($accountData as $data)
    @php $account = $data['account']; @endphp
    <div class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">

        {{-- Header cuenta --}}
        <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
            <div class="flex items-center gap-3">
                <h3 class="text-sm font-medium" style="color:var(--color-text-primary);">{{ $account->label }}</h3>
                <span class="text-[10px] px-1.5 py-0.5 rounded font-medium"
                      style="background: {{ $account->account_type === 'demo' ? '#3A2E0E' : '#16331F' }};
                             color: {{ $account->account_type === 'demo' ? 'var(--color-neutral)' : 'var(--color-profit)' }};">
                    {{ strtoupper($account->account_type) }}
                </span>
                <span class="text-[11px]" style="color:var(--color-text-muted);">{{ ucfirst($account->broker) }}</span>
            </div>
        </div>

        {{-- Consolidado de la cuenta --}}
        <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 p-4 border-b" style="border-color:var(--color-border-soft);">
            @foreach ([
                ['Balance inicial', $data['balance_start'] ? number_format($data['balance_start'], 2) . ' USDT' : '—', false],
                ['Balance final',   $data['balance_end']   ? number_format($data['balance_end'],   2) . ' USDT' : '—', false],
                ['P&L neto',        ($data['total_net_pnl'] >= 0 ? '+' : '') . number_format($data['total_net_pnl'], 2) . ' USDT', true],
                ['Win rate',        $data['win_rate'] . '%', false],
                ['Trades cerrados', $data['total_trades'], false],
                ['Mejor / Peor',    ($data['best_trade'] ? '+' . number_format($data['best_trade']->net_pnl ?? $data['best_trade']->pnl, 2) : '—') . ' / ' . ($data['worst_trade'] ? number_format($data['worst_trade']->net_pnl ?? $data['worst_trade']->pnl, 2) : '—'), false],
            ] as [$label, $value, $colored])
                <div class="rounded-md p-2.5" style="background:var(--color-surface-raised);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">{{ $label }}</p>
                    <p class="font-mono text-sm font-medium"
                       style="color: {{ $colored ? ($data['total_net_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)') : 'var(--color-text-primary)' }};">
                        {{ $value }}
                    </p>
                </div>
            @endforeach
        </div>

        {{-- Operaciones abiertas --}}
        @if ($data['open']->isNotEmpty())
            <div class="p-4 border-b" style="border-color:var(--color-border-soft);">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">
                    Operaciones abiertas ({{ $data['open']->count() }})
                    <span class="text-[10px] ml-2" style="color:var(--color-text-muted);">Precio actualizado cada 30s</span>
                </h4>
                <div class="overflow-x-auto">
                    <table class="w-full font-mono text-[11px]" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-2 text-left font-normal">Estrategia</th>
                                <th class="py-2 px-2 text-left font-normal">Símbolo</th>
                                <th class="py-2 px-2 text-left font-normal">Dir.</th>
                                <th class="py-2 px-2 text-left font-normal">Entrada</th>
                                <th class="py-2 px-2 text-left font-normal">Precio actual</th>
                                <th class="py-2 px-2 text-left font-normal">SL</th>
                                <th class="py-2 px-2 text-left font-normal">TP</th>
                                <th class="py-2 px-2 text-left font-normal">P&L flotante</th>
                                <th class="py-2 px-2 text-left font-normal">Tiempo</th>
                                <th class="py-2 px-2 text-left font-normal">Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($data['open'] as $trade)
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $trade->strategy }}</td>
                                    <td class="py-2 px-2">{{ $trade->symbol }}</td>
                                    <td class="py-2 px-2">
                                        <span style="color: {{ $trade->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                            {{ strtoupper($trade->side) }}
                                        </span>
                                    </td>
                                    <td class="py-2 px-2">{{ number_format($trade->entry_price, 2) }}</td>
                                    <td class="py-2 px-2" id="price_{{ $trade->id }}">—</td>
                                    <td class="py-2 px-2" style="color:var(--color-loss);">{{ number_format($trade->sl, 2) }}</td>
                                    <td class="py-2 px-2" style="color:var(--color-profit);">{{ number_format($trade->tp, 2) }}</td>
                                    <td class="py-2 px-2" id="pnl_{{ $trade->id }}">—</td>
                                    <td class="py-2 px-2">{{ $trade->entry_time->diffForHumans() }}</td>
                                    <td class="py-2 px-2">
                                        <span class="px-1.5 py-0.5 rounded text-[10px]"
                                              style="background:#13233D; color:var(--color-info);">
                                            {{ strtoupper(str_replace('_', ' ', $trade->status)) }}
                                        </span>
                                    </td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        @endif

        {{-- Operaciones cerradas del mes --}}
        @if ($data['closed']->isNotEmpty())
            <div class="p-4">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-secondary);">
                    Operaciones cerradas — {{ $month->translatedFormat('F Y') }} ({{ $data['closed']->count() }})
                </h4>
                <div class="overflow-x-auto">
                    <table class="w-full font-mono text-[11px]" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-2 text-left font-normal">Estrategia</th>
                                <th class="py-2 px-2 text-left font-normal">Símbolo</th>
                                <th class="py-2 px-2 text-left font-normal">Dir.</th>
                                <th class="py-2 px-2 text-left font-normal">Entrada</th>
                                <th class="py-2 px-2 text-left font-normal">Salida</th>
                                <th class="py-2 px-2 text-left font-normal">Razón</th>
                                <th class="py-2 px-2 text-left font-normal">Tamaño</th>
                                <th class="py-2 px-2 text-left font-normal">Comisión</th>
                                <th class="py-2 px-2 text-left font-normal">P&L neto</th>
                                <th class="py-2 px-2 text-left font-normal">Balance antes</th>
                                <th class="py-2 px-2 text-left font-normal">Balance después</th>
                                <th class="py-2 px-2 text-left font-normal">Slippage</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($data['closed'] as $trade)
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $trade->strategy }}</td>
                                    <td class="py-2 px-2">{{ $trade->symbol }}</td>
                                    <td class="py-2 px-2">
                                        <span style="color: {{ $trade->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                            {{ strtoupper($trade->side) }}
                                        </span>
                                    </td>
                                    <td class="py-2 px-2">{{ number_format($trade->entry_price, 2) }}<br><span style="color:var(--color-text-muted);">{{ $trade->entry_time->format('d/m H:i') }}</span></td>
                                    <td class="py-2 px-2">{{ number_format($trade->exit_price, 2) }}<br><span style="color:var(--color-text-muted);">{{ $trade->exit_time?->format('d/m H:i') }}</span></td>
                                    <td class="py-2 px-2">{{ str_replace('_', ' ', $trade->exit_reason ?? '—') }}</td>
                                    <td class="py-2 px-2">{{ $trade->size }}</td>
                                    <td class="py-2 px-2">{{ $trade->commission ? number_format($trade->commission, 4) : '—' }}</td>
                                    <td class="py-2 px-2 font-medium" style="color: {{ ($trade->net_pnl ?? $trade->pnl) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ ($trade->net_pnl ?? $trade->pnl) >= 0 ? '+' : '' }}{{ number_format($trade->net_pnl ?? $trade->pnl, 2) }}
                                        <br><span class="text-[10px]">{{ $trade->pnl_pct >= 0 ? '+' : '' }}{{ $trade->pnl_pct }}%</span>
                                    </td>
                                    <td class="py-2 px-2">{{ $trade->balance_before ? number_format($trade->balance_before, 2) : '—' }}</td>
                                    <td class="py-2 px-2">{{ $trade->balance_after ? number_format($trade->balance_after, 2) : '—' }}</td>
                                    <td class="py-2 px-2">{{ $trade->slippage_pct ? $trade->slippage_pct . '%' : '—' }}</td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        @elseif ($data['open']->isEmpty())
            <div class="p-6 text-center">
                <p class="text-sm" style="color:var(--color-text-muted);">Sin operaciones en {{ $month->translatedFormat('F Y') }}.</p>
            </div>
        @endif
    </div>
@empty
    <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-sm mb-2" style="color:var(--color-text-muted);">No tienes cuentas de broker configuradas.</p>
        <a href="{{ route('trading.accounts') }}" style="color:var(--color-info);" class="text-sm">Agregar una cuenta →</a>
    </div>
@endforelse

@endsection

@push('scripts')
<script>
// Actualizar precios de operaciones abiertas cada 30 segundos
async function refreshLivePrices() {
    try {
        const res = await fetch('{{ route("trading.live-prices") }}', {
            headers: { 'Accept': 'application/json', 'X-CSRF-TOKEN': '{{ csrf_token() }}' }
        });
        const data = await res.json();

        data.forEach(trade => {
            const priceEl = document.getElementById(`price_${trade.id}`);
            const pnlEl   = document.getElementById(`pnl_${trade.id}`);

            if (priceEl && trade.current_price) {
                priceEl.textContent = parseFloat(trade.current_price).toLocaleString('es-CO', { minimumFractionDigits: 2 });
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

// Ejecutar al cargar y luego cada 30 segundos
document.addEventListener('DOMContentLoaded', () => {
    const hasOpenTrades = document.querySelectorAll('[id^="price_"]').length > 0;
    if (hasOpenTrades) {
        refreshLivePrices();
        setInterval(refreshLivePrices, 30000);
    }
});
</script>
@endpush

@extends('layouts.app')

@section('title', $strategy)
@section('header', $strategy)

@section('content')

    <div class="mb-4">
        <a href="{{ route('paper-trading.index') }}" class="text-[11px]" style="color:var(--color-info);">← Volver al resumen</a>
    </div>

    {{-- KPIs --}}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">P&amp;L total</p>
            <p class="font-mono text-xl font-medium" style="color: {{ $totalPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                {{ $totalPnl >= 0 ? '+' : '' }}{{ number_format($totalPnl, 2) }}
            </p>
        </div>
        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Win rate</p>
            <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">{{ $winRate }}%</p>
        </div>
        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Profit factor</p>
            <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">{{ $profitFactor ?? '—' }}</p>
        </div>
        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Trades cerrados</p>
            <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">{{ $totalClosed }}</p>
        </div>
    </div>

    {{-- Equity Curve --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Curva de equity</h3>
        @if ($totalClosed > 0)
            <canvas id="equityChart" height="80"></canvas>
        @else
            <p class="text-sm" style="color:var(--color-text-muted);">Sin operaciones cerradas aún.</p>
        @endif
    </div>

    {{-- Posiciones abiertas --}}
    @if ($openTrades->count() > 0)
        <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Posiciones abiertas</h3>

            {{-- Mobile: cards --}}
            <div class="space-y-2 sm:hidden">
                @foreach ($openTrades as $t)
                    <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-medium" style="color:var(--color-text-primary);">{{ $t->symbol }}</span>
                            <span class="text-xs font-medium" style="color: {{ $t->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ strtoupper($t->side) }}
                            </span>
                        </div>
                        <div class="grid grid-cols-3 gap-2 font-mono text-[11px] mb-2" style="color:var(--color-text-muted);">
                            <div>
                                <p class="text-[10px]">Entrada</p>
                                <p style="color:var(--color-text-primary);">{{ number_format($t->entry_price, 2) }}</p>
                            </div>
                            <div>
                                <p class="text-[10px]">SL</p>
                                <p style="color:var(--color-text-primary);">{{ number_format($t->sl, 2) }}</p>
                            </div>
                            <div>
                                <p class="text-[10px]">TP</p>
                                <p style="color:var(--color-text-primary);">{{ number_format($t->tp, 2) }}</p>
                            </div>
                        </div>
                        <div class="flex items-center justify-between text-[11px]" style="color:var(--color-text-muted);">
                            <span>{{ $t->regime }}</span>
                            <span>
                                @if ($t->be_activated)
                                    <span style="color:var(--color-profit);">BE activado</span>
                                @endif
                            </span>
                            <span>{{ $t->entry_time->format('d/m H:i') }}</span>
                        </div>
                    </div>
                @endforeach
            </div>

            {{-- Desktop: tabla --}}
            <div class="overflow-x-auto hidden sm:block">
                <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                    <thead>
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <th class="py-2 px-2 font-normal">Símbolo</th>
                            <th class="py-2 px-2 font-normal">Lado</th>
                            <th class="py-2 px-2 font-normal">Entrada</th>
                            <th class="py-2 px-2 font-normal">SL</th>
                            <th class="py-2 px-2 font-normal">TP</th>
                            <th class="py-2 px-2 font-normal">BE</th>
                            <th class="py-2 px-2 font-normal">Régimen</th>
                            <th class="py-2 px-2 font-normal">Hora entrada</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($openTrades as $t)
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $t->symbol }}</td>
                                <td class="py-2 px-2">
                                    <span style="color: {{ $t->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ strtoupper($t->side) }}
                                    </span>
                                </td>
                                <td class="py-2 px-2">{{ number_format($t->entry_price, 2) }}</td>
                                <td class="py-2 px-2">{{ number_format($t->sl, 2) }}</td>
                                <td class="py-2 px-2">{{ number_format($t->tp, 2) }}</td>
                                <td class="py-2 px-2">
                                    @if ($t->be_activated)
                                        <span style="color:var(--color-profit);">Activado</span>
                                    @else
                                        <span>—</span>
                                    @endif
                                </td>
                                <td class="py-2 px-2">{{ $t->regime }}</td>
                                <td class="py-2 px-2 whitespace-nowrap">{{ $t->entry_time->format('Y-m-d H:i') }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
    @endif

    {{-- Historial de trades cerrados --}}
    <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Historial de operaciones</h3>

        @if ($closedTrades->count() === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Sin operaciones cerradas aún.</p>
        @else
            @php
                $reasonLabels = [
                    'stop_loss'   => 'Stop Loss',
                    'take_profit' => 'Take Profit',
                    'time_exit'   => 'Cierre por tiempo',
                ];
            @endphp

            {{-- Mobile: cards --}}
            <div class="space-y-2 sm:hidden">
                @foreach ($closedTrades as $t)
                    <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-medium" style="color:var(--color-text-primary);">{{ $t->symbol }}</span>
                                <span class="text-xs font-medium" style="color: {{ $t->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ strtoupper($t->side) }}
                                </span>
                            </div>
                            <span class="font-mono text-sm font-medium" style="color: {{ $t->pnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ $t->pnl >= 0 ? '+' : '' }}{{ number_format($t->pnl, 2) }}
                            </span>
                        </div>
                        <div class="grid grid-cols-2 gap-2 font-mono text-[11px] mb-2" style="color:var(--color-text-muted);">
                            <div>
                                <p class="text-[10px]">Entrada</p>
                                <p style="color:var(--color-text-primary);">{{ number_format($t->entry_price, 2) }}</p>
                            </div>
                            <div>
                                <p class="text-[10px]">Salida</p>
                                <p style="color:var(--color-text-primary);">{{ number_format($t->exit_price, 2) }}</p>
                            </div>
                        </div>
                        <div class="flex items-center justify-between text-[11px]" style="color:var(--color-text-muted);">
                            <span>{{ $reasonLabels[$t->exit_reason] ?? $t->exit_reason }}</span>
                            <span>{{ $t->regime }}</span>
                            <span>{{ $t->exit_time?->format('d/m H:i') }}</span>
                        </div>
                    </div>
                @endforeach
            </div>

            {{-- Desktop: tabla --}}
            <div class="overflow-x-auto hidden sm:block">
                <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                    <thead>
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <th class="py-2 px-2 font-normal">Símbolo</th>
                            <th class="py-2 px-2 font-normal">Lado</th>
                            <th class="py-2 px-2 font-normal">Entrada</th>
                            <th class="py-2 px-2 font-normal">Salida</th>
                            <th class="py-2 px-2 font-normal">P&amp;L</th>
                            <th class="py-2 px-2 font-normal">Razón</th>
                            <th class="py-2 px-2 font-normal">Régimen</th>
                            <th class="py-2 px-2 font-normal">Cierre</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($closedTrades as $t)
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $t->symbol }}</td>
                                <td class="py-2 px-2">
                                    <span style="color: {{ $t->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ strtoupper($t->side) }}
                                    </span>
                                </td>
                                <td class="py-2 px-2">{{ number_format($t->entry_price, 2) }}</td>
                                <td class="py-2 px-2">{{ number_format($t->exit_price, 2) }}</td>
                                <td class="py-2 px-2" style="color: {{ $t->pnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ $t->pnl >= 0 ? '+' : '' }}{{ number_format($t->pnl, 2) }}
                                </td>
                                <td class="py-2 px-2">{{ $reasonLabels[$t->exit_reason] ?? $t->exit_reason }}</td>
                                <td class="py-2 px-2">{{ $t->regime }}</td>
                                <td class="py-2 px-2 whitespace-nowrap">{{ $t->exit_time?->format('Y-m-d H:i') }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

@endsection

@if ($totalClosed > 0)
@push('scripts')
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
    const ctx = document.getElementById('equityChart');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: {!! json_encode(range(0, count($equityCurve) - 1)) !!},
            datasets: [{
                label: 'Equity',
                data: {!! json_encode($equityCurve) !!},
                borderColor: '#4D8FE8',
                backgroundColor: 'rgba(77, 143, 232, 0.1)',
                fill: true,
                tension: 0.1,
                pointRadius: 0,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: '#1E2530' }, ticks: { color: '#6B7787' } },
                y: { grid: { color: '#1E2530' }, ticks: { color: '#6B7787' } },
            }
        }
    });
</script>
@endpush
@endif
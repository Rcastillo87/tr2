@extends('layouts.app')

@section('title', $strategy)
@section('header', $strategy)

@section('content')

    <div class="mb-4">
        <a href="{{ route('paper-trading.index') }}" class="text-sm text-blue-400 hover:text-blue-300">← Volver al resumen</a>
    </div>

    {{-- KPIs --}}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">P&L Total</p>
            <p class="text-2xl font-semibold {{ $totalPnl >= 0 ? 'text-green-400' : 'text-red-400' }}">
                {{ $totalPnl >= 0 ? '+' : '' }}{{ number_format($totalPnl, 2) }} USDT
            </p>
        </div>
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">Win Rate</p>
            <p class="text-2xl font-semibold text-white">{{ $winRate }}%</p>
        </div>
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">Profit Factor</p>
            <p class="text-2xl font-semibold text-white">{{ $profitFactor ?? '—' }}</p>
        </div>
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">Trades Cerrados</p>
            <p class="text-2xl font-semibold text-white">{{ $totalClosed }}</p>
        </div>
    </div>

    {{-- Equity Curve --}}
    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-6">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">Curva de Equity</h3>
        @if ($totalClosed > 0)
            <canvas id="equityChart" height="80"></canvas>
        @else
            <p class="text-sm text-gray-500">Sin operaciones cerradas aún.</p>
        @endif
    </div>

    {{-- Posiciones abiertas --}}
    @if ($openTrades->count() > 0)
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-6">
            <h3 class="text-sm font-semibold text-gray-300 mb-4">Posiciones Abiertas</h3>
            <div class="overflow-x-auto">
                <table class="w-full text-xs text-left text-gray-400">
                    <thead>
                        <tr class="border-b border-gray-700">
                            <th class="py-2 pr-4">Símbolo</th>
                            <th class="py-2 pr-4">Lado</th>
                            <th class="py-2 pr-4">Entrada</th>
                            <th class="py-2 pr-4">SL</th>
                            <th class="py-2 pr-4">TP</th>
                            <th class="py-2 pr-4">BE</th>
                            <th class="py-2 pr-4">Régimen</th>
                            <th class="py-2">Hora entrada</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($openTrades as $t)
                            <tr class="border-b border-gray-800">
                                <td class="py-2 pr-4 text-white">{{ $t->symbol }}</td>
                                <td class="py-2 pr-4">
                                    <span class="{{ $t->side === 'long' ? 'text-green-400' : 'text-red-400' }}">
                                        {{ strtoupper($t->side) }}
                                    </span>
                                </td>
                                <td class="py-2 pr-4">{{ number_format($t->entry_price, 2) }}</td>
                                <td class="py-2 pr-4">{{ number_format($t->sl, 2) }}</td>
                                <td class="py-2 pr-4">{{ number_format($t->tp, 2) }}</td>
                                <td class="py-2 pr-4">
                                    @if ($t->be_activated)
                                        <span class="text-green-400">Activado</span>
                                    @else
                                        <span class="text-gray-500">—</span>
                                    @endif
                                </td>
                                <td class="py-2 pr-4">{{ $t->regime }}</td>
                                <td class="py-2">{{ $t->entry_time->format('Y-m-d H:i') }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </div>
    @endif

    {{-- Historial de trades cerrados --}}
    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">Historial de Operaciones</h3>

        @if ($closedTrades->count() === 0)
            <p class="text-sm text-gray-500">Sin operaciones cerradas aún.</p>
        @else
            <div class="overflow-x-auto">
                <table class="w-full text-xs text-left text-gray-400">
                    <thead>
                        <tr class="border-b border-gray-700">
                            <th class="py-2 pr-4">Símbolo</th>
                            <th class="py-2 pr-4">Lado</th>
                            <th class="py-2 pr-4">Entrada</th>
                            <th class="py-2 pr-4">Salida</th>
                            <th class="py-2 pr-4">P&L</th>
                            <th class="py-2 pr-4">Razón</th>
                            <th class="py-2 pr-4">Régimen</th>
                            <th class="py-2">Cierre</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($closedTrades as $t)
                            <tr class="border-b border-gray-800">
                                <td class="py-2 pr-4 text-white">{{ $t->symbol }}</td>
                                <td class="py-2 pr-4">
                                    <span class="{{ $t->side === 'long' ? 'text-green-400' : 'text-red-400' }}">
                                        {{ strtoupper($t->side) }}
                                    </span>
                                </td>
                                <td class="py-2 pr-4">{{ number_format($t->entry_price, 2) }}</td>
                                <td class="py-2 pr-4">{{ number_format($t->exit_price, 2) }}</td>
                                <td class="py-2 pr-4 {{ $t->pnl >= 0 ? 'text-green-400' : 'text-red-400' }}">
                                    {{ $t->pnl >= 0 ? '+' : '' }}{{ number_format($t->pnl, 2) }}
                                </td>
                                <td class="py-2 pr-4">
                                    @php
                                        $reasonLabels = [
                                            'stop_loss'   => 'Stop Loss',
                                            'take_profit' => 'Take Profit',
                                            'time_exit'   => 'Cierre por tiempo',
                                        ];
                                    @endphp
                                    {{ $reasonLabels[$t->exit_reason] ?? $t->exit_reason }}
                                </td>
                                <td class="py-2 pr-4">{{ $t->regime }}</td>
                                <td class="py-2">{{ $t->exit_time?->format('Y-m-d H:i') }}</td>
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
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.1,
                pointRadius: 0,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: '#374151' }, ticks: { color: '#9ca3af' } },
                y: { grid: { color: '#374151' }, ticks: { color: '#9ca3af' } },
            }
        }
    });
</script>
@endpush
@endif

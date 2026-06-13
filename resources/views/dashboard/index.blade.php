@extends('layouts.app')

@section('title', 'Vista General')
@section('header', 'Vista General')

@section('content')

    {{-- KPIs principales --}}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">

        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">P&L Total (Paper)</p>
            <p class="text-2xl font-semibold {{ $totalPnl >= 0 ? 'text-green-400' : 'text-red-400' }}">
                {{ $totalPnl >= 0 ? '+' : '' }}{{ number_format($totalPnl, 2) }} USDT
            </p>
        </div>

        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">Win Rate Global</p>
            <p class="text-2xl font-semibold text-white">{{ $winRate }}%</p>
        </div>

        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">Operaciones Cerradas</p>
            <p class="text-2xl font-semibold text-white">{{ $totalTrades }}</p>
        </div>

        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <p class="text-xs text-gray-400 mb-1">Posiciones Abiertas</p>
            <p class="text-2xl font-semibold text-white">{{ $openTrades }}</p>
        </div>

    </div>

    {{-- Régimen de mercado --}}
    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-6">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">Régimen de Mercado</h3>

        @if (count($regimes) === 0)
            <p class="text-sm text-gray-500">Sin datos de régimen disponibles aún.</p>
        @else
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                @foreach ($regimes as $symbol => $data)
                    @if ($data)
                        <div class="bg-gray-900 border border-gray-700 rounded-lg p-4">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-medium text-white">{{ $symbol }}</span>
                                <x-regime-badge :regime="$data['regime']" />
                            </div>
                            <div class="text-xs text-gray-400 space-y-1">
                                <p>ADX: {{ $data['adx'] }}</p>
                                <p>ATR: {{ $data['atr'] }} (avg {{ $data['atr_avg'] }})</p>
                                <p>BB Width: {{ $data['bb_width'] }} (avg {{ $data['bb_width_avg'] }})</p>
                            </div>
                        </div>
                    @endif
                @endforeach
            </div>
        @endif
    </div>

    {{-- Resumen por estrategia --}}
    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-300">Estrategias — Paper Trading</h3>
            <a href="{{ route('paper-trading.index') }}" class="text-xs text-blue-400 hover:text-blue-300">Ver detalle →</a>
        </div>

        @if (count($summary) === 0)
            <p class="text-sm text-gray-500">Aún no hay operaciones registradas.</p>
        @else
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                @foreach ($summary as $s)
                    <a href="{{ route('paper-trading.show', $s['strategy']) }}"
                       class="bg-gray-900 border border-gray-700 rounded-lg p-4 hover:border-blue-500 transition-colors">
                        <p class="font-medium text-white mb-2">{{ $s['strategy'] }}</p>
                        <div class="grid grid-cols-2 gap-2 text-xs text-gray-400">
                            <span>P&L: <span class="{{ $s['total_pnl'] >= 0 ? 'text-green-400' : 'text-red-400' }}">{{ number_format($s['total_pnl'], 2) }}</span></span>
                            <span>Win: {{ $s['win_rate'] }}%</span>
                            <span>Trades: {{ $s['total_trades'] }}</span>
                            <span>Abiertas: {{ $s['open_trades'] }}</span>
                        </div>
                    </a>
                @endforeach
            </div>
        @endif
    </div>

    {{-- Estado del Data Collector --}}
    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-300">Data Collector</h3>
            <a href="{{ route('data-collector.index') }}" class="text-xs text-blue-400 hover:text-blue-300">Ver detalle →</a>
        </div>

        @if (count($collector) === 0)
            <p class="text-sm text-gray-500">Sin datos disponibles.</p>
        @else
            <div class="overflow-x-auto">
                <table class="w-full text-xs text-left text-gray-400">
                    <thead>
                        <tr class="border-b border-gray-700">
                            <th class="py-2 pr-4">Par/Intervalo</th>
                            <th class="py-2 pr-4">Última vela</th>
                            <th class="py-2">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($collector as $key => $data)
                            <tr class="border-b border-gray-800">
                                <td class="py-2 pr-4 text-white">{{ $key }}</td>
                                <td class="py-2 pr-4">{{ $data['last_candle'] ?? '—' }}</td>
                                <td class="py-2">
                                    @if ($data['has_data'])
                                        <span class="text-green-400">●</span> OK
                                    @else
                                        <span class="text-red-400">●</span> Sin datos
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

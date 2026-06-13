@extends('layouts.app')

@section('title', 'Paper Trading')
@section('header', 'Paper Trading')

@section('content')

    @if (count($summary) === 0)
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-8 text-center">
            <p class="text-gray-400">Aún no hay datos de paper trading.</p>
        </div>
    @else
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            @foreach ($summary as $s)
                <a href="{{ route('paper-trading.show', $s['strategy']) }}"
                   class="bg-gray-800 border border-gray-700 rounded-xl p-5 hover:border-blue-500 transition-colors block">

                    <div class="flex items-start justify-between mb-4">
                        <h3 class="font-semibold text-white">{{ $s['strategy'] }}</h3>
                        @if ($s['open_trades'] > 0)
                            <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/30">
                                {{ $s['open_trades'] }} abierta(s)
                            </span>
                        @endif
                    </div>

                    <div class="space-y-3">
                        <div>
                            <p class="text-xs text-gray-400">P&L Total</p>
                            <p class="text-xl font-semibold {{ $s['total_pnl'] >= 0 ? 'text-green-400' : 'text-red-400' }}">
                                {{ $s['total_pnl'] >= 0 ? '+' : '' }}{{ number_format($s['total_pnl'], 2) }} USDT
                            </p>
                        </div>

                        <div class="grid grid-cols-3 gap-2 text-sm">
                            <div>
                                <p class="text-xs text-gray-400">Win Rate</p>
                                <p class="text-white font-medium">{{ $s['win_rate'] }}%</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-400">Trades</p>
                                <p class="text-white font-medium">{{ $s['total_trades'] }}</p>
                            </div>
                            <div>
                                <p class="text-xs text-gray-400">W/L</p>
                                <p class="text-white font-medium">{{ $s['wins'] }}/{{ $s['losses'] }}</p>
                            </div>
                        </div>
                    </div>

                    <div class="mt-4 text-xs text-blue-400">
                        Ver detalle →
                    </div>
                </a>
            @endforeach
        </div>
    @endif

@endsection

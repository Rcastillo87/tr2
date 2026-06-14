@extends('layouts.app')

@section('title', 'Vista General')
@section('header', 'Vista General')

@section('content')

    {{-- KPIs principales --}}
    <div class="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4 mb-6">

        <div class="rounded-xl p-4 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-xs mb-1" style="color:var(--color-text-muted);">P&amp;L Total (Paper)</p>
            <p class="text-xl lg:text-2xl font-semibold" style="color: {{ $totalPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                {{ $totalPnl >= 0 ? '+' : '' }}{{ number_format($totalPnl, 2) }} USDT
            </p>
        </div>

        <div class="rounded-xl p-4 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-xs mb-1" style="color:var(--color-text-muted);">Win Rate Global</p>
            <p class="text-xl lg:text-2xl font-semibold" style="color:var(--color-text-primary);">{{ $winRate }}%</p>
        </div>

        <div class="rounded-xl p-4 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-xs mb-1" style="color:var(--color-text-muted);">Operaciones Cerradas</p>
            <p class="text-xl lg:text-2xl font-semibold" style="color:var(--color-text-primary);">{{ $totalTrades }}</p>
        </div>

        <div class="rounded-xl p-4 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-xs mb-1" style="color:var(--color-text-muted);">Posiciones Abiertas</p>
            <p class="text-xl lg:text-2xl font-semibold" style="color:var(--color-info);">{{ $openTrades }}</p>
        </div>

    </div>

    {{-- Régimen de mercado --}}
    <div class="rounded-xl p-4 lg:p-5 mb-6 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-sm font-semibold mb-4" style="color:var(--color-text-secondary);">Régimen de Mercado</h3>

        @if (count($regimes) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Sin datos de régimen disponibles aún.</p>
        @else
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 lg:gap-4">
                @foreach ($regimes as $symbol => $data)
                    @if ($data)
                        <div class="rounded-lg p-4 border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-medium" style="color:var(--color-text-primary);">{{ $symbol }}</span>
                                <x-regime-badge :regime="$data['regime']" />
                            </div>
                            <div class="text-xs space-y-1" style="color:var(--color-text-muted);">
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
    <div class="rounded-xl p-4 lg:p-5 mb-6 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold" style="color:var(--color-text-secondary);">Estrategias — Paper Trading</h3>
            <a href="{{ route('paper-trading.index') }}" class="text-xs" style="color:var(--color-info);">Ver detalle →</a>
        </div>

        @if (count($summary) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Aún no hay operaciones registradas.</p>
        @else
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 lg:gap-4">
                @foreach ($summary as $s)
                    <a href="{{ route('paper-trading.show', $s['strategy']) }}"
                       class="rounded-lg p-4 border transition-colors block"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-soft);"
                       onmouseover="this.style.borderColor='var(--color-info)'"
                       onmouseout="this.style.borderColor='var(--color-border-soft)'">
                        <p class="font-medium mb-2 truncate" style="color:var(--color-text-primary);">{{ $s['strategy'] }}</p>
                        <div class="grid grid-cols-2 gap-2 text-xs" style="color:var(--color-text-muted);">
                            <span>P&amp;L: <span style="color: {{ $s['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ number_format($s['total_pnl'], 2) }}</span></span>
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
    <div class="rounded-xl p-4 lg:p-5 border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold" style="color:var(--color-text-secondary);">Data Collector</h3>
            <a href="{{ route('data-collector.index') }}" class="text-xs" style="color:var(--color-info);">Ver detalle →</a>
        </div>

        @if (count($collector) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Sin datos disponibles.</p>
        @else
            <div class="overflow-x-auto -mx-4 lg:mx-0 px-4 lg:px-0">
                <table class="w-full text-xs text-left min-w-[480px]" style="color:var(--color-text-muted);">
                    <thead>
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <th class="py-2 pr-4">Par/Intervalo</th>
                            <th class="py-2 pr-4 hidden sm:table-cell">Última vela</th>
                            <th class="py-2 pr-4 sm:hidden">Última vela</th>
                            <th class="py-2">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($collector as $key => $data)
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <td class="py-2 pr-4 font-medium" style="color:var(--color-text-primary);">{{ $key }}</td>

                                {{-- Desktop: fecha completa --}}
                                <td class="py-2 pr-4 hidden sm:table-cell">
                                    {{ $data['last_candle'] ?? '—' }}
                                </td>

                                {{-- Mobile: fecha corta (HH:MM) --}}
                                <td class="py-2 pr-4 sm:hidden">
                                    @if($data['last_candle'])
                                        {{ \Carbon\Carbon::parse($data['last_candle'])->format('d/m H:i') }}
                                    @else
                                        —
                                    @endif
                                </td>

                                <td class="py-2 whitespace-nowrap">
                                    @if ($data['has_data'])
                                        <span style="color:var(--color-profit);">●</span> OK
                                    @else
                                        <span style="color:var(--color-loss);">●</span> Sin datos
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
@extends('layouts.app')

@section('title', 'Vista General')
@section('header', 'Vista general')

@section('content')

    {{-- KPIs --}}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">

        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">P&L del mes (paper)</p>
            <p class="font-mono text-xl font-medium" style="color: {{ $totalPnlPct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                {{ $totalPnlPct >= 0 ? '+' : '' }}{{ number_format($totalPnlPct, 2) }}%
            </p>
        </div>

        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Win rate global</p>
            <p class="font-mono text-xl font-medium">{{ $winRate }}%</p>
        </div>

        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Operaciones cerradas (mes)</p>
            <p class="font-mono text-xl font-medium">{{ $totalTrades }}</p>
        </div>

        <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Posiciones abiertas</p>
            <p class="font-mono text-xl font-medium" style="color:var(--color-info);">{{ $openTrades }}</p>
        </div>

    </div>

    {{-- Régimen de mercado --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Régimen de mercado</h3>

        @if (count($regimes) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Sin datos de régimen disponibles aún.</p>
        @else
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                @foreach ($regimes as $symbol => $data)
                    @if ($data)
                        @php
                            $regimeColors = [
                                'TRENDING' => ['bg' => '#16331F', 'text' => 'var(--color-profit)'],
                                'RANGING'  => ['bg' => '#3A2E0E', 'text' => 'var(--color-neutral)'],
                                'VOLATILE' => ['bg' => '#3A1A1C', 'text' => 'var(--color-loss)'],
                            ];
                            $rc = $regimeColors[$data['regime']] ?? ['bg' => '#1E2530', 'text' => 'var(--color-text-secondary)'];
                        @endphp
                        <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium">{{ $symbol }}</span>
                                <span class="text-[10px] font-medium px-1.5 py-0.5 rounded" style="background:{{ $rc['bg'] }}; color:{{ $rc['text'] }};">
                                    {{ $data['regime'] }}
                                </span>
                            </div>
                            <div class="font-mono text-[11px] flex justify-between" style="color:var(--color-text-muted);">
                                <span>ADX {{ $data['adx'] }}</span>
                                <span>ATR {{ $data['atr'] }}</span>
                            </div>
                        </div>
                    @endif
                @endforeach
            </div>
        @endif
    </div>

    {{-- Resumen por estrategia --}}
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
                    @if (auth()->user()->canViewPaperTrading())
                        <a href="{{ route('paper-trading.show', $s['strategy']) }}"
                           class="rounded-md border p-3 block transition-colors"
                           style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                            <p class="text-sm font-medium mb-2">{{ $s['strategy'] }}</p>
                            <p class="font-mono text-lg font-medium mb-2" style="color: {{ $s['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ $s['total_pnl'] >= 0 ? '+' : '' }}{{ number_format($s['total_pnl'], 2) }}
                            </p>
                            <div class="grid grid-cols-3 gap-2 font-mono text-[11px]" style="color:var(--color-text-muted);">
                                <span>WR {{ $s['win_rate'] }}%</span>
                                <span>{{ $s['total_trades'] }} tr</span>
                                <span>{{ $s['open_trades'] }} abiertas</span>
                            </div>
                        </a>
                    @else
                        <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                            <p class="text-sm font-medium mb-2">{{ $s['strategy'] }}</p>
                            <p class="font-mono text-lg font-medium mb-2" style="color: {{ $s['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ $s['total_pnl'] >= 0 ? '+' : '' }}{{ number_format($s['total_pnl'], 2) }}
                            </p>
                            <div class="grid grid-cols-3 gap-2 font-mono text-[11px]" style="color:var(--color-text-muted);">
                                <span>WR {{ $s['win_rate'] }}%</span>
                                <span>{{ $s['total_trades'] }} tr</span>
                                <span>{{ $s['open_trades'] }} abiertas</span>
                            </div>
                        </div>
                    @endif
                @endforeach
            </div>
        @endif
    </div>

    {{-- Estado del Data Collector — solo admin y consultor --}}
    @can('viewAnalysisTools')
        <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Data collector</h3>
                <a href="{{ route('data-collector.index') }}" class="text-xs" style="color:var(--color-info);">Ver detalle →</a>
            </div>

            @if (count($collector) === 0)
                <p class="text-sm" style="color:var(--color-text-muted);">Sin datos disponibles.</p>
            @else
                <div class="overflow-x-auto -mx-1">
                    <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-1 font-normal">Par/Int</th>
                                <th class="py-2 px-1 font-normal">Última vela</th>
                                <th class="py-2 px-1 font-normal">Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($collector as $key => $data)
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <td class="py-2 px-1" style="color:var(--color-text-primary);">{{ $key }}</td>
                                    <td class="py-2 px-1 whitespace-nowrap">{{ $data['last_candle'] ?? '—' }}</td>
                                    <td class="py-2 px-1">
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
    @endcan

@endsection
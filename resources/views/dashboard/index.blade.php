@extends('layouts.app')

@section('title', 'Vista General')
@section('header', 'Vista general')

@section('content')

    {{-- 1. Régimen de mercado --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Régimen de mercado</h3>

        @if (count($regimes) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">Sin datos de régimen disponibles aún.</p>
        @else
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                @foreach (array_keys($regimes) as $symbol)
            @if (isset($regimes[$symbol]) && $regimes[$symbol])
                        @php
                            $data = $regimes[$symbol];
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

    {{-- 2. Resumen del mes --}}
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

    {{-- 4. Data Collector — solo admin y consultor --}}
    @can('viewAnalysisTools')
        <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Data collector</h3>
                @can('manageUsers')
                    <a href="{{ route('collector.configs.index') }}" class="text-xs" style="color:var(--color-info);">Configurar →</a>
                @endcan
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

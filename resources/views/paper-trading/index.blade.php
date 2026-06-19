@extends('layouts.app')

@section('title', 'Paper Trading')
@section('header', 'Paper Trading')

@section('content')

    {{-- Selector de mes --}}
    <form method="GET" action="{{ route('paper-trading.index') }}" class="flex items-center gap-2 mb-4">
        <label for="mes" class="text-[11px]" style="color:var(--color-text-muted);">Mes:</label>
        <select name="mes" id="mes" onchange="this.form.submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            @foreach ($availableMonths as $m)
                <option value="{{ $m['value'] }}" {{ $selectedMonth->format('Y-m') === $m['value'] ? 'selected' : '' }}>
                    {{ $m['label'] }}
                </option>
            @endforeach
        </select>
    </form>

    @if (empty($summary))
        <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-sm" style="color:var(--color-text-muted);">Sin operaciones registradas en {{ $selectedMonth->translatedFormat('F Y') }}.</p>
        </div>
    @else
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            @foreach ($summary as $s)
                <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">

                    {{-- Cabecera del grupo --}}
                    <div class="flex items-start justify-between mb-3 gap-2">
                        <h3 class="font-medium text-sm" style="color:var(--color-text-primary);">{{ $s['group'] }}</h3>
                        @if ($s['open_trades'] > 0)
                            <span class="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
                                  style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                                {{ $s['open_trades'] }} abierta(s)
                            </span>
                        @endif
                    </div>

                    {{-- P&L del mes --}}
                    <div class="mb-3">
                        <p class="text-[11px] mb-1" style="color:var(--color-text-muted);">P&amp;L del mes</p>
                        <p class="font-mono text-xl font-medium" style="color: {{ $s['total_pnl_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                            {{ $s['total_pnl_pct'] >= 0 ? '+' : '' }}{{ number_format($s['total_pnl_pct'], 2) }}%
                        </p>
                    </div>

                    {{-- Stats --}}
                    <div class="grid grid-cols-3 gap-2 font-mono text-[11px] mb-3" style="color:var(--color-text-muted);">
                        <div>
                            <p class="text-[10px]">Win rate</p>
                            <p style="color:var(--color-text-primary);">{{ $s['win_rate'] }}%</p>
                        </div>
                        <div>
                            <p class="text-[10px]">Trades</p>
                            <p style="color:var(--color-text-primary);">{{ $s['total_trades'] }}</p>
                        </div>
                        <div>
                            <p class="text-[10px]">W/L</p>
                            <p style="color:var(--color-text-primary);">{{ $s['wins'] }}/{{ $s['losses'] }}</p>
                        </div>
                    </div>

                    {{-- Sub-filas por config individual --}}
                    @if (auth()->user()->canViewPaperTrading() && count($s['config_stats']) > 0)
                        <div class="space-y-1 border-t pt-3 mt-1" style="border-color:var(--color-border-soft);">
                            @foreach ($s['config_stats'] as $cs)
                                <a href="{{ route('paper-trading.show', $cs['name']) }}?mes={{ $selectedMonth->format('Y-m') }}"
                                   class="block text-[11px] px-2 py-2 rounded transition-colors"
                                   onmouseover="this.style.background='var(--color-surface-raised)'"
                                   onmouseout="this.style.background='transparent'">
                                    {{-- Línea 1: nombre --}}
                                    <div class="flex items-center justify-between gap-2 mb-1">
                                        <span class="truncate" style="color:var(--color-info);">{{ $cs['name'] }}</span>
                                        <span style="color:var(--color-text-muted);">→</span>
                                    </div>
                                    {{-- Línea 2: stats --}}
                                    <div class="flex items-center gap-3 font-mono text-[10px]" style="color:var(--color-text-muted);">
                                        <span style="color: {{ $cs['total_pnl_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                            {{ $cs['total_pnl_pct'] >= 0 ? '+' : '' }}{{ number_format($cs['total_pnl_pct'], 2) }}%
                                        </span>
                                        <span>{{ $cs['total_trades'] }} trades</span>
                                        @if ($cs['open_trades'] > 0)
                                            <span style="color:var(--color-info);">{{ $cs['open_trades'] }} abierta(s)</span>
                                        @endif
                                    </div>
                                </a>
                            @endforeach
                        </div>
                    @endif
                </div>
            @endforeach
        </div>
    @endif

@endsection

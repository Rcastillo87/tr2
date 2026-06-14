@extends('layouts.app')

@section('title', 'Paper Trading')
@section('header', 'Paper Trading')

@section('content')

    @if (count($summary) === 0)
        <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-sm" style="color:var(--color-text-muted);">Aún no hay datos de paper trading.</p>
        </div>
    @else
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            @foreach ($summary as $s)
                <a href="{{ route('paper-trading.show', $s['strategy']) }}"
                   class="rounded-lg border p-4 block transition-colors"
                   style="background:var(--color-surface); border-color:var(--color-border-soft);"
                   onmouseover="this.style.borderColor='var(--color-info)'"
                   onmouseout="this.style.borderColor='var(--color-border-soft)'">

                    <div class="flex items-start justify-between mb-3 gap-2">
                        <h3 class="font-medium text-sm truncate" style="color:var(--color-text-primary);">{{ $s['strategy'] }}</h3>
                        @if ($s['open_trades'] > 0)
                            <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0" style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                                {{ $s['open_trades'] }} abierta(s)
                            </span>
                        @endif
                    </div>

                    <div class="space-y-3">
                        <div>
                            <p class="text-[11px] mb-1" style="color:var(--color-text-muted);">P&amp;L total</p>
                            <p class="font-mono text-xl font-medium" style="color: {{ $s['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ $s['total_pnl'] >= 0 ? '+' : '' }}{{ number_format($s['total_pnl'], 2) }} USDT
                            </p>
                        </div>

                        <div class="grid grid-cols-3 gap-2">
                            <div>
                                <p class="text-[11px]" style="color:var(--color-text-muted);">Win rate</p>
                                <p class="font-mono text-sm font-medium" style="color:var(--color-text-primary);">{{ $s['win_rate'] }}%</p>
                            </div>
                            <div>
                                <p class="text-[11px]" style="color:var(--color-text-muted);">Trades</p>
                                <p class="font-mono text-sm font-medium" style="color:var(--color-text-primary);">{{ $s['total_trades'] }}</p>
                            </div>
                            <div>
                                <p class="text-[11px]" style="color:var(--color-text-muted);">W/L</p>
                                <p class="font-mono text-sm font-medium" style="color:var(--color-text-primary);">{{ $s['wins'] }}/{{ $s['losses'] }}</p>
                            </div>
                        </div>
                    </div>

                    <div class="mt-3 text-[11px]" style="color:var(--color-info);">
                        Ver detalle →
                    </div>
                </a>
            @endforeach
        </div>
    @endif

@endsection
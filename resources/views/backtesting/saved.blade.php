@extends('layouts.app')
@section('title', 'Backtests guardados')
@section('header', 'Backtests guardados')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>
@php
    $sel = 'rounded-lg px-3 py-1.5 text-xs border focus:outline-none';
    $selStyle = 'background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);';
    $pill = [
        'active'  => ['#16331F', 'var(--color-profit)', '#1E4A2E'],
        'stopped' => ['#2A2213', '#E8C77A', '#4A3D1A'],
        'none'    => ['var(--color-surface-raised)', 'var(--color-text-muted)', 'var(--color-border-strong)'],
    ];
    $fmtTpm = function (array $tpm): string {
        if (count($tpm) <= 1) {
            $v = reset($tpm);
            return ($v === null || $v === false) ? 'N/D' : number_format($v, 2);
        }
        return collect($tpm)->map(fn ($v, $s) => $s . ' ' . ($v === null ? 'N/D' : number_format($v, 2)))->implode(' · ');
    };
@endphp

<div class="mb-4 flex flex-wrap justify-between items-center gap-2">
    <a href="{{ route('strategies.index') }}" class="text-[11px]" style="color:var(--color-text-muted);">← Volver a Estrategias</a>
    <span class="text-[12px]" style="color:var(--color-text-muted);">
        {{ $totals->total }} backtests · {{ $totals->active }} operando en Paper · {{ $totals->stopped }} detenidos · {{ $totals->total - $totals->active - $totals->stopped }} sin implementar
    </span>
</div>

<form method="GET" action="{{ route('backtesting.saved') }}" id="savedFilters" class="flex items-end gap-2 mb-4 flex-wrap">
    <label class="flex flex-col gap-1 text-[11px]" style="color:var(--color-text-muted);">Estrategia
        <select name="strategy" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todas</option>
            @foreach($strategies as $s)
                <option value="{{ $s->id }}" @selected($filters['strategy'] === $s->id)>{{ $s->name }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[11px]" style="color:var(--color-text-muted);">Estado en Paper
        <select name="paper" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todos</option>
            @foreach(\App\Services\SavedBacktests::PAPER as $k => $label)
                <option value="{{ $k }}" @selected($filters['paper'] === $k)>{{ $label }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[11px]" style="color:var(--color-text-muted);">Origen
        <select name="origin" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todos</option>
            @foreach(\App\Services\SavedBacktests::ORIGINS as $k => $label)
                <option value="{{ $k }}" @selected($filters['origin'] === $k)>{{ $label }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[11px]" style="color:var(--color-text-muted);">Moneda
        <input type="text" name="symbol" value="{{ $filters['symbol'] }}" placeholder="ENA, SOL…" maxlength="20" class="{{ $sel }}" style="{{ $selStyle }} width:130px;">
    </label>
    <label class="flex flex-col gap-1 text-[11px]" style="color:var(--color-text-muted);">Orden
        <select name="sort" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="recent" @selected($filters['sort'] === 'recent')>Más reciente</option>
            <option value="rating" @selected($filters['sort'] === 'rating')>Calificación (en la página)</option>
            <option value="tpm" @selected($filters['sort'] === 'tpm')>Trades/mes (en la página)</option>
        </select>
    </label>
    <button type="submit" class="px-3 py-1.5 rounded-lg text-xs border" style="{{ $selStyle }}">Filtrar</button>
    @if(array_filter($filters, fn ($v, $k) => $k !== 'sort' && $v !== null, ARRAY_FILTER_USE_BOTH))
        <a href="{{ route('backtesting.saved') }}" class="text-[11px] pb-2" style="color:var(--color-text-muted);">Quitar filtros</a>
    @endif
</form>

<div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="overflow-x-auto">
        <table class="w-full text-left text-[12px] table-compact" style="min-width: 1060px;">
            <thead>
                <tr style="color:var(--color-text-muted);">
                    <th class="py-2 px-3 font-normal">Backtest</th>
                    <th class="py-2 px-3 font-normal">Estrategia</th>
                    <th class="py-2 px-3 font-normal">Monedas / Int.</th>
                    <th class="py-2 px-3 font-normal">Origen</th>
                    <th class="py-2 px-3 font-normal">Calif.</th>
                    <th class="py-2 px-3 font-normal text-right">Ret. prom/mes</th>
                    <th class="py-2 px-3 font-normal text-right" title="Trades por mes de cada moneda en el backtest">Trades/mes</th>
                    <th class="py-2 px-3 font-normal">Paper</th>
                    <th class="py-2 px-3 font-normal text-right" title="Solo trades Paper cerrados">Paper: trades · P&amp;L</th>
                </tr>
            </thead>
            <tbody>
            @forelse($rows as $r)
                @php [$bg, $fg, $bd] = $pill[$r['paper']]; @endphp
                <tr class="border-t hover:bg-[#1A2230] transition-colors" style="border-color:var(--color-border-soft);">
                    <td class="py-2 px-3 whitespace-nowrap">
                        <a href="{{ route('backtesting.history', $r['strategy_id']) }}#bt-{{ $r['id'] }}" class="hover:underline" style="color:var(--color-info);">#{{ $r['id'] }}</a>
                        <span class="text-[11px]" style="color:var(--color-text-muted);">{{ $r['date']?->timezone('America/Bogota')->format('d-M') }}</span>
                    </td>
                    <td class="py-2 px-3" style="color:var(--color-text-primary);">{{ $r['strategy'] }}</td>
                    <td class="py-2 px-3 font-mono text-[11px]">{{ implode(', ', $r['symbols']) }} · {{ $r['interval'] }}</td>
                    <td class="py-2 px-3 text-[11px]" title="{{ $r['origin_text'] }}">
                        @if($r['run_id'] && $canSearch)
                            <a href="{{ route('strategies.search.show', $r['run_id']) }}" class="hover:underline" style="color:var(--color-info);">Búsqueda #{{ $r['run_id'] }}</a>
                        @elseif($r['origin'] === 'search')
                            Búsqueda #{{ $r['run_id'] }}
                        @else
                            <span style="color:var(--color-text-muted);">{{ $r['origin'] === 'manual' ? 'Manual' : 'No registrado' }}</span>
                        @endif
                    </td>
                    <td class="py-2 px-3 whitespace-nowrap" style="color:{{ \App\Helpers\RatingHelper::getColor($r['rating']) }};">★ {{ number_format($r['rating'], 1) }}</td>
                    <td class="py-2 px-3 text-right" style="color:{{ $r['ret_month'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ ($r['ret_month'] >= 0 ? '+' : '') . number_format($r['ret_month'], 2) }}%</td>
                    <td class="py-2 px-3 text-right font-mono" style="color:{{ collect($r['tpm'])->every(fn ($v) => $v === null) ? 'var(--color-text-muted)' : 'var(--color-text-primary)' }};">{{ $fmtTpm($r['tpm']) }}</td>
                    <td class="py-2 px-3 whitespace-nowrap">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-medium border" style="background:{{ $bg }}; color:{{ $fg }}; border-color:{{ $bd }};">
                            {{ \App\Services\SavedBacktests::PAPER[$r['paper']] }}@if($r['config_ids']) · #{{ implode(', #', $r['config_ids']) }}@endif
                        </span>
                    </td>
                    <td class="py-2 px-3 text-right whitespace-nowrap">
                        @if($r['paper'] === 'none')
                            <span style="color:var(--color-text-muted);">—</span>
                        @else
                            {{ $r['paper_n'] }} · <span style="color:{{ $r['paper_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ ($r['paper_pnl'] >= 0 ? '+' : '') . number_format($r['paper_pnl'], 2) }}%</span>
                        @endif
                    </td>
                </tr>
            @empty
                <tr><td colspan="9" class="px-4 py-8 text-center text-sm" style="color:var(--color-text-muted);">No hay backtests con estos filtros.</td></tr>
            @endforelse
            </tbody>
        </table>
    </div>
</div>

@if($rows->hasPages())
    <div class="mt-4">{{ $rows->links() }}</div>
@endif
<p class="mt-3 text-[11px]" style="color:var(--color-text-muted);">
    Paper: Operando = alguna de sus configs está activa · Detenido = tiene configs, ninguna activa · Sin implementar = nunca se llevó a Paper. Trades y P&amp;L de Paper: solo trades cerrados, suma de P&amp;L % de sus configs. N/D en Trades/mes: backtest de varias monedas guardado antes del 10-nov.
</p>
@endsection

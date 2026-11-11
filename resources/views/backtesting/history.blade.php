@extends('layouts.app')
@section('title', 'Historial de Backtests')
@section('header', 'Historial de backtests')

@section('content')
@php
    // Una sola vista para todas las estrategias (p55). Datos: App\Services\SavedBacktests
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
    $param = fn ($v, string $unit) => $v === null || $v === '' ? '—' : $v . $unit;
    $filtered = collect($filters)->except('sort')->filter(fn ($v) => $v !== null)->isNotEmpty();
@endphp
<style>
    button, a[href] { cursor: pointer; }
    .bt-card { scroll-margin-top: 80px; }
    .bt-card:target { border-color: var(--color-info) !important; box-shadow: 0 0 0 3px rgba(77, 143, 232, .18); }
</style>

<div class="mb-3 flex flex-wrap justify-between items-center gap-2">
    <a href="{{ route('strategies.index') }}" class="text-[11px]" style="color:var(--color-text-muted);">← Volver a Estrategias</a>
    <a href="{{ route('backtesting.run') }}{{ $filters['strategy'] ? '?strategy_id=' . $filters['strategy'] : '' }}" class="text-[11px] px-3 py-1.5 rounded bg-[#13233D] text-[var(--color-info)] border border-[#1E3A5F] font-medium">
        + Nuevo Backtest
    </a>
</div>

@if (session('status'))
    <div class="rounded-lg border p-3 mb-3 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">{{ session('status') }}</div>
@endif

<form method="GET" action="{{ route('backtesting.history') }}" class="rounded-lg border px-3 py-2.5 mb-2 flex items-end gap-2 flex-wrap" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <label class="flex flex-col gap-1 text-[10px]" style="color:var(--color-text-muted);">Estrategia
        <select name="strategy" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todas</option>
            @foreach($strategies as $s)
                <option value="{{ $s->id }}" @selected($filters['strategy'] === $s->id)>{{ $s->name }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[10px]" style="color:var(--color-text-muted);">Estado en Paper
        <select name="paper" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todos</option>
            @foreach(\App\Services\SavedBacktests::PAPER as $k => $label)
                <option value="{{ $k }}" @selected($filters['paper'] === $k)>{{ $label }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[10px]" style="color:var(--color-text-muted);">Origen
        <select name="origin" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todos</option>
            @foreach(\App\Services\SavedBacktests::ORIGINS as $k => $label)
                <option value="{{ $k }}" @selected($filters['origin'] === $k)>{{ $label }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[10px]" style="color:var(--color-text-muted);">Moneda
        <select name="symbol" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="">Todas</option>
            @foreach($symbols as $sym)
                <option value="{{ $sym }}" @selected($filters['symbol'] === $sym)>{{ $sym }}</option>
            @endforeach
        </select>
    </label>
    <label class="flex flex-col gap-1 text-[10px]" style="color:var(--color-text-muted);">Orden
        <select name="sort" class="{{ $sel }}" style="{{ $selStyle }}" onchange="this.form.submit()">
            <option value="recent" @selected($filters['sort'] === 'recent')>Más reciente</option>
            <option value="rating" @selected($filters['sort'] === 'rating')>Calificación</option>
            <option value="tpm" @selected($filters['sort'] === 'tpm')>Trades/mes</option>
        </select>
    </label>
    <noscript><button type="submit" class="{{ $sel }}" style="{{ $selStyle }}">Filtrar</button></noscript>
    @if($filtered)
        <a href="{{ route('backtesting.history') }}" class="text-[11px] pb-1.5" style="color:var(--color-text-muted);">Quitar filtros</a>
    @endif
</form>

<p class="text-[11px] mb-3" style="color:var(--color-text-muted);">
    {{ $totals->total }} backtests · {{ $totals->active }} operando en Paper · {{ $totals->stopped }} detenidos · {{ $totals->total - $totals->active - $totals->stopped }} sin implementar
    @if($filtered) · <b style="color:var(--color-text-primary);">{{ $rows->total() }}</b> con estos filtros @endif
</p>

<div class="space-y-3">
    @forelse($rows as $r)
        @php
            [$bg, $fg, $bd] = $pill[$r['paper']];
            $starColor = \App\Helpers\RatingHelper::getColor($r['rating']);
            $stars = (int) round($r['rating']);
            $p = $r['params'];
            $originShort = implode(' · ', array_slice(explode(' · ', $r['origin_text']), 0, 2));   // «Búsqueda #77 · fila X»; el resto en el title
        @endphp
        <div id="bt-{{ $r['id'] }}" class="bt-card rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            {{-- Fila 1: identidad, origen, estado en Paper y acciones --}}
            <div class="flex items-center justify-between flex-wrap gap-2 px-3 py-2 border-b" style="border-color:var(--color-border-soft);">
                <div class="flex items-center gap-2 flex-wrap text-[12px]">
                    <b style="color:var(--color-text-primary);">#{{ $r['id'] }}</b>
                    <span style="color:var(--color-text-muted);">{{ $r['date']?->timezone('America/Bogota')->format('Y-m-d H:i') }}</span>
                    <span class="text-[11px] font-mono px-2 py-0.5 rounded" style="background:var(--color-surface-raised); color:var(--color-text-muted);">{{ implode(', ', $r['symbols']) }} / {{ $r['interval'] }} / {{ $r['months'] }} m</span>
                    <span class="text-[11px]" style="color:var(--color-text-secondary);">{{ $r['strategy'] }}</span>
                    <span class="text-[11px]" title="{{ $r['origin_text'] }}">
                        @if($r['run_exists'] && $canSearch)
                            <a href="{{ route('strategies.search.show', $r['run_id']) }}" class="hover:underline" style="color:var(--color-info);">{{ $originShort }}</a>
                        @else
                            <span style="color:var(--color-text-muted);">{{ $originShort }}</span>
                        @endif
                    </span>
                </div>
                <div class="flex items-center gap-1.5">
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap" style="background:{{ $bg }}; color:{{ $fg }}; border-color:{{ $bd }};">
                        {{ \App\Services\SavedBacktests::PAPER[$r['paper']] }}@if($r['config_ids']) · config #{{ implode(', #', $r['config_ids']) }}@endif
                    </span>
                    @if($r['paper'] === 'active')
                        <form method="POST" action="{{ route('backtesting.stop-paper', $r['id']) }}" id="stop-form-{{ $r['id'] }}" style="display:inline;">
                            @csrf
                            <button type="button" onclick="confirmStop({{ $r['id'] }})" class="text-[11px] px-2 py-1 rounded border" style="background:#3A1A1C; color:var(--color-loss); border-color:#5A2226;">Detener</button>
                        </form>
                    @else
                        <form method="POST" action="{{ route('backtesting.implement-paper', $r['id']) }}" id="impl-form-{{ $r['id'] }}" style="display:inline;">
                            @csrf
                            <button type="button" onclick="confirmImplement({{ $r['id'] }})" class="text-[11px] px-2 py-1 rounded border font-medium" style="background:#13233D; color:var(--color-info); border-color:#1E3A5F;">Implementar en Paper</button>
                        </form>
                        <form method="POST" action="{{ route('backtesting.destroy-backtest', $r['id']) }}" id="del-form-{{ $r['id'] }}" style="display:inline;">
                            @csrf @method('DELETE')
                            <button type="button" onclick="confirmDelete({{ $r['id'] }})" class="text-[11px] px-2 py-1 rounded border" style="background:#3A1A1C; color:var(--color-loss); border-color:#5A2226;">Eliminar</button>
                        </form>
                    @endif
                    <a href="{{ route('backtesting.run') }}?backtest_id={{ $r['id'] }}" class="text-[11px] px-2 py-1 rounded border" style="background:var(--color-surface-raised); color:var(--color-text-primary); border-color:var(--color-border-strong);">Probar de nuevo</a>
                </div>
            </div>

            {{-- Fila 2: calificación y métricas del backtest + Paper --}}
            <div class="overflow-x-auto">
                <div style="display:grid; grid-template-columns:150px repeat(6,minmax(70px,1fr)) minmax(140px,1.4fr); min-width:820px; align-items:center;">
                    <div class="px-3 py-1.5 flex items-center gap-1.5" style="border-right:1px solid var(--color-border-soft);">
                        <span style="font-size:15px; line-height:1; color:{{ $starColor }};">{{ str_repeat('★', $stars) . str_repeat('☆', 5 - $stars) }}</span>
                        <b class="text-[12px]" style="color:{{ $starColor }};">{{ number_format($r['rating'], 1) }}</b>
                    </div>
                    @foreach([
                        ['Win Rate', number_format($r['wr'], 2) . '%', null],
                        ['Sharpe', number_format($r['sharpe'], 2), null],
                        ['Ret. prom/mes', number_format($r['ret_month'], 2) . '%', $r['ret_month'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)'],
                        ['Consistencia', number_format($r['consist'], 1) . '%', null],
                        ['Profit Factor', number_format($r['pf'], 2), null],
                        ['Trades/mes', $fmtTpm($r['tpm']), null],
                    ] as [$label, $value, $color])
                        <div class="px-2 py-1.5 text-center" style="border-right:1px solid var(--color-border-soft);">
                            <p class="text-[9px]" style="color:var(--color-text-muted); margin:0;">{{ $label }}</p>
                            <p class="text-[11px] font-mono" style="color:{{ $color ?? 'var(--color-text-primary)' }}; margin:0;">{{ $value }}</p>
                        </div>
                    @endforeach
                    <div class="px-3 py-1.5 text-right">
                        <p class="text-[9px]" style="color:var(--color-text-muted); margin:0;">Paper (cerrados · P&amp;L)</p>
                        <p class="text-[11px] font-mono" style="margin:0;">
                            @if($r['paper'] === 'none')
                                <span style="color:var(--color-text-muted);">—</span>
                            @else
                                {{ $r['paper_n'] }} · <span style="color:{{ $r['paper_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ ($r['paper_pnl'] >= 0 ? '+' : '') . number_format($r['paper_pnl'], 2) }}%</span>
                            @endif
                        </p>
                    </div>
                </div>
            </div>

            {{-- Fila 3: configuración --}}
            <div class="px-3 py-1 border-t text-[10px] font-mono" style="border-color:var(--color-border-soft); background:var(--color-base); color:var(--color-text-muted);">
                SL {{ $param($p['sl'], '%') }} · TP {{ $param($p['tp'], '%') }} · BE {{ $param($p['be'], '%') }} · Dur {{ $param($p['dur'], ' velas') }} · Riesgo {{ $param($p['risk'], '%') }}
                · {{ $r['trades'] }} trades · Ret. total <span style="color:{{ $r['ret_total'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ number_format($r['ret_total'], 2) }}%</span>
            </div>
        </div>
    @empty
        <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-sm" style="color:var(--color-text-muted);">No hay backtests guardados con estos filtros.</p>
        </div>
    @endforelse
</div>

@if($rows->hasPages())
    <div class="mt-4">{{ $rows->links() }}</div>
@endif
@endsection

@if ($errors->any())
<script>
    document.addEventListener('DOMContentLoaded', function() {
        if (window.Swal) {
            Swal.fire({
                title: 'Atención',
                text: @json($errors->first()),
                icon: 'error',
                background: '#11161F', color: '#E5E9F0',
                confirmButtonColor: '#F2545B',
            });
        } else {
            alert(@json($errors->first()));
        }
    });
</script>
@endif

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    window.confirmImplement = function(id) {
        Swal.fire({
            title: '¿Enviar a Paper Trading?', text: 'La estrategia empezará a operar en el simulador con esta configuración.',
            icon: 'question', showCancelButton: true, confirmButtonText: 'Sí, implementar', cancelButtonText: 'Cancelar',
            background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#4D8FE8', cancelButtonColor: '#232B38',
        }).then((result) => { if (result.isConfirmed) document.getElementById('impl-form-' + id).submit(); });
    };
    window.confirmStop = function(id) {
        Swal.fire({
            title: '¿Detener en Paper Trading?', text: 'La estrategia dejará de operar en el simulador inmediatamente.',
            icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, detener', cancelButtonText: 'Cancelar',
            background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
        }).then((result) => { if (result.isConfirmed) document.getElementById('stop-form-' + id).submit(); });
    };
    window.confirmDelete = function(id) {
        Swal.fire({
            title: '¿Eliminar Backtest?', text: 'Esta acción no se puede deshacer.',
            icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, eliminar', cancelButtonText: 'Cancelar',
            background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
        }).then((result) => { if (result.isConfirmed) document.getElementById('del-form-' + id).submit(); });
    };
});
</script>
@endpush

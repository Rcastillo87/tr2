@extends('layouts.app')
@section('title', 'Estrategias')
@section('header', 'Estrategias y Backtesting')

@section('content')
<style>
    button, a[href] { cursor: pointer; }
    .btn-action { transition: all 0.2s; }
    .btn-action:hover { transform: translateY(-1px); filter: brightness(1.2); }
    .table-compact th, .table-compact td { padding: 0.6rem 0.5rem; }
</style>

<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

<script>
    function togglePaperDetails(id) {
        const el = document.getElementById('paper-details-' + id);
        if (el) {
            el.style.display = (el.style.display === 'none') ? 'table-row' : 'none';
        }
    }

    function confirmDelete(id, name) {
        Swal.fire({
            title: '¿Eliminar estrategia?',
            text: `Estás a punto de borrar "${name}". Esta acción no se puede deshacer.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#374151',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar',
            background: '#1f2937',
            color: '#f3f4f6'
        }).then((result) => {
            if (result.isConfirmed) {
                document.getElementById('delete-form-' + id).submit();
            }
        });
    }

    function blockDelete(name) {
        Swal.fire({
            title: 'Acción bloqueada',
            text: `La estrategia "${name}" tiene una variante en Paper Trading. Debes pausarla en la sección de Paper antes de eliminarla.`,
            icon: 'error',
            confirmButtonColor: '#3b82f6',
            confirmButtonText: 'Entendido',
            background: '#1f2937',
            color: '#f3f4f6'
        });
    }
</script>

@if (session('status'))
    <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
        {{ session('status') }}
    </div>
@endif

@if (session('error'))
    <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#331616; border-color:#4A1E1E; color:#f87171;">
        {{ session('error') }}
    </div>
@endif

<div class="flex flex-col md:flex-row md:items-center justify-between mb-4 gap-4">
    <p class="text-[12px]" style="color:var(--color-text-muted);">
        Crea y prueba tus algoritmos. Selecciona el mejor backtest y llévalo a Paper Trading.
    </p>
    <a href="{{ route('strategies.create') }}" class="px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors text-center whitespace-nowrap" style="background:#3b82f6; box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.5);">
        + Nueva Estrategia
    </a>
</div>

<div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="overflow-x-auto">
        <table class="w-full text-left text-[12px] table-compact" style="min-width: 900px;">
            <thead>
                <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                    <th class="font-medium">Estrategia</th>
                    <th class="font-medium text-center">Estado</th>
                    <th class="font-medium text-center">Variantes</th>
                    <th class="font-medium text-center">Paper Trading</th>
                    <th class="font-medium text-right pr-4">Acciones</th>
                </tr>
            </thead>
            <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                @forelse($strategies as $s)
                @php $papers = $groupedPapers[$s->id] ?? []; @endphp
                <tr class="hover:bg-[#1A2230] transition-colors">
                    <td>
                        <span class="font-medium text-sm block" style="color:var(--color-text-primary);">{{ $s->name }}</span>
                        <span class="text-[10px]" style="color:var(--color-text-muted);">{{ $s->description }}</span>
                        @include('param-search._chip', ['sbRun' => $latestRuns[$s->id] ?? null])
                    </td>
                    <td class="text-center">
                        <span class="px-2 py-1 rounded-full text-[10px] font-medium" style="background:{{ $s->active ? '#16331F' : '#33221B' }}; color:{{ $s->active ? 'var(--color-profit)' : '#F59E0B' }};">
                            {{ $s->active ? 'Activa' : 'Inactiva' }}
                        </span>
                    </td>
                    <td class="text-center">
                        <span class="px-2 py-1 rounded-full text-[11px] font-mono" style="background:var(--color-surface-raised); color:var(--color-text-primary);">
                            {{ $s->backtests_count }}
                        </span>
                    </td>
                    <td class="text-center">
                        @if(count($papers) > 0)
                            <button type="button" onclick="togglePaperDetails({{ $s->id }})" class="px-2 py-1 rounded-md text-[10px] font-medium border inline-block transition-colors hover:brightness-110" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
                                🟢 {{ count($papers) }} Activo(s) ▼
                            </button>
                        @else
                            <span class="text-[10px] italic" style="color:var(--color-text-muted);">Sin configurar</span>
                        @endif
                    </td>
                    <td class="text-right pr-4">
                        <div class="flex items-center justify-end gap-2">
                            <button type="button" onclick="sbOpen({{ $s->id }}, @js($s->name))" class="btn-action btn-search px-3 py-1.5 rounded-md text-[11px] font-medium text-white whitespace-nowrap"
                                    @if($searchActive) disabled title="Ya hay una búsqueda en curso (solo una a la vez)" @endif>🔍 Buscar</button>
                            <a href="{{ route('backtesting.run', ['strategy_id' => $s->id]) }}" class="btn-action px-3 py-1.5 rounded-md text-[11px] font-medium text-white whitespace-nowrap" style="background:#3b82f6;">+ Nuevo Backtest</a>
                            <a href="{{ route('backtesting.history', $s->id) }}" class="btn-action px-3 py-1.5 rounded-md text-[11px] font-medium whitespace-nowrap" style="background:#374151; color:#e5e7eb;">Historial</a>
                            <a href="{{ route('strategies.edit', $s->id) }}" class="btn-action px-3 py-1.5 rounded-md text-[11px] font-medium text-white whitespace-nowrap" style="background:#10b981;">Editar</a>
                            
                            @if(count($papers) > 0)
                                <button type="button" onclick="blockDelete('{{ $s->name }}')" class="btn-action px-2 py-1.5 rounded-md text-[11px] font-medium text-gray-400 border border-gray-700 bg-gray-800/50" title="Tiene Paper Activo">
                                    🔒
                                </button>
                            @else
                                <form id="delete-form-{{ $s->id }}" action="{{ route('strategies.destroy', $s->id) }}" method="POST" class="inline">
                                    @csrf
                                    @method('DELETE')
                                    <button type="button" onclick="confirmDelete({{ $s->id }}, '{{ $s->name }}')" class="btn-action px-2 py-1.5 rounded-md text-[11px] font-medium text-red-400 border border-red-900/50 hover:bg-red-900/20" style="background:rgba(239, 68, 68, 0.1);">
                                        🗑️
                                    </button>
                                </form>
                            @endif
                        </div>
                    </td>
                </tr>
                
                {{-- ACORDEÓN CON EL DISEÑO EXACTO Y DATOS DEL BACKTEST --}}
                @if(count($papers) > 0)
                <tr id="paper-details-{{ $s->id }}" style="display: none; background-color: #0D1117;">
                    <td colspan="5" class="p-0 border-b" style="border-color:var(--color-border-soft);">
                        <div class="flex flex-col gap-2">
                            @foreach($papers as $bt_obj)
                                @php
                                    $metrics = $bt_obj->metrics ?? [];
                                    $wr = (float)($metrics['win_rate'] ?? 0);
                                    $sharpe = (float)($metrics['sharpe_ratio'] ?? 0);
                                    $ret = (float)($metrics['avg_monthly_pnl'] ?? 0);
                                    $consist = (float)($metrics['consist_pct'] ?? 0);
                                    $pf = (float)($metrics['profit_factor'] ?? 0);
                                    
                                    $rating = isset($metrics['rating']) ? (float)$metrics['rating'] : \App\Helpers\RatingHelper::calculate($wr, $sharpe, $pf, $ret, $consist);
                                    $color = \App\Helpers\RatingHelper::getColor($rating);
                                    
                                    $symbols = implode(', ', $bt_obj->symbols ?? []);
                                @endphp
                                <div class="flex flex-wrap items-center space-x-2 gap-x-3 text-[11px] p-2.5 rounded-md border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                                    <span class="font-bold whitespace-nowrap mr-2" style="color:var(--color-text-primary);">📈 {{ $symbols }} ({{ $bt_obj->interval }}m)</span>
                                    <span class="whitespace-nowrap" style="color:{{ $color }};">{{ str_repeat('★', (int)round($rating)) . str_repeat('☆', 5 - (int)round($rating)) }} {{ number_format($rating, 1) }}</span>
                                    
                                    <span class="text-gray-500 mx-1">|</span>
                                    <span class="whitespace-nowrap" style="color:var(--color-text-muted);">WR: <b style="color:var(--color-text-primary);">{{ number_format($wr, 2) }}%</b></span>
                                    
                                    <span class="text-gray-500 mx-1">|</span>
                                    <span class="whitespace-nowrap" style="color:var(--color-text-muted);">Sharpe: <b style="color:var(--color-text-primary);">{{ number_format($sharpe, 2) }}</b></span>
                                    
                                    <span class="text-gray-500 mx-1">|</span>
                                    <span class="whitespace-nowrap" style="color:var(--color-text-muted);">Ret: <b style="color:var(--color-profit);">{{ number_format($ret, 2) }}%</b></span>
                                    
                                    <span class="text-gray-500 mx-1">|</span>
                                    <span class="whitespace-nowrap" style="color:var(--color-text-muted);">Cons: <b style="color:var(--color-text-primary);">{{ number_format($consist, 1) }}%</b></span>
                                    
                                    <span class="text-gray-500 mx-1">|</span>
                                    <span class="whitespace-nowrap" style="color:var(--color-text-muted);">PF: <b style="color:var(--color-text-primary);">{{ number_format($pf, 2) }}</b></span>
                                </div>
                            @endforeach
                        </div>
                    </td>
                </tr>
                @endif

                @empty
                <tr>
                    <td colspan="5" class="px-4 py-8 text-center text-sm" style="color:var(--color-text-muted);">
                        No hay estrategias creadas. Empieza creando una nueva.
                    </td>
                </tr>
                @endforelse
            </tbody>
        </table>
    </div>
</div>

@include('param-search._styles')
@include('param-search._helpers')
@include('param-search._modal')
@include('param-search._index_script')
@endsection

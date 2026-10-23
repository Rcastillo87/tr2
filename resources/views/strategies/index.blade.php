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

<!-- SweetAlert2 -->
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

<script>
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

<!-- Tabla Única (Responsive con Scroll Horizontal) -->
<div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="overflow-x-auto">
        <table class="w-full text-left text-[12px] table-compact" style="min-width: 900px;">
            <thead>
                <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                    <th class="font-medium">Estrategia</th>
                    <th class="font-medium text-center">Estado</th>
                    <th class="font-medium text-center">Variantes</th>
                    <th class="font-medium text-center">Aprobada para Paper</th>
                    <th class="font-medium text-right pr-4">Acciones</th>
                </tr>
            </thead>
            <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                @forelse($strategies as $s)
                <tr class="hover:bg-[#1A2230] transition-colors">
                    <td>
                        <span class="font-medium text-sm block" style="color:var(--color-text-primary);">{{ $s->name }}</span>
                        <span class="text-[10px]" style="color:var(--color-text-muted);">{{ $s->description }}</span>
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
                        @if(isset($approvedPapers[$s->id]))
                            <span class="px-2 py-1 rounded-md text-[10px] font-medium border inline-block" style="background:#172554; border-color:#1e3a8a; color:#60a5fa;">
                                🟢 {{ $approvedPapers[$s->id] }}
                            </span>
                        @else
                            <span class="text-[10px] italic" style="color:var(--color-text-muted);">Ninguna</span>
                        @endif
                    </td>
                    <td class="text-right pr-4">
                        <div class="flex items-center justify-end gap-1.5">
                            <a href="{{ route('backtesting.index', ['strategy_id' => $s->id]) }}" class="btn-action px-3 py-1.5 rounded-md text-[11px] font-medium text-white whitespace-nowrap" style="background:#3b82f6;">+ Nuevo</a>
                            <a href="{{ route('backtesting.history', $s->id) }}" class="btn-action px-3 py-1.5 rounded-md text-[11px] font-medium border whitespace-nowrap" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">Historial</a>
                            <a href="{{ route('strategies.edit', $s->id) }}" class="btn-action px-3 py-1.5 rounded-md text-[11px] font-medium border whitespace-nowrap" style="background:transparent; border-color:var(--color-border-strong); color:var(--color-text-primary);">Editar</a>
                            
                            @if($activePapers[$s->id] ?? false)
                                <button type="button" onclick="blockDelete('{{ $s->name }}')" class="btn-action px-2 py-1.5 rounded-md text-[11px] font-medium text-gray-400 border border-gray-700 bg-gray-800/50" title="Tiene Paper Activo">
                                    🔒
                                </button>
                            @else
                                <form id="delete-form-{{ $s->id }}" action="{{ route('strategies.destroy', $s->id) }}" method="POST" class="inline">
                                    @csrf
                                    @method('DELETE')
                                    <button type="button" onclick="confirmDelete({{ $s->id }}, '{{ $s->name }}')" class="btn-action px-2 py-1.5 rounded-md text-[11px] font-medium text-red-400 border border-red-900/50 hover:bg-red-900/20">
                                        🗑️
                                    </button>
                                </form>
                            @endif
                        </div>
                    </td>
                </tr>
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

@endsection

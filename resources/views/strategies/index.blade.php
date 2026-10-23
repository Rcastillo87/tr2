@extends('layouts.app')
@section('title', 'Gestor de Estrategias')
@section('header', 'Gestor de Estrategias')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
        <p class="text-[11px]" style="color:var(--color-text-muted);">
            Crea y gestiona las estrategias base. El código o JSON aquí definido será la plantilla para los Backtests.
        </p>
        <a href="{{ route('strategies.create') }}"
           class="inline-flex items-center justify-center gap-1.5 text-sm font-medium px-4 py-2 rounded-lg transition-colors w-full md:w-auto"
           style="background:var(--color-info); color:#fff;">
            + Nueva Estrategia
        </a>
    </div>

    <div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-[12px]">
                <thead>
                    <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                        <th class="px-3 py-2 font-medium">Nombre</th>
                        
                        <th class="px-3 py-2 font-medium hidden md:table-cell">Descripción</th>
                        <th class="px-3 py-2 font-medium text-center">Estado</th>
                        <th class="px-3 py-2 font-medium text-right">Acciones</th>
                    </tr>
                </thead>
                <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                    @forelse($strategies as $s)
                    <tr class="hover:bg-[#1A2230] transition-colors">
                        <td class="px-3 py-3">
                            <span class="font-medium" style="color:var(--color-text-primary);">{{ $s->name }}</span>
                            <div class="md:hidden text-[10px] mt-0.5" style="color:var(--color-text-muted);">
                                {{ $s->description ?? 'Sin descripción' }}
                            </div>
                        </td>
                        
                        <td class="px-3 py-3 hidden md:table-cell text-[11px]" style="color:var(--color-text-muted);">
                            {{ Str::limit($s->description ?? 'Sin descripción', 50) }}
                        </td>
                        <td class="px-3 py-3 text-center">
                            <form method="POST" action="{{ route('strategies.toggle', $s) }}" style="display:inline;">
                                @csrf @method('PATCH')
                                <button type="submit" class="px-2 py-0.5 rounded-full text-[10px] border transition-colors"
                                        style="background:{{ $s->active ? '#16331F' : 'var(--color-surface-raised)' }}; border-color:{{ $s->active ? '#1E4A2E' : 'var(--color-border-strong)' }}; color:{{ $s->active ? 'var(--color-profit)' : 'var(--color-text-muted)' }};">
                                    {{ $s->active ? 'Activa' : 'Inactiva' }}
                                </button>
                            </form>
                        </td>
                        <td class="px-3 py-3 text-right space-x-2">
                            <a href="{{ route('strategies.edit', $s) }}" class="text-[11px]" style="color:var(--color-info);">Editar</a>
                            <form method="POST" action="{{ route('strategies.destroy', $s) }}" style="display:inline;" onsubmit="return confirmDelete(event, '{{ $s->name }}')">
                                @csrf @method('DELETE')
                                <button type="submit" class="text-[11px]" style="color:var(--color-loss);">Eliminar</button>
                            </form>
                        </td>
                    </tr>
                    @empty
                    <tr>
                        <td colspan="5" class="px-3 py-8 text-center text-sm" style="color:var(--color-text-muted);">
                            No hay estrategias registradas. Crea la primera.
                        </td>
                    </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
function confirmDelete(event, name) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: '¿Eliminar Estrategia?',
        html: `Vas a eliminar <b>${name}</b>.<br><br>Los backtests asociados también se eliminarán. Esta acción no se puede deshacer.`,
        icon: 'warning', showCancelButton: true,
        confirmButtonText: 'Sí, eliminar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
    }).then((result) => { if (result.isConfirmed) form.submit(); });
    return false;
}
</script>
@endpush

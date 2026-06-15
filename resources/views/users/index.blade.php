@extends('layouts.app')

@section('title', 'Usuarios')
@section('header', 'Usuarios')

@section('content')

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    @if ($errors->any())
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
            {{ $errors->first() }}
        </div>
    @endif

    @php
        $roleLabels = [
            'admin' => 'Administrador',
            'consultor' => 'Consultor',
            'inversionista' => 'Inversionista',
        ];
    @endphp

    <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Usuarios del sistema</h3>

        {{-- Mobile: cards --}}
        <div class="space-y-2 lg:hidden">
            @foreach ($users as $u)
                <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <div class="flex items-center justify-between mb-2">
                        <div class="min-w-0">
                            <p class="text-sm font-medium truncate" style="color:var(--color-text-primary);">{{ $u->name }}</p>
                            <p class="text-[11px] truncate" style="color:var(--color-text-muted);">{{ $u->email }}</p>
                        </div>
                        <span class="text-[11px] px-2 py-0.5 rounded shrink-0 ml-2" style="background:var(--color-surface); color:var(--color-text-secondary); border:1px solid var(--color-border-soft);">
                            {{ $roleLabels[$u->role] ?? $u->role }}
                        </span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="inline-flex items-center gap-1.5 text-[11px]" style="color: {{ $u->is_active ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                            <span class="h-2 w-2 rounded-full" style="background: {{ $u->is_active ? 'var(--color-profit)' : 'var(--color-loss)' }};"></span>
                            {{ $u->is_active ? 'Activo' : 'Inactivo' }}
                        </span>

                        @if ($u->id !== auth()->id())
                            <form method="POST" action="{{ route('users.toggle-active', $u) }}" onsubmit="return confirmToggle(event, {{ $u->is_active ? 'true' : 'false' }}, '{{ $u->name }}')">
                                @csrf
                                <button type="submit" class="text-[11px] px-2 py-1 rounded" style="color: {{ $u->is_active ? 'var(--color-loss)' : 'var(--color-profit)' }}; border:1px solid var(--color-border-soft);">
                                    {{ $u->is_active ? 'Inactivar' : 'Activar' }}
                                </button>
                            </form>
                        @else
                            <span class="text-[11px]" style="color:var(--color-text-muted);">Tu cuenta</span>
                        @endif
                    </div>
                </div>
            @endforeach
        </div>

        {{-- Desktop: tabla --}}
        <div class="overflow-x-auto hidden lg:block">
            <table class="w-full text-[11px] text-left" style="color:var(--color-text-muted);">
                <thead>
                    <tr class="border-b" style="border-color:var(--color-border-soft);">
                        <th class="py-2 px-2 font-normal">Nombre</th>
                        <th class="py-2 px-2 font-normal">Email</th>
                        <th class="py-2 px-2 font-normal">Rol</th>
                        <th class="py-2 px-2 font-normal">Estado</th>
                        <th class="py-2 px-2 font-normal">Acción</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($users as $u)
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <td class="py-2 px-2 font-medium" style="color:var(--color-text-primary);">{{ $u->name }}</td>
                            <td class="py-2 px-2">{{ $u->email }}</td>
                            <td class="py-2 px-2">
                                <span class="text-[11px] px-2 py-0.5 rounded" style="background:var(--color-surface-raised); color:var(--color-text-secondary); border:1px solid var(--color-border-soft);">
                                    {{ $roleLabels[$u->role] ?? $u->role }}
                                </span>
                            </td>
                            <td class="py-2 px-2">
                                <span class="inline-flex items-center gap-1.5" style="color: {{ $u->is_active ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    <span class="h-2 w-2 rounded-full" style="background: {{ $u->is_active ? 'var(--color-profit)' : 'var(--color-loss)' }};"></span>
                                    {{ $u->is_active ? 'Activo' : 'Inactivo' }}
                                </span>
                            </td>
                            <td class="py-2 px-2">
                                @if ($u->id !== auth()->id())
                                    <form method="POST" action="{{ route('users.toggle-active', $u) }}" onsubmit="return confirmToggle(event, {{ $u->is_active ? 'true' : 'false' }}, '{{ $u->name }}')">
                                        @csrf
                                        <button type="submit" class="px-2 py-1 rounded transition-colors" style="color: {{ $u->is_active ? 'var(--color-loss)' : 'var(--color-profit)' }}; border:1px solid var(--color-border-soft);">
                                            {{ $u->is_active ? 'Inactivar' : 'Activar' }}
                                        </button>
                                    </form>
                                @else
                                    <span style="color:var(--color-text-muted);">Tu cuenta</span>
                                @endif
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    </div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
    function confirmToggle(event, isActive, name) {
        event.preventDefault();
        const form = event.target;

        Swal.fire({
            title: isActive ? 'Inactivar usuario' : 'Activar usuario',
            html: isActive
                ? `¿Inactivar a <b>${name}</b>? No podrá iniciar sesión y sus estrategias en real se pausarán.`
                : `¿Activar a <b>${name}</b>? Podrá iniciar sesión nuevamente.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: isActive ? 'Inactivar' : 'Activar',
            cancelButtonText: 'Cancelar',
            background: '#11161F',
            color: '#E5E9F0',
            confirmButtonColor: isActive ? '#F2545B' : '#3DD68C',
            cancelButtonColor: '#232B38',
            customClass: {
                popup: 'rounded-xl border',
            }
        }).then((result) => {
            if (result.isConfirmed) {
                form.submit();
            }
        });

        return false;
    }
</script>
@endpush

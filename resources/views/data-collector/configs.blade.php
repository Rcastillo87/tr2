@extends('layouts.app')

@section('title', 'Data Collector — Configuración')
@section('header', 'Data Collector — Configuración')

@section('content')

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    <p class="text-[11px] mb-4" style="color:var(--color-text-muted);">
        Controla qué símbolos e intervalos se recolectan activamente. Los desactivados mantienen sus datos históricos
        pero dejan de recibir velas nuevas. El motor Python lee esta configuración en cada ciclo.
    </p>

    <div class="space-y-4">
        @foreach ($grouped as $symbol => $configs)
            <div class="rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                {{-- Cabecera del símbolo --}}
                <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
                    <span class="font-medium text-sm" style="color:var(--color-text-primary);">{{ $symbol }}</span>
                    <span class="text-[11px]" style="color:var(--color-text-muted);">
                        {{ $configs->where('active', true)->count() }}/{{ $configs->count() }} activos
                    </span>
                </div>

                {{-- Filas de intervalos --}}
                <div class="divide-y" style="border-color:var(--color-border-soft);">
                    @foreach ($configs as $config)
                        <div class="flex items-center justify-between px-4 py-2.5">
                            <div class="flex items-center gap-3">
                                <span class="font-mono text-sm" style="color:var(--color-text-primary);">{{ $config->interval }}</span>
                                @if ($config->notes)
                                    <span class="text-[11px]" style="color:var(--color-text-muted);">{{ $config->notes }}</span>
                                @endif
                            </div>
                            <form method="POST" action="{{ route('collector.configs.toggle', $config) }}"
                                  onsubmit="return confirmToggle(event, '{{ $config->symbol }}', '{{ $config->interval }}', {{ $config->active ? 'true' : 'false' }})">
                                @csrf @method('PATCH')
                                <button type="submit"
                                        class="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full border transition-colors"
                                        style="background: {{ $config->active ? '#16331F' : 'var(--color-surface-raised)' }};
                                               border-color: {{ $config->active ? '#1E4A2E' : 'var(--color-border-strong)' }};
                                               color: {{ $config->active ? 'var(--color-profit)' : 'var(--color-text-muted)' }};">
                                    <span class="h-1.5 w-1.5 rounded-full inline-block"
                                          style="background: {{ $config->active ? 'var(--color-profit)' : 'var(--color-text-muted)' }};"></span>
                                    {{ $config->active ? 'Activo' : 'Inactivo' }}
                                </button>
                            </form>
                        </div>
                    @endforeach
                </div>
            </div>
        @endforeach
    </div>

    <div class="mt-4 rounded-lg border p-3 text-[11px]" style="background:var(--color-surface-raised); border-color:var(--color-border-soft); color:var(--color-text-muted);">
        <strong style="color:var(--color-neutral);">Nota:</strong>
        Los cambios toman efecto en el próximo ciclo del colector (cada minuto).
        Desactivar un símbolo/intervalo no elimina sus datos históricos.
    </div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
function confirmToggle(event, symbol, interval, isActive) {
    event.preventDefault();
    const form = event.target;

    Swal.fire({
        title: isActive ? 'Desactivar recolección' : 'Activar recolección',
        html: isActive
            ? `¿Desactivar <b>${symbol}/${interval}</b>? Dejará de recibir velas nuevas. Los datos históricos se conservan.`
            : `¿Activar <b>${symbol}/${interval}</b>? Comenzará a recolectar velas nuevas en el próximo ciclo.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: isActive ? 'Desactivar' : 'Activar',
        cancelButtonText: 'Cancelar',
        background: '#11161F',
        color: '#E5E9F0',
        confirmButtonColor: isActive ? '#F2545B' : '#3DD68C',
        cancelButtonColor: '#232B38',
        customClass: { popup: 'rounded-xl border' }
    }).then((result) => {
        if (result.isConfirmed) form.submit();
    });

    return false;
}
</script>
@endpush

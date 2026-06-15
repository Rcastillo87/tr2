@extends('layouts.app')

@section('title', 'Cuentas — Trading Real')
@section('header', 'Trading real — Cuentas')

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

    <div class="flex items-center justify-between mb-4">
        <p class="text-xs" style="color:var(--color-text-muted);">Cuentas de broker vinculadas a tu usuario</p>
        <a href="{{ route('real-trading.accounts.create') }}"
           class="inline-flex items-center px-3 py-1.5 rounded-lg font-medium text-xs transition-colors"
           style="background:var(--color-info); color:#fff;">
            + Agregar cuenta
        </a>
    </div>

    @if ($accounts->isEmpty())
        <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <p class="text-sm" style="color:var(--color-text-muted);">Aún no tienes cuentas de broker configuradas.</p>
        </div>
    @else
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            @foreach ($accounts as $account)
                <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                    <div class="flex items-start justify-between mb-3 gap-2">
                        <div class="min-w-0">
                            <p class="text-sm font-medium truncate" style="color:var(--color-text-primary);">{{ $account->label }}</p>
                            <p class="text-[11px] mt-0.5" style="color:var(--color-text-muted);">{{ ucfirst($account->broker) }}</p>
                        </div>
                        <span class="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0" style="background: {{ $account->account_type === 'demo' ? '#3A2E0E' : '#16331F' }}; color: {{ $account->account_type === 'demo' ? 'var(--color-neutral)' : 'var(--color-profit)' }};">
                            {{ strtoupper($account->account_type) }}
                        </span>
                    </div>

                    <div class="flex items-center justify-between text-[11px] mb-3" style="color:var(--color-text-muted);">
                        <span class="inline-flex items-center gap-1.5">
                            <span class="h-2 w-2 rounded-full" style="background: {{ $account->status === 'active' ? 'var(--color-profit)' : 'var(--color-loss)' }};"></span>
                            {{ $account->status === 'active' ? 'Activa' : 'Pausada' }}
                        </span>
                        <span>{{ $account->subscriptions_count }} suscripción(es)</span>
                    </div>

                    <div class="flex items-center gap-2">
                        <form method="POST" action="{{ route('real-trading.accounts.toggle-status', $account) }}" class="flex-1">
                            @csrf
                            @method('PATCH')
                            <button type="submit" class="w-full text-[11px] px-2 py-1.5 rounded transition-colors" style="color: {{ $account->status === 'active' ? 'var(--color-loss)' : 'var(--color-profit)' }}; border:1px solid var(--color-border-soft);">
                                {{ $account->status === 'active' ? 'Pausar' : 'Activar' }}
                            </button>
                        </form>

                        @if ($account->subscriptions_count === 0)
                            <form method="POST" action="{{ route('real-trading.accounts.destroy', $account) }}" onsubmit="return confirmDelete(event, '{{ $account->label }}')" class="flex-1">
                                @csrf
                                @method('DELETE')
                                <button type="submit" class="w-full text-[11px] px-2 py-1.5 rounded transition-colors" style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
                                    Eliminar
                                </button>
                            </form>
                        @endif
                    </div>
                </div>
            @endforeach
        </div>
    @endif

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
    function confirmDelete(event, label) {
        event.preventDefault();
        const form = event.target;

        Swal.fire({
            title: 'Eliminar cuenta',
            html: `¿Eliminar la cuenta <b>${label}</b>? Esta acción no se puede deshacer.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Eliminar',
            cancelButtonText: 'Cancelar',
            background: '#11161F',
            color: '#E5E9F0',
            confirmButtonColor: '#F2545B',
            cancelButtonColor: '#232B38',
            customClass: { popup: 'rounded-xl border' }
        }).then((result) => {
            if (result.isConfirmed) {
                form.submit();
            }
        });

        return false;
    }
</script>
@endpush

@extends('layouts.app')
@section('title', 'Trading — Cuentas')
@section('header', 'Trading — Cuentas')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

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

{{-- Formulario crear cuenta --}}
<div class="rounded-lg border p-4 mb-6" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <h3 class="text-sm font-medium mb-4" style="color:var(--color-text-secondary);">Agregar cuenta de broker</h3>
    <form method="POST" action="{{ route('trading.accounts.store') }}" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3" onsubmit="showSaving()">
        @csrf
        <div>
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Broker</label>
            <select name="broker" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                    style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                <option value="bybit">Bybit</option>
            </select>
        </div>
        <div>
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Tipo</label>
            <select name="account_type" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                    style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                <option value="real">Real</option>
                @if ($canCreateDemo)
                    <option value="demo">Demo</option>
                @endif
            </select>
        </div>
        <div>
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">API Key</label>
            <input type="text" name="api_key" placeholder="Clave API del broker" autocomplete="off"
                   class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
        </div>
        <div>
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">API Secret</label>
            <input type="password" name="api_secret" placeholder="Secreto API" autocomplete="off"
                   class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                   style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
        </div>
        <div class="sm:col-span-2 lg:col-span-4 flex justify-end">
            <button type="submit" class="text-sm font-medium px-6 py-2 rounded-lg transition-colors"
                    style="background:var(--color-info); color:#fff;">
                Guardar cuenta
            </button>
        </div>
    </form>
    <p class="text-[10px] mt-2" style="color:var(--color-text-muted);">Las credenciales se almacenan cifradas. El nombre se genera automáticamente (ej. "Bybit Real").</p>
</div>

{{-- Lista de cuentas --}}
@forelse ($accounts as $account)
    @php
        $subscribedIds = $subscribedByAccount[$account->id] ?? [];
        $unsubscribed  = $availableConfigs->whereNotIn('id', $subscribedIds)->values();
    @endphp
    <div class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">

        {{-- Header --}}
        <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
            <div class="flex items-center gap-3">
                <p class="text-sm font-medium" style="color:var(--color-text-primary);">{{ $account->label }}</p>
                <span class="text-[10px] font-medium px-1.5 py-0.5 rounded"
                      style="background: {{ $account->account_type === 'demo' ? '#3A2E0E' : '#16331F' }};
                             color: {{ $account->account_type === 'demo' ? 'var(--color-neutral)' : 'var(--color-profit)' }};">
                    {{ strtoupper($account->account_type) }}
                </span>
                <span class="inline-flex items-center gap-1.5 text-[11px]" style="color:var(--color-text-muted);">
                    <span class="h-2 w-2 rounded-full" style="background: {{ $account->status === 'active' ? 'var(--color-profit)' : 'var(--color-loss)' }};"></span>
                    {{ $account->status === 'active' ? 'Activa' : 'Pausada' }}
                </span>
            </div>
            <div class="flex items-center gap-2">
                <form method="POST" action="{{ route('trading.accounts.toggle-status', $account) }}"
                      onsubmit="return confirmAccountToggle(event, '{{ $account->label }}', {{ $account->status === 'active' ? 'true' : 'false' }})">
                    @csrf @method('PATCH')
                    <button type="submit" class="text-[11px] px-3 py-1.5 rounded transition-colors"
                            style="color: {{ $account->status === 'active' ? 'var(--color-loss)' : 'var(--color-profit)' }}; border:1px solid var(--color-border-soft);">
                        {{ $account->status === 'active' ? 'Pausar' : 'Activar' }}
                    </button>
                </form>
                @if ($account->subscriptions_count === 0)
                    <form method="POST" action="{{ route('trading.accounts.destroy', $account) }}"
                          onsubmit="return confirmDelete(event, '{{ $account->label }}')">
                        @csrf @method('DELETE')
                        <button type="submit" class="text-[11px] px-3 py-1.5 rounded transition-colors"
                                style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
                            Eliminar
                        </button>
                    </form>
                @endif
            </div>
        </div>

        {{-- Estrategias --}}
        <div class="p-4">
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-[11px] font-medium" style="color:var(--color-text-secondary);">
                    Estrategias suscritas ({{ $account->subscriptions->count() }})
                </h4>
                @if ($unsubscribed->isNotEmpty())
                    <button type="button" onclick="openSubscribeModal({{ $account->id }}, '{{ $account->label }}')"
                            class="text-[11px] px-3 py-1 rounded transition-colors"
                            style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                        + Agregar estrategia
                    </button>
                @endif
            </div>

            @if ($account->subscriptions->isEmpty())
                <p class="text-[11px]" style="color:var(--color-text-muted);">No hay estrategias suscritas aún.</p>
            @else
                <table class="w-full text-[11px]" style="color:var(--color-text-muted);">
                    <thead>
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <th class="py-2 px-2 text-left font-medium">Estrategia</th>
                            <th class="py-2 px-2 text-left font-medium">Símbolo</th>
                            <th class="py-2 px-2 text-left font-medium">Int.</th>
                            <th class="py-2 px-2 text-left font-medium">Estado</th>
                            <th class="py-2 px-2 text-left font-medium">Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($account->subscriptions as $sub)
                            @php $lbs = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $sub->strategy }}</td>
                                <td class="py-2 px-2 font-mono">{{ $sub->symbol }}</td>
                                <td class="py-2 px-2 font-mono">{{ $lbs[$sub->interval] ?? $sub->interval }}</td>
                                <td class="py-2 px-2">
                                    <span class="px-1.5 py-0.5 rounded text-[10px]"
                                          style="background: {{ $sub->status === 'active' ? '#16331F' : '#3A1A1C' }};
                                                 color: {{ $sub->status === 'active' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ $sub->status === 'active' ? 'ACTIVA' : 'PAUSADA' }}
                                    </span>
                                </td>
                                <td class="py-2 px-2">
                                    <div class="flex items-center gap-3">
                                        @if ($sub->paperStrategyConfig)
                                            <button type="button"
                                                    onclick="showConfigModal({{ json_encode($sub->paperStrategyConfig->params) }}, '{{ $sub->strategy }}')"
                                                    class="transition-colors" style="color:var(--color-info);">
                                                Ver config
                                            </button>
                                        @endif
                                        <form method="POST" action="{{ route('trading.subscriptions.toggle', [$account, $sub]) }}"
                                              onsubmit="return confirmSubToggle(event, '{{ $sub->strategy }}', {{ $sub->status === 'active' ? 'true' : 'false' }})">
                                            @csrf @method('PATCH')
                                            <button type="submit" class="transition-colors"
                                                    style="color: {{ $sub->status === 'active' ? 'var(--color-loss)' : 'var(--color-profit)' }};">
                                                {{ $sub->status === 'active' ? 'Pausar' : 'Activar' }}
                                            </button>
                                        </form>
                                        <form method="POST" action="{{ route('trading.subscriptions.destroy', [$account, $sub]) }}"
                                              onsubmit="return confirmSubDelete(event, '{{ $sub->strategy }}')">
                                            @csrf @method('DELETE')
                                            <button type="submit" class="transition-colors" style="color:var(--color-text-muted);">
                                                Quitar
                                            </button>
                                        </form>
                                    </div>
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            @endif
        </div>
    </div>
@empty
    <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-sm" style="color:var(--color-text-muted);">Aún no tienes cuentas configuradas. Usa el formulario de arriba para agregar la primera.</p>
    </div>
@endforelse

{{-- Modal suscribir estrategia --}}
<div id="subscribeModalOverlay" class="hidden fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4" style="background:rgba(0,0,0,0.7);">
    <div class="rounded-lg border w-full max-w-2xl my-8" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between p-4 border-b" style="border-color:var(--color-border-soft);">
            <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                Agregar estrategia a <span id="modalAccountLabel" class="font-semibold"></span>
            </h3>
            <button type="button" onclick="closeSubscribeModal()" class="text-xl" style="color:var(--color-text-muted);">✕</button>
        </div>
        <div class="p-4">
            {{-- Datos de configs disponibles por cuenta (JSON para JS) --}}
            @foreach ($accounts as $account)
                @php
                    $subscribedIds = $subscribedByAccount[$account->id] ?? [];
                    $unsubscribed  = $availableConfigs->whereNotIn('id', $subscribedIds)->values();
                @endphp
                <div id="configsFor_{{ $account->id }}" class="hidden">
                    @if ($unsubscribed->isEmpty())
                        <p class="text-sm text-center py-4" style="color:var(--color-profit);">
                            ✓ Todas las estrategias activas ya están suscritas a esta cuenta.
                        </p>
                    @else
                        <div class="flex justify-end mb-3">
                            <form method="POST" id="addAllForm_{{ $account->id }}"
                                  action="{{ route('trading.subscriptions.store-all', $account) }}"
                                  onsubmit="return confirmAddAll(event, '{{ $account->label }}', {{ $unsubscribed->count() }})">
                                @csrf
                                <button type="submit" class="text-[11px] px-3 py-1.5 rounded font-medium transition-colors"
                                        style="background:#16331F; color:var(--color-profit); border:1px solid #1E4A2E;">
                                    + Añadir todas ({{ $unsubscribed->count() }})
                                </button>
                            </form>
                        </div>
                        <table class="w-full text-[11px]" style="color:var(--color-text-muted);">
                            <thead>
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <th class="py-2 px-2 text-left font-medium">Estrategia</th>
                                    <th class="py-2 px-2 text-left font-medium">Símbolo</th>
                                    <th class="py-2 px-2 text-left font-medium">Int.</th>
                                    <th class="py-2 px-2 text-left font-medium">Params</th>
                                    <th class="py-2 px-2 text-left font-medium">Acciones</th>
                                </tr>
                            </thead>
                            <tbody>
                                @foreach ($unsubscribed as $config)
                                    @php $lbs = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                                    <tr class="border-b" style="border-color:var(--color-border-soft);">
                                        <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $config->display_name }}</td>
                                        <td class="py-2 px-2 font-mono">{{ $config->symbol }}</td>
                                        <td class="py-2 px-2 font-mono">{{ $lbs[$config->interval] ?? $config->interval }}</td>
                                        <td class="py-2 px-2 font-mono text-[10px]">
                                            sl:{{ $config->params['sl_pct'] ?? '—' }}
                                            tp:{{ $config->params['tp_pct'] ?? '—' }}
                                            be:{{ $config->params['be_pct'] ?? '—' }}
                                        </td>
                                        <td class="py-2 px-2">
                                            <div class="flex items-center gap-2">
                                                <button type="button"
                                                        onclick="showConfigModal({{ json_encode($config->params) }}, '{{ $config->display_name }}')"
                                                        class="transition-colors" style="color:var(--color-text-muted);">
                                                    Ver config
                                                </button>
                                                <form method="POST"
                                                      action="{{ route('trading.subscriptions.store', $account) }}"
                                                      onsubmit="return confirmSubscribe(event, '{{ $config->display_name }}')">
                                                    @csrf
                                                    <input type="hidden" name="paper_strategy_config_id" value="{{ $config->id }}">
                                                    <button type="submit" class="px-2 py-1 rounded text-[10px] font-medium transition-colors"
                                                            style="background:var(--color-info); color:#fff;">
                                                        Suscribir
                                                    </button>
                                                </form>
                                            </div>
                                        </td>
                                    </tr>
                                @endforeach
                            </tbody>
                        </table>
                    @endif
                </div>
            @endforeach
        </div>
    </div>
</div>

{{-- Modal ver config completa --}}
<div id="configModalOverlay" class="hidden fixed inset-0 z-[60] flex items-center justify-center p-4" style="background:rgba(0,0,0,0.8);">
    <div class="rounded-lg border w-full max-w-lg" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between p-4 border-b" style="border-color:var(--color-border-soft);">
            <h3 id="configModalTitle" class="text-sm font-medium" style="color:var(--color-text-secondary);"></h3>
            <button type="button" onclick="closeConfigModal()" class="text-xl" style="color:var(--color-text-muted);">✕</button>
        </div>
        <div id="configModalBody" class="p-4 font-mono text-[11px] space-y-1.5" style="color:var(--color-text-muted);"></div>
    </div>
</div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
let currentAccountId = null;

function openSubscribeModal(accountId, accountLabel) {
    currentAccountId = accountId;
    document.getElementById('modalAccountLabel').textContent = accountLabel;

    // Mostrar solo los configs de esta cuenta
    document.querySelectorAll('[id^="configsFor_"]').forEach(el => el.classList.add('hidden'));
    const el = document.getElementById(`configsFor_${accountId}`);
    if (el) el.classList.remove('hidden');

    document.getElementById('subscribeModalOverlay').classList.remove('hidden');
}

function closeSubscribeModal() {
    document.getElementById('subscribeModalOverlay').classList.add('hidden');
}

function showConfigModal(params, title) {
    document.getElementById('configModalTitle').textContent = title;
    const labels = {
        sl_pct: 'Stop Loss %', tp_pct: 'Take Profit 1 %', tp2_pct: 'Take Profit 2 %',
        tp3_pct: 'Take Profit 3 %', tp4_pct: 'Take Profit 4 %', be_pct: 'Break-even %',
        max_duration: 'Máx. duración (velas)', risk_per_trade_pct: 'Riesgo/trade %',
        mode: 'Modo', regime_filter: 'Filtro régimen', macro_trend_filter: 'Filtro macro H4',
        trailing_mode: 'Trailing Stop', volatility_protection_mode: 'Protección volatilidad',
    };
    let html = '';
    for (const [key, label] of Object.entries(labels)) {
        if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
            let val = params[key];
            if (typeof val === 'boolean') val = val ? 'Sí' : 'No';
            html += `<div class="flex justify-between border-b pb-1" style="border-color:var(--color-border-soft);">
                        <span style="color:var(--color-text-secondary);">${label}</span>
                        <span style="color:var(--color-text-primary);">${val}</span>
                     </div>`;
        }
    }
    document.getElementById('configModalBody').innerHTML = html || '<p>Sin parámetros.</p>';
    document.getElementById('configModalOverlay').classList.remove('hidden');
}

function closeConfigModal() {
    document.getElementById('configModalOverlay').classList.add('hidden');
}

function showSaving() {
    Swal.fire({ title: 'Guardando...', allowOutsideClick: false, background: '#11161F', color: '#E5E9F0', didOpen: () => Swal.showLoading(), timer: 4000 });
}

function confirmAccountToggle(event, label, isActive) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: isActive ? 'Pausar cuenta' : 'Activar cuenta',
        html: isActive ? `¿Pausar <b>${label}</b>? Sus suscripciones también se pausarán.` : `¿Activar <b>${label}</b>?`,
        icon: 'warning', showCancelButton: true,
        confirmButtonText: isActive ? 'Pausar' : 'Activar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: isActive ? '#F2545B' : '#3DD68C', cancelButtonColor: '#232B38',
    }).then(r => { if (r.isConfirmed) form.submit(); });
    return false;
}

function confirmDelete(event, label) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: 'Eliminar cuenta', html: `¿Eliminar <b>${label}</b>? No se puede deshacer.`,
        icon: 'warning', showCancelButton: true,
        confirmButtonText: 'Eliminar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
    }).then(r => { if (r.isConfirmed) form.submit(); });
    return false;
}

function confirmSubscribe(event, name) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: 'Suscribir estrategia',
        html: `¿Suscribir <b>${name}</b>?<br><small>El bot comenzará a operar con esta estrategia en cuanto haya una señal válida.</small>`,
        icon: 'question', showCancelButton: true,
        confirmButtonText: 'Suscribir', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#4D8FE8', cancelButtonColor: '#232B38',
    }).then(r => {
        if (r.isConfirmed) {
            Swal.fire({ title: 'Suscribiendo...', allowOutsideClick: false, background: '#11161F', color: '#E5E9F0', didOpen: () => Swal.showLoading() });
            form.submit();
        }
    });
    return false;
}

function confirmAddAll(event, accountLabel, count) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: 'Añadir todas las estrategias',
        html: `¿Añadir las <b>${count}</b> estrategias disponibles a <b>${accountLabel}</b>?`,
        icon: 'question', showCancelButton: true,
        confirmButtonText: 'Añadir todas', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#3DD68C', cancelButtonColor: '#232B38',
    }).then(r => {
        if (r.isConfirmed) {
            Swal.fire({ title: 'Añadiendo...', allowOutsideClick: false, background: '#11161F', color: '#E5E9F0', didOpen: () => Swal.showLoading() });
            form.submit();
        }
    });
    return false;
}

function confirmSubToggle(event, name, isActive) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: isActive ? 'Pausar estrategia' : 'Activar estrategia',
        html: isActive ? `¿Pausar <b>${name}</b>?` : `¿Activar <b>${name}</b>?`,
        icon: 'warning', showCancelButton: true,
        confirmButtonText: isActive ? 'Pausar' : 'Activar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: isActive ? '#F2545B' : '#3DD68C', cancelButtonColor: '#232B38',
    }).then(r => { if (r.isConfirmed) form.submit(); });
    return false;
}

function confirmSubDelete(event, name) {
    event.preventDefault();
    const form = event.target;
    Swal.fire({
        title: 'Quitar estrategia', html: `¿Quitar <b>${name}</b> de esta cuenta?`,
        icon: 'warning', showCancelButton: true,
        confirmButtonText: 'Quitar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
    }).then(r => { if (r.isConfirmed) form.submit(); });
    return false;
}
</script>
@endpush

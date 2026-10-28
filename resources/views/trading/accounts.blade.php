@extends('layouts.app')
@section('title', 'Trading — Cuentas')
@section('header', 'Trading — Cuentas')

@section('content')
<div class="mb-4">
    <a href="{{ route('trading.index') }}" class="text-[11px] transition-colors" style="color:var(--color-text-muted);">
        ← Volver a Trading
    </a>
</div>

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

@include('trading.partials.risk_limits', ['accounts' => $accounts, 'risk' => $risk])

{{-- Formulario crear cuenta --}}
<div class="rounded-lg border p-4 mb-6" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <h3 class="text-sm font-medium mb-4" style="color:var(--color-text-secondary);">Agregar cuenta de broker</h3>
    <form method="POST" action="{{ route('trading.accounts.store') }}" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3" onsubmit="showSaving()">
        @csrf
        <div>
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Broker</label>
            <select name="broker" id="brokerSelect" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
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
        <div id="apiSecretField">
            <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">API Secret</label>
            <input type="password" name="api_secret" id="apiSecretInput" placeholder="Secreto API" autocomplete="off" required
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
    <div class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        {{-- Header --}}
        <div class="flex items-center justify-between px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
            <div class="flex items-center gap-2">
                <span class="font-medium text-sm" style="color:var(--color-text-primary);">{{ $account->label }}</span>
                <span class="px-2 py-0.5 rounded text-[10px] font-medium" style="background:{{ $account->status === 'active' ? '#16331F' : '#33221B' }}; color:{{ $account->status === 'active' ? 'var(--color-profit)' : '#F59E0B' }};">
                    {{ $account->status === 'active' ? 'Activa' : 'Pausada' }}
                </span>
                <span class="text-[10px]" style="color:var(--color-text-muted);">
                    ({{ ucfirst($account->broker) }} {{ strtoupper($account->account_type) }})
                </span>
            </div>
            <div class="flex items-center gap-2">
                <form method="POST" action="{{ route('trading.accounts.toggle-status', $account) }}">
                    @csrf @method('PATCH')
                    <button type="submit" class="text-[11px] px-2 py-1 rounded border" style="background:transparent; border-color:var(--color-border-strong); color:var(--color-text-primary);">
                        {{ $account->status === 'active' ? '⏸️ Pausar Cuenta' : '▶️ Reanudar Cuenta' }}
                    </button>
                </form>
                <form method="POST" action="{{ route('trading.accounts.destroy', $account) }}" onsubmit="return confirm('¿Eliminar esta cuenta?');">
                    @csrf @method('DELETE')
                    <button type="submit" class="text-[11px] px-2 py-1 rounded border text-red-400" style="background:transparent; border-color:#7F1D1D;">
                        🗑️
                    </button>
                </form>
            </div>
        </div>

        {{-- Body: Suscripciones --}}
        <div class="p-4">
            <div class="flex items-center justify-between mb-3">
                <h4 class="text-[11px] font-medium" style="color:var(--color-text-secondary);">
                    Configuraciones suscritas (<span id="account-count-{{ $account->id }}">{{ $account->subscriptions->count() }}</span>)
                </h4>
                @if (!empty($availableConfigsByAccount[$account->id]) && $availableConfigsByAccount[$account->id]->isNotEmpty())
                    <button type="button" onclick="openSubscribeModal({{ $account->id }}, '{{ $account->label }}')"
                            class="text-[11px] px-3 py-1 rounded transition-colors"
                            style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                        + Agregar Configuración
                    </button>
                @endif
            </div>

            <div id="account-subs-{{ $account->id }}">
                    @include('trading.partials.subscriptions_list', ['account' => $account])
                </div>
        </div>
    </div>
@empty
    <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-sm" style="color:var(--color-text-muted);">Aún no tienes cuentas configuradas. Usa el formulario de arriba para agregar la primera.</p>
    </div>
@endforelse
{{-- Modal suscribir estrategia --}}
<div id="subscribeModalOverlay" class="hidden fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4" style="background:rgba(0,0,0,0.7);">
    <div class="rounded-lg border w-full max-w-5xl my-8" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between p-4 border-b" style="border-color:var(--color-border-soft);">
            <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                Agregar configuración a <span id="modalAccountLabel" class="font-semibold"></span>
            </h3>
            <button type="button" onclick="closeSubscribeModal()" class="text-xl" style="color:var(--color-text-muted);">✕</button>
        </div>
        <div class="p-4 space-y-4">
            @foreach ($accounts as $account)
                <div id="configsFor_{{ $account->id }}" class="hidden">
                    @if (($availableConfigsByAccount[$account->id] ?? collect())->isEmpty())
                        <p class="text-sm text-center py-4" style="color:var(--color-profit);">
                            ✓ Todas las configuraciones activas ya están suscritas a esta cuenta.
                        </p>
                    @else
                        <div class="flex justify-end mb-3">
                            <form method="POST" action="{{ route('trading.subscriptions.store-all', $account) }}" onsubmit="submitAddAllForm(event, this, {{ $account->id }})">
                                @csrf
                                <button type="submit" class="text-[11px] px-3 py-1.5 rounded font-medium transition-colors" style="background:#16331F; color:var(--color-profit); border:1px solid #1E4A2E;">
                                    + Añadir todas las disponibles ({{ $availableConfigsByAccount[$account->id]->count() }})
                                </button>
                            </form>
                        </div>
                        
                        <div class="space-y-4" id="configsList_{{ $account->id }}">
                            @foreach ($availableConfigsByAccount[$account->id] as $group)
                                @php
                                    $bt = $group['backtest'];
                                    $params = $group['params'];
                                    $m = $group['metrics'];
                                    
                                    // CÁLCULO DE ESTRELLAS (Igual que en el Historial)
                                    $wr = $m['win_rate'];
                                    $sharpe = $m['sharpe_ratio'];
                                    $pf = $m['profit_factor'];
                                    $ret = $m['avg_monthly_pnl'];
                                    $consist = $m['consist_pct'];
                                    $trades = $m['total_trades'];
                                    
                                    $sWr = $wr >= 65 ? 5 : ($wr >= 55 ? 4 : ($wr >= 45 ? 3 : ($wr >= 35 ? 2 : 1)));
                                    $sSharpe = $sharpe >= 4 ? 5 : ($sharpe >= 3 ? 4 : ($sharpe >= 2 ? 3 : ($sharpe >= 1 ? 2 : 1)));
                                    $sPf = $pf >= 2.5 ? 5 : ($pf >= 2.0 ? 4 : ($pf >= 1.5 ? 3 : ($pf >= 1.0 ? 2 : 1)));
                                    $sRet = $ret >= 20 ? 5 : ($ret >= 10 ? 4 : ($ret >= 5 ? 3 : ($ret >= 2 ? 2 : 1)));
                                    $sCons = $consist >= 80 ? 5 : ($consist >= 60 ? 4 : ($consist >= 40 ? 3 : ($consist >= 20 ? 2 : 1)));
                                    
                                    $rating = round(($sWr + $sSharpe + $sPf + $sRet + $sCons) / 5, 1);
                                    if ($rating <= 0) $rating = 1.0;
                                    
                                    $starColor = $rating >= 4 ? '#F5C518' : ($rating >= 3 ? '#EF9F27' : ($rating >= 2 ? '#E8832A' : '#E24B4A'));
                                @endphp

                                <div class="rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);" id="group_{{ $account->id }}_{{ $group['id'] }}">
                                    {{-- Header con Botón --}}
                                    <div class="flex items-center justify-between px-4 py-2.5 border-b" style="border-color:var(--color-border-soft);">
                                        <div class="flex items-center gap-3">
                                            <span class="text-[12px] font-medium" style="color:var(--color-text-primary);">{{ $group['display_name'] }}</span>
                                            <span class="text-[11px]" style="color:var(--color-text-muted);">{{ implode(', ', $group['symbols']) }} / {{ $group['interval'] }} / {{ $group['months'] }} meses</span>
                                        </div>
                                        <form method="POST" action="{{ route('trading.subscriptions.store', $account) }}" class="inline" onsubmit="submitAddForm(event, this, 'group_{{ $account->id }}_{{ $group['id'] }}', {{ $account->id }})">
                                            @csrf
                                            @foreach($group['config_ids'] as $configId)
                                                <input type="hidden" name="paper_strategy_config_ids[]" value="{{ $configId }}">
                                            @endforeach
                                            <button type="submit" class="px-3 py-1.5 rounded text-[11px] font-medium text-white" style="background:var(--color-info);">
                                                + Agregar a la Cuenta
                                            </button>
                                        </form>
                                    </div>

                                    {{-- Fila de Configuración (SL, TP, etc.) --}}
                                    <div style="display: grid; grid-template-columns: repeat(5, 1fr); border-bottom: 1px solid var(--color-border-soft);">
                                        <div style="text-align: center; padding: 8px 0; border-right: 1px solid var(--color-border-soft);">
                                            <p class="text-[10px]" style="color:var(--color-text-muted);">Stop Loss</p>
                                            <p class="text-sm font-mono">{{ $params['sl_pct'] ?? '-' }}%</p>
                                        </div>
                                        <div style="text-align: center; padding: 8px 0; border-right: 1px solid var(--color-border-soft);">
                                            <p class="text-[10px]" style="color:var(--color-text-muted);">Take Profit 1</p>
                                            <p class="text-sm font-mono">{{ $params['tp_pct'] ?? '-' }}%</p>
                                        </div>
                                        <div style="text-align: center; padding: 8px 0; border-right: 1px solid var(--color-border-soft);">
                                            <p class="text-[10px]" style="color:var(--color-text-muted);">Break-even</p>
                                            <p class="text-sm font-mono">{{ $params['be_pct'] ?? '-' }}%</p>
                                        </div>
                                        <div style="text-align: center; padding: 8px 0; border-right: 1px solid var(--color-border-soft);">
                                            <p class="text-[10px]" style="color:var(--color-text-muted);">Duración</p>
                                            <p class="text-sm font-mono">{{ $params['max_duration'] ?? '-' }} velas</p>
                                        </div>
                                        <div style="text-align: center; padding: 8px 0;">
                                            <p class="text-[10px]" style="color:var(--color-text-muted);">Riesgo/trade</p>
                                            <p class="text-sm font-mono">{{ $params['risk_per_trade_pct'] ?? '-' }}%</p>
                                        </div>
                                    </div>

                                    {{-- Fila de Rating Global y Trades --}}
                                    <div class="flex items-center justify-between px-4 py-2 border-b" style="border-color:var(--color-border-soft);">
                                        <div class="flex items-center gap-2">
                                            <span style="font-size:18px; line-height:1; color:{{ $starColor }};">{{ str_repeat('★', (int)round($rating)) . str_repeat('☆', 5 - (int)round($rating)) }}</span>
                                            <span style="font-size:14px; font-weight:700; color:{{ $starColor }};">{{ number_format($rating, 1) }}</span>
                                        </div>
                                        <span class="text-[11px]" style="color:var(--color-text-muted);">{{ $trades }} trades</span>
                                    </div>

                                    {{-- Fila de Métricas (5 columnas) --}}
                                    <div style="display: grid; grid-template-columns: repeat(5, 1fr); padding: 8px; gap: 4px;">
                                        <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                                            <p style="font-size:10px; color:var(--color-text-muted); margin:0 0 3px;">Win Rate</p>
                                            <p style="font-size:14px; color:{{ $sWr > 0 ? $starColor : '#4B5563' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★', $sWr) }}{{ str_repeat('☆', 5 - $sWr) }}</p>
                                            <p style="font-size:11px; font-family:monospace; margin:0;">{{ number_format($wr, 2) }}%</p>
                                        </div>
                                        <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                                            <p style="font-size:10px; color:var(--color-text-muted); margin:0 0 3px;">Sharpe Ratio</p>
                                            <p style="font-size:14px; color:{{ $sSharpe > 0 ? $starColor : '#4B5563' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★', $sSharpe) }}{{ str_repeat('☆', 5 - $sSharpe) }}</p>
                                            <p style="font-size:11px; font-family:monospace; margin:0;">{{ number_format($sharpe, 2) }}</p>
                                        </div>
                                        <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                                            <p style="font-size:10px; color:var(--color-text-muted); margin:0 0 3px;">Ret. prom/mes</p>
                                            <p style="font-size:14px; color:{{ $sRet > 0 ? $starColor : '#4B5563' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★', $sRet) }}{{ str_repeat('☆', 5 - $sRet) }}</p>
                                            <p style="font-size:11px; font-family:monospace; color:{{ $ret >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}; margin:0;">{{ number_format($ret, 2) }}%</p>
                                        </div>
                                        <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                                            <p style="font-size:10px; color:var(--color-text-muted); margin:0 0 3px;">Consistencia</p>
                                            <p style="font-size:14px; color:{{ $sCons > 0 ? $starColor : '#4B5563' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★', $sCons) }}{{ str_repeat('☆', 5 - $sCons) }}</p>
                                            <p style="font-size:11px; font-family:monospace; margin:0;">{{ number_format($consist, 1) }}%</p>
                                        </div>
                                        <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                                            <p style="font-size:10px; color:var(--color-text-muted); margin:0 0 3px;">Profit Factor</p>
                                            <p style="font-size:14px; color:{{ $sPf > 0 ? $starColor : '#4B5563' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★', $sPf) }}{{ str_repeat('☆', 5 - $sPf) }}</p>
                                            <p style="font-size:11px; font-family:monospace; margin:0;">{{ number_format($pf, 2) }}</p>
                                        </div>
                                    </div>
                                </div>
                            @endforeach
                        </div>
                    @endif
                </div>
            @endforeach
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
function submitAddForm(event, form, groupId, accountId) {
    event.preventDefault();
    Swal.fire({
        title: '¿Agregar configuración?',
        text: "Se agregará esta configuración a la cuenta.",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#3b82f6',
        cancelButtonColor: '#374151',
        confirmButtonText: 'Sí, agregar',
        cancelButtonText: 'Cancelar',
        background: '#1f2937',
        color: '#f3f4f6'
    }).then((result) => {
        if (result.isConfirmed) {
            const formData = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRF-TOKEN': '{{ csrf_token() }}',
                    'Accept': 'application/json'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const row = document.getElementById(groupId);
                    if (row) row.remove();
                    
                    const container = document.getElementById('configsList_' + accountId);
                    if (container && container.children.length === 0) {
                        container.innerHTML = '<p class="text-sm text-center py-4" style="color:var(--color-profit);">✓ Todas las configuraciones activas ya están suscritas a esta cuenta.</p>';
                    }
                    
                    // Actualizar la tarjeta del broker
                    const subsContainer = document.getElementById('account-subs-' + accountId);
                    if (subsContainer && data.html) subsContainer.innerHTML = data.html;
                    
                    const countEl = document.getElementById('account-count-' + accountId);
                    if (countEl && data.count !== undefined) countEl.textContent = data.count;
                    
                    Swal.fire({ title: '¡Agregado!', text: data.message, icon: 'success', timer: 1500, showConfirmButton: false, background: '#1f2937', color: '#f3f4f6' });
                } else {
                    Swal.fire('Error', data.message || 'Error al agregar', 'error');
                }
            }).catch(() => Swal.fire('Error', 'Error de conexión', 'error'));
        }
    });
}

function submitAddAllForm(event, form, accountId) {
    event.preventDefault();
    Swal.fire({
        title: '¿Agregar todas las configuraciones?',
        text: "Se agregarán todas las configuraciones disponibles.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3b82f6',
        cancelButtonColor: '#374151',
        confirmButtonText: 'Sí, agregar todas',
        cancelButtonText: 'Cancelar',
        background: '#1f2937',
        color: '#f3f4f6'
    }).then((result) => {
        if (result.isConfirmed) {
            const formData = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRF-TOKEN': '{{ csrf_token() }}',
                    'Accept': 'application/json'
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const container = document.getElementById('configsList_' + accountId);
                    if (container) {
                        container.innerHTML = '<p class="text-sm text-center py-4" style="color:var(--color-profit);">✓ Todas las configuraciones activas ya están suscritas a esta cuenta.</p>';
                    }
                    
                    // Actualizar la tarjeta del broker
                    const subsContainer = document.getElementById('account-subs-' + accountId);
                    if (subsContainer && data.html) subsContainer.innerHTML = data.html;
                    
                    const countEl = document.getElementById('account-count-' + accountId);
                    if (countEl && data.count !== undefined) countEl.textContent = data.count;
                    
                    Swal.fire({ title: '¡Agregado!', text: data.message, icon: 'success', timer: 1500, showConfirmButton: false, background: '#1f2937', color: '#f3f4f6' });
                } else {
                    Swal.fire('Error', data.message || 'Error al agregar', 'error');
                }
            }).catch(() => Swal.fire('Error', 'Error de conexión', 'error'));
        }
    });
}
</script>
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

function showMetricsGuideModal() {
    document.getElementById('metricsGuideModalOverlay').classList.remove('hidden');
}

function closeMetricsGuideModal() {
    document.getElementById('metricsGuideModalOverlay').classList.add('hidden');
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

function confirmSubToggle(event, name, isActive, willPauseOther) {
    event.preventDefault();
    const form = event.target;
    let html;
    if (isActive) {
        html = `¿Pausar <b>${name}</b>?`;
    } else if (willPauseOther) {
        html = `¿Activar <b>${name}</b>? Esto pausará automáticamente la otra estrategia activa para este mismo símbolo (solo puede haber una a la vez).`;
    } else {
        html = `¿Activar <b>${name}</b>?`;
    }
    Swal.fire({
        title: isActive ? 'Pausar estrategia' : 'Activar estrategia',
        html: html,
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

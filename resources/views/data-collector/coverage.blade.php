@extends('layouts.app')

@section('title', 'Data Collector — Cobertura')
@section('header', 'Data Collector — Cobertura de históricos')

@section('content')

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    @if ($errors->any())
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3F1D1D; border-color:#7F2D2D; color:#FCA5A5;">
            @foreach ($errors->all() as $err)<div>{{ $err }}</div>@endforeach
        </div>
    @endif

    <div class="flex items-center justify-between mb-4">
        <p class="text-[11px]" style="color:var(--color-text-muted);">
            Estado de cobertura por broker/símbolo/intervalo. Backfill para llenar rangos, Invalidar para borrar datos corruptos, Recargar para redescargar todo.
        </p>
        <div class="flex gap-2">
            <a href="{{ route('collector.configs.index') }}"
               class="text-[11px] px-3 py-1.5 rounded border"
               style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                ← Símbolos activos
            </a>
            <button onclick="openAddSymbol()"
                    class="text-[11px] px-3 py-1.5 rounded border"
                    style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
                + Agregar símbolo
            </button>
        </div>
    </div>

    <div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <table class="w-full text-[11px]">
            <thead>
                <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                    <th class="text-left px-3 py-2 font-medium">Broker</th>
                    <th class="text-left px-3 py-2 font-medium">Símbolo</th>
                    <th class="text-left px-3 py-2 font-medium">Int</th>
                    <th class="text-right px-3 py-2 font-medium">Desde</th>
                    <th class="text-right px-3 py-2 font-medium">Hasta</th>
                    <th class="text-right px-3 py-2 font-medium">Filas</th>
                    <th class="text-center px-3 py-2 font-medium">Estado</th>
                    <th class="text-right px-3 py-2 font-medium">Acciones</th>
                </tr>
            </thead>
            <tbody>
                @forelse ($coverage as $c)
                    @php
                        $hasta = $c['hasta'] ? \Carbon\Carbon::parse($c['hasta']) : null;
                        if (!$hasta) {
                            $estadoTexto = 'Vacío'; $estadoColor = '#6B7280';
                        } elseif ($c['actualizado']) {
                            $estadoTexto = 'Actualizado'; $estadoColor = '#3DD68C';
                        } elseif ($hasta->gt(now()->subHours(2))) {
                            $estadoTexto = 'Atrasado'; $estadoColor = '#F59E0B';
                        } else {
                            $estadoTexto = 'Congelado'; $estadoColor = '#F2545B';
                        }
                    @endphp
                    <tr class="border-t" style="border-color:var(--color-border-soft);">
                        <td class="px-3 py-2 font-mono" style="color:var(--color-text-muted);">{{ $c['broker'] }}</td>
                        <td class="px-3 py-2 font-medium" style="color:var(--color-text-primary);">{{ $c['symbol'] }}</td>
                        <td class="px-3 py-2 font-mono" style="color:var(--color-text-primary);">{{ $c['interval'] }}</td>
                        <td class="px-3 py-2 text-right font-mono" style="color:var(--color-text-muted);">{{ $c['desde'] ? \Carbon\Carbon::parse($c['desde'])->format('Y-m-d') : '—' }}</td>
                        <td class="px-3 py-2 text-right font-mono" style="color:var(--color-text-muted);">{{ $hasta ? $hasta->format('Y-m-d H:i') : '—' }}</td>
                        <td class="px-3 py-2 text-right font-mono" style="color:var(--color-text-primary);">{{ number_format($c['total']) }}</td>
                        <td class="px-3 py-2 text-center">
                            <span class="inline-block px-2 py-0.5 rounded-full text-[10px]"
                                  style="background:{{ $estadoColor }}22; color:{{ $estadoColor }}; border:1px solid {{ $estadoColor }}44;">
                                {{ $estadoTexto }}
                            </span>
                        </td>
                        <td class="px-3 py-2 text-right">
                            <button onclick="openBackfill('{{ $c['symbol'] }}','{{ $c['interval'] }}','{{ $c['broker'] }}')"
                                    class="text-[10px] px-2 py-1 rounded border mr-1"
                                    style="background:var(--color-surface-raised); border-color:var(--color-border-soft); color:var(--color-text-primary);">
                                Backfill
                            </button>
                            <button onclick="openInvalidate('{{ $c['symbol'] }}','{{ $c['interval'] }}','{{ $c['broker'] }}')"
                                    class="text-[10px] px-2 py-1 rounded border mr-1"
                                    style="background:var(--color-surface-raised); border-color:#7F2D2D; color:#FCA5A5;">
                                Invalidar
                            </button>
                            <button onclick="openReload('{{ $c['symbol'] }}','{{ $c['interval'] }}','{{ $c['broker'] }}')"
                                    class="text-[10px] px-2 py-1 rounded border"
                                    style="background:#3F1D1D; border-color:#7F2D2D; color:#FCA5A5;">
                                Recargar
                            </button>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="8" class="px-3 py-6 text-center" style="color:var(--color-text-muted);">No hay datos aún.</td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    <div class="mt-4 rounded-lg border p-3 text-[11px]" style="background:var(--color-surface-raised); border-color:var(--color-border-soft); color:var(--color-text-muted);">
        <strong style="color:var(--color-neutral);">Acciones:</strong>
        <ul class="mt-1 space-y-1">
            <li><b>Backfill</b>: descarga un rango específico. Útil para llenar gaps.</li>
            <li><b>Invalidar</b>: borra un rango. <b style="color:#FCA5A5;">Requiere escribir CONFIRMAR.</b></li>
            <li><b>Recargar</b>: borra TODO + redescarga completa. <b style="color:#FCA5A5;">Requiere escribir CONFIRMAR.</b></li>
        </ul>
    </div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
const CSRF = '{{ csrf_token() }}';
const BASE = '{{ url("/") }}';

function openBackfill(symbol, interval, broker) {
    Swal.fire({
        title: 'Backfill',
        html: `<div style="text-align:left; font-size:13px;">
            <p style="margin-bottom:8px; color:#9CA3AF;">${symbol} / ${interval} / ${broker}</p>
            <label style="display:block; margin-bottom:4px;">Desde:</label>
            <input id="bf-start" type="date" class="swal2-input" style="width:100%; margin:0 0 8px 0;" value="2024-06-01">
            <label style="display:block; margin-bottom:4px;">Hasta (opcional):</label>
            <input id="bf-end" type="date" class="swal2-input" style="width:100%; margin:0;">
        </div>`,
        showCancelButton: true,
        confirmButtonText: 'Descargar',
        cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#3DD68C',
        cancelButtonColor: '#232B38',
        preConfirm: () => ({
            symbol, interval, broker,
            start_date: document.getElementById('bf-start').value,
            end_date: document.getElementById('bf-end').value || null,
        })
    }).then(r => {
        if (!r.isConfirmed) return;
        Swal.fire({title:'Descargando...', didOpen:()=>Swal.showLoading(), allowOutsideClick:false, background:'#11161F', color:'#E5E9F0'});
        fetch(`${BASE}/collector/backfill`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
            body: JSON.stringify(r.value)
        }).then(res=>res.json()).then(d=>{
            if(d.ok) Swal.fire({title:'✅ Backfill completo', html:`<b>${d.velas_insertadas||0}</b> velas insertadas`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            else Swal.fire({title:'Error', text:d.error||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
        });
    });
}

function openInvalidate(symbol, interval, broker) {
    Swal.fire({
        title: '⚠️ Invalidar rango',
        html: `<div style="text-align:left; font-size:13px;">
            <p style="margin-bottom:8px; color:#FCA5A5;"><b>Vas a BORRAR velas de:</b><br>${symbol} / ${interval} / ${broker}</p>
            <label style="display:block; margin-bottom:4px;">Desde (opcional):</label>
            <input id="inv-start" type="date" class="swal2-input" style="width:100%; margin:0 0 8px 0;">
            <label style="display:block; margin-bottom:4px;">Hasta (opcional):</label>
            <input id="inv-end" type="date" class="swal2-input" style="width:100%; margin:0 0 8px 0;">
            <p style="margin-top:8px; margin-bottom:4px;">Escribe <b style="color:#FCA5A5;">CONFIRMAR</b>:</p>
            <input id="inv-confirm" type="text" class="swal2-input" style="width:100%; margin:0;">
        </div>`,
        showCancelButton: true,
        confirmButtonText: 'Borrar velas',
        cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#F2545B',
        cancelButtonColor: '#232B38',
        preConfirm: () => {
            const c = document.getElementById('inv-confirm').value;
            if (c !== 'CONFIRMAR') { Swal.showValidationMessage('Escribe CONFIRMAR'); return false; }
            return {symbol, interval, broker,
                start_date: document.getElementById('inv-start').value || null,
                end_date: document.getElementById('inv-end').value || null,
                confirm: c};
        }
    }).then(r => {
        if (!r.isConfirmed) return;
        Swal.fire({title:'Borrando...', didOpen:()=>Swal.showLoading(), background:'#11161F', color:'#E5E9F0'});
        fetch(`${BASE}/collector/invalidate`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
            body: JSON.stringify(r.value)
        }).then(res=>res.json()).then(d=>{
            if(d.ok) Swal.fire({title:'✅ Borrado', html:`<b>${d.velas_borradas||0}</b> velas eliminadas`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            else Swal.fire({title:'Error', text:d.error||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
        });
    });
}

function openReload(symbol, interval, broker) {
    Swal.fire({
        title: '⚠️ Recargar completo',
        html: `<div style="text-align:left; font-size:13px;">
            <p style="margin-bottom:8px; color:#FCA5A5;"><b>Vas a BORRAR TODO y recargar:</b><br>${symbol} / ${interval} / ${broker}</p>
            <p style="margin-bottom:8px;">Puede tardar varios minutos.</p>
            <label style="display:block; margin-bottom:4px;">Escribe <b style="color:#FCA5A5;">CONFIRMAR</b>:</label>
            <input id="rl-confirm" type="text" class="swal2-input" style="width:100%; margin:0;">
        </div>`,
        showCancelButton: true,
        confirmButtonText: 'Recargar',
        cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#F2545B',
        cancelButtonColor: '#232B38',
        preConfirm: () => {
            const c = document.getElementById('rl-confirm').value;
            if (c !== 'CONFIRMAR') { Swal.showValidationMessage('Escribe CONFIRMAR'); return false; }
            return {symbol, interval, broker, confirm: c};
        }
    }).then(r => {
        if (!r.isConfirmed) return;
        Swal.fire({title:'Recargando... (puede tardar)', didOpen:()=>Swal.showLoading(), allowOutsideClick:false, background:'#11161F', color:'#E5E9F0'});
        fetch(`${BASE}/collector/reload`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
            body: JSON.stringify(r.value)
        }).then(res=>res.json()).then(d=>{
            if(d.ok) Swal.fire({title:'✅ Recarga completa', html:`<b>${d.velas_borradas||0}</b> borradas<br><b>${d.velas_descargadas||0}</b> descargadas`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            else Swal.fire({title:'Error', text:d.error||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
        });
    });
}

function openAddSymbol() {
    Swal.fire({
        title: 'Agregar símbolo',
        html: `<div style="text-align:left; font-size:13px;">
            <label style="display:block; margin-bottom:4px;">Símbolo:</label>
            <input id="as-symbol" type="text" class="swal2-input" placeholder="MATICUSDT" style="width:100%; margin:0 0 8px 0;">
            <label style="display:block; margin-bottom:4px;">Broker:</label>
            <select id="as-broker" class="swal2-input" style="width:100%; margin:0 0 8px 0;">
                <option value="bybit">Bybit</option>
                <option value="ig">IG</option>
            </select>
            <label style="display:block; margin-bottom:4px;">Intervals (coma):</label>
            <input id="as-intervals" type="text" class="swal2-input" value="1,5,15,60,120,240" style="width:100%; margin:0;">
        </div>`,
        showCancelButton: true,
        confirmButtonText: 'Agregar',
        cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0',
        confirmButtonColor: '#3DD68C',
        cancelButtonColor: '#232B38',
        preConfirm: () => {
            const sym = document.getElementById('as-symbol').value.trim().toUpperCase();
            const broker = document.getElementById('as-broker').value;
            const intervals = document.getElementById('as-intervals').value.split(',').map(s=>s.trim()).filter(s=>s);
            if (!sym || intervals.length===0) { Swal.showValidationMessage('Símbolo e intervals requeridos'); return false; }
            return {symbol: sym, broker, intervals, active: true};
        }
    }).then(r => {
        if (!r.isConfirmed) return;
        fetch(`${BASE}/collector/add-symbol`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
            body: JSON.stringify(r.value)
        }).then(()=>location.reload()).catch(e=>Swal.fire({title:'Error', text:e.message, icon:'error', background:'#11161F', color:'#E5E9F0'}));
    });
}
</script>
@endpush

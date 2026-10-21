@extends('layouts.app')

@section('title', 'Data Collector')
@section('header', 'Data Collector')

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

    @if (isset($debug) && $debug)
        <div class="rounded-lg border p-3 mb-4 text-xs font-mono" style="background:#3F1D1D; border-color:#7F2D2D; color:#FCA5A5;">
            <b>Debug:</b> {{ $debug }}
        </div>
    @endif

    @php
        $grouped = collect($rows)->groupBy(fn($r) => $r['broker'] . '|' . $r['symbol']);

        $classify = function($r) {
            if (!$r['hasta']) return 'vacio';
            if ($r['actualizado']) return 'ok';
            $hasta = \Carbon\Carbon::parse($r['hasta']);
            if ($hasta->gt(now()->subHours(2))) return 'atrasado';
            return 'congelado';
        };

        $stats = ['ok'=>0, 'atrasado'=>0, 'congelado'=>0, 'vacio'=>0];
        $activeCount = 0;
        foreach ($rows as $r) {
            $stats[$classify($r)]++;
            if ($r['active']) $activeCount++;
        }

        $estadoColor = ['ok'=>'#3DD68C', 'atrasado'=>'#F59E0B', 'congelado'=>'#F2545B', 'vacio'=>'#6B7280'];
        $estadoIcon  = ['ok'=>'✓', 'atrasado'=>'⚠', 'congelado'=>'❄', 'vacio'=>'—'];
    @endphp

    <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2 text-[11px]" style="color:var(--color-text-muted);">
            <span><b style="color:var(--color-text-primary);">{{ $grouped->count() }}</b> símbolos</span>
            <span>·</span>
            <span><b style="color:var(--color-text-primary);">{{ $activeCount }}/{{ count($rows) }}</b> intervals activos</span>
            <span>·</span>
            <span style="color:#3DD68C;"><b>{{ $stats['ok'] }}</b> ok</span>
            <span style="color:#F59E0B;"><b>{{ $stats['atrasado'] }}</b> atras.</span>
            <span style="color:#F2545B;"><b>{{ $stats['congelado'] }}</b> cong.</span>
        </div>
        <button onclick="openAddSymbol()"
                class="text-[10px] px-2.5 py-1 rounded border"
                style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            + Símbolo
        </button>
    </div>

    <div class="flex gap-1 mb-3">
        <button onclick="filterState('all')" data-filter="all" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">Todos</button>
        <button onclick="filterState('ok')" data-filter="ok" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#3DD68C44; color:#3DD68C;">✓ Ok</button>
        <button onclick="filterState('atrasado')" data-filter="atrasado" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#F59E0B44; color:#F59E0B;">⚠ Atrasados</button>
        <button onclick="filterState('congelado')" data-filter="congelado" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#F2545B44; color:#F2545B;">❄ Congelados</button>
    </div>

    <div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <table class="w-full text-[11px]">
            <thead>
                <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                    <th class="text-left px-2.5 py-1.5 font-medium" style="width:70px;">Broker</th>
                    <th class="text-left px-2.5 py-1.5 font-medium" style="width:100px;">Símbolo</th>
                    <th class="text-center px-2.5 py-1.5 font-medium" style="width:100px;">Recolecta</th>
                    <th class="text-left px-2.5 py-1.5 font-medium">Intervals</th>
                </tr>
            </thead>
            <tbody>
                @forelse ($grouped as $key => $groupRows)
                    @php
                        [$broker, $symbol] = explode('|', $key, 2);
                        $sortedRows = $groupRows->sortBy(fn($r) => is_numeric($r['interval']) ? (int)$r['interval'] : 9999);
                        $allActive = $groupRows->every('active', true);
                        $anyActive = $groupRows->contains('active', true);
                    @endphp
                    <tr class="group-row border-t" style="border-color:var(--color-border-soft);" data-symbol="{{ $symbol }}">
                        <td class="px-2.5 py-1.5 font-mono" style="color:var(--color-text-muted);">{{ $broker }}</td>
                        <td class="px-2.5 py-1.5 font-medium" style="color:var(--color-text-primary);">{{ $symbol }}</td>
                        <td class="px-2.5 py-1.5 text-center">
                            <form method="POST" action="{{ route('collector.toggle-all', [$broker, $symbol]) }}" style="display:inline;">
                                @csrf
                                <input type="hidden" name="active" value="{{ $allActive ? '0' : '1' }}">
                                <button type="submit" class="text-[10px] px-2 py-0.5 rounded-full border transition-colors"
                                        style="background:{{ $allActive ? '#16331F' : 'var(--color-surface-raised)' }}; border-color:{{ $allActive ? '#1E4A2E' : 'var(--color-border-strong)' }}; color:{{ $allActive ? 'var(--color-profit)' : 'var(--color-text-muted)' }};">
                                    {{ $allActive ? '✓ On' : ($anyActive ? '◐ Parcial' : '✗ Off') }}
                                </button>
                            </form>
                        </td>
                        <td class="px-2.5 py-1.5">
                            <div class="flex flex-wrap gap-1">
                                @foreach ($sortedRows as $r)
                                    @php
                                        $estado = $classify($r);
                                        $color = $estadoColor[$estado];
                                        $icon = $estadoIcon[$estado];
                                        $filasCorto = $r['total'] >= 1000 ? round($r['total']/1000, 1) . 'k' : number_format($r['total']);
                                        $hastaStr = $r['hasta'] ? \Carbon\Carbon::parse($r['hasta'])->format('Y-m-d H:i') : '—';
                                        $desdeStr = $r['desde'] ? \Carbon\Carbon::parse($r['desde'])->format('Y-m-d') : '—';
                                        $activeIcon = $r['active'] ? '' : '⏸ ';
                                    @endphp
                                    <button type="button"
                                            class="chip text-[10px] px-1.5 py-0.5 rounded font-mono transition-all hover:scale-105"
                                            data-estado="{{ $estado }}"
                                            style="background:{{ $color }}{{ $r['active'] ? '18' : '0A' }}; border:1px solid {{ $color }}{{ $r['active'] ? '55' : '22' }}; color:{{ $color }}; {{ $r['active'] ? '' : 'opacity:0.55;' }} min-width:72px; text-align:left;"
                                            onclick="openActions('{{ $symbol }}','{{ $r['interval'] }}','{{ $broker }}',{{ $r['total'] }},'{{ $desdeStr }}','{{ $hastaStr }}','{{ $estado }}',{{ $r['active'] ? 'true' : 'false' }})"
                                            title="{{ $symbol }} / {{ $r['interval'] }} — {{ $r['active'] ? 'activo' : 'inactivo' }} · {{ number_format($r['total']) }} velas">
                                        {{ $activeIcon }}{{ $r['interval'] }} {{ $icon }} {{ $filasCorto }}
                                    </button>
                                @endforeach
                            </div>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="4" class="px-3 py-6 text-center" style="color:var(--color-text-muted);">
                            No hay símbolos. Usa "+ Símbolo" para empezar.
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    <div class="mt-3 flex flex-wrap gap-3 text-[10px]" style="color:var(--color-text-muted);">
        <span><b style="color:#3DD68C;">✓</b> Actualizado</span>
        <span><b style="color:#F59E0B;">⚠</b> Atrasado</span>
        <span><b style="color:#F2545B;">❄</b> Congelado</span>
        <span><b>⏸</b> Recolección pausada</span>
        <span class="ml-auto">Click en chip para acciones</span>
    </div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
const CSRF = '{{ csrf_token() }}';
const BASE = '{{ url("/") }}';
const COLORS = { ok:'#3DD68C', atrasado:'#F59E0B', congelado:'#F2545B', vacio:'#6B7280' };
const ICONS = { ok:'✓', atrasado:'⚠', congelado:'❄', vacio:'—' };

function filterState(state) {
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.style.background = b.dataset.filter === state ? 'var(--color-surface-raised)' : 'transparent';
    });
    document.querySelectorAll('.chip').forEach(chip => {
        chip.style.display = (state === 'all' || chip.dataset.estado === state) ? '' : 'none';
    });
    document.querySelectorAll('.group-row').forEach(row => {
        const visible = row.querySelectorAll('.chip:not([style*="display: none"])');
        row.style.display = visible.length > 0 ? '' : 'none';
    });
}

function openActions(symbol, interval, broker, total, desde, hasta, estado, active) {
    const color = COLORS[estado] || '#6B7280';
    const icon = ICONS[estado] || '—';
    const estadoLabel = { ok:'Actualizado', atrasado:'Atrasado', congelado:'Congelado', vacio:'Vacío' }[estado] || estado;
    const toggleLabel = active ? '⏸ Desactivar recolección' : '▶ Activar recolección';
    const toggleColor = active ? '#F59E0B' : '#3DD68C';
    const toggleBg = active ? '#3F2D1D' : '#16331F';
    const toggleBorder = active ? '#7F5D2D' : '#1E4A2E';

    Swal.fire({
        title: `${symbol} / ${interval}`,
        html: `
            <div style="text-align:left; font-size:12px;">
                <div style="margin-bottom:12px; padding:10px; border-radius:6px; background:${color}10; border:1px solid ${color}44;">
                    <div style="color:${color}; font-weight:600; margin-bottom:4px;">${icon} ${estadoLabel} ${active ? '' : '· ⏸ pausado'}</div>
                    <div style="color:#9CA3AF; font-size:11px; line-height:1.6;">
                        Broker: <b style="color:#E5E9F0;">${broker}</b><br>
                        Velas: <b style="color:#E5E9F0;">${total.toLocaleString()}</b><br>
                        Desde: ${desde} · Hasta: ${hasta}
                    </div>
                </div>
                <div style="display:flex; flex-direction:column; gap:6px;">
                    <button onclick="toggleChip('${symbol}','${interval}','${broker}',${!active})" class="swal2-styled" style="background:${toggleBg}; color:${toggleColor}; border:1px solid ${toggleBorder}; margin:0; width:100%;">
                        ${toggleLabel}
                    </button>
                    <button onclick="doBackfill('${symbol}','${interval}','${broker}')" class="swal2-styled" style="background:#16331F; color:#3DD68C; border:1px solid #1E4A2E; margin:0;">
                        📥 Backfill (rango)
                    </button>
                    <button onclick="doInvalidate('${symbol}','${interval}','${broker}')" class="swal2-styled" style="background:#3F1D1D; color:#FCA5A5; border:1px solid #7F2D2D; margin:0;">
                        🗑 Invalidar rango
                    </button>
                    <button onclick="doReload('${symbol}','${interval}','${broker}')" class="swal2-styled" style="background:#3F1D1D; color:#FCA5A5; border:1px solid #7F2D2D; margin:0;">
                        🔄 Recargar completo
                    </button>
                </div>
            </div>
        `,
        showConfirmButton: false, showCloseButton: true,
        background: '#11161F', color: '#E5E9F0', width: 380,
    });
}

function toggleChip(symbol, interval, broker, newActive) {
    Swal.fire({title:'Aplicando...', didOpen:()=>Swal.showLoading(), allowOutsideClick:false, background:'#11161F', color:'#E5E9F0'});
    fetch(`${BASE}/collector/toggle-one`, {
        method:'POST',
        headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
        body: JSON.stringify({broker, symbol, interval, active: newActive})
    }).then(res=>res.json()).then(d=>{
        if (d.ok) location.reload();
        else Swal.fire({title:'Error', text:d.error||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
    }).catch(e => Swal.fire({title:'Error', text:e.message, icon:'error', background:'#11161F', color:'#E5E9F0'}));
}

function doBackfill(symbol, interval, broker) {
    Swal.fire({
        title: 'Backfill',
        html: `<div style="text-align:left; font-size:12px;">
            <p style="margin-bottom:8px; color:#9CA3AF;">${symbol} / ${interval} / ${broker}</p>
            <label style="display:block; margin-bottom:4px; font-size:11px;">Desde:</label>
            <input id="bf-start" type="date" class="swal2-input" style="width:100%; margin:0 0 8px 0; font-size:12px;" value="2024-06-01">
            <label style="display:block; margin-bottom:4px; font-size:11px;">Hasta (opcional):</label>
            <input id="bf-end" type="date" class="swal2-input" style="width:100%; margin:0; font-size:12px;">
        </div>`,
        showCancelButton: true, confirmButtonText: 'Descargar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0', width: 380,
        confirmButtonColor: '#3DD68C', cancelButtonColor: '#232B38',
        preConfirm: () => ({ symbol, interval, broker,
            start_date: document.getElementById('bf-start').value,
            end_date: document.getElementById('bf-end').value || null })
    }).then(r => {
        if (!r.isConfirmed) return;
        Swal.fire({title:'Descargando...', didOpen:()=>Swal.showLoading(), allowOutsideClick:false, background:'#11161F', color:'#E5E9F0'});
        fetch(`${BASE}/collector/backfill`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
            body: JSON.stringify(r.value)
        }).then(res=>res.json()).then(d=>{
            if(d.ok) Swal.fire({title:'✅ Backfill completo', html:`<b>${(d.velas_insertadas||0).toLocaleString()}</b> velas`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            else Swal.fire({title:'Error', text:d.error||d.detail||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
        });
    });
}

function doInvalidate(symbol, interval, broker) {
    Swal.fire({
        title: '⚠️ Invalidar rango',
        html: `<div style="text-align:left; font-size:12px;">
            <p style="margin-bottom:8px; color:#FCA5A5;"><b>Vas a borrar:</b> ${symbol} / ${interval} / ${broker}</p>
            <label style="display:block; margin-bottom:4px; font-size:11px;">Desde (opcional):</label>
            <input id="inv-start" type="date" class="swal2-input" style="width:100%; margin:0 0 8px 0; font-size:12px;">
            <label style="display:block; margin-bottom:4px; font-size:11px;">Hasta (opcional):</label>
            <input id="inv-end" type="date" class="swal2-input" style="width:100%; margin:0 0 8px 0; font-size:12px;">
            <p style="margin-top:8px; margin-bottom:4px; font-size:11px;">Escribe <b style="color:#FCA5A5;">CONFIRMAR</b>:</p>
            <input id="inv-confirm" type="text" class="swal2-input" style="width:100%; margin:0; font-size:12px;">
        </div>`,
        showCancelButton: true, confirmButtonText: 'Borrar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0', width: 380,
        confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
        preConfirm: () => {
            const c = document.getElementById('inv-confirm').value;
            if (c !== 'CONFIRMAR') { Swal.showValidationMessage('Escribe CONFIRMAR'); return false; }
            return {symbol, interval, broker,
                start_date: document.getElementById('inv-start').value || null,
                end_date: document.getElementById('inv-end').value || null, confirm: c};
        }
    }).then(r => {
        if (!r.isConfirmed) return;
        Swal.fire({title:'Borrando...', didOpen:()=>Swal.showLoading(), background:'#11161F', color:'#E5E9F0'});
        fetch(`${BASE}/collector/invalidate`, {
            method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'},
            body: JSON.stringify(r.value)
        }).then(res=>res.json()).then(d=>{
            if(d.ok) Swal.fire({title:'✅ Borrado', html:`<b>${(d.velas_borradas||0).toLocaleString()}</b> velas`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            else Swal.fire({title:'Error', text:d.error||d.detail||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
        });
    });
}

function doReload(symbol, interval, broker) {
    Swal.fire({
        title: '⚠️ Recargar completo',
        html: `<div style="text-align:left; font-size:12px;">
            <p style="margin-bottom:8px; color:#FCA5A5;"><b>Borrar TODO + redescargar:</b><br>${symbol} / ${interval} / ${broker}</p>
            <label style="display:block; margin-bottom:4px; font-size:11px;">Escribe <b style="color:#FCA5A5;">CONFIRMAR</b>:</label>
            <input id="rl-confirm" type="text" class="swal2-input" style="width:100%; margin:0; font-size:12px;">
        </div>`,
        showCancelButton: true, confirmButtonText: 'Recargar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0', width: 380,
        confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
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
            if(d.ok) Swal.fire({title:'✅ Recarga completa', html:`<b>${(d.velas_borradas||0).toLocaleString()}</b> borradas<br><b>${(d.velas_descargadas||0).toLocaleString()}</b> descargadas`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            else Swal.fire({title:'Error', text:d.error||d.detail||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'});
        });
    });
}

function openAddSymbol() {
    Swal.fire({
        title: 'Agregar símbolo',
        html: `<div style="text-align:left; font-size:12px;">
            <label style="display:block; margin-bottom:4px; font-size:11px;">Símbolo:</label>
            <input id="as-symbol" type="text" class="swal2-input" placeholder="MATICUSDT" style="width:100%; margin:0 0 8px 0; font-size:12px;">
            <label style="display:block; margin-bottom:4px; font-size:11px;">Broker:</label>
            <select id="as-broker" class="swal2-input" style="width:100%; margin:0 0 8px 0; font-size:12px;">
                <option value="bybit">Bybit</option>
                <option value="ig">IG</option>
            </select>
            <label style="display:block; margin-bottom:4px; font-size:11px;">Intervals (coma):</label>
            <input id="as-intervals" type="text" class="swal2-input" value="1,5,15,60,120,240" style="width:100%; margin:0; font-size:12px;">
        </div>`,
        showCancelButton: true, confirmButtonText: 'Agregar', cancelButtonText: 'Cancelar',
        background: '#11161F', color: '#E5E9F0', width: 380,
        confirmButtonColor: '#3DD68C', cancelButtonColor: '#232B38',
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
        }).then(res => res.json()).then(d => {
            if (d.inserted > 0) {
                Swal.fire({title:'✅ Agregado', html:`<b>${d.inserted}</b> intervalo(s)`, icon:'success', background:'#11161F', color:'#E5E9F0'}).then(()=>location.reload());
            } else {
                Swal.fire({title:'Sin cambios', text:'El símbolo ya existía', icon:'info', background:'#11161F', color:'#E5E9F0'});
            }
        });
    });
}
</script>
@endpush

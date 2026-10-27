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

        // Estado calculado por el motor con la regla por intervalo (ok ≤ 1 vela + 2 min; atrasado ≤ 3 velas)
        $stats = ['ok'=>0, 'atrasado'=>0, 'detenido'=>0, 'vacio'=>0];
        $activeCount = 0;
        foreach ($rows as $r) {
            $stats[$r['estado'] ?? 'vacio'] = ($stats[$r['estado'] ?? 'vacio'] ?? 0) + 1;
            if ($r['active']) $activeCount++;
        }

        $estadoColor = ['ok'=>'#3DD68C', 'atrasado'=>'#F59E0B', 'detenido'=>'#F2545B', 'vacio'=>'#6B7280'];
        $estadoIcon  = ['ok'=>'✓', 'atrasado'=>'⚠', 'detenido'=>'❄', 'vacio'=>'—'];
        $ivLabel = ['1'=>'1m', '5'=>'5m', '15'=>'15m', '60'=>'1h', '120'=>'2h', '240'=>'4h', 'D'=>'1D'];
        $fmtLag = function ($s) {
            if ($s === null) return '—';
            if ($s < 60) return $s . ' s';
            if ($s < 5400) return round($s / 60) . ' min';
            if ($s < 172800) return round($s / 3600, 1) . ' h';
            return round($s / 86400, 1) . ' d';
        };

        // Última validación contra Bybit (botón "Validar ahora")
        $valBySeries = collect($validation['series'] ?? [])->keyBy(fn ($s) => $s['symbol'] . '|' . $s['interval']);
        $vs = $validation['summary'] ?? null;
        $valAt = isset($validation['at']) ? \Carbon\Carbon::parse($validation['at']) : null;
        $runAt = isset($lastRun['at']) ? \Carbon\Carbon::parse($lastRun['at']) : null;
        $runStale = ! $runAt || $runAt->lt(now()->subMinutes(3));
        $runOk = $lastRun && ($lastRun['ok'] ?? false) && ! $runStale;
    @endphp

    <style>
        .dc-health { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px; }
        .dc-card { background:var(--color-surface); border:1px solid var(--color-border-soft); border-radius:10px; padding:12px 14px; }
        .dc-card h3 { margin:0 0 8px; font-size:11px; font-weight:600; color:var(--color-text-secondary); text-transform:uppercase; letter-spacing:.04em;
                      display:flex; justify-content:space-between; align-items:center; gap:8px; }
        .dc-big { font-size:15px; font-weight:600; }
        .dc-sub { display:block; font-size:10px; color:var(--color-text-muted); font-weight:400; }
        .dc-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:8px; }
        .dc-grid span { display:block; font-size:10px; color:var(--color-text-muted); }
        .dc-grid b { font-size:14px; }
        .dc-ok { color:var(--color-profit); } .dc-warn { color:#F59E0B; } .dc-bad { color:var(--color-loss); }
        .dc-btn { border:0; border-radius:6px; padding:5px 11px; font-size:11px; font-weight:500; color:#fff; background:#8B5CF6; cursor:pointer; text-transform:none; letter-spacing:0; }
        .dc-btn[disabled] { opacity:.5; cursor:wait; }
        .dc-lag { opacity:.75; }
        @media (max-width: 760px) { .dc-health { grid-template-columns:1fr; } .dc-grid { grid-template-columns:repeat(2,1fr); } }
    </style>

    <div class="dc-health">
        <div class="dc-card">
            <h3>Última corrida del collector</h3>
            @if (! $lastRun)
                <div class="dc-big dc-warn">Sin registro todavía</div>
                <span class="dc-sub">Aparece tras la próxima corrida (cada minuto).</span>
            @else
                <div class="dc-big {{ $runOk ? 'dc-ok' : 'dc-bad' }}">
                    {{ $runOk ? '✓' : '✗' }} {{ $runAt?->diffForHumans() }} · {{ $lastRun['duration_s'] ?? '—' }} s
                </div>
                <span class="dc-sub">
                    cada minuto · varias series en paralelo · nunca dos corridas a la vez
                    @if ($runStale) · <b class="dc-bad">el collector no corre hace más de 3 min</b> @endif
                </span>
                <div class="dc-grid">
                    <div><span>Series</span><b>{{ ($lastRun['series'] ?? 0) - ($lastRun['failed'] ?? 0) }}/{{ $lastRun['series'] ?? 0 }}</b></div>
                    <div><span>Fallas</span><b class="{{ ($lastRun['failed'] ?? 0) ? 'dc-bad' : 'dc-ok' }}">{{ $lastRun['failed'] ?? 0 }}</b></div>
                    <div><span>Velas escritas</span><b>{{ number_format($lastRun['saved'] ?? 0) }}</b></div>
                    <div><span>Al día</span><b class="dc-ok">{{ $stats['ok'] }}</b>
                        @if ($stats['atrasado'] + $stats['detenido']) <span class="dc-warn" style="display:inline">· {{ $stats['atrasado'] + $stats['detenido'] }} no</span> @endif
                    </div>
                </div>
                @if (! empty($lastRun['errors']))
                    <div class="dc-sub dc-bad" style="margin-top:6px">
                        @foreach (array_slice($lastRun['errors'], 0, 3, true) as $k => $e) {{ $k }}: {{ \Illuminate\Support\Str::limit($e, 90) }}<br> @endforeach
                    </div>
                @endif
            @endif
        </div>

        <div class="dc-card">
            <h3>Validación contra Bybit
                <button type="button" class="dc-btn" id="dcValidate" onclick="validateNow()" @if ($validating) disabled @endif>
                    {{ $validating ? '⏳ Validando…' : '🔍 Validar ahora' }}
                </button>
            </h3>
            @if (! $vs)
                <div class="dc-big dc-warn">Sin validar todavía</div>
                <span class="dc-sub">Compara las últimas 300 velas cerradas de cada serie con Bybit y revisa huecos en todo el historial · ≈ 1-2 min.</span>
            @else
                @php $allOk = $vs['ok'] === $vs['series']; @endphp
                <div class="dc-big {{ $allOk ? 'dc-ok' : 'dc-bad' }}">
                    {{ $allOk ? '✓' : '✗' }} {{ $vs['identical'] }}/{{ $vs['series'] }} idénticas a Bybit
                    @if (! $allOk) · {{ $vs['series'] - $vs['ok'] }} con fallas @endif
                </div>
                <span class="dc-sub">última: {{ $valAt?->diffForHumans() }} · últimas {{ $validation['n_recent'] ?? 300 }} velas cerradas por serie + historial completo · tardó {{ $validation['duration_s'] ?? '—' }} s</span>
                <div class="dc-grid">
                    <div><span>Distintas</span><b class="{{ $vs['diff_recent'] ? 'dc-bad' : 'dc-ok' }}">{{ $vs['diff_recent'] }}</b></div>
                    <div><span>Faltantes recientes</span><b class="{{ $vs['missing_recent'] ? 'dc-bad' : 'dc-ok' }}">{{ $vs['missing_recent'] }}</b></div>
                    <div><span>Huecos (historial)</span><b class="{{ $vs['missing_hist'] ? 'dc-bad' : 'dc-ok' }}">{{ number_format($vs['missing_hist']) }}</b></div>
                    <div><span>Desalineadas</span><b class="{{ $vs['misaligned'] ? 'dc-bad' : 'dc-ok' }}">{{ $vs['misaligned'] }}</b></div>
                </div>
            @endif
            @if ($validationError)
                <div class="dc-sub dc-bad" style="margin-top:6px">La última validación falló: {{ \Illuminate\Support\Str::limit($validationError, 160) }}</div>
            @endif
        </div>
    </div>

    <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2 text-[11px]" style="color:var(--color-text-muted);">
            <span><b style="color:var(--color-text-primary);">{{ $grouped->count() }}</b> símbolos</span>
            <span>·</span>
            <span><b style="color:var(--color-text-primary);">{{ $activeCount }}/{{ count($rows) }}</b> intervalos activos</span>
            <span>·</span>
            <span style="color:#3DD68C;"><b>{{ $stats['ok'] }}</b> al día</span>
            <span style="color:#F59E0B;"><b>{{ $stats['atrasado'] }}</b> atras.</span>
            <span style="color:#F2545B;"><b>{{ $stats['detenido'] }}</b> deten.</span>
        </div>
        <button onclick="openAddSymbol()"
                class="text-[10px] px-2.5 py-1 rounded border"
                style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            + Símbolo
        </button>
    </div>

    <div class="flex gap-1 mb-3 flex-wrap">
        <button onclick="filterState('all')" data-filter="all" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">Todos</button>
        <button onclick="filterState('ok')" data-filter="ok" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#3DD68C44; color:#3DD68C;">✓ Al día</button>
        <button onclick="filterState('atrasado')" data-filter="atrasado" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#F59E0B44; color:#F59E0B;">⚠ Atrasados</button>
        <button onclick="filterState('detenido')" data-filter="detenido" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#F2545B44; color:#F2545B;">❄ Detenidos</button>
        <button onclick="filterState('distinto')" data-filter="distinto" class="filter-btn text-[10px] px-2 py-0.5 rounded border" style="background:transparent; border-color:#F2545B44; color:#F2545B;">≠ Con fallas en la validación</button>
    </div>

    <div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="overflow-x-auto">
        <table class="w-full text-[11px]" style="min-width:860px;">
            <thead>
                <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                    <th class="text-left px-2.5 py-1.5 font-medium" style="width:70px;">Broker</th>
                    <th class="text-left px-2.5 py-1.5 font-medium" style="width:120px;">Símbolo</th>
                    <th class="text-center px-2.5 py-1.5 font-medium" style="width:90px;">Recolecta</th>
                    <th class="text-left px-2.5 py-1.5 font-medium">Intervalos · atraso de la última vela</th>
                    <th class="text-left px-2.5 py-1.5 font-medium" style="width:170px;">Historial (última validación)</th>
                </tr>
            </thead>
            <tbody>
                @forelse ($grouped as $key => $groupRows)
                    @php
                        [$broker, $symbol] = explode('|', $key, 2);
                        $sortedRows = $groupRows->sortBy(fn($r) => is_numeric($r['interval']) ? (int)$r['interval'] : 9999);
                        $allActive = $groupRows->every('active', true);
                        $anyActive = $groupRows->contains('active', true);
                        $desdeSym = $groupRows->pluck('desde')->filter()->min();
                        $symVal = $groupRows->map(fn ($r) => $valBySeries->get($r['symbol'] . '|' . $r['interval']))->filter();
                        $symBad = $symVal->reject(fn ($v) => $v['ok']);
                        $symHoles = $symVal->sum(fn ($v) => (int) ($v['missing_hist'] ?? 0));
                    @endphp
                    <tr class="group-row border-t" style="border-color:var(--color-border-soft);" data-symbol="{{ $symbol }}">
                        <td class="px-2.5 py-1.5 font-mono" style="color:var(--color-text-muted);">{{ $broker }}</td>
                        <td class="px-2.5 py-1.5" style="color:var(--color-text-primary);">
                            <span class="font-medium">{{ $symbol }}</span>
                            <span class="dc-sub">desde {{ $desdeSym ? \Carbon\Carbon::parse($desdeSym)->format('Y-m-d') : '—' }}</span>
                        </td>
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
                                        $estado = $r['estado'] ?? 'vacio';
                                        $v = $valBySeries->get($r['symbol'] . '|' . $r['interval']);
                                        $distinto = $v && ! $v['ok'];
                                        $color = $distinto ? '#F2545B' : $estadoColor[$estado];
                                        $icon = $distinto ? '≠' : $estadoIcon[$estado];
                                        $hastaStr = $r['hasta'] ? \Carbon\Carbon::parse($r['hasta'])->format('Y-m-d H:i') : '—';
                                        $desdeStr = $r['desde'] ? \Carbon\Carbon::parse($r['desde'])->format('Y-m-d') : '—';
                                        $activeIcon = $r['active'] ? '' : '⏸ ';
                                        $label = $ivLabel[$r['interval']] ?? $r['interval'];
                                        $valTxt = $v ? ($v['ok'] ? 'igual a Bybit, sin huecos'
                                            : trim(($v['diff_recent'] ?? 0 ? $v['diff_recent'] . ' distintas · ' : '') . (($v['missing_recent'] ?? 0) ? $v['missing_recent'] . ' faltan · ' : '')
                                              . (($v['missing_hist'] ?? 0) ? $v['missing_hist'] . ' huecos · ' : '') . (($v['misaligned'] ?? 0) ? $v['misaligned'] . ' fuera de horario · ' : '')
                                              . ($v['error'] ?? ''), ' ·')) : 'sin validar';
                                    @endphp
                                    <button type="button"
                                            class="chip text-[10px] px-1.5 py-0.5 rounded font-mono transition-all hover:scale-105"
                                            data-estado="{{ $estado }}" data-distinto="{{ $distinto ? '1' : '0' }}"
                                            style="background:{{ $color }}{{ $r['active'] ? '18' : '0A' }}; border:1px solid {{ $color }}{{ $r['active'] ? '55' : '22' }}; color:{{ $color }}; {{ $r['active'] ? '' : 'opacity:0.55;' }} min-width:84px; text-align:left;"
                                            onclick="openActions(@js($symbol), @js($r['interval']), @js($broker), @js($desdeStr), @js($hastaStr), @js($estado), {{ $r['active'] ? 'true' : 'false' }}, @js($fmtLag($r['lag_s'])), @js($valTxt))"
                                            title="{{ $symbol }} / {{ $label }} — {{ $r['active'] ? 'activo' : 'pausado' }} · atraso {{ $fmtLag($r['lag_s']) }} · {{ $valTxt }}">
                                        {{ $activeIcon }}<b>{{ $label }}</b> {{ $icon }} <span class="dc-lag">{{ $fmtLag($r['lag_s']) }}</span>
                                    </button>
                                @endforeach
                            </div>
                        </td>
                        <td class="px-2.5 py-1.5" style="white-space:nowrap;">
                            @if ($symVal->isEmpty())
                                <span style="color:var(--color-text-muted);">sin validar</span>
                            @elseif ($symBad->isEmpty())
                                <span class="dc-ok">✓ igual a Bybit · 0 huecos</span>
                            @else
                                <span class="dc-bad">✗ {{ $symBad->count() }} intervalo(s) con fallas{{ $symHoles ? ' · ' . number_format($symHoles) . ' huecos' : '' }}</span>
                            @endif
                            <span class="dc-sub">{{ $valAt ? 'validado ' . $valAt->diffForHumans() : 'pulsa "Validar ahora"' }}</span>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="5" class="px-3 py-6 text-center" style="color:var(--color-text-muted);">
                            No hay símbolos. Usa "+ Símbolo" para empezar.
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>
        </div>
    </div>

    <div class="mt-3 flex flex-wrap gap-3 text-[10px]" style="color:var(--color-text-muted);">
        <span><b style="color:#3DD68C;">✓</b> Al día (atraso ≤ 1 vela + 2 min)</span>
        <span><b style="color:#F59E0B;">⚠</b> Atrasado (hasta 3 velas)</span>
        <span><b style="color:#F2545B;">❄</b> Detenido</span>
        <span><b style="color:#F2545B;">≠</b> Con fallas en la última validación</span>
        <span><b>⏸</b> Recolección pausada</span>
        <span class="ml-auto">Click en chip para acciones</span>
    </div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
const CSRF = '{{ csrf_token() }}';
const BASE = '{{ url("/") }}';
const COLORS = { ok:'#3DD68C', atrasado:'#F59E0B', detenido:'#F2545B', vacio:'#6B7280' };
const ICONS = { ok:'✓', atrasado:'⚠', detenido:'❄', vacio:'—' };
const VALIDATE_URL = @json(route('collector.validate'));
const VALIDATION_STATUS_URL = @json(route('collector.validation-status'));

function filterState(state) {
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.style.background = b.dataset.filter === state ? 'var(--color-surface-raised)' : 'transparent';
    });
    document.querySelectorAll('.chip').forEach(chip => {
        const show = state === 'all' || (state === 'distinto' ? chip.dataset.distinto === '1' : chip.dataset.estado === state);
        chip.style.display = show ? '' : 'none';
    });
    document.querySelectorAll('.group-row').forEach(row => {
        const visible = row.querySelectorAll('.chip:not([style*="display: none"])');
        row.style.display = visible.length > 0 ? '' : 'none';
    });
}

function openActions(symbol, interval, broker, desde, hasta, estado, active, lag, validacion) {
    const color = COLORS[estado] || '#6B7280';
    const icon = ICONS[estado] || '—';
    const estadoLabel = { ok:'Al día', atrasado:'Atrasado', detenido:'Detenido', vacio:'Vacío' }[estado] || estado;
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
                        Atraso de la última vela: <b style="color:#E5E9F0;">${lag}</b><br>
                        Última validación: <b style="color:#E5E9F0;">${validacion}</b><br>
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

function validateNow() {
    const btn = document.getElementById('dcValidate');
    btn.disabled = true; btn.textContent = '⏳ Validando…';
    fetch(VALIDATE_URL, { method:'POST', headers:{'Content-Type':'application/json','X-CSRF-TOKEN':CSRF,'Accept':'application/json'} })
        .then(res => res.json()).then(d => {
            if (!d.ok) { btn.disabled = false; btn.textContent = '🔍 Validar ahora';
                return Swal.fire({title:'No se pudo validar', text:d.error||'Error', icon:'error', background:'#11161F', color:'#E5E9F0'}); }
            pollValidation(d.since);
        }).catch(e => { btn.disabled = false; btn.textContent = '🔍 Validar ahora'; });
}

function pollValidation(since) {
    fetch(VALIDATION_STATUS_URL, { headers:{'Accept':'application/json'} }).then(r => r.json()).then(d => {
        if (d.running) return setTimeout(() => pollValidation(since), 5000);
        location.reload();   // terminó: la página muestra el resultado nuevo
    }).catch(() => setTimeout(() => pollValidation(since), 10000));
}
@if ($validating)
document.addEventListener('DOMContentLoaded', () => pollValidation(null));
@endif

function openAddSymbol() {
    Swal.fire({
        title: 'Agregar símbolo',
        html: `<div style="text-align:left; font-size:12px;">
            <label style="display:block; margin-bottom:4px; font-size:11px;">Símbolo:</label>
            <input id="as-symbol" type="text" class="swal2-input" placeholder="MATICUSDT" style="width:100%; margin:0 0 8px 0; font-size:12px;">
            <label style="display:block; margin-bottom:4px; font-size:11px;">Broker:</label>
            <select id="as-broker" class="swal2-input" style="width:100%; margin:0 0 8px 0; font-size:12px;">
                <option value="bybit">Bybit</option>
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

@extends('layouts.app')
@section('title', 'Búsqueda de configuración')
@section('header', 'Estrategias y Backtesting')

@section('content')
@include('param-search._styles')
@include('param-search._helpers')

<div class="flex flex-wrap justify-between items-end gap-3 mb-3">
    <div>
        <h2 style="margin:0;font-size:18px;font-weight:600;color:var(--color-text-primary)">
            Búsqueda · {{ $run->strategy?->name ?? 'Estrategia eliminada' }} · <span id="sbIvs"></span>
        </h2>
        <p id="sbMeta" class="sb-muted" style="margin:3px 0 0;font-size:12px"></p>
        <p id="sbSyms" style="margin:4px 0 0;font-size:12px;color:var(--color-text-secondary)"></p>
    </div>
    <a href="{{ route('strategies.index') }}" class="sb-btn gray">← Volver a Estrategias</a>
</div>

<div id="sbOutdated" class="sb-alert warn mb-3" style="display:none">
    ⚠️ La estrategia cambió después de esta búsqueda: sus resultados ya no describen el código actual. Vuelve a buscar antes de crear backtests.
</div>

{{-- En curso --}}
<div id="sbRunning" class="sb-card" style="display:none;padding:18px;max-width:680px">
    <div class="flex justify-between gap-3 flex-wrap">
        <div><b style="font-size:15px" id="sbRunTitle"></b><span class="sb-sub" id="sbRunSub"></span></div>
        <span class="sb-badge run" id="sbRunBadge">En cola</span>
    </div>
    <div class="sb-bar"><i id="sbBar"></i></div>
    <div class="flex justify-between sb-muted" style="font-size:11px"><span id="sbProg"></span><span id="sbEta"></span></div>
    <div class="sb-steps" id="sbSteps"></div>
    <div class="flex justify-between items-center gap-3 mt-4 flex-wrap">
        <span class="sb-muted" style="font-size:11px">Corre con prioridad baja: no afecta a Paper ni a Real. Puedes cerrar esta página y volver.</span>
        <button type="button" class="sb-btn red" id="sbCancel" onclick="sbCancel()">Cancelar búsqueda</button>
    </div>
</div>

{{-- Terminada con error o cancelada --}}
<div id="sbFailed" class="sb-alert err" style="display:none;max-width:680px"></div>

{{-- Resultados --}}
<div id="sbResults" style="display:none">
    <div class="sb-kpis mb-3" id="sbKpis"></div>
    <div class="sb-alert warn mb-3">⚠️ Solo se pueden crear las <b>robustas validadas</b>. Las que ganan en muestra pero pierden fuera de muestra se muestran
        atenuadas: son las que más se parecen a "ganó en el pasado por casualidad". Las estrellas se calculan igual que en el historial, sobre todo el
        periodo y las monedas elegidas abajo.</div>
    <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
        <div class="sb-coins" id="sbFilter"></div>
        <span class="sb-muted" style="font-size:11px">Orden: <b style="color:#C4B5FD">Retorno total ↓</b> · luego estrellas · luego consistencia</span>
    </div>
    <div id="sbEmpty" class="sb-alert info" style="display:none"></div>
    <div class="sb-card sb-table" style="overflow:hidden"><div style="overflow-x:auto">
        <table class="sb-rs">
            <thead><tr>
                <th style="width:30px"></th><th>Estrellas</th><th>Configuración</th>
                <th class="r">PF en muestra</th><th class="r">PF fuera</th><th class="r">PF total · <span style="color:#C4B5FD">Retorno ↓</span></th>
                <th>Monedas que quedan</th><th class="r">Consistencia</th><th class="r">Trades</th><th class="r">DD máx</th><th>Estado</th>
            </tr></thead>
            <tbody id="sbRows"></tbody>
        </table>
    </div></div>
    <div class="sb-cards" id="sbCards"></div>

    <div class="sb-foot mt-3">
        <div style="font-size:12px;color:var(--color-text-secondary)"><b style="color:#DDD6FE" id="sbSel">0 seleccionadas</b> · se creará en el historial con
            <select id="sbMode">
                <option value="all">todas las monedas (búsqueda + validación)</option>
                <option value="search">solo las de búsqueda</option>
                <option value="winners">solo las que ganaron</option>
            </select>
        </div>
        <button type="button" class="sb-btn purple" id="sbCreate" onclick="sbCreate()" disabled>💾 Crear en historial</button>
    </div>
</div>

{{-- Búsquedas anteriores --}}
<div class="sb-card mt-5" style="overflow:hidden">
    <div style="padding:10px 12px;border-bottom:1px solid var(--color-border-soft)">
        <h3 style="margin:0;font-size:13px;font-weight:600;color:var(--color-text-secondary)">Búsquedas anteriores de esta estrategia (últimas {{ $keep }})</h3>
    </div>
    @forelse($history as $h)
        @php
            $ivs = collect($h->intervals ?? [])->map(fn ($i) => $labels[$i] ?? $i)->implode(', ');
            $outdated = $h->strategy_code_md5 && $codeMd5 && $h->strategy_code_md5 !== $codeMd5;
        @endphp
        <div class="sb-hrow">
            <span>{{ $h->created_at?->timezone(config('app.timezone'))->format('d M H:i') }} · <span class="sb-badge int">{{ $ivs }}</span> · {{ $h->tested ?? '—' }} combinaciones</span>
            <span class="{{ (int) $h->validated > 0 ? 'sb-pos' : 'sb-muted' }}">
                @if($h->status === 'done') {{ (int) $h->validated }} validadas · {{ (int) $h->robust }} robustas
                @elseif(in_array($h->status, ['queued', 'running'])) en curso
                @elseif($h->status === 'cancelled') cancelada
                @else falló @endif
                @if($outdated) · ⚠️ código desactualizado @endif
            </span>
            @if($h->id === $run->id)
                <span class="sb-muted">esta</span>
            @else
                <a href="{{ route('strategies.search.show', $h->id) }}" style="color:#9DC0F2;text-decoration:underline">Ver</a>
            @endif
        </div>
    @empty
        <div class="sb-hrow sb-muted">Sin búsquedas.</div>
    @endforelse
</div>

@push('scripts')
<script>
(function () {
    const URL_STATUS = @json(route('strategies.search.status', $run->id));
    const URL_RESULTS = @json(route('strategies.search.results', $run->id));
    const URL_CANCEL = @json(route('strategies.search.cancel', $run->id));
    const URL_CREATE = @json(route('strategies.search.create', $run->id));
    const URL_HISTORY = @json($run->strategy ? route('backtesting.history', $run->strategy_id) : null);
    const $ = id => document.getElementById(id);
    let state = null, data = null, onlyRobust = true, selected = new Set(), pending = new Set(), timer = null, wasActive = false;

    const fmtDate = iso => iso ? new Date(iso).toLocaleString('es-CO', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
    const ivs = s => (s.intervals || []).map(i => SB.LABEL[i] || i).join(', ');

    function header(s) {
        $('sbIvs').textContent = ivs(s);
        const p = s.period;
        let meta = 'Iniciada ' + fmtDate(s.created_at) + ' · ' + (s.search_symbols || []).length + ' monedas de búsqueda · '
                 + (s.validation_symbols || []).length + ' de validación';
        if (p) meta += ` · 24 meses (${p.start} → ${p.end}) · en muestra hasta ${p.split}`;
        if (s.elapsed_s) meta += ` · duró ${Math.floor(s.elapsed_s / 60)} min ${Math.round(s.elapsed_s % 60)} s`;
        $('sbMeta').textContent = meta;
        const short = a => (a || []).map(x => SB.esc(x.replace('USDT', ''))).join(' · ');
        $('sbSyms').innerHTML = '<b>Búsqueda:</b> ' + short(s.search_symbols)
            + ((s.validation_symbols || []).length ? ' &nbsp;—&nbsp; <b>Validación:</b> ' + short(s.validation_symbols) : ' &nbsp;—&nbsp; sin validación');
        $('sbOutdated').style.display = s.outdated ? 'block' : 'none';
    }

    function showRunning(s) {
        $('sbRunning').style.display = 'block';
        $('sbRunTitle').textContent = (s.strategy || '') + ' · ' + ivs(s);
        $('sbRunSub').textContent = (s.search_symbols || []).join(' · ') + ((s.validation_symbols || []).length ? ' — validación: ' + s.validation_symbols.join(' · ') : '');
        const started = s.started_at ? (Date.now() - new Date(s.started_at).getTime()) / 1000 : 0;
        const mm = Math.floor(started / 60), ss = String(Math.round(started % 60)).padStart(2, '0');
        $('sbRunBadge').textContent = s.status === 'queued' ? 'En cola' : `En curso · ${mm}:${ss}`;
        const frac = s.progress_total ? s.progress_done / s.progress_total : 0;
        $('sbBar').style.width = Math.max(2, Math.round(frac * 100)) + '%';
        $('sbProg').textContent = s.progress_total ? `${s.progress_done} de ${s.progress_total} backtests · ${s.progress_note || ''}` : (s.progress_note || 'Esperando turno en la cola…');
        const left = frac > 0.05 && started > 10 ? Math.max(1, Math.round(started / frac - started)) : 0;
        $('sbEta').textContent = left ? (left >= 90 ? '≈ ' + Math.round(left / 60) + ' min restantes' : '≈ ' + left + ' s restantes') : '';
        const order = ['datos', 'busqueda', 'validacion', 'fin'];
        const at = order.indexOf(s.phase || '');
        const steps = [['datos', 'Cargando datos (24 meses, velas de 1 minuto)'],
                       ['busqueda', 'Probando combinaciones en ' + (s.search_symbols || []).join(' · ') + ' (en muestra / fuera de muestra)'],
                       ['validacion', (s.validation_symbols || []).length ? 'Validando las robustas en ' + s.validation_symbols.join(' · ') : 'Sin validación en otras monedas'],
                       ['fin', 'Calculando estrellas']];
        $('sbSteps').innerHTML = steps.map(([k, t], i) => {
            const st = s.status === 'queued' ? 'wait' : (i < at ? 'ok' : (i === at ? 'now' : 'wait'));
            return `<div><span class="sb-${st}">${st === 'ok' ? '✓' : (st === 'now' ? '●' : '○')}</span> ${SB.esc(t)}</div>`;
        }).join('');
        $('sbCancel').disabled = false;
    }

    async function poll() {
        try { state = await SB.api(URL_STATUS); } catch (e) { timer = setTimeout(poll, 8000); return; }
        header(state);
        if (state.status === 'queued' || state.status === 'running') { wasActive = true; showRunning(state); timer = setTimeout(poll, 4000); return; }
        if (wasActive) { window.location.reload(); return; }   // refresca también "Búsquedas anteriores"
        $('sbRunning').style.display = 'none';
        if (state.status === 'done') return loadResults();
        $('sbFailed').style.display = 'block';
        $('sbFailed').innerHTML = (state.status === 'cancelled' ? '⏹ Búsqueda cancelada.' : '✗ La búsqueda falló.') +
            (state.error ? '<pre style="white-space:pre-wrap;margin:8px 0 0;font-size:11px">' + SB.esc(state.error) + '</pre>' : '');
    }

    async function loadResults() {
        try { data = await SB.api(URL_RESULTS + '?symbols=' + $('sbMode').value); }
        catch (e) { $('sbFailed').style.display = 'block'; $('sbFailed').textContent = 'No se pudieron cargar los resultados: ' + e.message; return; }
        state = data.run; header(state);
        $('sbResults').style.display = 'block';
        renderResults();
        // "Crear en historial" en curso: refrescar hasta que todas las elegidas tengan resultado
        const busy = data.rows.some(r => r.created && r.created.status === 'running') || [...pending].some(id => !rowById(id)?.created);
        if (busy) { clearTimeout(timer); timer = setTimeout(loadResults, 5000); } else { pending.clear(); }
    }
    const rowById = id => data.rows.find(r => r.id === id);

    function wins(r) {
        // "4 de 6 · quedan: LINK, NEAR, SOL, SUI" (las monedas rentables que quedaron en la configuración)
        const keep = r.survivors || [], out = r.discarded || [], short = s => s.replace('USDT', '');
        return `<b class="sb-pos">${keep.length} de ${keep.length + out.length}</b> · quedan: ${SB.esc(keep.map(short).join(', ') || '—')}`;
    }
    function status(r) {
        const c = r.created;
        if (c && c.status === 'done') return `<span class="sb-badge ok">✓ Creado #${c.backtest_id}</span>`;
        if (c && c.status === 'running') return '<span class="sb-badge run">Creando…</span>';
        if (c && c.status === 'error') return `<span class="sb-badge no" title="${SB.esc(c.error)}">✗ No se creó</span>`;
        if (pending.has(r.id)) return '<span class="sb-badge run">En cola…</span>';
        if (r.creatable) return '<span class="sb-badge ok">✓ Robusta · validada</span>';
        if (r.robusta) return '<span class="sb-badge no">✗ Falló en monedas nuevas</span>';
        return '<span class="sb-badge no">✗ Falló fuera de muestra</span>';
    }
    function canPick(r) { return r.creatable && !state.outdated && !(r.created && ['done', 'running'].includes(r.created.status)) && !pending.has(r.id); }

    function renderResults() {
        const s = state, rows = data.rows, robust = rows.filter(r => r.robusta);
        const best = rows.length ? Math.max(...rows.map(r => r.summary.total_return_pct)) : null;
        $('sbKpis').innerHTML = [
            ['Combinaciones probadas', s.tested ?? '—', '', ''], ['Candidatas', s.candidates ?? 0, 'ganan en muestra', ''],
            ['Robustas', s.robust ?? 0, 'también fuera de muestra', (s.robust ?? 0) > 0 ? 'sb-pos' : ''],
            ['Validadas', s.validated ?? 0, 'en monedas nuevas', (s.validated ?? 0) > 0 ? 'sb-pos' : ''],
            ['Mejor retorno total', best === null ? '—' : SB.pct(best, 1), '24 meses · monedas elegidas', best === null ? '' : SB.cls(best)],
        ].map(([t, v, sub, c]) => `<div class="sb-kpi"><span>${t}</span><b class="${c}">${v}</b>${sub ? '<span>' + sub + '</span>' : ''}</div>`).join('');
        $('sbFilter').innerHTML = `<button type="button" class="sb-coin${onlyRobust ? ' on' : ''}" data-f="1">Robustas (${robust.length})</button>` +
                                  `<button type="button" class="sb-coin${onlyRobust ? '' : ' on'}" data-f="0">Todas las candidatas (${rows.length})</button>`;
        document.querySelectorAll('#sbFilter .sb-coin').forEach(b => b.onclick = () => { onlyRobust = b.dataset.f === '1'; renderResults(); });

        const list = onlyRobust ? robust : rows;
        $('sbEmpty').style.display = list.length ? 'none' : 'block';
        document.querySelector('.sb-table').style.display = list.length ? '' : 'none';
        document.querySelector('.sb-foot').style.display = robust.length ? '' : 'none';
        $('sbEmpty').innerHTML = rows.length
            ? 'Ninguna candidata aguantó fuera de muestra. Mira "Todas las candidatas" para ver cuáles ganaban en el pasado y por qué se descartaron.'
            : `Ninguna de las ${s.tested ?? 0} combinaciones ganó en muestra en al menos 3/4 de las monedas con PF ≥ 1.15. Es un resultado válido: con esta
               estrategia y temporalidad no apareció una ventaja. Prueba otra temporalidad u otra estrategia.`;

        $('sbRows').innerHTML = list.map(r => {
            const m = r.summary, on = selected.has(r.id), pick = canPick(r);
            return `<tr class="${r.creatable ? '' : 'off'}">
              <td><input type="checkbox" class="sb-chk" data-id="${r.id}" ${on ? 'checked' : ''} ${pick ? '' : 'disabled'}></td>
              <td><span class="sb-stars" style="color:${SB.starColor(m.rating)}">${SB.stars(m.rating)}</span> <b style="color:${SB.starColor(m.rating)}">${SB.num(m.rating, 1)}</b>
                  <span class="sb-sub">WR ${SB.num(m.win_rate, 0)}% · Sharpe ${SB.num(m.sharpe_ratio, 2)}</span></td>
              <td>${SB.cfgTags(r.cfg)}<span class="sb-sub" style="margin-top:4px">${SB.LABEL[r.interval] || r.interval}</span></td>
              <td class="r ${SB.pfCls(r.is.pf)}">${SB.num(r.is.pf)}<span class="sb-sub">${SB.pct(r.is.ret)}</span></td>
              <td class="r ${SB.pfCls(r.oos.pf)}">${SB.num(r.oos.pf)}<span class="sb-sub">${SB.pct(r.oos.ret)}</span></td>
              <td class="r ${SB.pfCls(m.profit_factor)}">${SB.num(m.profit_factor)}<span class="sb-sub">${SB.pct(m.total_return_pct)}</span></td>
              <td>${wins(r)}</td>
              <td class="r">${SB.num(m.consist_pct, 0)}%<span class="sb-sub">${Math.round(m.consist_pct * (data.months || 24) / 100)}/${data.months || 24} meses</span></td>
              <td class="r">${m.total_trades.toLocaleString('es-CO')}</td><td class="r">${SB.num(m.max_drawdown_pct, 1)}%</td>
              <td>${status(r)}</td></tr>`;
        }).join('');
        $('sbCards').innerHTML = list.map(r => {
            const m = r.summary, on = selected.has(r.id), pick = canPick(r);
            return `<div class="sb-rc${r.creatable ? '' : ' off'}">
              <div class="sb-rc-top"><label class="sb-switch"><input type="checkbox" class="sb-chk" data-id="${r.id}" ${on ? 'checked' : ''} ${pick ? '' : 'disabled'}>
                <span class="sb-stars" style="color:${SB.starColor(m.rating)}">${SB.stars(m.rating)}</span><b style="color:${SB.starColor(m.rating)}">${SB.num(m.rating, 1)}</b></label>${status(r)}</div>
              ${SB.cfgTags(r.cfg)}
              <div class="sb-sub" style="margin:6px 0">${wins(r)}</div>
              <div class="sb-rc-grid"><div><span>PF en muestra</span><b class="${SB.pfCls(r.is.pf)}">${SB.num(r.is.pf)}</b></div>
                <div><span>PF fuera</span><b class="${SB.pfCls(r.oos.pf)}">${SB.num(r.oos.pf)}</b></div>
                <div><span>Retorno total</span><b class="${SB.cls(m.total_return_pct)}">${SB.pct(m.total_return_pct)}</b></div>
                <div><span>Consistencia</span><b>${SB.num(m.consist_pct, 0)}%</b></div><div><span>Trades</span><b>${m.total_trades}</b></div>
                <div><span>DD máx</span><b>${SB.num(m.max_drawdown_pct, 1)}%</b></div></div></div>`;
        }).join('');
        document.querySelectorAll('.sb-chk[data-id]').forEach(c => c.onchange = () => {
            c.checked ? selected.add(c.dataset.id) : selected.delete(c.dataset.id); renderResults(); });
        [...selected].forEach(id => { const r = rowById(id); if (!r || !canPick(r)) selected.delete(id); });
        $('sbSel').textContent = selected.size === 1 ? '1 seleccionada' : selected.size + ' seleccionadas';
        $('sbCreate').disabled = !selected.size;
    }

    $('sbMode').addEventListener('change', loadResults);

    window.sbCancel = async function () {
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'warning', title: '¿Cancelar la búsqueda?', text: 'Se detiene en unos segundos y no guarda resultados.',
            showCancelButton: true, confirmButtonText: 'Sí, cancelar', cancelButtonText: 'Seguir', confirmButtonColor: '#ef4444' });
        if (!ok.isConfirmed) return;
        $('sbCancel').disabled = true;
        try { await SB.api(URL_CANCEL, { method: 'POST' }); } catch (e) { Swal.fire({ ...SB.SWAL, icon: 'error', title: 'Error', text: e.message }); }
        clearTimeout(timer); poll();
    };

    window.sbCreate = async function () {
        const mode = $('sbMode'), ids = [...selected];
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'question', title: 'Crear en el historial',
            html: `Se correrán y guardarán <b>${ids.length}</b> backtest(s) con <b>${SB.esc(mode.options[mode.selectedIndex].text)}</b>, por el mismo camino que la pantalla de Backtesting.<br><br>No se implementan en Paper: eso lo decides en el historial.`,
            showCancelButton: true, confirmButtonText: 'Crear', cancelButtonText: 'Volver' });
        if (!ok.isConfirmed) return;
        $('sbCreate').disabled = true;
        try {
            const r = await SB.api(URL_CREATE, { method: 'POST', body: JSON.stringify({ rows: ids, symbols: mode.value }) });
            ids.forEach(id => pending.add(id)); selected.clear();
            Swal.fire({ ...SB.SWAL, icon: 'success', title: 'En cola', html: SB.esc(r.message) + (URL_HISTORY ? `<br><br><a href="${URL_HISTORY}" style="color:#C4B5FD;text-decoration:underline">Ir al historial</a>` : ''),
                timer: 4000 });
            renderResults(); clearTimeout(timer); timer = setTimeout(loadResults, 3000);
        } catch (e) { Swal.fire({ ...SB.SWAL, icon: 'error', title: 'No se pudo crear', text: e.message }); renderResults(); }
    };

    poll();
})();
</script>
@endpush
@endsection

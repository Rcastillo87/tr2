@extends('layouts.app')
@section('title', 'Búsqueda de configuración')
@section('header', 'Estrategias y Backtesting')

@section('content')
@include('param-search._styles')
@include('param-search._helpers')

<div class="flex flex-wrap justify-between items-end gap-3 mb-3">
    <div>
        <h2 style="margin:0;font-size:18px;font-weight:600;color:var(--color-text-primary)">
            {{ $run->strategy?->name ?? 'Estrategia eliminada' }} · <span id="sbIvs"></span>
        </h2>
        <p id="sbMeta" class="sb-muted" style="margin:3px 0 0;font-size:12px"></p>
        <p id="sbSyms" style="margin:4px 0 0;font-size:12px;color:var(--color-text-secondary)"></p>
    </div>
    <a href="{{ route('strategies.index') }}" class="sb-btn gray">← Volver a Estrategias</a>
</div>

<div id="sbOutdated" class="sb-alert warn mb-3" style="display:none">
    ⚠️ La estrategia cambió después de esta búsqueda: sus resultados ya no describen el código actual. Vuelve a buscar antes de crear backtests.
</div>

{{-- En cola / en curso --}}
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

{{-- Resultados: solo configuraciones rentables --}}
<div id="sbResults" style="display:none">
    <div class="sb-kpis mb-3" id="sbKpis"></div>
    <div class="flex flex-wrap justify-between items-center gap-2 mb-2">
        <div class="sb-coins" id="sbFilter"></div>
        <span class="sb-muted" style="font-size:11px">Orden: <b style="color:#C4B5FD">Retorno total ↓</b> · luego estrellas · luego consistencia</span>
    </div>
    <div id="sbEmpty" class="sb-alert info" style="display:none"></div>
    <div class="sb-card sb-table" style="overflow:hidden"><div style="overflow-x:auto">
        <table class="sb-rs">
            <thead><tr>
                <th style="width:30px"></th><th>Estrellas</th><th>Configuración</th><th class="r"><span style="color:#C4B5FD">Retorno ↓</span></th>
                <th>Monedas que quedan</th><th class="r">PF</th><th class="r">Consistencia</th><th class="r">Trades</th><th class="r">DD máx</th><th>Al final</th>
            </tr></thead>
            <tbody id="sbRows"></tbody>
        </table>
    </div></div>
    <div class="sb-cards" id="sbCards"></div>

    <div class="sb-foot mt-3">
        <div style="font-size:12px;color:var(--color-text-secondary)"><b style="color:#DDD6FE" id="sbSel">0 seleccionadas</b> · se crean en el historial de
            backtests con las monedas que quedan en cada una</div>
        <button type="button" class="sb-btn purple" id="sbCreate" onclick="sbCreate()" disabled>💾 Crear en historial</button>
    </div>
    <p class="sb-muted" style="font-size:11px;margin:10px 0 0" id="sbNote"></p>
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
                @if($h->status === 'done') {{ (int) $h->validated }} rentable(s)
                @elseif($h->status === 'queued') en cola
                @elseif($h->status === 'running') en curso
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
    let state = null, data = null, rows = [], onlyLate = true, selected = new Set(), pending = new Set(), timer = null, wasActive = false;

    const fmtDate = iso => iso ? new Date(iso).toLocaleString('es-CO', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
    const ivs = s => (s.intervals || []).map(i => SB.LABEL[i] || i).join(', ');
    const short = a => (a || []).map(x => SB.esc(x.replace('USDT', ''))).join(', ');
    const lateMonths = () => Math.round((data?.months || 24) / 3);

    function header(s) {
        $('sbIvs').textContent = ivs(s);
        const p = s.period;
        let meta = `Búsqueda #${s.id} · iniciada ${fmtDate(s.created_at)} · ${(s.search_symbols || []).length} monedas`;
        if (p) meta += ` · 24 meses (${p.start} → ${p.end})`;
        if (s.elapsed_s) meta += ` · duró ${Math.floor(s.elapsed_s / 60)} min ${Math.round(s.elapsed_s % 60)} s`;
        $('sbMeta').textContent = meta;
        $('sbSyms').innerHTML = '<b>Monedas:</b> ' + short(s.search_symbols);
        $('sbOutdated').style.display = s.outdated ? 'block' : 'none';
    }

    function showRunning(s) {
        $('sbRunning').style.display = 'block';
        $('sbRunTitle').textContent = (s.strategy || '') + ' · ' + ivs(s);
        $('sbRunSub').textContent = (s.search_symbols || []).map(x => x.replace('USDT', '')).join(' · ');
        const started = s.started_at ? (Date.now() - new Date(s.started_at).getTime()) / 1000 : 0;
        const mm = Math.floor(started / 60), ss = String(Math.round(started % 60)).padStart(2, '0');
        $('sbRunBadge').textContent = s.status === 'queued' ? 'En cola' : `En curso · ${mm}:${ss}`;
        const frac = s.progress_total ? s.progress_done / s.progress_total : 0;
        $('sbBar').style.width = Math.max(2, Math.round(frac * 100)) + '%';
        $('sbProg').textContent = s.progress_total ? `${s.progress_done} de ${s.progress_total} backtests · ${s.progress_note || ''}`
            : (s.status === 'queued' ? 'Esperando turno: corre una búsqueda a la vez.' : (s.progress_note || ''));
        $('sbEta').textContent = '';
        const order = ['datos', 'busqueda', 'fin'], at = order.indexOf(s.phase || '');
        const steps = [['datos', 'Cargando velas (una moneda a la vez)'],
                       ['busqueda', 'Probando combinaciones moneda por moneda'],
                       ['fin', 'Quedándose con las monedas rentables y calculando estrellas']];
        $('sbSteps').innerHTML = steps.map(([k, t], i) => {
            const st = s.status === 'queued' ? 'wait' : (i < at ? 'ok' : (i === at || (at < 0 && i === 0) ? 'now' : 'wait'));
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

    /** Filas rentables, sin repetidas: las que dan exactamente el mismo resultado se juntan en la primera (ya vienen ordenadas). */
    function dedupe(list) {
        const seen = new Map(), out = [];
        list.forEach(r => {
            const m = r.summary;
            const key = [r.interval, m.total_return_pct, m.total_trades, m.consist_pct, m.profit_factor, m.max_drawdown_pct, (r.survivors || []).join()].join('|');
            if (seen.has(key)) { seen.get(key).dups.push(r.id); return; }
            const row = { ...r, dups: [] }; seen.set(key, row); out.push(row);
        });
        return out;
    }

    async function loadResults() {
        try { data = await SB.api(URL_RESULTS + '?symbols=survivors'); }
        catch (e) { $('sbFailed').style.display = 'block'; $('sbFailed').textContent = 'No se pudieron cargar los resultados: ' + e.message; return; }
        state = data.run; header(state);
        rows = dedupe(data.rows.filter(r => r.creatable));
        $('sbResults').style.display = 'block';
        renderResults();
        const busy = data.rows.some(r => r.created && r.created.status === 'running') || [...pending].some(id => !rowById(id)?.created);
        if (busy) { clearTimeout(timer); timer = setTimeout(loadResults, 5000); } else { pending.clear(); }
    }
    const rowById = id => data.rows.find(r => r.id === id);

    function coinsCell(r) {
        const keep = r.survivors || [], out = r.discarded || [];
        return `<b class="sb-pos">${keep.length} de ${keep.length + out.length}</b> · quedan: ${short(keep) || '—'}`;
    }
    function finalCell(r) {
        const late = r.oos_ok ? '<span class="sb-badge late">✓ también gana</span>' : '<span class="sb-badge early">solo al principio</span>';
        const c = r.created;
        let st = '';
        if (c && c.status === 'done') st = `<span class="sb-badge ok">✓ Creado #${c.backtest_id}</span>`;
        else if (c && c.status === 'running') st = '<span class="sb-badge run">Creando…</span>';
        else if (c && c.status === 'error') st = `<span class="sb-badge no" title="${SB.esc(c.error)}">✗ No se creó</span>`;
        else if (pending.has(r.id)) st = '<span class="sb-badge run">En cola…</span>';
        return late + (st ? '<div style="margin-top:4px">' + st + '</div>' : '');
    }
    function canPick(r) { return r.creatable && !state.outdated && !(r.created && ['done', 'running'].includes(r.created.status)) && !pending.has(r.id); }
    const dupNote = r => r.dups.length ? `<div class="sb-dup">≡ también ${r.dups.map(SB.esc).join(', ')} (mismo resultado)</div>` : '';
    const stars = m => `<span class="sb-stars" style="color:${SB.starColor(m.rating)}">${SB.stars(m.rating)}</span> <b style="color:${SB.starColor(m.rating)}">${SB.num(m.rating, 1)}</b>`;

    function renderResults() {
        const s = state, late = rows.filter(r => r.oos_ok), months = data.months || 24;
        const best = rows.length ? Math.max(...rows.map(r => r.summary.total_return_pct)) : null;
        const total = data.rows.filter(r => r.creatable).length;
        $('sbKpis').innerHTML = [
            ['Combinaciones probadas', s.tested ?? '—', '', ''],
            ['Rentables', total, '', total ? 'sb-pos' : ''],
            ['También ganan al final', late.length, `últimos ${lateMonths()} meses`, late.length ? 'sb-pos' : ''],
            ['Configuraciones distintas', rows.length, total > rows.length ? (total - rows.length) + ' repetidas' : '', ''],
            ['Mejor retorno total', best === null ? '—' : SB.pct(best, 1), '', best === null ? '' : SB.cls(best)],
        ].map(([t, v, sub, c]) => `<div class="sb-kpi"><span>${t}</span><b class="${c}">${v}</b>${sub ? '<span>' + sub + '</span>' : ''}</div>`).join('');
        $('sbFilter').innerHTML = `<button type="button" class="sb-coin${onlyLate ? ' on' : ''}" data-f="1">También ganan al final (${late.length})</button>` +
                                  `<button type="button" class="sb-coin${onlyLate ? '' : ' on'}" data-f="0">Todas las rentables (${rows.length})</button>`;
        document.querySelectorAll('#sbFilter .sb-coin').forEach(b => b.onclick = () => { onlyLate = b.dataset.f === '1'; renderResults(); });

        const list = onlyLate ? late : rows;
        $('sbEmpty').style.display = list.length ? 'none' : 'block';
        document.querySelector('.sb-table').style.display = list.length ? '' : 'none';
        document.querySelector('.sb-foot').style.display = rows.length ? '' : 'none';
        $('sbEmpty').innerHTML = rows.length
            ? `Ninguna configuración rentable ganó también en los últimos ${lateMonths()} meses. Mira "Todas las rentables".`
            : `Ninguna de las ${s.tested ?? 0} combinaciones fue rentable en alguna moneda con ${data.min_trades || 30} o más operaciones. Es un resultado
               válido: con esta estrategia, temporalidad y monedas no apareció una ventaja. Prueba otra temporalidad u otras monedas.`;
        $('sbNote').innerHTML = `<b>"Al final"</b>: si la configuración también ganó en los últimos ${lateMonths()} meses de los ${months} (con las monedas que quedan). Es la señal de que no fue suerte del principio.`;

        $('sbRows').innerHTML = list.map(r => {
            const m = r.summary, on = selected.has(r.id), pick = canPick(r);
            return `<tr>
              <td><input type="checkbox" class="sb-chk" data-id="${r.id}" ${on ? 'checked' : ''} ${pick ? '' : 'disabled'}></td>
              <td>${stars(m)}<span class="sb-sub">WR ${SB.num(m.win_rate, 0)}% · Sharpe ${SB.num(m.sharpe_ratio, 2)}</span></td>
              <td>${SB.cfgTags(r.cfg)}<span class="sb-sub" style="margin-top:4px">${SB.LABEL[r.interval] || r.interval}</span>${dupNote(r)}</td>
              <td class="r"><b class="${SB.cls(m.total_return_pct)}">${SB.pct(m.total_return_pct)}</b></td>
              <td class="sb-qd">${coinsCell(r)}</td>
              <td class="r ${SB.pfCls(m.profit_factor)}">${SB.num(m.profit_factor)}</td>
              <td class="r">${SB.num(m.consist_pct, 0)}%<span class="sb-sub">${Math.round(m.consist_pct * months / 100)}/${months} meses</span></td>
              <td class="r">${m.total_trades.toLocaleString('es-CO')}</td><td class="r">${SB.num(m.max_drawdown_pct, 1)}%</td>
              <td>${finalCell(r)}</td></tr>`;
        }).join('');
        $('sbCards').innerHTML = list.map(r => {
            const m = r.summary, on = selected.has(r.id), pick = canPick(r);
            return `<div class="sb-rc">
              <div class="sb-rc-top"><label class="sb-switch"><input type="checkbox" class="sb-chk" data-id="${r.id}" ${on ? 'checked' : ''} ${pick ? '' : 'disabled'}>
                ${stars(m)}</label>${finalCell(r)}</div>
              ${SB.cfgTags(r.cfg)}<span class="sb-sub" style="margin-top:4px">${SB.LABEL[r.interval] || r.interval}</span>${dupNote(r)}
              <div class="sb-qd" style="margin-top:8px;font-size:12px">${coinsCell(r)}</div>
              <div class="sb-rc-grid"><div><span>Retorno</span><b class="${SB.cls(m.total_return_pct)}">${SB.pct(m.total_return_pct)}</b></div>
                <div><span>PF</span><b class="${SB.pfCls(m.profit_factor)}">${SB.num(m.profit_factor)}</b></div>
                <div><span>Consistencia</span><b>${SB.num(m.consist_pct, 0)}%</b></div><div><span>Trades</span><b>${m.total_trades}</b></div>
                <div><span>DD máx</span><b>${SB.num(m.max_drawdown_pct, 1)}%</b></div></div></div>`;
        }).join('');
        document.querySelectorAll('.sb-chk[data-id]').forEach(c => c.onchange = () => {
            c.checked ? selected.add(c.dataset.id) : selected.delete(c.dataset.id); renderResults(); });
        [...selected].forEach(id => { const r = rowById(id); if (!r || !canPick(r)) selected.delete(id); });
        $('sbSel').textContent = selected.size === 1 ? '1 seleccionada' : selected.size + ' seleccionadas';
        $('sbCreate').textContent = selected.size ? `💾 Crear ${selected.size} en historial` : '💾 Crear en historial';
        $('sbCreate').disabled = !selected.size;
    }

    window.sbCancel = async function () {
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'warning', title: '¿Cancelar la búsqueda?', text: 'Se detiene en unos segundos y no guarda resultados.',
            showCancelButton: true, confirmButtonText: 'Sí, cancelar', cancelButtonText: 'Seguir', confirmButtonColor: '#ef4444' });
        if (!ok.isConfirmed) return;
        $('sbCancel').disabled = true;
        try { await SB.api(URL_CANCEL, { method: 'POST' }); } catch (e) { Swal.fire({ ...SB.SWAL, icon: 'error', title: 'Error', text: e.message }); }
        clearTimeout(timer); poll();
    };

    window.sbCreate = async function () {
        const ids = [...selected];
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'question', title: 'Crear en el historial',
            html: `Se correrán y guardarán <b>${ids.length}</b> backtest(s), cada uno con <b>las monedas que quedan</b> en su configuración, por el mismo camino que la pantalla de Backtesting.<br><br>No se implementan en Paper: eso lo decides en el historial.`,
            showCancelButton: true, confirmButtonText: 'Crear', cancelButtonText: 'Volver' });
        if (!ok.isConfirmed) return;
        $('sbCreate').disabled = true;
        try {
            const r = await SB.api(URL_CREATE, { method: 'POST', body: JSON.stringify({ rows: ids, symbols: 'survivors' }) });
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

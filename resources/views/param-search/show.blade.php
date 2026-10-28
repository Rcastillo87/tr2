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
        <p id="sbFocusLine" style="margin:6px 0 0;font-size:11px;display:none"></p>
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

{{-- Resultados v3: por moneda (una pestaña por moneda, cada una con su ranking) o por temporalidad (≥ 3/4 de las monedas) --}}
<div id="sbResults3" style="display:none">
    <div class="sb-tabs mb-3" id="sbTabs" role="tablist" aria-label="Monedas"></div>
    <div class="sb-kpis mb-3" id="sbKpis3"></div>
    <div id="sbEmpty3" class="sb-alert info mb-3" style="display:none"></div>
    <div class="sb-card sb-table" id="sbTable3" style="overflow:hidden"><div style="overflow-x:auto">
        <table class="sb-rs"><thead id="sbHead3"></thead><tbody id="sbRows3"></tbody></table>
    </div></div>
    <div class="sb-cards" id="sbCards3"></div>
    <div class="sb-foot mt-3" id="sbFoot3">
        <div style="font-size:12px;color:var(--color-text-secondary)"><b style="color:#DDD6FE" id="sbSel3">0 seleccionadas</b> · <span id="sbFootNote3"></span></div>
        <button type="button" class="sb-btn purple" id="sbCreate3" onclick="sbCreate()" disabled>💾 Crear en historial</button>
    </div>
    <p class="sb-muted" style="font-size:11px;margin:10px 0 0" id="sbNote3"></p>
</div>

{{-- Búsquedas anteriores --}}
<div class="sb-card mt-5" style="overflow:hidden">
    <div style="padding:10px 12px;border-bottom:1px solid var(--color-border-soft);display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 16px;align-items:center">
        <h3 style="margin:0;font-size:13px;font-weight:600;color:var(--color-text-secondary)">Búsquedas anteriores de esta estrategia (últimas {{ $keep }})</h3>
        <span class="sb-muted" style="font-size:11px">Eliminar quita la búsqueda y sus resultados; los backtests ya creados en el historial no se tocan.</span>
    </div>
    @if($history->isEmpty())
        <div class="sb-hrow sb-muted">Sin búsquedas.</div>
    @else
    <div style="overflow-x:auto">
    <table class="sb-hist">
        <thead><tr><th>Fecha</th><th>Enfoque</th><th>Modo · temporalidades</th><th>Monedas probadas</th><th>Resultado</th><th style="text-align:right">Acciones</th></tr></thead>
        <tbody>
        @foreach($history as $h)
            @php
                $ivs = collect($h->intervals ?? [])->map(fn ($i) => $labels[$i] ?? $i)->implode(' · ');
                $outdated = $h->strategy_code_md5 && $codeMd5 && $h->strategy_code_md5 !== $codeMd5;
                $active = in_array($h->status, \App\Models\ParamSearchRun::ACTIVE, true);
                $v3 = (int) $h->version >= 3 || $active;
                $dur = $h->elapsed_s ? sprintf('%d min %02d s', intdiv((int) $h->elapsed_s, 60), (int) $h->elapsed_s % 60) : null;
            @endphp
            <tr>
                <td style="white-space:nowrap">{{ $h->created_at?->timezone(config('app.timezone'))->format('d M H:i') }}
                    <span class="sb-sub">#{{ $h->id }}{{ $dur ? ' · ' . $dur : '' }}{{ $h->id === $run->id ? ' · esta' : '' }}</span></td>
                <td>@if($v3)<span class="sb-badge focus">{{ $focuses[$h->focus] ?? $h->focus }}</span>@else<span class="sb-muted">—</span>@endif</td>
                <td><span class="sb-badge int">{{ $v3 ? ($h->mode === 'symbol' ? 'Por moneda' : 'Por temporalidad') : 'Anterior a v3' }}</span>
                    <span class="sb-sub" style="margin-top:4px">{{ $ivs }}</span></td>
                <td><div class="sb-coins">@foreach((array) $h->search_symbols as $sym)<span class="sb-coin val" style="border-style:solid">{{ str_replace('USDT', '', $sym) }}</span>@endforeach</div></td>
                <td class="{{ $h->status === 'done' && (int) $h->validated > 0 ? 'sb-pos' : 'sb-muted' }}">
                    @if($h->status === 'done') {{ (int) $h->validated }} {{ $v3 ? 'ganan en los dos tramos' : 'rentable(s)' }}
                    @elseif($h->status === 'queued') En cola
                    @elseif($h->status === 'running') En curso · {{ $h->progress_total ? round($h->progress_done / $h->progress_total * 100) : 0 }} %
                    @elseif($h->status === 'cancelled') Cancelada
                    @else Falló @endif
                    @if($outdated)<span class="sb-sub">⚠️ código desactualizado</span>@endif
                    @if($h->status === 'done')<span class="sb-sub">{{ $h->tested ?? '—' }} combinaciones</span>@endif
                </td>
                <td style="text-align:right;white-space:nowrap">
                    @if($h->id !== $run->id)<a href="{{ route('strategies.search.show', $h->id) }}" style="color:#9DC0F2;text-decoration:underline;font-size:12px;margin-right:10px">Ver</a>@endif
                    <button type="button" class="sb-btn red sm" onclick="sbDelete({{ $h->id }})" @disabled($active)
                            aria-label="Eliminar búsqueda #{{ $h->id }}" @if($active) title="Cancela la búsqueda antes de eliminarla" @endif>Eliminar</button>
                </td>
            </tr>
        @endforeach
        </tbody>
    </table>
    </div>
    @endif
</div>

@push('scripts')
<script>
(function () {
    const URL_STATUS = @json(route('strategies.search.status', $run->id));
    const URL_RESULTS = @json(route('strategies.search.results', $run->id));
    const URL_CANCEL = @json(route('strategies.search.cancel', $run->id));
    const URL_CREATE = @json(route('strategies.search.create', $run->id));
    const URL_HISTORY = @json($run->strategy ? route('backtesting.history', $run->strategy_id) : null);
    const URL_DESTROY = @json(route('strategies.search.destroy', '__RUN__'));
    const URL_STRATEGIES = @json(route('strategies.index'));
    const RUN_ID = {{ $run->id }};
    const FOCUS_LABEL = @json($focuses);
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
        $('sbFocusLine').style.display = s.focus ? '' : 'none';
        if (s.focus) $('sbFocusLine').innerHTML = `<span class="sb-badge focus">Enfoque: ${SB.esc(FOCUS_LABEL[s.focus] || s.focus)}</span>
            <span class="sb-muted" style="margin-left:6px">${s.mode === 'symbol' ? 'Por moneda: cada moneda tiene su propio ranking.'
            : 'Por temporalidad: se acepta si gana en ≥ ¾ de las monedas; métricas de todas.'} Ninguna moneda se descarta después de ver el resultado.</span>`;
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
        if (data.version >= 3) { $('sbResults3').style.display = 'block'; renderV3(); }
        else { $('sbResults').style.display = 'block'; renderResults(); }
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

    // ── v3 ──────────────────────────────────────────────────────────────────────────────────────────────
    let tab = null;
    function createdBadge(r) {
        const c = r.created;
        if (c && c.status === 'done') return `<span class="sb-badge ok">✓ Creado #${c.backtest_id}</span>`;
        if (c && c.status === 'running') return '<span class="sb-badge run">Creando…</span>';
        if (c && c.status === 'error') return `<span class="sb-badge no" title="${SB.esc(c.error)}">✗ No se creó</span>`;
        if (pending.has(r.id)) return '<span class="sb-badge run">En cola…</span>';
        return '';
    }
    function nearText(n) {
        const c = n.cfg || {};
        return `${SB.LABEL[n.interval] || n.interval} · SL ${c.sl_pct}% / TP ${c.tp_pct}%: ${SB.esc(n.why)}`;
    }
    function renderV3() {
        const s = state, symMode = data.mode === 'symbol', months = data.months || 24, late = lateMonths(), first = months - late;
        const key = { gain: 'total_return_pct', wr: 'win_rate', cons: 'consist_pct' }[data.focus] || 'total_return_pct';
        const syms = s.search_symbols || [];
        if (symMode && !syms.includes(tab)) tab = syms.find(x => rows.some(r => r.symbol === x)) || syms[0];
        $('sbTabs').style.display = symMode ? '' : 'none';
        $('sbTabs').innerHTML = syms.map(x => { const n = rows.filter(r => r.symbol === x).length;
            return `<button type="button" role="tab" class="sb-tab${x === tab ? ' on' : ''}" aria-selected="${x === tab}" data-tab="${x}">
                ${SB.esc(x.replace('USDT', ''))}<i class="${n ? 'ok' : ''}">${n}</i></button>`; }).join('');
        document.querySelectorAll('#sbTabs .sb-tab').forEach(b => b.onclick = () => { tab = b.dataset.tab; renderV3(); });

        const list = symMode ? rows.filter(r => r.symbol === tab) : rows;
        const near = symMode ? ((data.near || {})[tab] || []) : (Array.isArray(data.near) ? data.near : []);
        const best = list.length ? Math.max(...list.map(r => r.summary.total_return_pct)) : null;
        $('sbKpis3').innerHTML = [
            ['Probadas', s.tested ?? '—', symMode ? 'en ' + SB.esc(tab.replace('USDT', '')) : ''],
            ['Ganan en los dos tramos', list.length, ''],
            ['Mejor retorno 24 m', best === null ? '—' : SB.pct(best, 1), ''],
            ['Temporalidades', (s.intervals || []).length, ivs(s)],
            ['Duró', s.elapsed_s ? `${Math.floor(s.elapsed_s / 60)} min ${Math.round(s.elapsed_s % 60)} s` : '—', ''],
        ].map(([t, v, sub], i) => `<div class="sb-kpi"><span>${t}</span><b class="${i === 1 && list.length ? 'sb-pos' : (i === 2 && best !== null ? SB.cls(best) : '')}">${v}</b>${sub ? '<span>' + sub + '</span>' : ''}</div>`).join('');

        const H = (label, k, cls = 'r') => `<th class="${cls}${k === key ? ' key' : ''}">${label}${k === key ? ' ↓' : ''}</th>`;
        $('sbHead3').innerHTML = `<tr><th style="width:30px"></th><th>Estrellas</th><th>Configuración</th>${H('Retorno 24 m', 'total_return_pct')}
            ${H('Win rate', 'win_rate')}${H('Consistencia', 'consist_pct')}<th class="r">PF</th><th class="r">Trades</th><th class="r">DD máx</th>
            <th class="r">Primeros ${first} m</th><th class="r">Últimos ${late} m</th>${symMode ? '' : '<th>Monedas que ganan</th>'}<th></th></tr>`;
        $('sbEmpty3').style.display = list.length ? 'none' : 'block';
        $('sbTable3').style.display = list.length ? '' : 'none';
        $('sbFoot3').style.display = rows.length ? '' : 'none';
        $('sbEmpty3').innerHTML = `<b>Ninguna configuración gana ${symMode ? 'en ' + SB.esc(tab.replace('USDT', '')) : 'en ≥ ¾ de las monedas'} en los dos tramos.</b>`
            + (near.length ? '<div class="sb-near" style="margin-top:8px"><span>Las que más se acercaron:</span>' + near.map(n => `<span>· ${nearText(n)}</span>`).join('') + '</div>'
                           : ' Es un resultado válido: con esta estrategia y temporalidades no apareció una ventaja.');
        const coins3 = r => { const w = r.survivors || [], l = r.discarded || [];
            return `<b class="sb-pos">${w.length} de ${w.length + l.length}</b><span class="sb-sub">ganan: ${short(w) || '—'}</span>`
                 + (l.length ? `<span class="sb-sub">pierden: ${short(l)}</span>` : ''); };
        $('sbRows3').innerHTML = list.map(r => {
            const m = r.summary, on = selected.has(r.id), pick = canPick(r);
            return `<tr>
              <td><input type="checkbox" class="sb-chk" data-id="${r.id}" aria-label="Elegir configuración" ${on ? 'checked' : ''} ${pick ? '' : 'disabled'}></td>
              <td>${stars(m)}<span class="sb-sub">Sharpe ${SB.num(m.sharpe_ratio, 2)}</span></td>
              <td>${SB.cfgTags(r.cfg)}<span class="sb-sub" style="margin-top:4px">${SB.LABEL[r.interval] || r.interval}</span>${dupNote(r)}</td>
              <td class="r"><b class="${SB.cls(m.total_return_pct)}">${SB.pct(m.total_return_pct)}</b></td>
              <td class="r">${SB.num(m.win_rate, 0)}%</td>
              <td class="r">${SB.num(m.consist_pct, 0)}%<span class="sb-sub">${Math.round(m.consist_pct * months / 100)}/${months} meses</span></td>
              <td class="r ${SB.pfCls(m.profit_factor)}">${SB.num(m.profit_factor)}</td>
              <td class="r">${m.total_trades.toLocaleString('es-CO')}</td><td class="r">${SB.num(m.max_drawdown_pct, 1)}%</td>
              <td class="r ${SB.cls(r.is.ret)}">${SB.pct(r.is.ret)}</td>
              <td class="r"><span class="sb-badge late">${SB.pct(r.oos.ret)}</span></td>
              ${symMode ? '' : `<td class="sb-qd">${coins3(r)}</td>`}
              <td>${createdBadge(r)}</td></tr>`;
        }).join('');
        $('sbCards3').innerHTML = list.map(r => {
            const m = r.summary, on = selected.has(r.id), pick = canPick(r);
            return `<div class="sb-rc">
              <div class="sb-rc-top"><label class="sb-switch"><input type="checkbox" class="sb-chk" data-id="${r.id}" ${on ? 'checked' : ''} ${pick ? '' : 'disabled'}>
                ${stars(m)}</label>${createdBadge(r)}</div>
              ${SB.cfgTags(r.cfg)}<span class="sb-sub" style="margin-top:4px">${SB.LABEL[r.interval] || r.interval}</span>
              <div class="sb-rc-grid"><div><span>Retorno 24 m</span><b class="${SB.cls(m.total_return_pct)}">${SB.pct(m.total_return_pct)}</b></div>
                <div><span>Win rate</span><b>${SB.num(m.win_rate, 0)}%</b></div><div><span>Consistencia</span><b>${SB.num(m.consist_pct, 0)}%</b></div>
                <div><span>Primeros ${first} m</span><b class="${SB.cls(r.is.ret)}">${SB.pct(r.is.ret)}</b></div>
                <div><span>Últimos ${late} m</span><b class="sb-pos">${SB.pct(r.oos.ret)}</b></div><div><span>Trades</span><b>${m.total_trades}</b></div></div>
              ${symMode ? '' : `<div class="sb-qd" style="margin-top:8px;font-size:12px">${coins3(r)}</div>`}</div>`;
        }).join('');
        document.querySelectorAll('#sbResults3 .sb-chk[data-id]').forEach(c => c.onchange = () => {
            c.checked ? selected.add(c.dataset.id) : selected.delete(c.dataset.id); renderV3(); });
        [...selected].forEach(id => { const r = rowById(id); if (!r || !canPick(r)) selected.delete(id); });
        $('sbSel3').textContent = selected.size === 1 ? '1 seleccionada' : selected.size + ' seleccionadas';
        $('sbFootNote3').textContent = symMode ? 'cada una se crea en el historial con su moneda' : 'cada una se crea en el historial con todas las monedas probadas';
        $('sbCreate3').textContent = selected.size ? `💾 Crear ${selected.size} en historial` : '💾 Crear en historial';
        $('sbCreate3').disabled = !selected.size;
        $('sbNote3').innerHTML = `<b>Primeros ${first} m</b>: tramo con el que se eligió. <b>Últimos ${late} m</b>: tramo que nunca se usó para elegir; `
            + `toda configuración de la lista también ganó ahí.` + (data.focus === 'wr' ? ` Enfoque win rate: además profit factor ≥ ${SB.num(data.wr_min_pf ?? 1.2, 1)}.` : '');
    }

    window.sbDelete = async function (id) {
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'warning', title: `¿Eliminar la búsqueda #${id}?`,
            text: 'Se borran la búsqueda y sus resultados. Los backtests ya creados en el historial no se tocan.',
            showCancelButton: true, confirmButtonText: 'Sí, eliminar', cancelButtonText: 'Volver', confirmButtonColor: '#ef4444' });
        if (!ok.isConfirmed) return;
        try {
            await SB.api(URL_DESTROY.replace('__RUN__', id), { method: 'DELETE' });
            window.location.href = id === RUN_ID ? URL_STRATEGIES : window.location.href;
        } catch (e) { Swal.fire({ ...SB.SWAL, icon: 'error', title: 'No se pudo eliminar', text: e.message }); }
    };

    window.sbCancel = async function () {
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'warning', title: '¿Cancelar la búsqueda?', text: 'Se detiene en unos segundos y no guarda resultados.',
            showCancelButton: true, confirmButtonText: 'Sí, cancelar', cancelButtonText: 'Seguir', confirmButtonColor: '#ef4444' });
        if (!ok.isConfirmed) return;
        $('sbCancel').disabled = true;
        try { await SB.api(URL_CANCEL, { method: 'POST' }); } catch (e) { Swal.fire({ ...SB.SWAL, icon: 'error', title: 'Error', text: e.message }); }
        clearTimeout(timer); poll();
    };

    window.sbCreate = async function () {
        const ids = [...selected], v3 = data.version >= 3;
        const which = !v3 ? '<b>las monedas que quedan</b> en su configuración' : (data.mode === 'symbol' ? '<b>su moneda</b>' : '<b>todas las monedas probadas</b>');
        const ok = await Swal.fire({ ...SB.SWAL, icon: 'question', title: 'Crear en el historial',
            html: `Se correrán y guardarán <b>${ids.length}</b> backtest(s), cada uno con ${which}, por el mismo camino que la pantalla de Backtesting.<br><br>No se implementan en Paper: eso lo decides en el historial.`,
            showCancelButton: true, confirmButtonText: 'Crear', cancelButtonText: 'Volver' });
        if (!ok.isConfirmed) return;
        $(v3 ? 'sbCreate3' : 'sbCreate').disabled = true;
        try {
            const r = await SB.api(URL_CREATE, { method: 'POST', body: JSON.stringify({ rows: ids, symbols: 'survivors' }) });
            ids.forEach(id => pending.add(id)); selected.clear();
            Swal.fire({ ...SB.SWAL, icon: 'success', title: 'En cola', html: SB.esc(r.message) + (URL_HISTORY ? `<br><br><a href="${URL_HISTORY}" style="color:#C4B5FD;text-decoration:underline">Ir al historial</a>` : ''),
                timer: 4000 });
            (v3 ? renderV3 : renderResults)(); clearTimeout(timer); timer = setTimeout(loadResults, 3000);
        } catch (e) { Swal.fire({ ...SB.SWAL, icon: 'error', title: 'No se pudo crear', text: e.message }); (v3 ? renderV3 : renderResults)(); }
    };

    poll();
})();
</script>
@endpush
@endsection

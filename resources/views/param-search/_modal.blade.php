{{-- Ventana "Buscar configuración" (Estrategias). Requiere _styles y _helpers. --}}
<div class="sb-overlay" id="sbModal" role="dialog" aria-modal="true" aria-labelledby="sbTitle">
    <div class="sb-modal">
        <div class="sb-mh">
            <div><h2 id="sbTitle">🔍 Buscar configuración</h2><p id="sbSub">Cargando…</p></div>
            <button type="button" class="sb-x" onclick="sbClose()" aria-label="Cerrar">✕</button>
        </div>
        <div class="sb-mb" id="sbBody">
            <div id="sbActive" class="sb-alert warn" style="display:none"></div>
            <div>
                <span class="sb-t">Temporalidad</span>
                <div class="sb-seg" id="sbIntervals"></div>
                <div class="sb-help">Solo 15 minutos o más. Puedes marcar varias: cada una suma su tiempo.</div>
            </div>
            <div>
                <span class="sb-t">Monedas para buscar <span style="text-transform:none;font-weight:400" class="sb-muted" id="sbLimits"></span></span>
                <div class="sb-coins" id="sbCoins"></div>
                <div class="sb-help">La búsqueda elige SOLO con estas monedas y con los primeros 2/3 del periodo.</div>
            </div>
            <div>
                <label class="sb-switch"><input type="checkbox" id="sbValidate" checked> Validar las robustas en las demás monedas activas</label>
                <div class="sb-coins" style="margin-top:6px" id="sbValCoins"></div>
                <div class="sb-help">Monedas que la búsqueda nunca vio: si también ganan ahí, la ventaja es más creíble.</div>
            </div>
            <div>
                <span class="sb-t">Fijo (no editable)</span>
                <div class="sb-lock" id="sbFixed"></div>
            </div>
            <div class="sb-est"><span>Tiempo estimado: <b id="sbEst">—</b> · prioridad baja, 1 proceso</span><span class="sb-muted" style="font-size:11px">1 búsqueda a la vez</span></div>
        </div>
        <div class="sb-mf">
            <button type="button" class="sb-btn gray" onclick="sbClose()">Cancelar</button>
            <button type="button" class="sb-btn purple" id="sbStart" onclick="sbStart()">Iniciar búsqueda</button>
        </div>
    </div>
</div>

@push('scripts')
<script>
(function () {
    const URL_OPTIONS = @json(route('strategies.search.options', '__ID__'));
    const URL_START = @json(route('strategies.search.start', '__ID__'));
    const URL_SHOW = @json(route('strategies.search.show', '__RUN__'));
    const PREFERRED = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'LINKUSDT'];
    let opt = null, strategyId = null, picked = new Set(), coins = new Set();

    const $ = id => document.getElementById(id);
    function inter(lists) { return lists.length ? lists.reduce((a, b) => a.filter(x => b.includes(x))) : []; }

    function render() {
        const L = opt.limits;
        $('sbIntervals').innerHTML = opt.intervals.map(iv => {
            const n = (opt.symbols[iv] || []).length, ok = n >= L.min_symbols;
            return `<button type="button" class="sb-opt${picked.has(iv) ? ' on' : ''}" data-iv="${iv}" ${ok ? '' : 'disabled title="Sin datos suficientes"'}>
                      <b>${SB.LABEL[iv] || iv}</b><small>${ok ? '≈ ' + (opt.minutes[iv] || 5) + ' min' : 'sin datos'}${iv === 'D' && ok ? ' · ' + n + ' monedas' : ''}</small></button>`;
        }).join('');
        const avail = inter([...picked].map(iv => opt.symbols[iv] || []));
        [...coins].forEach(c => { if (!avail.includes(c)) coins.delete(c); });
        $('sbCoins').innerHTML = avail.length ? avail.map(s => `<button type="button" class="sb-coin${coins.has(s) ? ' on' : ''}" data-c="${s}">${s}</button>`).join('')
            : '<span class="sb-muted" style="font-size:11px">Elige una temporalidad.</span>';
        const val = avail.filter(s => !coins.has(s));
        $('sbValCoins').innerHTML = $('sbValidate').checked ? (val.length ? val.map(s => `<span class="sb-coin val">${s.replace('USDT', '')}</span>`).join('')
            : '<span class="sb-muted" style="font-size:11px">No quedan monedas para validar.</span>') : '';
        $('sbLimits').textContent = `(${L.min_symbols} a ${L.max_symbols} · ${coins.size} elegidas)`;
        const mins = [...picked].reduce((a, iv) => a + (opt.minutes[iv] || 5), 0);
        $('sbEst').textContent = mins ? '≈ ' + mins + ' min' : 'elige al menos una';
        const okCount = coins.size >= L.min_symbols && coins.size <= L.max_symbols;
        $('sbStart').disabled = !!opt.active || !picked.size || !okCount;
        document.querySelectorAll('#sbIntervals .sb-opt:not([disabled])').forEach(b => b.onclick = () => {
            picked.has(b.dataset.iv) ? picked.delete(b.dataset.iv) : picked.add(b.dataset.iv); render(); });
        document.querySelectorAll('#sbCoins .sb-coin').forEach(b => b.onclick = () => {
            const c = b.dataset.c;
            if (coins.has(c)) coins.delete(c); else if (coins.size < L.max_symbols) coins.add(c);
            render(); });
    }

    window.sbOpen = async function (id, name) {
        strategyId = id; opt = null; picked = new Set(['240']); coins = new Set();
        $('sbSub').textContent = name + ' · cargando opciones…';
        $('sbModal').classList.add('on');
        try {
            opt = await SB.api(URL_OPTIONS.replace('__ID__', id));
        } catch (e) { $('sbSub').textContent = 'No se pudieron cargar las opciones: ' + e.message; return; }
        $('sbSub').textContent = `${name} · prueba ${opt.limits.samples} combinaciones y te muestra las mejores. No crea nada hasta que tú elijas.`;
        $('sbFixed').innerHTML = `<div><span>Periodo</span>${opt.limits.months} meses</div><div><span>Comisión</span>${opt.fixed.commission_pct}% por lado</div>
            <div><span>Slippage</span>${opt.fixed.slippage_pct}% por lado</div><div><span>Riesgo</span>${opt.fixed.risk_pct}% por operación</div>`;
        const a = opt.active;
        $('sbActive').style.display = a ? 'block' : 'none';
        if (a) $('sbActive').innerHTML = `Ya hay una búsqueda en curso (${SB.esc(a.strategy)} · ${(a.intervals || []).map(i => SB.LABEL[i]).join(', ')}). Solo una a la vez para no afectar la operación. <a href="${URL_SHOW.replace('__RUN__', a.id)}" style="color:#fff;text-decoration:underline">Ver progreso</a>`;
        (opt.symbols['240'] || []).filter(s => PREFERRED.includes(s)).forEach(s => coins.add(s));
        render();
    };
    window.sbClose = () => $('sbModal').classList.remove('on');
    $('sbValidate').addEventListener('change', render);
    $('sbModal').addEventListener('click', e => { if (e.target.id === 'sbModal') sbClose(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') sbClose(); });

    window.sbStart = async function () {
        $('sbStart').disabled = true;
        try {
            const r = await SB.api(URL_START.replace('__ID__', strategyId), { method: 'POST',
                body: JSON.stringify({ intervals: [...picked], symbols: [...coins], validate: $('sbValidate').checked }) });
            window.location.href = URL_SHOW.replace('__RUN__', r.run.id);
        } catch (e) {
            Swal.fire({ ...SB.SWAL, icon: 'error', title: 'No se pudo iniciar', text: e.message });
            $('sbStart').disabled = false;
        }
    };
})();
</script>
@endpush

{{-- Ventana "Buscar configuración" (Estrategias). Enfoque: ganancia | win rate | consistencia. Modos: por temporalidad
     (1 temporalidad, 1..N monedas) | por moneda (1..5 monedas, todas las temporalidades con datos, cada moneda por separado).
     Para una estrategia o para todas (en cola). Requiere _styles y _helpers. --}}
<div class="sb-overlay" id="sbModal" role="dialog" aria-modal="true" aria-labelledby="sbTitle">
    <div class="sb-modal">
        <div class="sb-mh">
            <div><h2 id="sbTitle">🔍 Buscar configuración</h2><p id="sbSub">Cargando…</p></div>
            <button type="button" class="sb-x" onclick="sbClose()" aria-label="Cerrar">✕</button>
        </div>
        <div class="sb-mb" id="sbBody">
            <div id="sbActive" class="sb-alert warn" style="display:none;order:0"></div>
            <div style="order:0">
                <span class="sb-t">¿Qué buscas?</span>
                <div class="sb-focus" id="sbFocus"></div>
                <div class="sb-help">En los tres enfoques solo se aceptan configuraciones que ganan. El enfoque decide qué combinaciones se prueban y el orden de los resultados.</div>
            </div>
            <div style="order:0">
                <span class="sb-t">¿Cómo quieres buscar?</span>
                <div class="sb-mode" id="sbModes">
                    <button type="button" data-mode="interval"><b>Por temporalidad</b><small>1 temporalidad · 1 a todas las monedas</small></button>
                    <button type="button" data-mode="symbol"><b>Por moneda</b><small>1 a 5 monedas · todas las temporalidades · cada moneda por separado</small></button>
                </div>
            </div>
            <div id="sbIvBox">
                <span class="sb-t" id="sbIvTitle">Temporalidad</span>
                <div class="sb-seg" id="sbIntervals"></div>
                <div class="sb-help" id="sbIvHelp"></div>
            </div>
            <div id="sbCoinBox">
                <div class="sb-rowh">
                    <span class="sb-t" style="margin:0">Monedas <span style="text-transform:none;font-weight:400" class="sb-muted" id="sbLimits"></span></span>
                    <span id="sbAllNone" style="font-size:11px"><button type="button" class="sb-link" data-all="1">Todas</button> <span class="sb-muted">·</span> <button type="button" class="sb-link" data-all="0">Ninguna</button></span>
                </div>
                <div class="sb-coins" id="sbCoins"></div>
                <div class="sb-help" id="sbCoinHelp"></div>
            </div>
            <div class="sb-rule" id="sbRule" style="order:3"></div>
            <div class="sb-lock" id="sbFixed" style="order:4"></div>
            <div class="sb-est" id="sbEst" style="order:5"></div>
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
    const URL_START_ALL = @json(route('strategies.search.start-all'));
    const URL_SHOW = @json(route('strategies.search.show', '__RUN__'));
    const PREFERRED = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT'];
    const FOCUS = {
        gain: ['Ordena por retorno total de 24 meses.', 'Prueba objetivos amplios y trailing.', 'Se ordena por retorno total.'],
        wr:   ['Ordena por % de trades ganadores.', 'Prueba objetivos cercanos y break-even temprano.',
               'Además exige profit factor ≥ 1,2, para que ganar seguido no signifique perder plata.'],
        cons: ['Ordena por % de meses en positivo.', 'Prueba filtros de régimen, macro y volumen.', 'Se ordena por meses en positivo; empates, por retorno.'],
    };
    let opt = null, target = null, mode = 'interval', iv = null, coins = new Set(), focus = 'gain';

    const $ = id => document.getElementById(id);
    const short = s => s.replace('USDT', '');
    const union = () => [...new Set(opt.intervals.flatMap(i => opt.symbols[i] || []))].sort();
    const ivsFor = cs => cs.length ? opt.intervals.filter(i => cs.every(c => (opt.symbols[i] || []).includes(c))) : [];
    const maxSym = () => mode === 'symbol' ? opt.limits.max_symbols_symbol_mode : Infinity;
    const available = () => mode === 'interval' ? (iv ? (opt.symbols[iv] || []) : []) : union();

    function render() {
        document.querySelectorAll('#sbModes button').forEach(b => {
            b.classList.toggle('on', b.dataset.mode === mode); b.setAttribute('aria-pressed', b.dataset.mode === mode); });
        $('sbFocus').innerHTML = Object.entries(opt.focuses || {}).map(([k, label]) => `<button type="button" data-focus="${k}"
            class="${k === focus ? 'on' : ''}" aria-pressed="${k === focus}"><b>${SB.esc(label)}</b><small>${SB.esc(FOCUS[k][0])}</small>
            <small class="sb-sub">${SB.esc(FOCUS[k][1])}</small></button>`).join('');
        document.querySelectorAll('#sbFocus button').forEach(b => b.onclick = () => { focus = b.dataset.focus; render(); });
        $('sbRule').innerHTML = `Una configuración se acepta solo si <b>gana en los primeros 16 meses</b> (donde se elige) <b>y también en los
            últimos 8</b> (que nunca se usan para elegir), con <b>${opt.limits.min_trades ?? 30} o más operaciones</b>`
            + (mode === 'interval' ? ', en al menos <b>¾ de las monedas</b> elegidas (las métricas son de todas).' : ', en cada moneda por separado.')
            + ` <span class="sb-muted">${SB.esc(FOCUS[focus][2])}</span>`;
        const avail = available();
        [...coins].forEach(c => { if (!avail.includes(c)) coins.delete(c); });

        if (mode === 'interval') {
            $('sbIvTitle').textContent = 'Temporalidad';
            $('sbIntervals').innerHTML = opt.intervals.map(i => {
                const n = (opt.symbols[i] || []).length, locked = !n || (iv && i !== iv);
                return `<button type="button" class="sb-opt${i === iv ? ' on' : ''}${iv && i !== iv ? ' dis' : ''}" data-iv="${i}" ${locked ? 'disabled' : ''}>
                          <b>${SB.LABEL[i] || i}</b><small>${n ? n + ' monedas' : 'sin datos'}</small></button>`;
            }).join('');
            $('sbIvHelp').textContent = iv ? `${SB.LABEL[iv] || iv} elegida: las demás quedan bloqueadas. Tócala de nuevo para cambiar.` : 'Elige una temporalidad.';
        } else {
            const inc = ivsFor([...coins]);
            $('sbIvTitle').textContent = 'Temporalidades que se probarán';
            $('sbIntervals').innerHTML = opt.intervals.map(i => `<span class="sb-opt ${inc.includes(i) ? 'inc' : 'dis'}"><b>${SB.LABEL[i] || i}</b>
                <small>${inc.includes(i) ? '✓ incluida' : (coins.size ? 'sin datos' : '—')}</small></span>`).join('');
            $('sbIvHelp').textContent = !coins.size ? `Elige de 1 a ${maxSym()} monedas.` : (inc.length
                ? 'Se prueban todas las temporalidades donde las monedas elegidas tienen datos.'
                : 'Esas monedas no tienen datos en ninguna temporalidad común.');
        }

        const full = coins.size >= maxSym();
        $('sbCoins').innerHTML = !avail.length ? '<span class="sb-muted" style="font-size:11px">Elige una temporalidad.</span>'
            : avail.map(s => `<button type="button" class="sb-coin${coins.has(s) ? ' on' : ''}" data-c="${s}" ${!coins.has(s) && full ? 'disabled' : ''}>${SB.esc(short(s))}</button>`).join('');
        $('sbLimits').textContent = mode === 'interval' ? `(${coins.size} de ${avail.length})` : `(${coins.size} de máx. ${opt.limits.max_symbols_symbol_mode})`;
        $('sbAllNone').style.display = mode === 'interval' && avail.length ? '' : 'none';
        $('sbCoinHelp').textContent = mode === 'symbol' ? `Al llegar a ${maxSym()}, las demás se bloquean.` : '';
        $('sbIvBox').style.order = mode === 'symbol' ? 2 : 1;
        $('sbCoinBox').style.order = mode === 'symbol' ? 1 : 2;

        const ok = coins.size > 0 && (mode === 'interval' ? !!iv : ivsFor([...coins]).length > 0);
        const nIv = mode === 'interval' ? (iv ? 1 : 0) : ivsFor([...coins]).length;
        const bt = coins.size * nIv * opt.limits.samples;
        $('sbEst').style.display = bt ? '' : 'none';
        $('sbEst').innerHTML = `<span>${coins.size} moneda(s) × ${nIv} temporalidad(es) × ${opt.limits.samples} combinaciones = ${bt.toLocaleString('es-CO')} backtests</span>
            <b>≈ ${Math.max(1, Math.round((bt * 0.35 + coins.size * 10) / 60))} min</b>`;
        $('sbStart').disabled = !!(opt.active && !target.all) || !ok;

        document.querySelectorAll('#sbIntervals button.sb-opt:not([disabled])').forEach(b => b.onclick = () => {
            iv = iv === b.dataset.iv ? null : b.dataset.iv; render(); });
        document.querySelectorAll('#sbCoins .sb-coin:not([disabled])').forEach(b => b.onclick = () => {
            const c = b.dataset.c; coins.has(c) ? coins.delete(c) : coins.add(c); render(); });
    }

    document.querySelectorAll('#sbModes button').forEach(b => b.onclick = () => {
        if (!opt || mode === b.dataset.mode) return;
        mode = b.dataset.mode;
        if (mode === 'symbol') coins = new Set([...coins].slice(0, opt.limits.max_symbols_symbol_mode));
        else if (!iv) iv = opt.intervals.find(i => (opt.symbols[i] || []).length) || null;
        render();
    });
    document.querySelectorAll('#sbAllNone [data-all]').forEach(b => b.onclick = () => {
        coins = new Set(b.dataset.all === '1' ? available() : []); render(); });

    async function open(t, optionsId) {
        target = t; opt = null; mode = 'interval'; iv = '240'; coins = new Set(); focus = 'gain';
        $('sbTitle').textContent = t.all ? '🔍 Buscar en todas las estrategias' : '🔍 Buscar configuración';
        $('sbSub').textContent = 'Cargando opciones…';
        $('sbStart').textContent = t.all ? `Buscar en las ${t.all} estrategias` : 'Iniciar búsqueda';
        $('sbStart').disabled = true;
        $('sbModal').classList.add('on');
        try { opt = await SB.api(URL_OPTIONS.replace('__ID__', optionsId)); }
        catch (e) { $('sbSub').textContent = 'No se pudieron cargar las opciones: ' + e.message; return; }

        const what = `prueba ${opt.limits.samples} combinaciones por temporalidad y te muestra solo las que ganan. No crea nada hasta que tú elijas.`;
        $('sbSub').textContent = t.all ? `Una búsqueda por estrategia activa (${t.all}); quedan en cola y corren una tras otra · ${what}` : `${t.name} · ${what}`;
        $('sbFixed').innerHTML = `<div><span>Periodo</span>${opt.limits.months} meses</div><div><span>Comisión</span>${opt.fixed.commission_pct}% por lado</div>
            <div><span>Slippage</span>${opt.fixed.slippage_pct}% por lado</div><div><span>Riesgo</span>${opt.fixed.risk_pct}% por operación</div>`;
        const a = t.all ? null : opt.active;
        $('sbActive').style.display = a ? 'block' : 'none';
        if (a) $('sbActive').innerHTML = `Esta estrategia ya tiene una búsqueda ${a.status === 'queued' ? 'en cola' : 'en curso'}.
            <a href="${URL_SHOW.replace('__RUN__', a.id)}" style="color:#fff;text-decoration:underline">Ver progreso</a>`;
        if (!(opt.symbols[iv] || []).length) iv = opt.intervals.find(i => (opt.symbols[i] || []).length) || null;
        (opt.symbols[iv] || []).filter(s => PREFERRED.includes(s)).forEach(s => coins.add(s));
        render();
    }
    window.sbOpen = (id, name) => open({ id, name }, id);
    window.sbOpenAll = (count, anyStrategyId) => open({ all: count }, anyStrategyId);
    window.sbClose = () => $('sbModal').classList.remove('on');
    $('sbModal').addEventListener('click', e => { if (e.target.id === 'sbModal') sbClose(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') sbClose(); });

    window.sbStart = async function () {
        $('sbStart').disabled = true;
        const body = JSON.stringify({ mode, focus, intervals: mode === 'interval' ? [iv] : [], symbols: [...coins] });
        try {
            if (target.all) {
                const r = await SB.api(URL_START_ALL, { method: 'POST', body });
                const made = Object.values(r.created || {}), skip = Object.entries(r.skipped || {});
                await Swal.fire({ ...SB.SWAL, icon: made.length ? 'success' : 'warning',
                    title: made.length ? `${made.length} búsqueda(s) en cola` : 'No se encoló ninguna búsqueda',
                    html: (made.length ? 'Corren una tras otra: ' + made.map(SB.esc).join(', ') + '.' : '')
                        + (skip.length ? '<br><br><b>Se saltaron:</b><br>' + skip.map(([n, m]) => SB.esc(n) + ': ' + SB.esc(m)).join('<br>') : '') });
                window.location.reload();
            } else {
                const r = await SB.api(URL_START.replace('__ID__', target.id), { method: 'POST', body });
                window.location.href = URL_SHOW.replace('__RUN__', r.run.id);
            }
        } catch (e) {
            Swal.fire({ ...SB.SWAL, icon: 'error', title: 'No se pudo iniciar', text: e.message });
            $('sbStart').disabled = false;
        }
    };
})();
</script>
@endpush

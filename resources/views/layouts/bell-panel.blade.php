{{-- Desplegable de la campana (una vez por página). Al abrirlo se cargan los últimos avisos y se marcan como leídos. --}}
<style>
    .tr-bell { position: relative; background: var(--color-surface-raised); border: 1px solid var(--color-border-soft); border-radius: 8px;
               width: 34px; height: 32px; display: inline-grid; place-items: center; font-size: 14px; line-height: 1; cursor: pointer; flex-shrink: 0; }
    .tr-bell-n { position: absolute; top: -7px; right: -7px; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px; background: var(--color-loss);
                 color: #fff; font-size: 10px; font-style: normal; font-weight: 700; display: grid; place-items: center; border: 2px solid var(--color-surface); }
    .tr-drop { position: fixed; top: 64px; right: 16px; width: 360px; max-width: calc(100vw - 32px); max-height: 72vh; overflow-y: auto; background: #1f2937;
               border: 1px solid #2b3646; border-radius: 12px; box-shadow: 0 20px 50px rgba(0, 0, 0, .5); z-index: 70; display: none; }
    .tr-drop.on { display: block; }
    .tr-drop h4 { margin: 0; padding: 12px 14px; font-size: 13px; font-weight: 600; color: var(--color-text-primary); border-bottom: 1px solid #2b3646; }
    .tr-nt { display: grid; grid-template-columns: 22px 1fr; gap: 8px; padding: 10px 14px; border-top: 1px solid #2b3646; font-size: 12px;
             color: var(--color-text-primary); text-decoration: none; }
    .tr-nt:first-child { border-top: 0; }
    .tr-nt:hover { background: rgba(255, 255, 255, .03); }
    .tr-nt.unread { background: rgba(139, 92, 246, .07); }
    .tr-nt b { display: block; font-weight: 600; }
    .tr-nt span.b { display: block; color: var(--color-text-secondary); }
    .tr-nt small { display: block; color: var(--color-text-muted); font-size: 10px; margin-top: 2px; }
    .tr-nt-empty { padding: 16px 14px; font-size: 12px; color: var(--color-text-muted); }
    .tr-all { display: block; text-align: center; padding: 10px; font-size: 12px; color: #A78BFA; border-top: 1px solid #2b3646; text-decoration: none; }
</style>
<div class="tr-drop" id="trDrop" role="dialog" aria-label="Avisos">
    <h4>Avisos</h4>
    <div id="trDropList"><div class="tr-nt-empty">Cargando…</div></div>
    <a class="tr-all" href="{{ route('notifications.index') }}">Ver todos los avisos →</a>
</div>
<script>
(function () {
    const drop = document.getElementById('trDrop'), list = document.getElementById('trDropList');
    const URL_RECENT = @json(route('notifications.recent')), URL_READ = @json(route('notifications.read'));
    const URL_ALL = @json(route('notifications.index')), TOKEN = @json(csrf_token());
    const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    window.trBellToggle = async function (e) {
        e.stopPropagation();
        drop.style.top = (e.currentTarget.getBoundingClientRect().bottom + 8) + 'px';
        if (!drop.classList.toggle('on')) return;
        try {
            const r = await fetch(URL_RECENT, { headers: { Accept: 'application/json' }, credentials: 'same-origin' });
            if (!r.ok) throw new Error(r.status);
            const d = await r.json();
            list.innerHTML = d.items.length ? d.items.map(n => `<a class="tr-nt${n.unread ? ' unread' : ''}" href="${esc(n.url || URL_ALL)}">
                <span>${n.icon}</span><div><b>${esc(n.title)}</b>${n.body ? '<span class="b">' + esc(n.body) + '</span>' : ''}<small>${esc(n.ago)}</small></div></a>`).join('')
                : '<div class="tr-nt-empty">Sin avisos.</div>';
            if (d.unread > 0) {
                await fetch(URL_READ, { method: 'POST', headers: { 'X-CSRF-TOKEN': TOKEN, Accept: 'application/json' }, credentials: 'same-origin' });
                document.querySelectorAll('.tr-bell-n').forEach(b => b.remove());
            }
        } catch (err) {
            list.innerHTML = '<div class="tr-nt-empty">No se pudieron cargar los avisos.</div>';
        }
    };
    document.addEventListener('click', e => { if (drop.classList.contains('on') && !drop.contains(e.target)) drop.classList.remove('on'); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') drop.classList.remove('on'); });
})();
</script>

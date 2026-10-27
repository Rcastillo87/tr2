{{-- Lista de Estrategias: actualiza el chip de la búsqueda en curso sin recargar la página --}}
@push('scripts')
<script>
(function () {
    const chip = document.querySelector('[data-sb-active]');
    if (!chip) return;
    const label = chip.querySelector('span');
    async function tick() {
        let s;
        try { s = await SB.api(chip.dataset.sbStatusUrl); } catch (e) { return setTimeout(tick, 10000); }
        if (s.status === 'queued' || s.status === 'running') {
            label.textContent = s.status === 'queued' ? 'En cola · ' + chip.dataset.sbIvs
                : `Buscando ${chip.dataset.sbIvs} · ${s.progress_done}/${s.progress_total}`;
            return setTimeout(tick, 5000);
        }
        chip.querySelector('.sb-dot')?.remove();
        chip.classList.add(s.status === 'done' ? ((s.validated || 0) > 0 ? 'ok' : 'muted') : 'bad');
        label.textContent = s.status === 'done' ? `Búsqueda ${chip.dataset.sbIvs} terminada · ${s.validated || 0} validada(s) · ver resultados`
            : `Búsqueda ${chip.dataset.sbIvs} ${s.status === 'cancelled' ? 'cancelada' : 'falló'}`;
        document.querySelectorAll('.btn-search[disabled]').forEach(b => { b.disabled = false; b.removeAttribute('title'); });
    }
    setTimeout(tick, 3000);
})();
</script>
@endpush

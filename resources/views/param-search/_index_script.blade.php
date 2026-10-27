{{-- Lista de Estrategias: actualiza los chips de las búsquedas en cola / en curso sin recargar la página --}}
@push('scripts')
<script>
(function () {
    document.querySelectorAll('[data-sb-active]').forEach(chip => {
        const label = chip.querySelector('span');
        async function tick() {
            let s;
            try { s = await SB.api(chip.dataset.sbStatusUrl); } catch (e) { return setTimeout(tick, 10000); }
            if (s.status === 'queued' || s.status === 'running') {
                if (s.status === 'running') label.textContent = `Buscando ${chip.dataset.sbIvs} · ${s.progress_done}/${s.progress_total}`;
                return setTimeout(tick, s.status === 'running' ? 5000 : 15000);
            }
            chip.querySelector('.sb-dot')?.remove();
            const n = s.survivors ?? s.validated ?? 0;
            chip.classList.add(s.status === 'done' ? (n > 0 ? 'ok' : 'muted') : 'bad');
            label.textContent = s.status === 'done' ? `Búsqueda ${chip.dataset.sbIvs} terminada · ${n} rentable(s) · ver resultados`
                : `Búsqueda ${chip.dataset.sbIvs} ${s.status === 'cancelled' ? 'cancelada' : 'falló'}`;
            const btn = document.querySelector(`.btn-search[data-sb-btn="${chip.dataset.sbStrategy}"]`);
            if (btn) { btn.disabled = false; btn.removeAttribute('title'); }
        }
        setTimeout(tick, 3000);
    });
})();
</script>
@endpush

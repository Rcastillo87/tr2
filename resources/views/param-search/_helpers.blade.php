{{-- Utilidades JS compartidas del módulo "Buscar configuración" --}}
<script>
window.SB = window.SB || (function () {
    const LABEL = { '15': '15m', '60': '1h', '120': '2h', '240': '4h', 'D': '1D' };
    const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    // Mismos umbrales que App\Helpers\RatingHelper::getColor
    const starColor = r => r >= 4 ? '#F5C518' : (r >= 3 ? '#EF9F27' : (r >= 2 ? '#E8832A' : '#E24B4A'));
    const stars = r => { const n = Math.max(0, Math.min(5, Math.round(r))); return '★'.repeat(n) + '☆'.repeat(5 - n); };
    const num = (v, d = 2) => (v === null || v === undefined || isNaN(v)) ? '—' : Number(v).toFixed(d);
    const pct = (v, d = 1) => (v === null || v === undefined || isNaN(v)) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(d) + '%';
    const cls = v => v > 0 ? 'sb-pos' : (v < 0 ? 'sb-neg' : '');
    const pfCls = v => v >= 1 ? 'sb-pos' : 'sb-neg';
    function cfgTags(c) {
        const t = [];
        t.push(['SL ' + c.sl_pct + '%'], ['TP ' + c.tp_pct + '%']);
        t.push([Number(c.be_pct) >= 99 ? 'Sin BE' : 'BE ' + c.be_pct + '%']);
        if (c.trailing_mode === 'fixed') t.push(['Trailing fijo ' + c.trailing_distance_pct + '% · act. ' + c.trailing_activation_buffer_pct + '%']);
        else if (c.trailing_mode === 'atr') t.push(['Trailing ATR ×' + c.trailing_atr_mult + ' · act. ' + c.trailing_activation_buffer_pct + '%']);
        else t.push(['Sin trailing']);
        if (c.regime_filter) t.push(['Régimen', 1]);
        if (c.macro_trend_filter) t.push(['Macro H4', 1]);
        if (c.btc_trend_filter) t.push(['Tendencia BTC', 1]);
        if (c.volume_filter) t.push(['Volumen ' + c.volume_filter_period + ' ×' + c.volume_filter_mult, 1]);
        if (c.close_on_opposite) t.push(['Señal opuesta', 1]);
        t.push([Number(c.max_duration) > 0 ? 'Máx ' + c.max_duration + ' velas' : 'Sin límite de duración']);
        return '<div class="sb-cfg">' + t.map(([s, y]) => '<span class="sb-tag' + (y ? ' y' : '') + '">' + esc(s) + '</span>').join('') + '</div>';
    }
    function ago(iso) {
        if (!iso) return '';
        const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
        if (m < 1) return 'ahora'; if (m < 60) return 'hace ' + m + ' min';
        const h = Math.round(m / 60); return h < 48 ? 'hace ' + h + ' h' : 'hace ' + Math.round(h / 24) + ' d';
    }
    async function api(url, opts = {}) {
        const r = await fetch(url, { headers: { 'Accept': 'application/json', 'Content-Type': 'application/json',
            'X-CSRF-TOKEN': '{{ csrf_token() }}', 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin', ...opts });
        let body = {}; try { body = await r.json(); } catch (e) { /* respuesta no JSON */ }
        if (!r.ok) throw new Error(body.error || body.message || ('Error ' + r.status));
        return body;
    }
    const SWAL = { background: '#1f2937', color: '#f3f4f6', confirmButtonColor: '#8B5CF6', cancelButtonColor: '#374151' };
    return { LABEL, esc, starColor, stars, num, pct, cls, pfCls, cfgTags, ago, api, SWAL };
})();
</script>

{{-- Estilos del módulo "Buscar configuración" (autocontenidos: no dependen de recompilar Tailwind) --}}
<style>
    .sb-accent { --sb-a: #8B5CF6; --sb-a-soft: rgba(139, 92, 246, .14); }
    .btn-search { background: #8B5CF6; }
    .btn-search[disabled] { opacity: .45; cursor: not-allowed; transform: none; filter: none; }
    .sb-chip { display: inline-flex; align-items: center; gap: 6px; margin-top: 5px; padding: 2px 8px; border-radius: 999px; font-size: 10px;
               background: rgba(139, 92, 246, .14); color: #C4B5FD; border: 1px solid rgba(139, 92, 246, .35); text-decoration: none; }
    .sb-chip.ok { background: #16331F; color: var(--color-profit); border-color: #1E4A2E; }
    .sb-chip.bad { background: #3A1A1C; color: #F2545B; border-color: #5A2226; }
    .sb-chip.muted { background: var(--color-surface-raised); color: var(--color-text-muted); border-color: var(--color-border-strong); }
    .sb-dot { width: 6px; height: 6px; border-radius: 50%; background: #A78BFA; animation: sbPulse 1.2s infinite; }
    @keyframes sbPulse { 50% { opacity: .25; } }

    .sb-overlay { position: fixed; inset: 0; background: rgba(3, 6, 10, .72); display: none; align-items: flex-start; justify-content: center;
                  padding: 40px 16px; overflow-y: auto; z-index: 60; }
    .sb-overlay.on { display: flex; }
    .sb-modal { background: #1f2937; border: 1px solid var(--color-border-strong); border-radius: 12px; width: 100%; max-width: 640px;
                box-shadow: 0 20px 50px rgba(0, 0, 0, .5); color: var(--color-text-primary); }
    .sb-mh { padding: 16px 20px; border-bottom: 1px solid #2b3646; display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
    .sb-mh h2 { margin: 0; font-size: 16px; font-weight: 600; }
    .sb-mh p { margin: 3px 0 0; font-size: 11px; color: var(--color-text-secondary); }
    .sb-x { background: none; border: 0; color: var(--color-text-muted); font-size: 18px; line-height: 1; cursor: pointer; }
    .sb-mb { padding: 16px 20px; display: grid; gap: 16px; }
    .sb-t { display: block; font-size: 11px; font-weight: 600; color: var(--color-text-secondary); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .04em; }
    .sb-help { font-size: 11px; color: var(--color-text-muted); margin-top: 5px; }
    .sb-seg { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
    .sb-opt { border: 1px solid var(--color-border-strong); background: var(--color-surface); border-radius: 8px; padding: 8px 6px; text-align: center;
              color: var(--color-text-secondary); cursor: pointer; }
    .sb-opt b { display: block; font-size: 13px; color: var(--color-text-primary); }
    .sb-opt small { font-size: 10px; color: var(--color-text-muted); }
    .sb-opt.on { border-color: #8B5CF6; background: rgba(139, 92, 246, .14); }
    .sb-opt.on b { color: #DDD6FE; }
    .sb-opt[disabled] { opacity: .4; cursor: not-allowed; }
    .sb-coins { display: flex; flex-wrap: wrap; gap: 6px; }
    .sb-coin { border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-text-secondary); border-radius: 999px;
               padding: 4px 10px; font-size: 11px; cursor: pointer; }
    .sb-coin.on { border-color: var(--color-info); background: rgba(77, 143, 232, .15); color: #BFD6F6; }
    .sb-coin.val { border-style: dashed; color: var(--color-text-muted); cursor: default; }
    .sb-switch { display: flex; align-items: center; gap: 8px; font-size: 12px; cursor: pointer; }
    .sb-switch input, .sb-chk { accent-color: #8B5CF6; width: 15px; height: 15px; }
    .sb-lock { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: 8px; padding: 10px 12px;
               display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; font-size: 11px; }
    .sb-lock span { color: var(--color-text-muted); display: block; font-size: 10px; }
    .sb-est { display: flex; justify-content: space-between; align-items: center; gap: 10px; background: rgba(139, 92, 246, .14);
              border: 1px solid rgba(139, 92, 246, .35); border-radius: 8px; padding: 10px 12px; font-size: 12px; }
    .sb-est b { color: #DDD6FE; }
    .sb-mf { padding: 14px 20px; border-top: 1px solid #2b3646; display: flex; justify-content: flex-end; gap: 8px; }
    .sb-btn { border: 0; border-radius: 8px; padding: 9px 16px; font-size: 12px; font-weight: 500; color: #fff; cursor: pointer; white-space: nowrap;
              display: inline-flex; align-items: center; gap: 6px; text-decoration: none; transition: filter .2s; }
    .sb-btn:hover { filter: brightness(1.15); }
    .sb-btn[disabled] { opacity: .45; cursor: not-allowed; filter: none; }
    .sb-btn.gray { background: #374151; color: #e5e7eb; }
    .sb-btn.purple { background: #8B5CF6; }
    .sb-btn.red { background: rgba(239, 68, 68, .1); border: 1px solid rgba(127, 29, 29, .6); color: #f87171; }
    .sb-alert { border-radius: 8px; padding: 9px 12px; font-size: 11.5px; }
    .sb-alert.warn { background: #2A2213; border: 1px solid #4A3A18; color: #E8C77A; }
    .sb-alert.err { background: #3A1A1C; border: 1px solid #5A2226; color: #F8A4A8; }
    .sb-alert.info { background: rgba(77, 143, 232, .1); border: 1px solid rgba(77, 143, 232, .3); color: #BFD6F6; }

    .sb-card { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: 10px; }
    .sb-bar { height: 8px; border-radius: 999px; background: var(--color-surface-raised); overflow: hidden; margin: 10px 0 6px; }
    .sb-bar i { display: block; height: 100%; width: 0; background: linear-gradient(90deg, #7C3AED, #A78BFA); transition: width .6s; }
    .sb-steps { display: grid; gap: 6px; margin-top: 14px; font-size: 12px; }
    .sb-steps div { display: flex; gap: 8px; align-items: center; color: var(--color-text-secondary); }
    .sb-ok { color: var(--color-profit); } .sb-now { color: #C4B5FD; } .sb-wait { color: var(--color-text-muted); }
    .sb-pos { color: var(--color-profit); } .sb-neg { color: var(--color-loss); } .sb-muted { color: var(--color-text-muted); }
    .sb-sub { display: block; font-size: 10px; color: var(--color-text-muted); }
    .sb-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
    .sb-kpi { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: 8px; padding: 10px 12px; }
    .sb-kpi span { font-size: 10px; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: .04em; }
    .sb-kpi b { display: block; font-size: 18px; font-variant-numeric: tabular-nums; }
    table.sb-rs { width: 100%; min-width: 1100px; border-collapse: collapse; font-size: 12px; }
    table.sb-rs th { background: var(--color-surface-raised); color: var(--color-text-muted); font-weight: 500; padding: 9px 8px; text-align: left; white-space: nowrap; }
    table.sb-rs th.r, table.sb-rs td.r { text-align: right; }
    table.sb-rs td { padding: 10px 8px; border-top: 1px solid var(--color-border-soft); vertical-align: top; font-variant-numeric: tabular-nums; }
    table.sb-rs tr.off td { opacity: .5; }
    .sb-stars { font-size: 14px; letter-spacing: 1px; white-space: nowrap; }
    .sb-cfg { display: flex; flex-wrap: wrap; gap: 4px; }
    .sb-tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: var(--color-surface-raised); border: 1px solid var(--color-border-strong);
              color: var(--color-text-secondary); white-space: nowrap; }
    .sb-tag.y { border-color: #1E4A2E; color: var(--color-profit); background: #132A1B; }
    .sb-badge { font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 999px; white-space: nowrap; display: inline-block; }
    .sb-badge.ok { background: #16331F; color: var(--color-profit); }
    .sb-badge.no { background: #3A1A1C; color: var(--color-loss); }
    .sb-badge.int { background: rgba(77, 143, 232, .15); color: #9DC0F2; }
    .sb-badge.run { background: rgba(139, 92, 246, .14); color: #C4B5FD; }
    .sb-foot { position: sticky; bottom: 0; background: #151C27; border: 1px solid #8B5CF6; border-radius: 10px; padding: 10px 14px; display: flex;
               flex-wrap: wrap; gap: 10px; justify-content: space-between; align-items: center; box-shadow: 0 -6px 20px rgba(0, 0, 0, .35); z-index: 5; }
    .sb-foot select { background: var(--color-surface); color: var(--color-text-primary); border: 1px solid var(--color-border-strong); border-radius: 6px;
                      padding: 6px 8px; font-size: 12px; }
    .sb-hrow { display: flex; flex-wrap: wrap; gap: 8px 16px; justify-content: space-between; align-items: center; padding: 9px 12px;
               border-top: 1px solid var(--color-border-soft); font-size: 12px; }
    /* paso 4: modos, reglas y resultados v2 */
    .sb-mode { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .sb-mode button { text-align: left; border: 1px solid var(--color-border-strong); background: var(--color-surface); border-radius: 10px;
                      padding: 10px 12px; color: var(--color-text-secondary); cursor: pointer; }
    .sb-mode button b { display: block; color: var(--color-text-primary); font-size: 13px; margin-bottom: 2px; }
    .sb-mode button small { font-size: 11px; color: var(--color-text-muted); }
    .sb-mode button.on { border-color: #8B5CF6; background: rgba(139, 92, 246, .14); }
    .sb-opt.dis { opacity: .35; cursor: not-allowed; }
    span.sb-opt { cursor: default; }
    .sb-opt.inc { border-style: dashed; border-color: #5B4A8B; }
    .sb-coin[disabled] { opacity: .35; cursor: not-allowed; }
    .sb-rowh { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
    .sb-link { background: none; border: 0; color: #A78BFA; font-size: 11px; padding: 0; cursor: pointer; }
    .sb-rule { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: 8px; padding: 10px 12px;
               font-size: 11.5px; color: var(--color-text-secondary); }
    .sb-rule b { color: var(--color-text-primary); }
    .sb-badge.late { background: #16331F; color: var(--color-profit); }
    .sb-badge.early { background: #2A2213; color: #E8C77A; }
    .sb-dup { font-size: 10px; color: var(--color-text-muted); margin-top: 4px; }
    .sb-qd b { color: var(--color-profit); }
    .sb-cards { display: none; }
    @media (max-width: 760px) {
        .sb-kpis { grid-template-columns: repeat(2, 1fr); }
        .sb-kpis .sb-kpi:last-child { grid-column: span 2; }
        .sb-lock { grid-template-columns: repeat(2, 1fr); }
        .sb-seg { grid-template-columns: repeat(3, 1fr); }
        .sb-table { display: none; }
        .sb-cards { display: grid; gap: 10px; }
        .sb-rc { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: 10px; padding: 12px; }
        .sb-rc.off { opacity: .55; }
        .sb-rc-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
        .sb-rc-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 10px 0 2px; font-size: 12px; }
        .sb-rc-grid span { display: block; font-size: 10px; color: var(--color-text-muted); }
        .sb-foot { position: static; flex-direction: column; align-items: stretch; }
        .sb-foot .sb-btn { justify-content: center; }
        .sb-mode { grid-template-columns: 1fr; }
    }
</style>

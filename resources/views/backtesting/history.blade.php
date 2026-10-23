@extends('layouts.app')
@section('title', 'Historial de Backtests')
@section('header', 'Historial: ' . $strategy->name)

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

<div class="mb-4 flex justify-between items-center">
    <a href="{{ route('strategies.index') }}" class="text-[11px]" style="color:var(--color-text-muted);">← Volver a Estrategias</a>
    <a href="{{ route('backtesting.run') }}?strategy_id={{ $strategy->id }}" class="text-[11px] px-3 py-1.5 rounded bg-[#13233D] text-[var(--color-info)] border border-[#1E3A5F] font-medium">
        + Nuevo Backtest para esta Estrategia
    </a>
</div>

<div class="space-y-4">
    @forelse($backtests as $bt)
        @php
            $params = $bt->config_params ?? [];
            $metrics = $bt->metrics ?? [];
            
                        $sharpe = (float)($metrics['sharpe_ratio'] ?? 0);
            $wr = (float)($metrics['win_rate'] ?? 0);
            $pf = (float)($metrics['profit_factor'] ?? 0);
            $trades = (int)($metrics['total_trades'] ?? 0);

            // Leemos el retorno total y la consistencia
            $ret = (float)($metrics['total_return_pct'] ?? $metrics['avg_monthly_pnl'] ?? 0);
            $consist = (float)($metrics['consist_pct'] ?? 0);
            
            // El Rating ya viene calculado desde el backend (1.8)
            $rating = (float)($metrics['rating'] ?? 0);
            if ($rating == 0) {
                // Fallback por si es un backtest viejo sin rating
                $sWr = $wr >= 65 ? 5 : ($wr >= 55 ? 4 : ($wr >= 45 ? 3 : ($wr >= 35 ? 2 : 1)));
                $sSharpe = $sharpe >= 4 ? 5 : ($sharpe >= 3 ? 4 : ($sharpe >= 2 ? 3 : ($sharpe >= 1 ? 2 : 1)));
                $sPf = $pf >= 2.5 ? 5 : ($pf >= 2.0 ? 4 : ($pf >= 1.5 ? 3 : ($pf >= 1.0 ? 2 : 1)));
                $sRet = $ret >= 20 ? 5 : ($ret >= 10 ? 4 : ($ret >= 5 ? 3 : ($ret >= 2 ? 2 : 1)));
                $sCons = $consist >= 80 ? 5 : ($consist >= 60 ? 4 : ($consist >= 40 ? 3 : ($consist >= 20 ? 2 : 1)));
                $rating = round(($sWr + $sSharpe + $sPf + $sRet + $sCons) / 5, 1);
                if ($rating <= 0) $rating = 1.0;
            }

            $starColor = $rating >= 4 ? '#F5C518' : ($rating >= 3 ? '#EF9F27' : ($rating >= 2 ? '#E8832A' : '#E24B4A'));
            $isOperating = (isset($activeBacktestId) && $activeBacktestId == $bt->id);
        @endphp
        
        <div class="rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex items-center justify-between px-4 py-2.5 border-b" style="border-color:var(--color-border-soft);">
                <div class="flex items-center gap-3">
                    <span class="text-[12px] font-medium" style="color:var(--color-text-primary);">{{ $bt->updated_at->timezone('America/Bogota')->format('Y-m-d H:i') }}</span>
                    <span class="text-[11px] font-mono px-2 py-0.5 rounded" style="background:var(--color-surface-raised); color:var(--color-text-muted);">{{ implode(', ', $bt->symbols ?? []) }} / {{ $bt->interval }} / {{ $bt->months }} meses</span>
                </div>
                <div class="flex items-center gap-2">
                    @if($isOperating)
                        <span class="px-3 py-1 rounded text-[11px] font-medium border" style="background:#16331F; color:var(--color-profit); border-color:#1E4A2E;">🟢 OPERANDO EN PAPER</span>
                        <form method="POST" action="{{ route('backtesting.stop-paper', $bt) }}" id="stop-form-{{ $bt->id }}" style="display:inline;">
                            @csrf
                            <button type="button" onclick="confirmStop({{ $bt->id }})" class="text-[11px] px-2 py-1 rounded border transition-colors" style="background:#3A1A1C; color:var(--color-loss); border-color:#5A2226;">🛑 Detener</button>
                        </form>
                    @else
                        <form method="POST" action="{{ route('backtesting.implement-paper', $bt) }}" id="impl-form-{{ $bt->id }}" style="display:inline;">
                            @csrf
                            <button type="button" onclick="confirmImplement({{ $bt->id }})" class="text-[11px] px-3 py-1.5 rounded border font-medium transition-colors" style="background:#13233D; color:var(--color-info); border-color:#1E3A5F;">⚡ Implementar en Paper</button>
                        </form>
                        
                        <form method="POST" action="{{ route('backtesting.destroy-backtest', $bt) }}" id="del-form-{{ $bt->id }}" style="display:inline;">
                            @csrf @method('DELETE')
                            <button type="button" onclick="confirmDelete({{ $bt->id }})" class="text-[11px] px-2 py-1.5 rounded border transition-colors" style="background:#3A1A1C; color:var(--color-loss); border-color:#5A2226;">🗑 Eliminar</button>
                        </form>
                    @endif

                    <a href="{{ route('backtesting.run') }}?backtest_id={{ $bt->id }}" class="text-[11px] px-2 py-1.5 rounded border transition-colors" style="background:var(--color-surface-raised); color:var(--color-text-primary); border-color:var(--color-border-strong);">🔄 Probar de nuevo</a>
                </div>
            </div>

            <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:0; border-bottom:1px solid var(--color-border-soft);">
                @foreach([
                    ['Stop Loss', ($params['sl_pct'] ?? '—').'%'],
                    ['Take Profit 1', ($params['tp_pct'] ?? '—').'%'],
                    ['Break-even', ($params['be_pct'] ?? '—').'%'],
                    ['Duración', ($params['max_duration'] ?? '—').' velas'],
                    ['Riesgo/trade', ($params['risk_per_trade_pct'] ?? '—').'%'],
                ] as [$label, $value])
                <div class="px-2 py-2 text-center" style="border-right:1px solid var(--color-border-soft);">
                    <p class="text-[9px] mb-0.5" style="color:var(--color-text-muted);">{{ $label }}</p>
                    <p class="text-[9px] font-mono font-medium" style="color:var(--color-text-primary);">{{ $value }}</p>
                </div>
                @endforeach
            </div>

            <div class="px-4 py-3">
                <div class="flex items-center justify-between mb-2">
                    <div style="display:inline-flex; align-items:center; gap:6px; background:var(--color-surface-raised); border-radius:5px; padding:4px 10px;">
                        <span style="font-size:18px; line-height:1; color:{{ $starColor }};">{{ str_repeat('★', (int)round($rating)) . str_repeat('☆', 5 - (int)round($rating)) }}</span>
                        <span style="font-size:14px; font-weight:700; color:{{ $starColor }};">{{ $rating > 0 ? $rating : '—' }}</span>
                    </div>
                    <div class="flex gap-4"><span class="text-[11px]" style="color:var(--color-text-muted);"><b style="color:var(--color-text-primary);">{{ $trades }}</b> trades</span></div>
                </div>
                
                <div style="display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:4px;">
                    @foreach([
                        ['Win Rate', $sWr, number_format($wr, 2) . '%'],
                        ['Sharpe Ratio', $sSharpe, number_format($sharpe, 2)],
                        ['Ret. prom/mes', $sRet, number_format($ret, 2) . '%'],
                        ['Consistencia', $sCons, number_format($consist, 1) . '%'],
                        ['Profit Factor', $sPf, number_format($pf, 2)],
                    ] as [$mlabel, $mstar, $mval])
                    <div style="text-align:center; border-radius:4px; padding:6px 4px; background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                        <p style="font-size:11px; color:var(--color-text-muted); margin:0 0 3px;">{{ $mlabel }}</p>
                        <p class="hidden sm:block" style="font-size:14px; color:{{ $mstar > 0 ? $starColor : '#4B5563' }}; margin:0 0 3px; line-height:1;">{{ str_repeat('★', $mstar) . str_repeat('☆', 5 - $mstar) }}</p>
                        <p style="font-size:11px; font-family:monospace; color:var(--color-text-primary); margin:0;">{{ $mval }}</p>
                    </div>
                    @endforeach
                </div>
            </div>
        </div>
    @empty
    <div class="rounded-lg border p-8 text-center" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-sm" style="color:var(--color-text-muted);">No hay backtests guardados para esta estrategia.</p>
    </div>
    @endforelse
</div>
@endsection


@if ($errors->any())
<script>
    document.addEventListener('DOMContentLoaded', function() {
        if (window.Swal) {
            Swal.fire({
                title: 'Atención',
                text: '{{ $errors->first() }}',
                icon: 'error',
                background: '#11161F', color: '#E5E9F0',
                confirmButtonColor: '#F2545B',
            });
        } else {
            alert('{{ $errors->first() }}');
        }
    });
</script>
@endif

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {
    window.confirmImplement = function(id) {
        Swal.fire({
            title: '¿Enviar a Paper Trading?', text: 'La estrategia empezará a operar en el simulador con esta configuración.',
            icon: 'question', showCancelButton: true, confirmButtonText: 'Sí, implementar', cancelButtonText: 'Cancelar',
            background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#4D8FE8', cancelButtonColor: '#232B38',
        }).then((result) => { if (result.isConfirmed) document.getElementById('impl-form-' + id).submit(); });
    };
    window.confirmStop = function(id) {
        Swal.fire({
            title: '¿Detener en Paper Trading?', text: 'La estrategia dejará de operar en el simulador inmediatamente.',
            icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, detener', cancelButtonText: 'Cancelar',
            background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
        }).then((result) => { if (result.isConfirmed) document.getElementById('stop-form-' + id).submit(); });
    };
    window.confirmDelete = function(id) {
        Swal.fire({
            title: '¿Eliminar Backtest?', text: 'Esta acción no se puede deshacer.',
            icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, eliminar', cancelButtonText: 'Cancelar',
            background: '#11161F', color: '#E5E9F0', confirmButtonColor: '#F2545B', cancelButtonColor: '#232B38',
        }).then((result) => { if (result.isConfirmed) document.getElementById('del-form-' + id).submit(); });
    };
});
</script>
@endpush

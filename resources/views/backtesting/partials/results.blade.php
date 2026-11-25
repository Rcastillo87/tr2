@if ($result)
@php
    // ── CÁLCULOS BASE ──
    // Usamos el Helper centralizado
    // D-70: una sola fórmula de estrellas (App\Helpers\RatingHelper) y meses con el retorno real de la cuenta
    // (App\Support\BacktestMonths): el acumulado termina en el retorno de la moneda, el mismo número en toda la pantalla.
    $starColor = fn($r) => \App\Helpers\RatingHelper::getColor($r);

    $bySymbol = [];
    foreach(($result['individual_results'] ?? []) as $ind) {
        $ia = $ind['aggregate_metrics'] ?? [];
        $monthly = $ind['monthly_breakdown'] ?? [];
        $months = \App\Support\BacktestMonths::build($monthly, (float) ($ia['initial_balance'] ?? 10000));
        $st = \App\Support\BacktestMonths::stats($months);
        $bySymbol[$ind['symbol']] = [
            'agg' => $ia, 'months' => $months, 'avg_monthly' => $st['avg'],
            'consist' => $st['consist'], 'rating' => \App\Helpers\RatingHelper::forMetrics($ia, $monthly)['rating'],
        ];
    }
    $symbolsList = array_keys($bySymbol);
    $isMulti = count($symbolsList) > 1;

    $allMonths = [];
    foreach($bySymbol as $data) { foreach($data['months'] as $k => $m) { $allMonths[$k] = true; } }
    $allMonths = array_keys($allMonths); sort($allMonths);

    $aggGlobal = $result['aggregate_metrics'] ?? [];
    // C5-12 (D-62): el DD del consolidado es el peor de las monedas (cada una se simula sola, D-41), no el de una cartera
    $ddConsolidatedNote = 'DD del consolidado = el peor DD entre las monedas. Cada moneda se simula sola, así que no es la caída de una cartera con todas a la vez.';
    $monthlyTotals = []; $monthlyAcum = [];
    foreach($bySymbol as $data) {
        foreach($data['months'] as $k => $m) {
            $monthlyTotals[$k] = ($monthlyTotals[$k] ?? 0) + $m['pct'];
        }
    }
    foreach ($allMonths as $k) {   // acumulado del consolidado = suma de los acumulados de las monedas (termina en la suma de los retornos)
        $monthlyAcum[$k] = 0;
        foreach ($bySymbol as $data) {
            $last = null;
            foreach ($data['months'] as $mk => $m) { if ($mk <= $k) { $last = $m['acum']; } }
            $monthlyAcum[$k] += $last ?? 0;
        }
    }
    $avgGlobal = count($monthlyTotals) > 0 ? array_sum($monthlyTotals) / count($monthlyTotals) : 0;
    $positiveGlobal = count(array_filter($monthlyTotals, fn($v) => $v > 0));
    $consistGlobal = count($monthlyTotals) > 0 ? round($positiveGlobal / count($monthlyTotals) * 100, 1) : 0;
    $pnlsGlobal = array_values($monthlyTotals); // Para el conteo en la tabla
    $sumRatings = array_sum(array_column($bySymbol, 'rating'));
    $countSymbols = count($bySymbol);
    $ratingGlobal = $countSymbols > 0 ? round($sumRatings / $countSymbols, 1) : 0;
@endphp

<div class="mt-6 rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-strong);">

    {{-- Header --}}
    <div class="px-4 py-3 border-b flex flex-col md:flex-row justify-between items-start md:items-center gap-3" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
        
        {{-- Izquierda: Título --}}
        <div>
            <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                Resultados: {{ $result['strategy'] }}
            </h3>
            <p class="text-[11px] mt-0.5" style="color:var(--color-text-muted);">
                {{ count($symbolsList) }} moneda(s) • {{ $result['interval'] }} • {{ $result['save_payload']['months'] ?? 6 }} meses
            </p>
        </div>

        {{-- Derecha: Botones --}}
        <div class="flex items-center gap-3">
            @if(isset($result['save_payload']))
            <form id="saveBacktestForm" method="POST" action="{{ route('backtesting.save') }}" class="m-0">
                @csrf
                @php
                    $payload = $result['save_payload'];
                    $payload['backtest_id'] = request('backtest_id');
                    // D-70: se conservan las métricas del servidor (DD, trades por moneda…); antes se perdía el DD al guardar
                    $payload['metrics'] = array_merge((array) ($result['save_payload']['metrics'] ?? []), [
                        'total_trades' => $aggGlobal['total_trades'] ?? 0,
                        'win_rate' => $aggGlobal['win_rate'] ?? 0,
                        'sharpe_ratio' => $aggGlobal['sharpe_ratio'] ?? 0,
                        'profit_factor' => $aggGlobal['profit_factor'] ?? 0,
                        'total_return_pct' => $aggGlobal['total_return_pct'] ?? 0,
                        'avg_monthly_pnl' => $avgGlobal ?? 0,
                        'consist_pct' => $consistGlobal ?? 0,
                        'rating' => $ratingGlobal ?? 0,
                        'max_drawdown_pct' => $aggGlobal['max_drawdown_pct'] ?? null,
                        'max_drawdown_floating_pct' => $aggGlobal['max_drawdown_floating_pct'] ?? null,
                        'individual_results' => $result['individual_results'] ?? []
                    ]);
                @endphp
                <input type="hidden" name="save_data" value="{{ base64_encode(json_encode($payload)) }}">
                <button type="button" onclick="confirmSaveBacktest()" class="text-[12px] font-medium px-4 py-1.5 rounded transition-colors" style="background:var(--color-profit); color:#fff;">
                    💾 Guardar en Historial
                </button>
            </form>
            @endif

            @if(isset($warnings) && count($warnings) > 0)
                <button type="button" onclick="window.showBacktestLog()" class="text-[12px] font-medium px-4 py-1.5 rounded transition-colors flex items-center gap-2" style="background:#3A1A1C; color:#F2545B; border: 1px solid #5A2226;">
                    ⚠️ Ver Log de Errores
                </button>
            @endif
        </div>
    </div>

    {{-- Configuración --}}
    @php
        $cfg = $implementParams ?? [];
        $cfgParts = [];
        if(\App\Support\LevelsLabel::isAuto($cfg)) {   // D-45: SL/TP automáticos
            $cfgParts[] = 'SL=' . \App\Support\LevelsLabel::sl($cfg);
            $cfgParts[] = 'TP1=' . \App\Support\LevelsLabel::tp($cfg);
            $cfgParts[] = 'BE=' . \App\Support\LevelsLabel::be($cfg);
        } else {
            if(isset($cfg['sl_pct'])) $cfgParts[] = "SL={$cfg['sl_pct']}%";
            if(isset($cfg['tp_pct'])) $cfgParts[] = "TP1={$cfg['tp_pct']}%";
            if(isset($cfg['be_pct'])) $cfgParts[] = "BE={$cfg['be_pct']}%";
        }
        if(isset($cfg['max_duration'])) $cfgParts[] = "Dur={$cfg['max_duration']} velas";
        if(isset($cfg['risk_per_trade_pct'])) $cfgParts[] = "Riesgo={$cfg['risk_per_trade_pct']}%";
    @endphp
    <div class="px-4 py-2 border-b text-[11px] font-mono flex flex-wrap gap-3" style="border-color:var(--color-border-soft); color:var(--color-text-muted); background:#0D1117;">
        <span class="font-bold" style="color:var(--color-text-primary);">Configuración:</span>
        <span>{{ implode(' | ', $cfgParts) }}</span>
    </div>

    {{-- TABLA 1: Resumen por moneda --}}
    <div class="overflow-x-auto border-b" style="border-color:var(--color-border-soft);">
        <table class="w-full text-left text-[11px]">
            <thead>
                <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                    <th class="px-4 py-2 font-medium whitespace-nowrap">Moneda</th>
                    <th class="px-3 py-2 font-medium text-center whitespace-nowrap">Rating</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap">Trades</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap">Win Rate</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap">Sharpe</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap">PF</th>
                    <th class="px-3 py-2 font-medium text-center whitespace-nowrap">Mejor Mes</th>
                    <th class="px-3 py-2 font-medium text-center whitespace-nowrap">Peor Mes</th>
                    <th class="px-3 py-2 font-medium text-center whitespace-nowrap">Consistencia</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap">Retorno</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap" title="Peor caída del capital contando solo trades cerrados">DD cerrado</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap" title="Peor caída del capital contando también lo que bajó un trade mientras estaba abierto">DD flotante</th>
                    <th class="px-3 py-2 font-medium text-right whitespace-nowrap">Prom. Mensual P&L</th>
                </tr>
            </thead>
            <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                @php
                    // Drawdown (Fase 12 · 4A, D-38): null = el backtest no trae el dato (guardados antes de p75)
                    $fmtDd = fn ($v) => $v === null ? '—' : number_format((float) $v, 2) . '%';
                @endphp
                @foreach($symbolsList as $sym)
                @php
                    $d = $bySymbol[$sym]; $r = $d['rating']; $c = $starColor($r);
                    $bestMonth = '—'; $worstMonth = '—'; $bestVal = null; $worstVal = null; $winsM = 0;
                    foreach($d['months'] as $m) {
                        $val = (float)$m['pct'];
                        if($bestVal === null || $val > $bestVal) { $bestVal = $val; $bestMonth = $m['month']; }
                        if($worstVal === null || $val < $worstVal) { $worstVal = $val; $worstMonth = $m['month']; }
                        if($val > 0) $winsM++;
                    }
                    $totalM = count($d['months']);
                @endphp
                <tr class="hover:bg-[#1A2230] transition-colors">
                    <td class="px-4 py-2 font-medium whitespace-nowrap" style="color:var(--color-text-primary);">{{ $sym }}</td>
                    <td class="px-3 py-2 text-center whitespace-nowrap">
                        <span style="color:{{ $c }}; font-size:12px;">{{ str_repeat('★', (int)round($r)) . str_repeat('☆', 5 - (int)round($r)) }}</span>
                        <span class="ml-1 font-bold" style="color:{{ $c }};">{{ $r }}</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ $d['agg']['total_trades'] ?? 0 }}</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($d['agg']['win_rate'] ?? 0, 2) }}%</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($d['agg']['sharpe_ratio'] ?? 0, 2) }}</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($d['agg']['profit_factor'] ?? 0, 2) }}</td>
                    <td class="px-3 py-2 text-center font-mono text-[10px] whitespace-nowrap">
                        @if($bestVal !== null)
                            <span style="color:var(--color-profit);">{{ $bestMonth }}</span><br>
                            <span style="color:var(--color-profit); font-weight:600;">{{ $bestVal > 0 ? '+' : '' }}{{ number_format($bestVal, 2) }}%</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[10px] whitespace-nowrap">
                        @if($worstVal !== null)
                            <span style="color:var(--color-loss);">{{ $worstMonth }}</span><br>
                            <span style="color:var(--color-loss); font-weight:600;">{{ number_format($worstVal, 2) }}%</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[10px] whitespace-nowrap">
                        <span style="color:var(--color-text-muted);">{{ $winsM }}/{{ $totalM }} meses</span><br>
                        <span style="color:var(--color-text-primary); font-weight:600;">{{ $totalM > 0 ? round($winsM / $totalM * 100, 1) : 0 }}%</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono font-medium whitespace-nowrap" style="color:{{ ($d['agg']['total_return_pct'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ number_format($d['agg']['total_return_pct'] ?? 0, 2) }}%</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ $fmtDd($d['agg']['max_drawdown_pct'] ?? null) }}</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ $fmtDd($d['agg']['max_drawdown_floating_pct'] ?? null) }}</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:{{ ($d['avg_monthly'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">{{ number_format($d['avg_monthly'] ?? 0, 2) }}%</td>
                </tr>
                @endforeach

                @php
                    // Calcular Mejor/Peor mes actual
                    $currBestVal = null; $currWorstVal = null;
                    foreach($bySymbol as $data) {
                        foreach($data['months'] as $m) {
                            $val = (float)$m['pct'];
                            if ($currBestVal === null || $val > $currBestVal) $currBestVal = $val;
                            if ($currWorstVal === null || $val < $currWorstVal) $currWorstVal = $val;
                        }
                    }

                    // Preparar los datos del backtest guardado (si existe)
                    if ($prevBacktest) {
                        $prevM = $prevBacktest->metrics ?? [];
                        // D-70: la misma fórmula que la fila actual (no la calificación vieja guardada)
                        $prevRating = \App\Helpers\RatingHelper::fromMetrics((array) $prevM);
                        $prevTrades = (int)($prevM['total_trades'] ?? 0);
                        $prevWr = (float)($prevM['win_rate'] ?? 0);
                        $prevSharpe = (float)($prevM['sharpe_ratio'] ?? 0);
                        $prevPf = (float)($prevM['profit_factor'] ?? 0);
                        $prevConsist = (float)($prevM['consist_pct'] ?? 0);
                        // Si no tiene retorno total, usar el promedio mensual multiplicado por los meses
                        $prevRet = (float)($prevM['total_return_pct'] ?? 0);
    if ($prevRet == 0) {
        // Multiplicar por los meses REALES de los datos (9), no por los 24 solicitados
        $prevRet = (float)($prevM['avg_monthly_pnl'] ?? 0) * count($allMonths);
    }
                        $prevAvgMonthly = (float)($prevM['avg_monthly_pnl'] ?? 0);
                        $prevDd = isset($prevM['max_drawdown_pct']) ? (float) $prevM['max_drawdown_pct'] : null;
                        $prevDdFloat = isset($prevM['max_drawdown_floating_pct']) ? (float) $prevM['max_drawdown_floating_pct'] : null;
                        
                        // Extraer mejor/peor mes del guardado
                        $prevBestVal = -999; $prevWorstVal = 999;
                        if (isset($prevM['individual_results'])) {
                            foreach ($prevM['individual_results'] as $ind) {
                                $pMonths = \App\Support\BacktestMonths::build((array) ($ind['monthly_breakdown'] ?? []),
                                    (float) ($ind['aggregate_metrics']['initial_balance'] ?? 10000));
                                foreach ($pMonths as $m) {
                                    $val = (float) $m['pct'];
                                    if ($val > $prevBestVal) $prevBestVal = $val;
                                    if ($val < $prevWorstVal) $prevWorstVal = $val;
                                }
                            }
                        } 
                        
                        if ($prevBestVal == -999) {
                            // Fallback para backtests viejos: usamos los valores actuales para no mostrar "—"
                            $prevBestVal = $currBestVal != -999 ? $currBestVal : 0;
                            $prevWorstVal = $currWorstVal != 999 ? $currWorstVal : 0;
                        }
                    }
                @endphp

                {{-- FILA DEL CONSOLIDADO ACTUAL: solo con varias monedas (con una, es la misma moneda; D-70) --}}
                @if($isMulti)
                <tr style="background:var(--color-surface-raised); border-t-2 border-[var(--color-border-strong)];">
                    <td class="px-4 py-2 font-bold whitespace-nowrap" style="color:var(--color-info);">CONSOLIDADO</td>
                    <td class="px-3 py-2 text-center whitespace-nowrap">
                        <div>
                            <span style="color:{{ $starColor($ratingGlobal) }}; font-size:12px;">{{ str_repeat('★', (int)round($ratingGlobal)) . str_repeat('☆', 5 - (int)round($ratingGlobal)) }}</span>
                            <span class="ml-1 font-bold" style="color:{{ $starColor($ratingGlobal) }};">{{ number_format($ratingGlobal, 1) }}</span>
                        </div>
                    </td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ $aggGlobal['total_trades'] ?? 0 }}</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($aggGlobal['win_rate'] ?? 0, 2) }}%</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($aggGlobal['sharpe_ratio'] ?? 0, 2) }}</td>
                    <td class="px-3 py-2 text-right font-mono whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($aggGlobal['profit_factor'] ?? 0, 2) }}</td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap">
                        @if($currBestVal != -999)
                            <div style="color:var(--color-profit); font-weight:600;">+{{ number_format($currBestVal, 2) }}%</div>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap">
                        @if($currWorstVal != 999)
                            <div style="color:var(--color-loss); font-weight:600;">{{ number_format($currWorstVal, 2) }}%</div>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[10px] whitespace-nowrap">
                        <div style="color:var(--color-text-muted);">{{ $positiveGlobal }}/{{ count($pnlsGlobal) }} meses</div>
                        <div style="color:var(--color-text-primary); font-weight:600;">{{ $consistGlobal }}%</div>
                    </td>
                    <td class="px-3 py-2 text-right font-mono font-bold whitespace-nowrap" style="color:{{ ($aggGlobal['total_return_pct'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                        {{ number_format($aggGlobal['total_return_pct'] ?? 0, 2) }}%
                    </td>
                    <td class="px-3 py-2 text-right font-mono font-bold whitespace-nowrap" style="color:var(--color-text-muted);"@if($isMulti) title="{{ $ddConsolidatedNote }}"@endif>{{ $fmtDd($aggGlobal['max_drawdown_pct'] ?? null) }}@if($isMulti)<div class="font-sans font-normal text-[10px]" style="color:var(--color-neutral);">peor moneda</div>@endif</td>
                    <td class="px-3 py-2 text-right font-mono font-bold whitespace-nowrap" style="color:var(--color-text-muted);"@if($isMulti) title="{{ $ddConsolidatedNote }}"@endif>{{ $fmtDd($aggGlobal['max_drawdown_floating_pct'] ?? null) }}@if($isMulti)<div class="font-sans font-normal text-[10px]" style="color:var(--color-neutral);">peor moneda</div>@endif</td>
                    <td class="px-3 py-2 text-right font-mono font-bold whitespace-nowrap" style="color:{{ ($avgGlobal ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                        {{ number_format($avgGlobal ?? 0, 2) }}%
                    </td>
                </tr>
                @endif

                @if($prevBacktest)
                {{-- FILA DE DATOS GUARDADOS (PREVIOS) --}}
                <tr style="background:#1E293B; border-t:1px solid #334155;">
                    <td class="px-4 py-2 font-bold whitespace-nowrap" style="color:#94A3B8;">GUARDADO (PREVIO)</td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($prevRating, 1) }}</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ $prevTrades }}</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($prevWr, 2) }}%</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($prevSharpe, 2) }}</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($prevPf, 2) }}</td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">
                        @if(isset($prevBestVal) && $prevBestVal !== null) {{ $prevBestVal > 0 ? '+' : '' }}{{ number_format($prevBestVal, 2) }}% @else — @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">
                        @if(isset($prevWorstVal) && $prevWorstVal !== null) {{ number_format($prevWorstVal, 2) }}% @else — @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($prevConsist, 1) }}%</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">
                        @if($prevRet !== null) {{ number_format($prevRet, 2) }}% @else — @endif
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ $fmtDd($prevDd) }}</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ $fmtDd($prevDdFloat) }}</td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap" style="color:var(--color-text-muted);">{{ number_format($prevAvgMonthly, 2) }}%</td>
                </tr>

                {{-- FILA COMPARATIVO --}}
                <tr style="background:#0D1117; border-t:1px solid #334155;">
                    <td class="px-4 py-2 font-bold whitespace-nowrap" style="color:var(--color-info);">COMPARATIVO</td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap">
                        @php $diff = $ratingGlobal - $prevRating; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 1) }})</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @php $diff = ($aggGlobal['total_trades'] ?? 0) - $prevTrades; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ $diff }})</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @php $diff = ($aggGlobal['win_rate'] ?? 0) - $prevWr; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @php $diff = ($aggGlobal['sharpe_ratio'] ?? 0) - $prevSharpe; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }})</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @php $diff = ($aggGlobal['profit_factor'] ?? 0) - $prevPf; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }})</span>
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap">
                        @if($currBestVal != -999 && isset($prevBestVal) && $prevBestVal !== null)
                            @php $diff = $currBestVal - $prevBestVal; @endphp
                            <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap">
                        @if($currWorstVal != 999 && isset($prevWorstVal) && $prevWorstVal !== null)
                            @php $diff = $currWorstVal - $prevWorstVal; @endphp
                            <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-center font-mono text-[11px] whitespace-nowrap">
                        @php $diff = $consistGlobal - $prevConsist; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 1) }}%)</span>
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @if($prevRet !== null)
                            @php $diff = ($aggGlobal['total_return_pct'] ?? 0) - $prevRet; @endphp
                            <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @if(isset($aggGlobal['max_drawdown_pct']) && $prevDd !== null)
                            {{-- en drawdown, bajar es mejorar: verde si el nuevo es menor --}}
                            @php $diff = (float) $aggGlobal['max_drawdown_pct'] - $prevDd; @endphp
                            <span style="color:{{ $diff < 0 ? 'var(--color-profit)' : ($diff > 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @if(isset($aggGlobal['max_drawdown_floating_pct']) && $prevDdFloat !== null)
                            {{-- en drawdown, bajar es mejorar: verde si el nuevo es menor --}}
                            @php $diff = (float) $aggGlobal['max_drawdown_floating_pct'] - $prevDdFloat; @endphp
                            <span style="color:{{ $diff < 0 ? 'var(--color-profit)' : ($diff > 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                        @else
                            <span style="color:var(--color-text-muted);">—</span>
                        @endif
                    </td>
                    <td class="px-3 py-2 text-right font-mono text-[11px] whitespace-nowrap">
                        @php $diff = ($avgGlobal ?? 0) - $prevAvgMonthly; @endphp
                        <span style="color:{{ $diff > 0 ? 'var(--color-profit)' : ($diff < 0 ? 'var(--color-loss)' : 'var(--color-text-muted)') }};">({{ $diff > 0 ? '+' : '' }}{{ number_format($diff, 2) }}%)</span>
                    </td>
                </tr>
                @endif
                </tbody>
        </table>
        @if($isMulti)
            <p class="px-4 py-2 text-[11px]" style="color:var(--color-text-muted);"><span style="color:var(--color-neutral);">DD del consolidado:</span> {{ \Illuminate\Support\Str::after($ddConsolidatedNote, 'DD del consolidado = ') }}</p>
        @endif
    </div>

    {{-- TABLA 2: Desglose Mensual --}}
    <div class="p-4">
        @if($isMulti)
            {{-- Tabla cruzada para múltiples monedas --}}
            <div class="overflow-x-auto">
                <table class="w-full text-left text-[11px]">
                    <thead>
                        <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                            <th class="px-3 py-2 font-medium">Mes</th>
                            @foreach($symbolsList as $sym)
                                <th class="px-3 py-2 font-medium text-center border-l" style="border-color:var(--color-border-soft);">{{ $sym }}</th>
                            @endforeach
                            <th class="px-3 py-2 font-medium text-center border-l" style="border-color:var(--color-border-strong); color:var(--color-info);">CONSOLIDADO</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                        @foreach($allMonths as $month)
                        @php
                            $monthTrades = 0; $monthWins = 0; $monthPnl = 0;
                            foreach($symbolsList as $sym) {
                                $m = $bySymbol[$sym]['months'][$month] ?? null;
                                if($m) { $monthTrades += $m['trades']; $monthWins += $m['wins']; $monthPnl += $m['pct']; }
                            }
                        @endphp
                        <tr>
                            <td class="px-3 py-2 font-mono font-medium" style="color:var(--color-text-primary);">{{ $month }}</td>
                            @foreach($symbolsList as $sym)
                                @php
                                    $found = $bySymbol[$sym]['months'][$month] ?? null;
                                @endphp
                                <td class="px-3 py-2 text-center border-l text-[10px] font-mono" style="border-color:var(--color-border-soft);">
                                    @if($found)
                                        <div style="color:var(--color-text-muted);">{{ $found['trades'] }}t | {{ $found['wins'] }}/{{ $found['losses'] }}</div>
                                        <div style="color:{{ $found['pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}; font-weight:600;">{{ $found['pct'] >= 0 ? '+' : '' }}{{ number_format($found['pct'], 2) }}%</div>
                                    @else
                                        <span style="color:var(--color-text-muted);">—</span>
                                    @endif
                                </td>
                            @endforeach
                            <td class="px-3 py-2 text-center border-l text-[10px] font-mono" style="border-color:var(--color-border-strong); background:#0D1117;">
                                <div style="color:var(--color-text-secondary);">{{ $monthTrades }}t | {{ $monthWins }}/{{ $monthTrades - $monthWins }}</div>
                                <div style="color:{{ $monthPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}; font-weight:600;">{{ $monthPnl >= 0 ? '+' : '' }}{{ number_format($monthPnl, 2) }}%</div>
                                <div style="color:var(--color-text-muted);" title="Acumulado: suma de lo que creció cada moneda hasta este mes">acum {{ ($monthlyAcum[$month] ?? 0) >= 0 ? '+' : '' }}{{ number_format($monthlyAcum[$month] ?? 0, 2) }}%</div>
                            </td>
                        </tr>
                        @endforeach
                    </tbody>
                    <tfoot>
                        <tr style="background:var(--color-surface-raised); border-top:2px solid var(--color-border-strong);">
                            <td class="px-3 py-2 font-bold" style="color:var(--color-text-primary);">TOTAL</td>
                            @foreach($symbolsList as $sym)
                                @php $d = $bySymbol[$sym]; @endphp
                                <td class="px-3 py-2 text-center border-l text-[10px] font-mono" style="border-color:var(--color-border-soft);">
                                    <div style="color:var(--color-text-secondary);">{{ $d['agg']['total_trades'] }}t</div>
                                    <div style="color:{{ ($d['agg']['total_return_pct'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}; font-weight:700;">{{ ($d['agg']['total_return_pct'] ?? 0) >= 0 ? '+' : '' }}{{ number_format($d['agg']['total_return_pct'] ?? 0, 2) }}%</div>
                                </td>
                            @endforeach
                            <td class="px-3 py-2 text-center border-l text-[10px] font-mono" style="border-color:var(--color-border-strong); background:#0D1117;">
                                <div style="color:var(--color-text-secondary); font-weight:700;">{{ $aggGlobal['total_trades'] ?? 0 }}t</div>
                                <div style="color:{{ ($aggGlobal['total_return_pct'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}; font-weight:700;">{{ ($aggGlobal['total_return_pct'] ?? 0) >= 0 ? '+' : '' }}{{ number_format($aggGlobal['total_return_pct'] ?? 0, 2) }}%</div>
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        @else
            {{-- Tabla de columnas para 1 sola moneda --}}
            @php $singleSym = $symbolsList[0]; $singleData = $bySymbol[$singleSym]; @endphp
            <div class="overflow-x-auto">
                <table class="w-full text-left text-[11px]">
                    <thead>
                        <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                            <th class="px-3 py-2 font-medium">Mes</th>
                            <th class="px-3 py-2 font-medium text-center">Trades</th>
                            <th class="px-3 py-2 font-medium text-center">Ganadas</th>
                            <th class="px-3 py-2 font-medium text-center">Perdidas</th>
                            <th class="px-3 py-2 font-medium text-right">P&L %</th>
                            <th class="px-3 py-2 font-medium text-right">Acumulado</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                        @php $acum = 0; $totalWins = 0; $totalLosses = 0; @endphp
                        @foreach($allMonths as $month)
                            @php
                                $found = $singleData['months'][$month] ?? null;
                                if ($found) {
                                    $acum = $found['acum'];   // D-70: lo que creció la cuenta (termina en el retorno)
                                    $totalWins += $found['wins'];
                                    $totalLosses += $found['losses'];
                                }
                            @endphp
                            <tr class="hover:bg-[#1A2230] transition-colors">
                                <td class="px-3 py-2 font-mono font-medium" style="color:var(--color-text-primary);">{{ $month }}</td>
                                @if($found)
                                    <td class="px-3 py-2 text-center font-mono" style="color:var(--color-text-muted);">{{ $found['trades'] }}</td>
                                    <td class="px-3 py-2 text-center font-mono" style="color:var(--color-profit);">{{ $found['wins'] }}</td>
                                    <td class="px-3 py-2 text-center font-mono" style="color:var(--color-loss);">{{ $found['losses'] }}</td>
                                    <td class="px-3 py-2 text-right font-mono font-medium" style="color:{{ $found['pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ $found['pct'] >= 0 ? '+' : '' }}{{ number_format($found['pct'], 2) }}%
                                    </td>
                                    <td class="px-3 py-2 text-right font-mono" style="color:{{ $acum >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ $acum >= 0 ? '+' : '' }}{{ number_format($acum, 2) }}%
                                    </td>
                                @else
                                    <td colspan="5" class="px-3 py-2 text-center font-mono" style="color:var(--color-text-muted);">—</td>
                                @endif
                            </tr>
                        @endforeach
                    </tbody>
                    <tfoot>
                        <tr style="background:var(--color-surface-raised); border-top:2px solid var(--color-border-strong);">
                            <td class="px-3 py-2 font-bold" style="color:var(--color-text-primary);">TOTAL</td>
                            <td class="px-3 py-2 text-center font-mono font-bold" style="color:var(--color-text-primary);">{{ $singleData['agg']['total_trades'] }}</td>
                            <td class="px-3 py-2 text-center font-mono font-bold" style="color:var(--color-profit);">{{ $totalWins }}</td>
                            <td class="px-3 py-2 text-center font-mono font-bold" style="color:var(--color-loss);">{{ $totalLosses }}</td>
                            <td class="px-3 py-2 text-right font-mono font-bold" style="color:{{ ($singleData['agg']['total_return_pct'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ ($singleData['agg']['total_return_pct'] ?? 0) >= 0 ? '+' : '' }}{{ number_format($singleData['agg']['total_return_pct'] ?? 0, 2) }}%
                            </td>
                            <td class="px-3 py-2 text-right font-mono font-bold" style="color:{{ ($singleData['agg']['total_return_pct'] ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ ($singleData['agg']['total_return_pct'] ?? 0) >= 0 ? '+' : '' }}{{ number_format($singleData['agg']['total_return_pct'] ?? 0, 2) }}%
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        @endif
    </div>
</div>



@endif

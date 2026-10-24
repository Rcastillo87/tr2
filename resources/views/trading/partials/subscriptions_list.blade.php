@if ($account->subscriptions->isEmpty())
    <p class="text-[11px] italic" style="color:var(--color-text-muted);">No hay configuraciones suscritas en esta cuenta.</p>
@else
    @php
        // Agrupar por backtest_id (o por nombre base si no hay backtest)
        $groupedSubs = $account->subscriptions->groupBy(function($sub) {
            return $sub->paperStrategyConfig?->backtest_id ?? trim(explode(' — ', $sub->strategy)[0]);
        });
    @endphp
    <div class="flex flex-col gap-2">
        @foreach($groupedSubs as $groupKey => $subs)
            @php
                $first = $subs->first();
                $bt = $first->paperStrategyConfig?->backtest;

                // Símbolos y meses
                if ($bt) {
                    $symbols = is_array($bt->symbols) ? $bt->symbols : json_decode($bt->symbols, true);
                    $months = $bt->months;
                } else {
                    $symbols = $subs->pluck('symbol')->unique()->values()->toArray();
                    $months = null;
                }

                $interval = $bt ? $bt->interval : $first->interval;
                $baseName = trim(explode(' — ', $first->strategy)[0]);
                $displayName = $baseName . ' — ' . implode(', ', $symbols) . ' (' . $interval . ')';
                $status = $first->status;

                // Métricas del backtest
                $m = $bt->metrics ?? [];
                $wr = (float)($m['win_rate'] ?? 0);
                $sharpe = (float)($m['sharpe_ratio'] ?? 0);
                $pf = (float)($m['profit_factor'] ?? 0);
                $ret = (float)($m['avg_monthly_pnl'] ?? 0);
                $consist = (float)($m['consist_pct'] ?? 0);
                $trades = (int)($m['total_trades'] ?? 0);

                // Cálculo de estrellas (igual que en el historial)
                $sWr = $wr >= 65 ? 5 : ($wr >= 55 ? 4 : ($wr >= 45 ? 3 : ($wr >= 35 ? 2 : 1)));
                $sSharpe = $sharpe >= 4 ? 5 : ($sharpe >= 3 ? 4 : ($sharpe >= 2 ? 3 : ($sharpe >= 1 ? 2 : 1)));
                $sPf = $pf >= 2.5 ? 5 : ($pf >= 2.0 ? 4 : ($pf >= 1.5 ? 3 : ($pf >= 1.0 ? 2 : 1)));
                $sRet = $ret >= 20 ? 5 : ($ret >= 10 ? 4 : ($ret >= 5 ? 3 : ($ret >= 2 ? 2 : 1)));
                $sCons = $consist >= 80 ? 5 : ($consist >= 60 ? 4 : ($consist >= 40 ? 3 : ($consist >= 20 ? 2 : 1)));

                $rating = round(($sWr + $sSharpe + $sPf + $sRet + $sCons) / 5, 1);
                if ($rating <= 0) $rating = 1.0;
                $starColor = $rating >= 4 ? '#F5C518' : ($rating >= 3 ? '#EF9F27' : ($rating >= 2 ? '#E8832A' : '#E24B4A'));
            @endphp
            <div class="flex items-center justify-between p-3 rounded-lg border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1 flex-wrap">
                        <span class="font-medium text-sm" style="color:var(--color-text-primary);">{{ $displayName }}</span>
                        <span class="px-2 py-0.5 rounded text-[10px] font-medium" style="background:{{ $status === 'active' ? '#16331F' : '#33221B' }}; color:{{ $status === 'active' ? 'var(--color-profit)' : '#F59E0B' }};">
                            {{ $status === 'active' ? 'Activa' : 'Pausada' }}
                        </span>
                        @if($months)
                            <span class="text-[10px] px-2 py-0.5 rounded" style="background:var(--color-surface); border:1px solid var(--color-border-soft); color:var(--color-text-muted);">
                                {{ $months }} meses
                            </span>
                        @endif
                    </div>
                    <div class="flex items-center gap-4 text-[11px] flex-wrap" style="color:var(--color-text-muted);">
                        <span style="color:{{ $starColor }};">{{ str_repeat('★', (int)round($rating)) . str_repeat('☆', 5 - (int)round($rating)) }} {{ number_format($rating, 1) }}</span>
                        <span>WR: {{ number_format($wr, 1) }}%</span>
                        <span>Sharpe: {{ number_format($sharpe, 2) }}</span>
                        <span>Ret. prom/mes: {{ number_format($ret, 2) }}%</span>
                        <span>Cons: {{ number_format($consist, 1) }}%</span>
                        <span>PF: {{ number_format($pf, 2) }}</span>
                        <span>{{ $trades }} trades</span>
                    </div>
                </div>
                <div class="flex items-center gap-2 ml-4">
                    @foreach($subs as $sub)
                        <form method="POST" action="{{ route('trading.subscriptions.toggle', [$account, $sub]) }}" class="inline">
                            @csrf @method('PATCH')
                            <button type="submit" class="px-2 py-1 rounded text-[11px] border" style="background:transparent; border-color:var(--color-border-strong); color:var(--color-text-primary);">
                                {{ $sub->status === 'active' ? '⏸️ Pausar' : '▶️ Reanudar' }}
                            </button>
                        </form>
                        <form method="POST" action="{{ route('trading.subscriptions.destroy', [$account, $sub]) }}" class="inline" onsubmit="return confirm('¿Eliminar esta suscripción?');">
                            @csrf @method('DELETE')
                            <button type="submit" class="px-2 py-1 rounded text-[11px] border text-red-400" style="background:transparent; border-color:#7F1D1D;">
                                🗑️
                            </button>
                        </form>
                    @endforeach
                </div>
            </div>
        @endforeach
    </div>
@endif

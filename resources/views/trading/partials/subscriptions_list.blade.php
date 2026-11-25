@if ($account->subscriptions->isEmpty())
    <p class="text-[11px] italic" style="color:var(--color-text-muted);">No hay configuraciones suscritas en esta cuenta.</p>
@else
    @php
        // Agrupar por backtest_id (o por nombre base si no hay backtest)
        // 24-nov: cada moneda con su estado y el aviso de misma moneda (App\Support\SubscriptionRows)
        $rows = \App\Support\SubscriptionRows::build($account->subscriptions->map(fn ($s) => [
            'id' => (int) $s->id, 'symbol' => (string) $s->symbol, 'strategy' => (string) $s->strategy,
            'status' => (string) $s->status, 'retire_on_close' => (bool) $s->retire_on_close,
        ])->values()->all());
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

                // Métricas del backtest
                $m = $bt->metrics ?? [];
                $wr = (float)($m['win_rate'] ?? 0);
                $sharpe = (float)($m['sharpe_ratio'] ?? 0);
                $pf = (float)($m['profit_factor'] ?? 0);
                $ret = (float)($m['avg_monthly_pnl'] ?? 0);
                $consist = (float)($m['consist_pct'] ?? 0);
                $trades = (int)($m['total_trades'] ?? 0);

                // D-70: estrellas con la fórmula única (App\Helpers\RatingHelper)
                $rating = \App\Helpers\RatingHelper::fromMetrics((array) ($bt->metrics ?? []));
                $starColor = \App\Helpers\RatingHelper::getColor($rating);
            @endphp
            <div class="flex items-center justify-between p-3 rounded-lg border" style="background:var(--color-surface-raised); border-color:var(--color-border-soft);">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1 flex-wrap">
                        <span class="font-medium text-sm" style="color:var(--color-text-primary);">{{ $displayName }}</span>
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
                <div class="flex flex-col gap-1.5 ml-4">
                    @foreach($subs as $sub)
                        @php
                            $row = $rows[$sub->id];
                            $note = \App\Support\SubscriptionRows::sharedNote($row['shares']);
                            $coin = str_replace('USDT', '', $sub->symbol);
                            $badge = ['active' => ['#16331F', 'var(--color-profit)'], 'paused' => ['#33221B', '#F59E0B'],
                                      'retiring' => ['var(--color-surface)', 'var(--color-text-muted)']][$row['state']];
                        @endphp
                        <div class="flex items-center justify-end gap-2 flex-wrap" data-sub-row="{{ $sub->id }}">
                            <span class="text-[11px]" style="color:var(--color-text-secondary);">{{ $sub->symbol }}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-medium" style="background:{{ $badge[0] }}; color:{{ $badge[1] }};">{{ $row['label'] }}</span>
                            @if ($row['state'] === 'retiring')
                                <span class="text-[10px]" style="color:var(--color-text-muted);">Quitada de Paper · su operación sigue hasta el SL/TP</span>
                            @else
                                <form method="POST" action="{{ route('trading.subscriptions.toggle', [$account, $sub]) }}" class="inline"
                                      onsubmit="return confirmSubToggle(event, @js($sub->strategy), {{ $row['state'] === 'active' ? 'true' : 'false' }}, @js(implode(', ', $row['shares'])))">
                                    @csrf @method('PATCH')
                                    <button type="submit" class="px-2 py-1 rounded text-[11px] border" style="background:transparent; border-color:var(--color-border-strong); color:var(--color-text-primary);">
                                        {{ $row['state'] === 'active' ? '⏸️ Pausar ' . $coin : '▶️ Reanudar ' . $coin }}
                                    </button>
                                </form>
                                <form method="POST" action="{{ route('trading.subscriptions.destroy', [$account, $sub]) }}" class="inline"
                                      onsubmit="return confirmSubDelete(event, @js($sub->strategy))">
                                    @csrf @method('DELETE')
                                    <button type="submit" aria-label="Eliminar {{ $sub->symbol }}" class="px-2 py-1 rounded text-[11px] border text-red-400" style="background:transparent; border-color:#7F1D1D;">
                                        🗑️
                                    </button>
                                </form>
                            @endif
                        </div>
                        @if ($note)
                            <div class="text-[10px] px-2 py-1 rounded text-right" style="background:#2A2410; color:#F5C518;">ⓘ {{ $note }}</div>
                        @endif
                    @endforeach
                </div>
            </div>
        @endforeach
    </div>
@endif

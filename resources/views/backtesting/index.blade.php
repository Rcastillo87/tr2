@extends('layouts.app')

@section('title', 'Backtesting')
@section('header', 'Backtesting')

@section('content')

    {{-- Formulario --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Configurar backtest</h3>

        <form method="POST" action="{{ route('backtesting.run') }}" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            @csrf

            <div class="col-span-2 sm:col-span-1">
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Estrategia</label>
                <select name="strategy" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    @foreach ($strategies as $s)
                        <option value="{{ $s }}" {{ ($old['strategy'] ?? '') === $s ? 'selected' : '' }}>{{ $s }}</option>
                    @endforeach
                </select>
            </div>

            <div class="col-span-2 sm:col-span-1">
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Símbolo</label>
                <select name="symbol" class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    @foreach ($symbols as $sym)
                        <option value="{{ $sym }}" {{ ($old['symbol'] ?? '') === $sym ? 'selected' : '' }}>{{ $sym }}</option>
                    @endforeach
                </select>
            </div>

            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Timeframe</label>
                <input type="text" value="1H (fijo)" disabled
                       class="w-full rounded-lg px-3 py-2 text-sm border"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-muted);">
            </div>

            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Stop Loss %</label>
                <input type="number" step="0.1" name="sl_pct" value="{{ $old['sl_pct'] ?? '1.5' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit %</label>
                <input type="number" step="0.1" name="tp_pct" value="{{ $old['tp_pct'] ?? '3.0' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Break-even %</label>
                <input type="number" step="0.1" name="be_pct" value="{{ $old['be_pct'] ?? '2.0' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Máx. duración (velas H1)</label>
                <input type="number" step="1" name="max_duration" value="{{ $old['max_duration'] ?? '24' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            <div class="col-span-2 sm:col-span-3 lg:col-span-2 flex items-center gap-2 mt-1">
                <input type="checkbox" name="regime_filter" id="regime_filter" value="1"
                       {{ ($old['regime_filter'] ?? '1') ? 'checked' : '' }}
                       class="w-4 h-4 rounded border"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); accent-color:var(--color-info);">
                <label for="regime_filter" class="text-sm" style="color:var(--color-text-secondary);">Aplicar filtro de régimen</label>
            </div>

            <div class="col-span-2 sm:col-span-3 lg:col-span-2 flex items-end">
                <button type="submit"
                        class="w-full text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                        style="background:var(--color-info); color:#fff;">
                    Ejecutar backtest (walk-forward)
                </button>
            </div>
        </form>
    </div>

    {{-- Error --}}
    @if ($error)
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
            {{ $error }}
        </div>
    @endif

    {{-- Resultado --}}
    @if ($result)
        @php
            $agg = $result['aggregate_metrics'];
        @endphp

        <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                    {{ $result['strategy'] }} — {{ $result['symbol'] }}
                </h3>
                @if ($result['passed'])
                    <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium self-start sm:self-auto" style="background:#16331F; color:var(--color-profit); border:1px solid #1E4A2E;">
                        ✓ Aprobada para paper trading
                    </span>
                @else
                    <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium self-start sm:self-auto" style="background:#3A1A1C; color:var(--color-loss); border:1px solid #5A2226;">
                        ✗ No aprobada
                    </span>
                @endif
            </div>

            {{-- Métricas agregadas --}}
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Total trades</p>
                    <p class="font-mono text-base font-medium" style="color:var(--color-text-primary);">{{ $agg['total_trades'] }}</p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Win rate</p>
                    <p class="font-mono text-base font-medium" style="color:var(--color-text-primary);">{{ $agg['win_rate'] }}%</p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Profit factor</p>
                    <p class="font-mono text-base font-medium" style="color:var(--color-text-primary);">{{ $agg['profit_factor'] ?? '—' }}</p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Sharpe ratio</p>
                    <p class="font-mono text-base font-medium" style="color:var(--color-text-primary);">{{ $agg['sharpe_ratio'] }}</p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Max drawdown</p>
                    <p class="font-mono text-base font-medium" style="color:var(--color-text-primary);">{{ $agg['max_drawdown_pct'] }}%</p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Return total</p>
                    <p class="font-mono text-base font-medium" style="color: {{ $agg['total_return_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                        {{ $agg['total_return_pct'] }}%
                    </p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">Expectancy</p>
                    <p class="font-mono text-base font-medium" style="color:var(--color-text-primary);">{{ $agg['expectancy'] }}</p>
                </div>
                <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                    <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">P&amp;L total</p>
                    <p class="font-mono text-base font-medium" style="color: {{ $agg['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                        {{ number_format($agg['total_pnl'], 2) }}
                    </p>
                </div>
            </div>

            {{-- Razones --}}
            <div class="mb-4">
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-muted);">Criterios de evaluación</h4>
                <ul class="space-y-1">
                    @foreach ($result['pass_reasons'] as $reason)
                        <li class="text-sm" style="color: {{ str_contains($reason, 'aprobada') ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                            • {{ $reason }}
                        </li>
                    @endforeach
                </ul>
            </div>

            {{-- Resultados por ventana --}}
            <div>
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-muted);">Resultados por ventana (walk-forward)</h4>

                {{-- Mobile: cards --}}
                <div class="space-y-2 sm:hidden">
                    @foreach ($result['window_results'] as $w)
                        <div class="rounded-md border p-3" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium" style="color:var(--color-text-primary);">Ventana {{ $w['window'] }}</span>
                                <span class="font-mono text-sm font-medium" style="color: {{ $w['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ number_format($w['total_pnl'], 2) }}
                                </span>
                            </div>
                            <div class="grid grid-cols-3 gap-2 font-mono text-[11px]" style="color:var(--color-text-muted);">
                                <div>
                                    <p class="text-[10px]">Trades</p>
                                    <p style="color:var(--color-text-primary);">{{ $w['total_trades'] }}</p>
                                </div>
                                <div>
                                    <p class="text-[10px]">Win rate</p>
                                    <p style="color:var(--color-text-primary);">{{ $w['win_rate'] }}%</p>
                                </div>
                                <div>
                                    <p class="text-[10px]">P. factor</p>
                                    <p style="color:var(--color-text-primary);">{{ $w['profit_factor'] ?? '—' }}</p>
                                </div>
                                <div>
                                    <p class="text-[10px]">Sharpe</p>
                                    <p style="color:var(--color-text-primary);">{{ $w['sharpe_ratio'] }}</p>
                                </div>
                                <div class="col-span-2">
                                    <p class="text-[10px]">Drawdown</p>
                                    <p style="color:var(--color-text-primary);">{{ $w['max_drawdown_pct'] }}%</p>
                                </div>
                            </div>
                        </div>
                    @endforeach
                </div>

                {{-- Desktop: tabla --}}
                <div class="overflow-x-auto hidden sm:block">
                    <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-2 font-normal">Ventana</th>
                                <th class="py-2 px-2 font-normal">Trades</th>
                                <th class="py-2 px-2 font-normal">Win rate</th>
                                <th class="py-2 px-2 font-normal">Profit factor</th>
                                <th class="py-2 px-2 font-normal">Sharpe</th>
                                <th class="py-2 px-2 font-normal">Drawdown</th>
                                <th class="py-2 px-2 font-normal">P&amp;L</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($result['window_results'] as $w)
                                <tr class="border-b" style="border-color:var(--color-border-soft);">
                                    <td class="py-2 px-2" style="color:var(--color-text-primary);">{{ $w['window'] }}</td>
                                    <td class="py-2 px-2">{{ $w['total_trades'] }}</td>
                                    <td class="py-2 px-2">{{ $w['win_rate'] }}%</td>
                                    <td class="py-2 px-2">{{ $w['profit_factor'] ?? '—' }}</td>
                                    <td class="py-2 px-2">{{ $w['sharpe_ratio'] }}</td>
                                    <td class="py-2 px-2">{{ $w['max_drawdown_pct'] }}%</td>
                                    <td class="py-2 px-2" style="color: {{ $w['total_pnl'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ number_format($w['total_pnl'], 2) }}
                                    </td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    @endif

@endsection

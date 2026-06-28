@extends('layouts.app')
@section('title', 'Trading')
@section('header', 'Trading')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

{{-- Filtros + link cuentas --}}
<div class="flex items-center justify-between mb-3 flex-wrap gap-2">
    <a href="{{ route('trading.accounts') }}"
       class="text-[11px] px-3 py-1.5 rounded transition-colors"
       style="background:var(--color-surface-raised); color:var(--color-info); border:1px solid var(--color-border-soft);">
        ⚙ Gestionar cuentas
    </a>
</div>

<form method="GET" action="{{ route('trading.index') }}" id="filterForm">
    <div class="flex items-center gap-2 mb-4 flex-wrap">

        {{-- Mes --}}
        <select name="month" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            @foreach ($availableMonths as $m)
                <option value="{{ $m['value'] }}" {{ $month->format('Y-m') === $m['value'] ? 'selected' : '' }}>
                    {{ $m['label'] }}
                </option>
            @endforeach
        </select>

        {{-- Estrategia --}}
        <select name="strategy" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterStrategy === 'all' ? 'selected' : '' }}>Todas las estrategias</option>
            @foreach ($filterOptions['strategies'] as $s)
                <option value="{{ $s }}" {{ $filterStrategy === $s ? 'selected' : '' }}>{{ $s }}</option>
            @endforeach
        </select>

        {{-- Símbolo --}}
        <select name="symbol" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterSymbol === 'all' ? 'selected' : '' }}>Todos los símbolos</option>
            @foreach ($filterOptions['symbols'] as $sym)
                <option value="{{ $sym }}" {{ $filterSymbol === $sym ? 'selected' : '' }}>{{ $sym }}</option>
            @endforeach
        </select>

        {{-- Intervalo --}}
        @php $iLabels = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
        <select name="interval" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterInterval === 'all' ? 'selected' : '' }}>Todos los intervalos</option>
            @foreach ($filterOptions['intervals'] as $iv)
                <option value="{{ $iv }}" {{ $filterInterval === $iv ? 'selected' : '' }}>{{ $iLabels[$iv] ?? $iv }}</option>
            @endforeach
        </select>

        {{-- Resultado --}}
        <select name="result" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all"  {{ $filterResult === 'all'  ? 'selected' : '' }}>Todos los resultados</option>
            <option value="win"  {{ $filterResult === 'win'  ? 'selected' : '' }}>Ganadoras</option>
            <option value="loss" {{ $filterResult === 'loss' ? 'selected' : '' }}>Perdedoras</option>
        </select>

        {{-- Cuenta --}}
        <select name="account" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterAccount === 'all' ? 'selected' : '' }}>Todas las cuentas</option>
            @foreach ($filterOptions['accounts'] as $acc)
                <option value="{{ $acc->id }}" {{ $filterAccount == $acc->id ? 'selected' : '' }}>
                    {{ ucfirst($acc->broker) }} {{ strtoupper($acc->account_type) }} — {{ $acc->label }}
                </option>
            @endforeach
        </select>

        @if ($filterStrategy !== 'all' || $filterSymbol !== 'all' || $filterInterval !== 'all' || $filterResult !== 'all' || $filterAccount !== 'all')
            <a href="{{ route('trading.index', ['month' => $month->format('Y-m')]) }}"
               class="text-xs px-2 py-1 rounded transition-colors"
               style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
               Limpiar filtros
            </a>
        @endif
    </div>
</form>

{{-- KPIs --}}
<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">P&L neto del mes</p>
        <p class="font-mono text-xl font-medium" style="color: {{ $totalNetPnl >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
            {{ $totalNetPnl >= 0 ? '+' : '' }}{{ number_format($totalNetPnl, 2) }} USDT
        </p>
    </div>
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Win rate</p>
        <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">{{ $winRate }}%</p>
    </div>
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Profit factor</p>
        <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">{{ $profitFactor ?? '—' }}</p>
    </div>
    <div class="rounded-lg border p-3" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <p class="text-[11px] mb-1.5" style="color:var(--color-text-muted);">Trades cerrados</p>
        <p class="font-mono text-xl font-medium" style="color:var(--color-text-primary);">
            {{ $totalClosed }} <span class="text-sm font-normal" style="color:var(--color-text-muted);">({{ $wins }}G / {{ $totalClosed - $wins }}P)</span>
        </p>
    </div>
</div>

{{-- Curva de equity --}}
@if (count($equityCurve) > 1)
<div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <p class="text-xs font-medium mb-3" style="color:var(--color-text-secondary);">Curva de equity (USDT)</p>
    <canvas id="equityChart" height="80"></canvas>
</div>
@endif

{{-- Guia de estados --}}
<div class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <button type="button" onclick="toggleTradingGuide()"
            class="w-full flex items-center justify-between px-4 py-3 text-left"
            style="color:var(--color-text-secondary);">
        <span class="text-xs font-medium">📖 Guía de estados y columnas</span>
        <span id="tradingGuideChevron" class="text-[11px]" style="color:var(--color-text-muted);">▼ Mostrar</span>
    </button>
    <div id="tradingGuideContent" class="hidden px-4 pb-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-[11px]" style="color:var(--color-text-muted);">
            <div class="space-y-2">
                <p class="text-[10px] font-medium uppercase tracking-wide" style="color:var(--color-info);">Estados de operación</p>
                <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:#EF9F27;"></span><span class="font-medium" style="color:var(--color-text-primary);">pending_open</span> — Orden enviada a Bybit, esperando confirmación de ejecución.</div>
                <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:#1D9E75;"></span><span class="font-medium" style="color:var(--color-text-primary);">open</span> — Posición confirmada y activa en Bybit. El monitor la vigila cada 5 min.</div>
                <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:#6B7280;"></span><span class="font-medium" style="color:var(--color-text-primary);">closed</span> — Cerrada correctamente. PnL, comisión y balance calculados.</div>
                <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:#8B5CF6;"></span><span class="font-medium" style="color:var(--color-text-primary);">orphaned</span> — No confirmada en 38s. El reconciliador la adopta si existe en Bybit.</div>
                <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:#E24B4A;"></span><span class="font-medium" style="color:var(--color-text-primary);">failed</span> — No se pudo abrir. Señal expiró o Bybit rechazó la orden.</div>
                <div><span class="inline-block w-2 h-2 rounded-full mr-1" style="background:#374151;"></span><span class="font-medium" style="color:var(--color-text-primary);">error</span> — Error técnico durante la apertura.</div>
            </div>
            <div class="space-y-2">
                <p class="text-[10px] font-medium uppercase tracking-wide" style="color:var(--color-info);">Columnas — Posiciones abiertas</p>
                <div><span class="font-medium" style="color:var(--color-text-primary);">Precio actual</span> — Precio en tiempo real del mercado. ▲ verde = precio a favor · ▼ rojo = en contra.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">SL</span> — Stop Loss: precio al que Bybit cierra automáticamente para limitar la pérdida.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">TP</span> — Take Profit: precio al que Bybit cierra automáticamente para capturar la ganancia.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">P&L flotante</span> — Ganancia/pérdida no realizada en % sobre el capital. Se actualiza cada 20s.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">Estado</span> — Badge de color indicando el estado actual de la operación.</div>
            </div>
            <div class="space-y-2">
                <p class="text-[10px] font-medium uppercase tracking-wide" style="color:var(--color-info);">Columnas — Historial</p>
                <div><span class="font-medium" style="color:var(--color-text-primary);">Razón de cierre</span> — stop_loss · take_profit_1-4 · time_exit · reconciled_sl_tp_bybit.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">Comisión</span> — Costo de la operación (taker fee Bybit ~0.055%).</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">P&L neto</span> — Ganancia/pérdida real en USDT después de comisiones.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">Bal. antes/después</span> — Balance de la cuenta antes y después de la operación.</div>
                <div><span class="font-medium" style="color:var(--color-text-primary);">DEMO/REAL</span> — Indica si la cuenta es testnet (demo) o mainnet (real).</div>
            </div>
        </div>
    </div>
</div>

{{-- Posiciones abiertas --}}
@if ($openTrades->isNotEmpty())
<div class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">
            Posiciones abiertas ({{ $openTrades->count() }})
        </h3>
        <span class="text-[10px]" style="color:var(--color-text-muted);">Precio actualizado cada 20s</span>
    </div>
    <div class="overflow-x-auto">
        <table class="w-full font-mono text-[11px]" style="color:var(--color-text-muted);">
            <thead>
                <tr class="border-b" style="border-color:var(--color-border-soft);">
                    <th class="py-2 px-3 text-left font-normal">Estrategia</th>
                    <th class="py-2 px-3 text-left font-normal">Símbolo</th>
                    <th class="py-2 px-3 text-left font-normal">Int.</th>
                    <th class="py-2 px-3 text-left font-normal">Dir.</th>
                    <th class="py-2 px-3 text-left font-normal">Entrada</th>
                    <th class="py-2 px-3 text-left font-normal">Precio actual</th>
                    <th class="py-2 px-3 text-left font-normal">SL</th>
                    <th class="py-2 px-3 text-left font-normal">TP</th>
                    <th class="py-2 px-3 text-left font-normal">P&L flotante</th>
                    <th class="py-2 px-3 text-left font-normal">Hora entrada</th>
                    <th class="py-2 px-3 text-left font-normal">Estado</th>
                    <th class="py-2 px-3 text-left font-normal">Cuenta</th>
                </tr>
            </thead>
            <tbody>
                @foreach ($openTrades as $trade)
                    @php $lbs = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                    <tr class="border-b" style="border-color:var(--color-border-soft);">
                        <td class="py-2 px-3" style="color:var(--color-text-primary);">{{ $trade->strategy }}</td>
                        <td class="py-2 px-3">{{ $trade->symbol }}</td>
                        <td class="py-2 px-3">{{ $lbs[$trade->interval] ?? $trade->interval }}</td>
                        <td class="py-2 px-3">
                            <span style="color: {{ $trade->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ strtoupper($trade->side) }}
                            </span>
                        </td>
                        <td class="py-2 px-3">{{ number_format($trade->entry_price, 2) }}</td>
                        <td class="py-2 px-3 font-mono" id="price_{{ $trade->id }}"
                            data-entry="{{ $trade->entry_price }}"
                            data-side="{{ $trade->side }}"
                            style="color:var(--color-text-muted);">
                            {{ $trade->current_price ? number_format($trade->current_price, 2) : '—' }}
                        </td>
                        <td class="py-2 px-3" style="color:var(--color-loss);">{{ number_format($trade->sl, 2) }}</td>
                        <td class="py-2 px-3" style="color:var(--color-profit);">{{ number_format($trade->tp, 2) }}</td>
                        <td class="py-2 px-3" id="pnl_{{ $trade->id }}"
                            style="color: {{ ($trade->floating_pnl_pct ?? 0) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                            {{ $trade->floating_pnl_pct !== null ? ($trade->floating_pnl_pct >= 0 ? '+' : '') . number_format($trade->floating_pnl_pct, 3) . '%' : '—' }}
                        </td>
                        <td class="py-2 px-3">
                            {{ \Carbon\Carbon::parse($trade->entry_time)->timezone('America/Bogota')->format('d/m H:i') }}
                        </td>
                        <td class="py-2 px-3">
                            @php
                                $statusColors = [
                                    'pending_open'  => ['bg'=>'#3A2E0E','color'=>'#EF9F27'],
                                    'open'          => ['bg'=>'#16331F','color'=>'var(--color-profit)'],
                                    'orphaned'      => ['bg'=>'#2D1B69','color'=>'#8B5CF6'],
                                    'pending_close' => ['bg'=>'#1A2B3C','color'=>'var(--color-info)'],
                                ];
                                $sc = $statusColors[$trade->status] ?? ['bg'=>'#1F2937','color'=>'var(--color-text-muted)'];
                            @endphp
                            <span class="text-[10px] px-1.5 py-0.5 rounded font-medium"
                                  style="background:{{ $sc['bg'] }}; color:{{ $sc['color'] }};">
                                {{ str_replace('_', ' ', $trade->status) }}
                            </span>
                        </td>
                        <td class="py-2 px-3">
                            @php
                                $acct = $filterOptions['accounts']->firstWhere('id', $trade->broker_account_id);
                            @endphp
                            <span class="text-[10px] px-1.5 py-0.5 rounded font-medium"
                                  style="background: {{ ($acct?->account_type ?? '') === 'demo' ? '#3A2E0E' : '#16331F' }};
                                         color: {{ ($acct?->account_type ?? '') === 'demo' ? 'var(--color-neutral)' : 'var(--color-profit)' }};">
                                {{ strtoupper($acct?->account_type ?? 'real') }}
                            </span>
                            <span class="text-[10px] ml-1" style="color:var(--color-text-muted);">{{ ucfirst($trade->broker ?? 'bybit') }}</span>
                        </td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    </div>
</div>
@endif

{{-- Historial --}}
<div class="rounded-lg border" style="background:var(--color-surface); border-color:var(--color-border-soft);">
    <div class="px-4 py-3 border-b" style="border-color:var(--color-border-soft);">
        <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">
            Historial de operaciones — {{ ucfirst($month->translatedFormat('F Y')) }}
            {{-- Cuenta --}}
        <select name="account" onchange="document.getElementById('filterForm').submit()"
                class="rounded-lg px-3 py-1.5 text-xs border focus:outline-none"
                style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            <option value="all" {{ $filterAccount === 'all' ? 'selected' : '' }}>Todas las cuentas</option>
            @foreach ($filterOptions['accounts'] as $acc)
                <option value="{{ $acc->id }}" {{ $filterAccount == $acc->id ? 'selected' : '' }}>
                    {{ ucfirst($acc->broker) }} {{ strtoupper($acc->account_type) }} — {{ $acc->label }}
                </option>
            @endforeach
        </select>

        @if ($filterStrategy !== 'all' || $filterSymbol !== 'all' || $filterInterval !== 'all' || $filterResult !== 'all' || $filterAccount !== 'all')
                <span class="text-[10px] ml-2" style="color:var(--color-info);">(filtrado)</span>
            @endif
        </h3>
    </div>

    @if ($closedTrades->isEmpty())
        <div class="p-6 text-center">
            <p class="text-sm" style="color:var(--color-text-muted);">Sin operaciones cerradas en este período.</p>
        </div>
    @else
        <div class="overflow-x-auto">
            <table class="w-full font-mono text-[11px]" style="color:var(--color-text-muted);">
                <thead>
                    <tr class="border-b" style="border-color:var(--color-border-soft); background:var(--color-surface-raised);">
                        <th class="py-2 px-3 text-left font-normal">Estrategia</th>
                        <th class="py-2 px-3 text-left font-normal">Símbolo</th>
                        <th class="py-2 px-3 text-left font-normal">Int.</th>
                        <th class="py-2 px-3 text-left font-normal">Dir.</th>
                        <th class="py-2 px-3 text-left font-normal">Entrada</th>
                        <th class="py-2 px-3 text-left font-normal">Salida</th>
                        <th class="py-2 px-3 text-left font-normal">Estado</th>
                        <th class="py-2 px-3 text-left font-normal">Razón</th>
                        <th class="py-2 px-3 text-left font-normal">Tamaño</th>
                        <th class="py-2 px-3 text-left font-normal">Comisión</th>
                        <th class="py-2 px-3 text-left font-normal">P&L neto</th>
                        <th class="py-2 px-3 text-left font-normal">Bal. antes</th>
                        <th class="py-2 px-3 text-left font-normal">Bal. después</th>
                        <th class="py-2 px-3 text-left font-normal">Cuenta</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($closedTrades as $trade)
                        @php $lbs = ['60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1','1'=>'1m','5'=>'5m','15'=>'15m']; @endphp
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <td class="py-2 px-3" style="color:var(--color-text-primary);">{{ $trade->strategy }}</td>
                            <td class="py-2 px-3">{{ $trade->symbol }}</td>
                            <td class="py-2 px-3">{{ $lbs[$trade->interval] ?? ($trade->interval ?? '—') }}</td>
                            <td class="py-2 px-3">
                                <span style="color: {{ $trade->side === 'long' ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ strtoupper($trade->side) }}
                                </span>
                            </td>
                            <td class="py-2 px-3">
                                {{ number_format($trade->entry_price, 2) }}<br>
                                <span style="color:var(--color-text-muted);">
                                    {{ \Carbon\Carbon::parse($trade->entry_time)->timezone('America/Bogota')->format('d/m H:i') }}
                                </span>
                            </td>
                            <td class="py-2 px-3">
                                {{ number_format($trade->exit_price, 2) }}<br>
                                <span style="color:var(--color-text-muted);">
                                    {{ $trade->exit_time ? \Carbon\Carbon::parse($trade->exit_time)->timezone('America/Bogota')->format('d/m H:i') : '—' }}
                                </span>
                            </td>
                            <td class="py-2 px-3">
                                @php
                                    $histStatusColors = [
                                        'closed'   => ['bg'=>'#16331F','color'=>'var(--color-profit)'],
                                        'failed'   => ['bg'=>'#3A1A1C','color'=>'var(--color-loss)'],
                                        'error'    => ['bg'=>'#1F2937','color'=>'var(--color-text-muted)'],
                                        'orphaned' => ['bg'=>'#2D1B69','color'=>'#8B5CF6'],
                                        'ignored'  => ['bg'=>'#1F2937','color'=>'var(--color-text-muted)'],
                                    ];
                                    $hsc = $histStatusColors[$trade->status ?? 'closed'] ?? ['bg'=>'#16331F','color'=>'var(--color-profit)'];
                                @endphp
                                <span class="text-[10px] px-1.5 py-0.5 rounded font-medium"
                                      style="background:{{ $hsc['bg'] }}; color:{{ $hsc['color'] }};">
                                    {{ str_replace('_', ' ', $trade->status ?? 'closed') }}
                                </span>
                            </td>
                            <td class="py-2 px-3">{{ str_replace('_', ' ', $trade->exit_reason ?? '—') }}</td>
                            <td class="py-2 px-3">{{ $trade->size }}</td>
                            <td class="py-2 px-3">{{ $trade->commission ? number_format($trade->commission, 4) : '—' }}</td>
                            <td class="py-2 px-3 font-medium"
                                style="color: {{ ($trade->net_pnl ?? $trade->pnl) >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                {{ ($trade->net_pnl ?? $trade->pnl) >= 0 ? '+' : '' }}{{ number_format($trade->net_pnl ?? $trade->pnl, 2) }} USDT
                                <br><span class="text-[10px]">{{ $trade->pnl_pct >= 0 ? '+' : '' }}{{ $trade->pnl_pct }}%</span>
                            </td>
                            <td class="py-2 px-3">{{ $trade->balance_before ? number_format($trade->balance_before, 2) : '—' }}</td>
                            <td class="py-2 px-3">{{ $trade->balance_after ? number_format($trade->balance_after, 2) : '—' }}</td>
                            <td class="py-2 px-3">
                                @php
                                    $acct2 = $filterOptions['accounts']->firstWhere('id', $trade->broker_account_id);
                                @endphp
                                <span class="text-[10px] px-1.5 py-0.5 rounded font-medium"
                                      style="background: {{ ($acct2?->account_type ?? '') === 'demo' ? '#3A2E0E' : '#16331F' }};
                                             color: {{ ($acct2?->account_type ?? '') === 'demo' ? 'var(--color-neutral)' : 'var(--color-profit)' }};">
                                    {{ strtoupper($acct2?->account_type ?? 'real') }}
                                </span>
                                <span class="text-[10px] ml-1" style="color:var(--color-text-muted);">{{ ucfirst($trade->broker ?? 'bybit') }}</span>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    @endif
</div>

@endsection

@push('scripts')
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const equityData = {!! json_encode($equityCurve) !!};
const totalNetPnl = {{ $totalNetPnl }};

// Curva de equity
@if (count($equityCurve) > 1)
const ctx = document.getElementById('equityChart').getContext('2d');
const color = equityData[equityData.length - 1] >= 0 ? 'rgba(61,214,140,1)' : 'rgba(242,84,91,1)';
const colorAlpha = equityData[equityData.length - 1] >= 0 ? 'rgba(61,214,140,0.1)' : 'rgba(242,84,91,0.1)';
new Chart(ctx, {
    type: 'line',
    data: {
        labels: equityData.map((_, i) => i),
        datasets: [{
            data: equityData,
            borderColor: color,
            backgroundColor: colorAlpha,
            borderWidth: 1.5,
            pointRadius: 0,
            fill: true,
            tension: 0.3,
        }]
    },
    options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: {
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#6B7280', font: { size: 10 }, callback: v => v + ' USDT' }
            }
        }
    }
});
@endif

// Precio en tiempo real (cada 30s)
function toggleTradingGuide() {
    const content = document.getElementById('tradingGuideContent');
    const chevron = document.getElementById('tradingGuideChevron');
    const isHidden = content.classList.contains('hidden');
    content.classList.toggle('hidden', !isHidden);
    chevron.textContent = isHidden ? '▲ Ocultar' : '▼ Mostrar';
    localStorage.setItem('tradingGuideOpen', isHidden ? '1' : '0');
}

document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('tradingGuideOpen') === '1') {
        document.getElementById('tradingGuideContent')?.classList.remove('hidden');
        const chevron = document.getElementById('tradingGuideChevron');
        if (chevron) chevron.textContent = '▲ Ocultar';
    }
});

async function refreshLivePrices() {
    try {
        const res = await fetch('{{ route("trading.live-prices") }}', {
            headers: { 'Accept': 'application/json', 'X-CSRF-TOKEN': '{{ csrf_token() }}' }
        });
        const data = await res.json();

        data.forEach(trade => {
            const priceEl = document.getElementById('price_' + trade.id);
            const pnlEl   = document.getElementById('pnl_' + trade.id);

            if (priceEl && trade.current_price) {
                const current = parseFloat(trade.current_price);
                const entry   = parseFloat(priceEl.dataset.entry);
                const side    = priceEl.dataset.side;
                const up      = current >= entry;
                const isGood  = side === 'long' ? up : !up;
                const arrow   = up ? '▲ ' : '▼ ';
                priceEl.textContent = arrow + current.toLocaleString('es-CO', {
                    minimumFractionDigits: 2, maximumFractionDigits: 2
                });
                priceEl.style.color = isGood ? 'var(--color-profit)' : 'var(--color-loss)';
            }
            if (pnlEl && trade.floating_pnl_pct !== null) {
                const pct = parseFloat(trade.floating_pnl_pct);
                pnlEl.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(3) + '%';
                pnlEl.style.color = pct >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
            }
        });
    } catch (e) {
        console.warn('Error actualizando precios:', e);
    }
}

@if ($openTrades->isNotEmpty())
refreshLivePrices();
setInterval(refreshLivePrices, 20000);
@endif
</script>
@endpush

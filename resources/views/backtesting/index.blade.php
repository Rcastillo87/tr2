@extends('layouts.app')

@section('title', 'Backtesting')
@section('header', 'Backtesting')

@section('content')

    {{-- Formulario --}}
    <div class="rounded-lg border p-4 mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Configurar backtest</h3>
            <span class="text-[11px]" style="color:var(--color-text-muted);">Los parámetros se precargan desde la config activa al seleccionar estrategia + símbolo</span>
        </div>

        <form method="POST" action="{{ route('backtesting.run') }}" id="backtestForm"
              class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            @csrf

            {{-- Estrategia --}}
            <div class="col-span-2 sm:col-span-1">
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Estrategia</label>
                <select name="strategy" id="strategy" onchange="loadParams()"
                        class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    @foreach ($strategies as $key => $def)
                        <option value="{{ $key }}" {{ ($old['strategy'] ?? '') === $key ? 'selected' : '' }}>
                            {{ $def['label'] }}
                        </option>
                    @endforeach
                </select>
            </div>

            {{-- Símbolo --}}
            <div class="col-span-2 sm:col-span-1">
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Símbolo</label>
                <select name="symbol" id="symbol" onchange="loadParams()"
                        class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    @foreach ($symbols as $sym)
                        <option value="{{ $sym }}" {{ ($old['symbol'] ?? '') === $sym ? 'selected' : '' }}>{{ $sym }}</option>
                    @endforeach
                </select>
            </div>

            {{-- Intervalo --}}
            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Intervalo</label>
                <select name="interval" id="interval"
                        class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none"
                        style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
                    @foreach ($intervals as $iv)
                        <option value="{{ $iv }}" {{ ($old['interval'] ?? '60') === $iv ? 'selected' : '' }}>
                            @php
                                $labels = ['1'=>'1m','5'=>'5m','15'=>'15m','60'=>'H1','120'=>'H2','240'=>'H4','D'=>'D1'];
                            @endphp
                            {{ $labels[$iv] ?? $iv }}
                        </option>
                    @endforeach
                </select>
            </div>

            {{-- Stop Loss --}}
            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Stop Loss %</label>
                <input type="number" step="0.1" name="sl_pct" id="sl_pct"
                       value="{{ $old['sl_pct'] ?? '1.5' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            {{-- Take Profit --}}
            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Take Profit %</label>
                <input type="number" step="0.1" name="tp_pct" id="tp_pct"
                       value="{{ $old['tp_pct'] ?? '3.0' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            {{-- Break-even --}}
            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Break-even %</label>
                <input type="number" step="0.1" name="be_pct" id="be_pct"
                       value="{{ $old['be_pct'] ?? '2.0' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            {{-- Max duracion --}}
            <div>
                <label class="block text-[11px] mb-1" style="color:var(--color-text-muted);">Máx. duración (velas)</label>
                <input type="number" step="1" name="max_duration" id="max_duration"
                       value="{{ $old['max_duration'] ?? '24' }}"
                       class="w-full rounded-lg px-3 py-2 text-sm border focus:outline-none font-mono"
                       style="background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);">
            </div>

            {{-- Indicador de precarga --}}
            <div id="preloadIndicator" class="col-span-2 sm:col-span-3 lg:col-span-4 hidden">
                <p class="text-[11px] px-2 py-1.5 rounded" style="background:#13233D; color:var(--color-info); border:1px solid #1E3A5F;">
                    ✓ Parámetros precargados desde: <span id="preloadSource" class="font-medium"></span>
                </p>
            </div>

            {{-- Filtro de regimen --}}
            <div class="col-span-2 sm:col-span-3 lg:col-span-2 flex items-center gap-2 mt-1">
                <input type="checkbox" name="regime_filter" id="regime_filter" value="1"
                       {{ ($old['regime_filter'] ?? '1') ? 'checked' : '' }}
                       class="w-4 h-4 rounded border"
                       style="accent-color:var(--color-info);">
                <label for="regime_filter" class="text-sm" style="color:var(--color-text-secondary);">Aplicar filtro de régimen</label>
            </div>

            {{-- Boton --}}
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
        @php $agg = $result['aggregate_metrics']; @endphp

        <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                <h3 class="text-sm font-medium" style="color:var(--color-text-secondary);">
                    {{ $result['strategy'] }} — {{ $result['symbol'] }} / {{ $result['interval'] }}
                </h3>
                @if ($result['passed'])
                    <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium self-start sm:self-auto"
                          style="background:#16331F; color:var(--color-profit); border:1px solid #1E4A2E;">
                        ✓ Aprobada para paper trading
                    </span>
                @else
                    <span class="inline-flex items-center px-2.5 py-1 rounded text-[11px] font-medium self-start sm:self-auto"
                          style="background:#3A1A1C; color:var(--color-loss); border:1px solid #5A2226;">
                        ✗ No aprobada
                    </span>
                @endif
            </div>

            {{-- Métricas agregadas --}}
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
                @foreach ([
                    'total_trades'     => 'Total trades',
                    'win_rate'         => 'Win rate',
                    'profit_factor'    => 'Profit factor',
                    'sharpe_ratio'     => 'Sharpe ratio',
                    'max_drawdown_pct' => 'Max drawdown',
                    'total_return_pct' => 'Return total',
                    'expectancy'       => 'Expectancy',
                    'total_pnl'        => 'P&L total',
                ] as $key => $label)
                    <div class="rounded-md border p-2.5" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <p class="text-[10px] mb-1" style="color:var(--color-text-muted);">{{ $label }}</p>
                        <p class="font-mono text-base font-medium"
                           style="color: {{ in_array($key, ['total_return_pct', 'total_pnl']) ? ($agg[$key] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)') : 'var(--color-text-primary)' }};">
                            {{ isset($agg[$key]) ? (in_array($key, ['win_rate', 'max_drawdown_pct', 'total_return_pct']) ? $agg[$key] . '%' : (in_array($key, ['total_pnl']) ? number_format($agg[$key], 2) : $agg[$key])) : '—' }}
                        </p>
                    </div>
                @endforeach
            </div>

            {{-- Razones --}}
            @if (!empty($result['pass_reasons']))
                <div class="mb-4">
                    <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-muted);">Criterios de evaluación</h4>
                    <ul class="space-y-1">
                        @foreach ($result['pass_reasons'] as $reason)
                            <li class="text-sm" style="color:var(--color-loss);">• {{ $reason }}</li>
                        @endforeach
                    </ul>
                </div>
            @endif

            {{-- Resultados por ventana --}}
            <div>
                <h4 class="text-[11px] font-medium mb-2" style="color:var(--color-text-muted);">Resultados por ventana (walk-forward)</h4>

                <div class="overflow-x-auto">
                    <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                        <thead>
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <th class="py-2 px-2 font-normal">Ventana</th>
                                <th class="py-2 px-2 font-normal">Trades</th>
                                <th class="py-2 px-2 font-normal">Win rate</th>
                                <th class="py-2 px-2 font-normal">P. factor</th>
                                <th class="py-2 px-2 font-normal">Sharpe</th>
                                <th class="py-2 px-2 font-normal">Drawdown</th>
                                <th class="py-2 px-2 font-normal">Return</th>
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
                                    <td class="py-2 px-2"
                                        style="color: {{ $w['total_return_pct'] >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                        {{ $w['total_return_pct'] }}%
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

@push('scripts')
<script>
// Configs de paper trading disponibles para precarga
const paperConfigs = {!! $paperConfigs->toJson() !!};

// Mapa de clase+modo a key de estrategia del formulario
const strategyClassMap = {
    'VwapStrategy_trend_follow': 'VWAP Tendencia',
    'VwapStrategy_reversion':    'VWAP Reversión',
    'MeanReversionStrategy_':    'Reversión a la Media',
    'EmaDonchianStrategy_':      'Tendencia EMA/Donchian',
};

function loadParams() {
    const strategy = document.getElementById('strategy').value;
    const symbol   = document.getElementById('symbol').value;

    // Buscar config activa que coincida con esta estrategia+simbolo
    const config = paperConfigs.find(c => {
        const mode = c.params?.mode || '';
        const key  = c.strategy_class + '_' + mode;
        return strategyClassMap[key] === strategy && c.symbol === symbol;
    });

    const indicator = document.getElementById('preloadIndicator');
    const source    = document.getElementById('preloadSource');

    if (config) {
        const p = config.params;
        if (p.sl_pct !== undefined)     document.getElementById('sl_pct').value      = p.sl_pct;
        if (p.tp_pct !== undefined)     document.getElementById('tp_pct').value      = p.tp_pct;
        if (p.be_pct !== undefined)     document.getElementById('be_pct').value      = p.be_pct;
        if (p.max_duration !== undefined) document.getElementById('max_duration').value = p.max_duration;

        // Precargar intervalo si la config lo especifica
        const intervalSelect = document.getElementById('interval');
        if (config.interval) {
            for (let opt of intervalSelect.options) {
                if (opt.value === config.interval) {
                    opt.selected = true;
                    break;
                }
            }
        }

        indicator.classList.remove('hidden');
        source.textContent = config.display_name;
    } else {
        indicator.classList.add('hidden');
    }
}

// Precargar al cargar la pagina si hay valores previos
document.addEventListener('DOMContentLoaded', () => {
    @if (!empty($old['strategy']))
        // Solo precargar si no hay valores manuales del POST
        @if (empty($old['sl_pct']))
            loadParams();
        @endif
    @else
        loadParams();
    @endif
});
</script>
@endpush

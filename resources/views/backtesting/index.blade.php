@extends('layouts.app')

@section('title', 'Backtesting')
@section('header', 'Backtesting')

@section('content')

    {{-- Formulario --}}
    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-6">
        <h3 class="text-sm font-semibold text-gray-300 mb-4">Configurar Backtest</h3>

        <form method="POST" action="{{ route('backtesting.run') }}" class="grid grid-cols-1 md:grid-cols-3 gap-4">
            @csrf

            <div>
                <label class="block text-xs text-gray-400 mb-1">Estrategia</label>
                <select name="strategy" class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                    @foreach ($strategies as $s)
                        <option value="{{ $s }}" {{ ($old['strategy'] ?? '') === $s ? 'selected' : '' }}>{{ $s }}</option>
                    @endforeach
                </select>
            </div>

            <div>
                <label class="block text-xs text-gray-400 mb-1">Símbolo</label>
                <select name="symbol" class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                    @foreach ($symbols as $sym)
                        <option value="{{ $sym }}" {{ ($old['symbol'] ?? '') === $sym ? 'selected' : '' }}>{{ $sym }}</option>
                    @endforeach
                </select>
            </div>

            <div>
                <label class="block text-xs text-gray-400 mb-1">Timeframe</label>
                <input type="text" value="1H (fijo)" disabled
                       class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-500">
            </div>

            <div>
                <label class="block text-xs text-gray-400 mb-1">Stop Loss %</label>
                <input type="number" step="0.1" name="sl_pct" value="{{ $old['sl_pct'] ?? '1.5' }}"
                       class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>

            <div>
                <label class="block text-xs text-gray-400 mb-1">Take Profit %</label>
                <input type="number" step="0.1" name="tp_pct" value="{{ $old['tp_pct'] ?? '3.0' }}"
                       class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>

            <div>
                <label class="block text-xs text-gray-400 mb-1">Break-even %</label>
                <input type="number" step="0.1" name="be_pct" value="{{ $old['be_pct'] ?? '2.0' }}"
                       class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>

            <div>
                <label class="block text-xs text-gray-400 mb-1">Máx. duración (velas H1)</label>
                <input type="number" step="1" name="max_duration" value="{{ $old['max_duration'] ?? '24' }}"
                       class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>

            <div class="flex items-center gap-2 mt-6">
                <input type="checkbox" name="regime_filter" id="regime_filter" value="1"
                       {{ ($old['regime_filter'] ?? '1') ? 'checked' : '' }}
                       class="w-4 h-4 rounded bg-gray-900 border-gray-700 text-blue-600 focus:ring-blue-500">
                <label for="regime_filter" class="text-sm text-gray-300">Aplicar filtro de régimen</label>
            </div>

            <div class="flex items-end">
                <button type="submit"
                        class="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                    Ejecutar Backtest (Walk-Forward)
                </button>
            </div>
        </form>
    </div>

    {{-- Error --}}
    @if ($error)
        <div class="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-6 text-red-400 text-sm">
            {{ $error }}
        </div>
    @endif

    {{-- Resultado --}}
    @if ($result)
        @php
            $agg = $result['aggregate_metrics'];
        @endphp

        <div class="bg-gray-800 border border-gray-700 rounded-xl p-5 mb-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-sm font-semibold text-gray-300">
                    {{ $result['strategy'] }} — {{ $result['symbol'] }}
                </h3>
                @if ($result['passed'])
                    <span class="inline-flex items-center px-3 py-1 rounded-md text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/30">
                        ✓ Aprobada para Paper Trading
                    </span>
                @else
                    <span class="inline-flex items-center px-3 py-1 rounded-md text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30">
                        ✗ No aprobada
                    </span>
                @endif
            </div>

            {{-- Métricas agregadas --}}
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Total Trades</p>
                    <p class="text-lg font-semibold text-white">{{ $agg['total_trades'] }}</p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Win Rate</p>
                    <p class="text-lg font-semibold text-white">{{ $agg['win_rate'] }}%</p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Profit Factor</p>
                    <p class="text-lg font-semibold text-white">{{ $agg['profit_factor'] ?? '—' }}</p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Sharpe Ratio</p>
                    <p class="text-lg font-semibold text-white">{{ $agg['sharpe_ratio'] }}</p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Max Drawdown</p>
                    <p class="text-lg font-semibold text-white">{{ $agg['max_drawdown_pct'] }}%</p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Return Total</p>
                    <p class="text-lg font-semibold {{ $agg['total_return_pct'] >= 0 ? 'text-green-400' : 'text-red-400' }}">
                        {{ $agg['total_return_pct'] }}%
                    </p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">Expectancy</p>
                    <p class="text-lg font-semibold text-white">{{ $agg['expectancy'] }}</p>
                </div>
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-3">
                    <p class="text-xs text-gray-400 mb-1">P&L Total</p>
                    <p class="text-lg font-semibold {{ $agg['total_pnl'] >= 0 ? 'text-green-400' : 'text-red-400' }}">
                        {{ number_format($agg['total_pnl'], 2) }}
                    </p>
                </div>
            </div>

            {{-- Razones --}}
            <div class="mb-6">
                <h4 class="text-xs font-semibold text-gray-400 mb-2">Criterios de evaluación</h4>
                <ul class="space-y-1">
                    @foreach ($result['pass_reasons'] as $reason)
                        <li class="text-sm {{ str_contains($reason, 'aprobada') ? 'text-green-400' : 'text-red-400' }}">
                            • {{ $reason }}
                        </li>
                    @endforeach
                </ul>
            </div>

            {{-- Resultados por ventana --}}
            <div>
                <h4 class="text-xs font-semibold text-gray-400 mb-2">Resultados por Ventana (Walk-Forward)</h4>
                <div class="overflow-x-auto">
                    <table class="w-full text-xs text-left text-gray-400">
                        <thead>
                            <tr class="border-b border-gray-700">
                                <th class="py-2 pr-4">Ventana</th>
                                <th class="py-2 pr-4">Trades</th>
                                <th class="py-2 pr-4">Win Rate</th>
                                <th class="py-2 pr-4">Profit Factor</th>
                                <th class="py-2 pr-4">Sharpe</th>
                                <th class="py-2 pr-4">Drawdown</th>
                                <th class="py-2">P&L</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($result['window_results'] as $w)
                                <tr class="border-b border-gray-800">
                                    <td class="py-2 pr-4 text-white">{{ $w['window'] }}</td>
                                    <td class="py-2 pr-4">{{ $w['total_trades'] }}</td>
                                    <td class="py-2 pr-4">{{ $w['win_rate'] }}%</td>
                                    <td class="py-2 pr-4">{{ $w['profit_factor'] ?? '—' }}</td>
                                    <td class="py-2 pr-4">{{ $w['sharpe_ratio'] }}</td>
                                    <td class="py-2 pr-4">{{ $w['max_drawdown_pct'] }}%</td>
                                    <td class="py-2 {{ $w['total_pnl'] >= 0 ? 'text-green-400' : 'text-red-400' }}">
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

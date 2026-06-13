@extends('layouts.app')

@section('title', 'Data Collector')
@section('header', 'Data Collector')

@section('content')

    <div class="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-300">Estado de la Recolección de Datos</h3>
            <span class="text-xs text-gray-500">Actualización automática cada 1 minuto</span>
        </div>

        @if (count($status) === 0)
            <p class="text-sm text-gray-500">No se pudo conectar con el motor de recolección.</p>
        @else
            <div class="overflow-x-auto">
                <table class="w-full text-sm text-left text-gray-400">
                    <thead>
                        <tr class="border-b border-gray-700">
                            <th class="py-3 pr-4">Par / Intervalo</th>
                            <th class="py-3 pr-4">Última Vela</th>
                            <th class="py-3">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($status as $key => $data)
                            @php
                                [$symbol, $interval] = explode('/', $key);
                                $intervalLabels = ['1' => '1m', '5' => '5m', '15' => '15m', '60' => '1h'];
                            @endphp
                            <tr class="border-b border-gray-800">
                                <td class="py-3 pr-4 text-white font-medium">
                                    {{ $symbol }} <span class="text-gray-500">/ {{ $intervalLabels[$interval] ?? $interval }}</span>
                                </td>
                                <td class="py-3 pr-4">
                                    {{ $data['last_candle'] ? \Carbon\Carbon::parse($data['last_candle'])->format('Y-m-d H:i:s') . ' UTC' : '—' }}
                                </td>
                                <td class="py-3">
                                    @if ($data['has_data'])
                                        <span class="inline-flex items-center gap-1.5 text-green-400">
                                            <span class="h-2 w-2 rounded-full bg-green-500"></span> Activo
                                        </span>
                                    @else
                                        <span class="inline-flex items-center gap-1.5 text-red-400">
                                            <span class="h-2 w-2 rounded-full bg-red-500"></span> Sin datos
                                        </span>
                                    @endif
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>

@endsection

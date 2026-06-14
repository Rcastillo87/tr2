@extends('layouts.app')

@section('title', 'Data Collector')
@section('header', 'Data Collector')

@section('content')

    <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-3">
            <h3 class="text-xs font-medium" style="color:var(--color-text-secondary);">Estado de la recolección de datos</h3>
            <span class="text-[11px]" style="color:var(--color-text-muted);">Actualización automática cada 1 minuto</span>
        </div>

        @if (count($status) === 0)
            <p class="text-sm" style="color:var(--color-text-muted);">No se pudo conectar con el motor de recolección.</p>
        @else
            @php
                $intervalLabels = ['1' => '1m', '5' => '5m', '15' => '15m', '60' => '1h'];
            @endphp

            {{-- Mobile: cards --}}
            <div class="space-y-2 sm:hidden">
                @foreach ($status as $key => $data)
                    @php
                        [$symbol, $interval] = explode('/', $key);
                    @endphp
                    <div class="rounded-md border p-3 flex items-center justify-between" style="background:var(--color-surface-raised); border-color:var(--color-border-strong);">
                        <div>
                            <p class="text-sm font-medium" style="color:var(--color-text-primary);">
                                {{ $symbol }} <span style="color:var(--color-text-muted);">/ {{ $intervalLabels[$interval] ?? $interval }}</span>
                            </p>
                            <p class="font-mono text-[11px] mt-1" style="color:var(--color-text-muted);">
                                {{ $data['last_candle'] ? \Carbon\Carbon::parse($data['last_candle'])->format('d/m H:i') . ' UTC' : '—' }}
                            </p>
                        </div>
                        @if ($data['has_data'])
                            <span class="inline-flex items-center gap-1.5 text-[11px]" style="color:var(--color-profit);">
                                <span class="h-2 w-2 rounded-full" style="background:var(--color-profit);"></span> Activo
                            </span>
                        @else
                            <span class="inline-flex items-center gap-1.5 text-[11px]" style="color:var(--color-loss);">
                                <span class="h-2 w-2 rounded-full" style="background:var(--color-loss);"></span> Sin datos
                            </span>
                        @endif
                    </div>
                @endforeach
            </div>

            {{-- Desktop: tabla --}}
            <div class="overflow-x-auto hidden sm:block">
                <table class="w-full text-sm text-left" style="color:var(--color-text-muted);">
                    <thead>
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <th class="py-3 pr-4 font-normal">Par / Intervalo</th>
                            <th class="py-3 pr-4 font-normal">Última vela</th>
                            <th class="py-3 font-normal">Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($status as $key => $data)
                            @php
                                [$symbol, $interval] = explode('/', $key);
                            @endphp
                            <tr class="border-b" style="border-color:var(--color-border-soft);">
                                <td class="py-3 pr-4 font-medium" style="color:var(--color-text-primary);">
                                    {{ $symbol }} <span style="color:var(--color-text-muted);">/ {{ $intervalLabels[$interval] ?? $interval }}</span>
                                </td>
                                <td class="py-3 pr-4 font-mono text-xs">
                                    {{ $data['last_candle'] ? \Carbon\Carbon::parse($data['last_candle'])->format('Y-m-d H:i:s') . ' UTC' : '—' }}
                                </td>
                                <td class="py-3">
                                    @if ($data['has_data'])
                                        <span class="inline-flex items-center gap-1.5" style="color:var(--color-profit);">
                                            <span class="h-2 w-2 rounded-full" style="background:var(--color-profit);"></span> Activo
                                        </span>
                                    @else
                                        <span class="inline-flex items-center gap-1.5" style="color:var(--color-loss);">
                                            <span class="h-2 w-2 rounded-full" style="background:var(--color-loss);"></span> Sin datos
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

@extends('layouts.app')
@section('title', 'Backtesting')
@section('header', 'Backtesting')

@section('content')
<style>button, a[href] { cursor: pointer; }</style>

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    <div class="flex items-center justify-between mb-4">
        <p class="text-[11px]" style="color:var(--color-text-muted);">
            Selecciona una estrategia para ver su historial de backtests o crear uno nuevo.
        </p>
    </div>

    <div class="rounded-lg border overflow-hidden" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="overflow-x-auto">
            <table class="w-full text-left text-[12px]">
                <thead>
                    <tr style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                        <th class="px-4 py-3 font-medium">Estrategia</th>
                        <th class="px-4 py-3 font-medium text-center">Backtests Guardados</th>
                        <th class="px-4 py-3 font-medium text-center">Estado en Paper</th>
                        <th class="px-4 py-3 font-medium text-right">Acciones</th>
                    </tr>
                </thead>
                <tbody class="divide-y" style="border-color:var(--color-border-soft);">
                    @forelse($strategies as $s)
                    <tr class="hover:bg-[#1A2230] transition-colors">
                        <td class="px-4 py-4">
                            <span class="font-medium text-sm block" style="color:var(--color-text-primary);">{{ $s->name }}</span>
                            <span class="text-[10px]" style="color:var(--color-text-muted);">{{ $s->description }}</span>
                        </td>
                        <td class="px-4 py-4 text-center">
                            <span class="px-2 py-1 rounded-full text-[11px] font-mono" style="background:var(--color-surface-raised); color:var(--color-text-primary);">
                                {{ $s->backtests_count }}
                            </span>
                        </td>
                        <td class="px-4 py-4 text-center">
                            @if($s->is_operating)
                                <span class="px-2 py-0.5 rounded text-[10px] font-medium" style="background:#16331F; color:var(--color-profit); border: 1px solid #1E4A2E;">
                                    OPERANDO
                                </span>
                            @else
                                <span class="px-2 py-0.5 rounded text-[10px] font-medium" style="background:var(--color-surface-raised); color:var(--color-text-muted);">
                                    NO IMPLEMENTADO
                                </span>
                            @endif
                        </td>
                        <td class="px-4 py-4 text-right space-x-2">
                            <a href="{{ route('backtesting.run') }}?strategy_id={{ $s->id }}" class="text-[11px] font-medium px-3 py-1.5 rounded border transition-colors" style="background:var(--color-info); color:#fff; border-color:var(--color-info);">
                                + Nuevo Backtest
                            </a>
                            <a href="{{ route('backtesting.history', $s) }}" class="text-[11px] font-medium px-3 py-1.5 rounded border transition-colors inline-block" style="background:var(--color-surface-raised); color:var(--color-text-primary); border-color:var(--color-border-strong);">
                                Ver Historial ({{ $s->backtests_count }})
                            </a>
                        </td>
                    </tr>
                    @empty
                    <tr>
                        <td colspan="4" class="px-4 py-8 text-center text-sm" style="color:var(--color-text-muted);">
                            No hay estrategias activas.
                        </td>
                    </tr>
                    @endforelse
                </tbody>
            </table>
        </div>
    </div>
@endsection

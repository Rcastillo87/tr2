@extends('layouts.app')

@section('title', 'Configuración de estrategias')
@section('header', 'Paper Trading — Configuración de estrategias')

@section('content')

    @if (session('status'))
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#16331F; border-color:#1E4A2E; color:var(--color-profit);">
            {{ session('status') }}
        </div>
    @endif

    @if ($errors->any())
        <div class="rounded-lg border p-3 mb-4 text-sm" style="background:#3A1A1C; border-color:#5A2226; color:var(--color-loss);">
            {{ $errors->first() }}
        </div>
    @endif

    <p class="text-[11px] mb-4" style="color:var(--color-text-muted);">
        Cada fila representa una combinación activa de estrategia + símbolo + intervalo en paper trading.
        Solo el administrador puede editar estos parámetros.
    </p>

    {{-- Mobile/tablet: cards --}}
    <div class="space-y-2 lg:hidden">
        @foreach ($configs as $config)
            <div class="rounded-lg border p-4" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <div class="flex items-start justify-between mb-2 gap-2">
                    <div class="min-w-0">
                        <p class="text-sm font-medium truncate" style="color:var(--color-text-primary);">{{ $config->display_name }}</p>
                        <p class="text-[11px] mt-0.5" style="color:var(--color-text-muted);">{{ $config->strategy_class }}</p>
                    </div>
                    <span class="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0"
                          style="background: {{ $config->active ? '#16331F' : '#3A1A1C' }}; color: {{ $config->active ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                        {{ $config->active ? 'ACTIVA' : 'INACTIVA' }}
                    </span>
                </div>
                <div class="grid grid-cols-2 gap-2 font-mono text-[11px] mb-3" style="color:var(--color-text-muted);">
                    <div><p class="text-[10px]">Símbolo</p><p style="color:var(--color-text-primary);">{{ $config->symbol }}</p></div>
                    <div><p class="text-[10px]">Intervalo</p><p style="color:var(--color-text-primary);">{{ $config->interval }}</p></div>
                </div>
                <div class="flex gap-2">
                    <a href="{{ route('paper-trading.configs.edit', $config) }}"
                       class="flex-1 text-center text-[11px] px-2 py-1.5 rounded border transition-colors"
                       style="color:var(--color-info); border-color:var(--color-border-soft);">
                        Editar
                    </a>
                    <form method="POST" action="{{ route('paper-trading.configs.toggle', $config) }}" class="flex-1">
                        @csrf @method('PATCH')
                        <button type="submit" class="w-full text-[11px] px-2 py-1.5 rounded border transition-colors"
                                style="color: {{ $config->active ? 'var(--color-loss)' : 'var(--color-profit)' }}; border-color:var(--color-border-soft);">
                            {{ $config->active ? 'Desactivar' : 'Activar' }}
                        </button>
                    </form>
                </div>
            </div>
        @endforeach
    </div>

    {{-- Desktop: tabla --}}
    <div class="rounded-lg border hidden lg:block" style="background:var(--color-surface); border-color:var(--color-border-soft);">
        <div class="overflow-x-auto">
            <table class="w-full font-mono text-[11px] text-left" style="color:var(--color-text-muted);">
                <thead>
                    <tr class="border-b" style="border-color:var(--color-border-soft);">
                        <th class="py-2.5 px-3 font-normal">Nombre</th>
                        <th class="py-2.5 px-3 font-normal">Clase</th>
                        <th class="py-2.5 px-3 font-normal">Símbolo</th>
                        <th class="py-2.5 px-3 font-normal">Intervalo</th>
                        <th class="py-2.5 px-3 font-normal">Modo/Params clave</th>
                        <th class="py-2.5 px-3 font-normal">Estado</th>
                        <th class="py-2.5 px-3 font-normal">Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach ($configs as $config)
                        <tr class="border-b" style="border-color:var(--color-border-soft);">
                            <td class="py-2 px-3" style="color:var(--color-text-primary);">{{ $config->display_name }}</td>
                            <td class="py-2 px-3">{{ $config->strategy_class }}</td>
                            <td class="py-2 px-3">{{ $config->symbol }}</td>
                            <td class="py-2 px-3">{{ $config->interval }}</td>
                            <td class="py-2 px-3" style="color:var(--color-text-muted);">
                                @if (isset($config->params['mode']))
                                    mode: {{ $config->params['mode'] }} |
                                @endif
                                sl: {{ $config->params['sl_pct'] ?? '—' }}% |
                                tp: {{ $config->params['tp_pct'] ?? '—' }}%
                            </td>
                            <td class="py-2 px-3">
                                <span class="px-1.5 py-0.5 rounded text-[10px]"
                                      style="background: {{ $config->active ? '#16331F' : '#3A1A1C' }}; color: {{ $config->active ? 'var(--color-profit)' : 'var(--color-loss)' }};">
                                    {{ $config->active ? 'ACTIVA' : 'INACTIVA' }}
                                </span>
                            </td>
                            <td class="py-2 px-3">
                                <div class="flex items-center gap-2">
                                    <a href="{{ route('paper-trading.configs.edit', $config) }}"
                                       class="text-[11px]" style="color:var(--color-info);">
                                        Editar
                                    </a>
                                    <form method="POST" action="{{ route('paper-trading.configs.toggle', $config) }}">
                                        @csrf @method('PATCH')
                                        <button type="submit" class="text-[11px]"
                                                style="color: {{ $config->active ? 'var(--color-loss)' : 'var(--color-profit)' }};">
                                            {{ $config->active ? 'Desactivar' : 'Activar' }}
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    </div>

@endsection

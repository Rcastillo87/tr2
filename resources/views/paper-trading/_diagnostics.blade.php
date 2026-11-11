{{-- RQ-01.5: diagnóstico de Paper (qué decidió cada config activa en su última evaluación y por qué). Datos: App\Services\PaperDiagnostics --}}
@php
    $tone = [
        'problem'  => ['#3A1A1C', 'var(--color-loss)', '#5A2226'],
        'missing'  => ['#3A1A1C', 'var(--color-loss)', '#5A2226'],
        'stale'    => ['#3A1A1C', 'var(--color-loss)', '#5A2226'],
        'blocked'  => ['#2A2213', '#E8C77A', '#4A3D1A'],
        'filtered' => ['#2A2213', '#E8C77A', '#4A3D1A'],
        'position' => ['#13233D', 'var(--color-info)', '#1E3A5F'],
        'trade'    => ['#16331F', 'var(--color-profit)', '#1E4A2E'],
        'quiet'    => ['var(--color-surface-raised)', 'var(--color-text-muted)', 'var(--color-border-strong)'],
    ];
    $bog = fn ($t) => $t?->copy()->timezone('America/Bogota')->format('d-m H:i');
    $problems = $d['counts']['problem'] ?? 0;
@endphp
<details class="rounded-lg border mb-4" style="background:var(--color-surface); border-color:var(--color-border-soft);" @if($problems > 0) open @endif>
    <summary class="px-4 py-3 flex items-center justify-between flex-wrap gap-2 cursor-pointer" style="list-style:none;">
        <span class="text-xs font-medium" style="color:var(--color-text-secondary);">
            Diagnóstico ({{ count($d['rows']) }} configs activas) ▾
        </span>
        <span class="flex flex-wrap gap-3 text-[11px]" style="color:var(--color-text-muted);">
            @foreach(\App\Services\PaperDiagnostics::GROUPS as $g => $label)
                @if(($d['counts'][$g] ?? 0) > 0 || $g === 'problem')
                    <span>{{ $label }}: <b style="color:{{ $g === 'problem' && $problems > 0 ? 'var(--color-loss)' : 'var(--color-text-primary)' }};">{{ $d['counts'][$g] ?? 0 }}</b></span>
                @endif
            @endforeach
            <span>Última evaluación: <b style="color:var(--color-text-primary);">{{ $bog($d['last']) ?? '—' }}</b></span>
        </span>
    </summary>
    <div class="overflow-x-auto border-t" style="border-color:var(--color-border-soft);">
        <table class="w-full text-[11px]" style="color:var(--color-text-muted); min-width: 900px;">
            <thead>
                <tr class="border-b" style="border-color:var(--color-border-soft);">
                    <th class="py-2 px-3 text-left font-normal">Config</th>
                    <th class="py-2 px-3 text-left font-normal">Decisión</th>
                    <th class="py-2 px-3 text-left font-normal">Régimen</th>
                    <th class="py-2 px-3 text-left font-normal">Vela evaluada</th>
                    <th class="py-2 px-3 text-left font-normal">Últimas 24 h</th>
                    <th class="py-2 px-3 text-left font-normal">Detalle</th>
                </tr>
            </thead>
            <tbody>
            @forelse($d['rows'] as $r)
                @php [$bg, $fg, $bd] = $tone[$r['group']] ?? $tone['quiet']; @endphp
                <tr class="border-b align-top" style="border-color:var(--color-border-soft);">
                    <td class="py-2 px-3 whitespace-nowrap" style="color:var(--color-text-primary);">#{{ $r['id'] }} · {{ $r['symbol'] }} · {{ $r['interval'] }}</td>
                    <td class="py-2 px-3 whitespace-nowrap">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-medium border" style="background:{{ $bg }}; color:{{ $fg }}; border-color:{{ $bd }};">{{ $r['label'] }}</span>
                    </td>
                    <td class="py-2 px-3 font-mono">{{ $r['regime'] ?? '—' }}</td>
                    <td class="py-2 px-3 font-mono whitespace-nowrap">{{ $bog($r['candle_time']) ?? '—' }}@if($r['bars'] !== null) <span class="text-[10px]">({{ $r['bars'] }} velas)</span>@endif</td>
                    <td class="py-2 px-3">
                        @forelse($r['day'] as [$label, $n])
                            <span class="whitespace-nowrap">{{ $label }} {{ $n }}</span>@if(! $loop->last) · @endif
                        @empty
                            —
                        @endforelse
                    </td>
                    <td class="py-2 px-3">
                        @if($r['trace'] || $r['detail'] !== '')
                            <details>
                                <summary class="cursor-pointer" style="color:var(--color-info);">Ver</summary>
                                <div class="mt-2 flex flex-col gap-2" style="min-width: 420px;">
                                    @if($r['detail'] !== '')<span>{{ $r['detail'] }}</span>@endif
                                    @if($r['trace'])
                                        <div class="flex flex-wrap gap-1 font-mono text-[10px]">
                                            @foreach($r['trace'] as $t)
                                                <span class="px-1.5 py-0.5 rounded border" style="background:{{ $t['kills'] ? '#2A2213' : 'var(--color-surface-raised)' }}; color:{{ $t['kills'] ? '#E8C77A' : ($t['signal'] !== 0 ? 'var(--color-text-primary)' : 'var(--color-text-muted)') }}; border-color:{{ $t['kills'] ? '#4A3D1A' : 'var(--color-border-strong)' }};">{{ $t['step'] }} · {{ $t['signal'] }}{{ $t['kills'] ? ' · anuló' : '' }}</span>
                                            @endforeach
                                        </div>
                                        <span class="text-[10px]">Cada paso recibe la señal del anterior (1 largo, −1 corto, 0 nada).</span>
                                    @endif
                                </div>
                            </details>
                        @else
                            —
                        @endif
                    </td>
                </tr>
            @empty
                <tr><td colspan="6" class="py-4 px-3 text-center">No hay configs activas en Paper.</td></tr>
            @endforelse
            </tbody>
        </table>
    </div>
</details>

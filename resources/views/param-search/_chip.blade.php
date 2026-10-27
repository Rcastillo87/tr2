{{-- Estado de la última búsqueda de una estrategia (lista de Estrategias). Variables: $sbRun, $sbLabels --}}
@if($sbRun)
    @php
        $ivs = collect($sbRun->intervals ?? [])->map(fn ($i) => $sbLabels[$i] ?? $i)->implode(', ');
        $url = route('strategies.search.show', $sbRun->id);
    @endphp
    <br>
    @if(in_array($sbRun->status, ['queued', 'running']))
        <a class="sb-chip" href="{{ $url }}" data-sb-active="{{ $sbRun->id }}"
           data-sb-status-url="{{ route('strategies.search.status', $sbRun->id) }}" data-sb-ivs="{{ $ivs }}">
            <i class="sb-dot"></i><span>{{ $sbRun->status === 'queued' ? "En cola · {$ivs}" : "Buscando {$ivs} · {$sbRun->progress_done}/{$sbRun->progress_total}" }}</span>
        </a>
    @elseif($sbRun->status === 'done')
        <a class="sb-chip {{ (int) $sbRun->validated > 0 ? 'ok' : 'muted' }}" href="{{ $url }}">
            {{ (int) $sbRun->validated > 0 ? '✓' : '○' }} Búsqueda {{ $ivs }} · {{ (int) $sbRun->validated }} validada(s) · {{ $sbRun->finished_at?->diffForHumans() }}
        </a>
    @else
        <a class="sb-chip bad" href="{{ $url }}">✗ Búsqueda {{ $ivs }} {{ $sbRun->status === 'cancelled' ? 'cancelada' : 'falló' }}</a>
    @endif
@endif

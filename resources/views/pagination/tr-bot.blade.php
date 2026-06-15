@if ($paginator->hasPages())
    <nav role="navigation" aria-label="Paginación" class="flex items-center gap-1 font-mono text-[11px]">

        {{-- Anterior --}}
        @if ($paginator->onFirstPage())
            <span class="px-2.5 py-1.5 rounded cursor-not-allowed" style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
                ‹ Anterior
            </span>
        @else
            <a href="{{ $paginator->previousPageUrl() }}" class="px-2.5 py-1.5 rounded transition-colors" style="color:var(--color-text-secondary); border:1px solid var(--color-border-soft);"
               onmouseover="this.style.borderColor='var(--color-info)'" onmouseout="this.style.borderColor='var(--color-border-soft)'">
                ‹ Anterior
            </a>
        @endif

        {{-- Numeros de pagina --}}
        @foreach ($elements as $element)
            @if (is_string($element))
                <span class="px-2.5 py-1.5" style="color:var(--color-text-muted);">{{ $element }}</span>
            @endif

            @if (is_array($element))
                @foreach ($element as $page => $url)
                    @if ($page == $paginator->currentPage())
                        <span class="px-2.5 py-1.5 rounded font-medium" style="background:var(--color-info); color:#fff;">{{ $page }}</span>
                    @else
                        <a href="{{ $url }}" class="px-2.5 py-1.5 rounded transition-colors" style="color:var(--color-text-secondary); border:1px solid var(--color-border-soft);"
                           onmouseover="this.style.borderColor='var(--color-info)'" onmouseout="this.style.borderColor='var(--color-border-soft)'">
                            {{ $page }}
                        </a>
                    @endif
                @endforeach
            @endif
        @endforeach

        {{-- Siguiente --}}
        @if ($paginator->hasMorePages())
            <a href="{{ $paginator->nextPageUrl() }}" class="px-2.5 py-1.5 rounded transition-colors" style="color:var(--color-text-secondary); border:1px solid var(--color-border-soft);"
               onmouseover="this.style.borderColor='var(--color-info)'" onmouseout="this.style.borderColor='var(--color-border-soft)'">
                Siguiente ›
            </a>
        @else
            <span class="px-2.5 py-1.5 rounded cursor-not-allowed" style="color:var(--color-text-muted); border:1px solid var(--color-border-soft);">
                Siguiente ›
            </span>
        @endif

    </nav>
@endif

@props(['messages'])
@if ($messages)
    <ul {{ $attributes->merge(['class' => 'text-[11px] space-y-1 mt-1']) }} style="color:var(--color-loss);">
        @foreach ((array) $messages as $message)
            <li>{{ $message }}</li>
        @endforeach
    </ul>
@endif

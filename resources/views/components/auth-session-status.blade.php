@props(['status'])
@if ($status)
    <div {{ $attributes->merge(['class' => 'font-medium text-sm mb-4']) }} style="color:var(--color-profit);">
        {{ $status }}
    </div>
@endif

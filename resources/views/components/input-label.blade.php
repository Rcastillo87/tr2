@props(['value'])
<label {{ $attributes->merge(['class' => 'block text-[11px] mb-1']) }} style="color:var(--color-text-muted);">
    {{ $value ?? $slot }}
</label>

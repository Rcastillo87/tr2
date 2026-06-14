@props(['disabled' => false])
<input @disabled($disabled) {{ $attributes->merge([
    'class' => 'w-full rounded-lg px-3 py-2 text-sm border focus:outline-none transition-colors',
    'style' => 'background:var(--color-surface-raised); border-color:var(--color-border-strong); color:var(--color-text-primary);',
]) }}
onfocus="this.style.borderColor='var(--color-info)'"
onblur="this.style.borderColor='var(--color-border-strong)'">

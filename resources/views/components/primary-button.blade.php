<button {{ $attributes->merge([
    'type' => 'submit',
    'class' => 'inline-flex items-center px-4 py-2 rounded-lg font-medium text-sm transition-colors',
    'style' => 'background:var(--color-info); color:#fff;',
]) }}>
    {{ $slot }}
</button>

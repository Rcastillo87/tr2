@php
    $regimeColors = [
        'TRENDING' => 'bg-green-500/10 text-green-400 border-green-500/30',
        'RANGING'  => 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
        'VOLATILE' => 'bg-red-500/10 text-red-400 border-red-500/30',
    ];
    $color = $regimeColors[$regime] ?? 'bg-gray-500/10 text-gray-400 border-gray-500/30';
@endphp

<span class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium border {{ $color }}">
    {{ $regime }}
</span>

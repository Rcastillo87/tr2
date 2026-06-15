@php
    $user = auth()->user();

    $links = [
        ['route' => 'dashboard',            'match' => 'dashboard',          'icon' => 'home',     'label' => 'Vista general', 'visible' => true],
        ['route' => 'paper-trading.index',  'match' => 'paper-trading.*',    'icon' => 'chart',    'label' => 'Paper trading', 'visible' => $user?->canViewPaperTrading() ?? false],
        ['route' => 'backtesting.index',    'match' => 'backtesting.*',      'icon' => 'flask',    'label' => 'Backtesting',   'visible' => $user?->canViewAnalysisTools() ?? false],
        ['route' => 'data-collector.index', 'match' => 'data-collector.*',   'icon' => 'database', 'label' => 'Data collector','visible' => $user?->canViewAnalysisTools() ?? false],
        ['route' => 'users.index',          'match' => 'users.*',            'icon' => 'users',    'label' => 'Usuarios',      'visible' => $user?->canManageUsers() ?? false],
    ];
@endphp
@foreach ($links as $link)
    @continue(! $link['visible'])
    @php $active = request()->routeIs($link['match']); @endphp
    <a href="{{ route($link['route']) }}"
       class="flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors"
       style="
           {{ $active ? 'background:var(--color-surface-raised); color:var(--color-text-primary);' : 'color:var(--color-text-secondary);' }}
       "
       onmouseover="this.style.color='var(--color-text-primary)'"
       onmouseout="this.style.color='{{ $active ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}'">
        @include('layouts.icon', ['name' => $link['icon']])
        {{ $link['label'] }}
    </a>
@endforeach

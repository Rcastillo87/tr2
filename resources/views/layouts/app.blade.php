<!DOCTYPE html>
<html lang="es" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#0A0E14">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <title>@yield('title', 'tr-bot')</title>
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body class="bg-base text-[var(--color-text-primary)] font-sans antialiased" style="background:var(--color-base); color:var(--color-text-primary);">

    <div class="flex h-screen overflow-hidden">

        {{-- Sidebar — desktop only --}}
        <aside class="hidden lg:flex lg:w-60 flex-col border-r"
               style="background:var(--color-surface); border-color:var(--color-border-soft);">
            <div class="p-4 border-b" style="border-color:var(--color-border-soft);">
                <p class="text-[11px] uppercase tracking-wider" style="color:var(--color-text-muted);">tr-bot</p>
                <p class="text-base font-medium mt-0.5" style="color:var(--color-text-primary);">Vista general</p>
            </div>

            <nav class="flex-1 px-3 py-4 space-y-1">
                @include('layouts.nav-links')
            </nav>

            <div class="p-3 border-t space-y-2" style="border-color:var(--color-border-soft);">
                <div class="flex items-center gap-2 px-3 py-2 rounded-md" style="background:var(--color-surface-raised);">
                    <span class="relative flex h-2 w-2">
                        <span class="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping" style="background:var(--color-profit);"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2" style="background:var(--color-profit);"></span>
                    </span>
                    <span class="text-xs" style="color:var(--color-text-secondary);">Sistema activo</span>
                </div>

                @auth
                    @php
                        $roleLabels = [
                            'admin' => 'Administrador',
                            'consultor' => 'Consultor',
                            'inversionista' => 'Inversionista',
                        ];
                    @endphp
                    <div class="flex items-center justify-between gap-2 px-3 py-2 rounded-md" style="background:var(--color-surface-raised);">
                        <div class="min-w-0">
                            <p class="text-xs font-medium truncate" style="color:var(--color-text-primary);">{{ auth()->user()->name }}</p>
                            <p class="text-[10px]" style="color:var(--color-text-muted);">{{ $roleLabels[auth()->user()->role] ?? auth()->user()->role }}</p>
                        </div>
                        <form method="POST" action="{{ route('logout') }}">
                            @csrf
                            <button type="submit" class="text-[11px] shrink-0" style="color:var(--color-loss);">
                                Salir
                            </button>
                        </form>
                    </div>
                @endauth
            </div>
        </aside>

        {{-- Main content --}}
        <div class="flex-1 flex flex-col overflow-hidden">

            {{-- Top bar — mobile/tablet only --}}
            <header class="lg:hidden flex items-center justify-between px-4 py-3 border-b"
                    style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <div class="min-w-0">
                    <p class="text-[10px] uppercase tracking-wider" style="color:var(--color-text-muted);">tr-bot</p>
                    <p class="text-sm font-medium mt-0.5 truncate">@yield('header', 'Dashboard')</p>
                </div>

                <div class="flex items-center gap-3 shrink-0">
                    <span class="relative flex h-2 w-2">
                        <span class="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping" style="background:var(--color-profit);"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2" style="background:var(--color-profit);"></span>
                    </span>

                    @auth
                        <form method="POST" action="{{ route('logout') }}">
                            @csrf
                            <button type="submit" class="text-[11px]" style="color:var(--color-loss);">
                                Salir
                            </button>
                        </form>
                    @endauth
                </div>
            </header>

            {{-- Desktop header --}}
            <header class="hidden lg:block px-6 py-4 border-b" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <h2 class="text-lg font-medium">@yield('header', 'Dashboard')</h2>
            </header>

            <main class="flex-1 overflow-y-auto p-4 lg:p-6 pb-20 lg:pb-6">
                @yield('content')
            </main>
        </div>
    </div>

    {{-- Bottom nav — mobile/tablet only --}}
    <nav class="lg:hidden fixed bottom-0 left-0 right-0 border-t z-50"
         style="background:var(--color-surface); border-color:var(--color-border-soft); padding-bottom: env(safe-area-inset-bottom);">
        <div class="grid grid-cols-4">
            @php
                $navItems = [
                    ['route' => 'dashboard', 'icon' => 'home', 'label' => 'General'],
                    ['route' => 'paper-trading.index', 'icon' => 'chart', 'label' => 'Paper'],
                    ['route' => 'backtesting.index', 'icon' => 'flask', 'label' => 'Backtest'],
                    ['route' => 'data-collector.index', 'icon' => 'database', 'label' => 'Datos'],
                ];
            @endphp

            @foreach ($navItems as $item)
                @php
                    $active = request()->routeIs($item['route'] === 'dashboard' ? 'dashboard' : str_replace('.index', '.*', $item['route']));
                @endphp
                <a href="{{ route($item['route']) }}"
                   class="flex flex-col items-center justify-center py-2.5 gap-1 text-[11px]"
                   style="color: {{ $active ? 'var(--color-info)' : 'var(--color-text-muted)' }};">
                    @include('layouts.icon', ['name' => $item['icon']])
                    {{ $item['label'] }}
                </a>
            @endforeach
        </div>
    </nav>

    @stack('scripts')

    <script>
      if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
          navigator.serviceWorker.register('/sw.js');
        });
      }
    </script>

    @vite('resources/js/app.js')
</body>
</html>

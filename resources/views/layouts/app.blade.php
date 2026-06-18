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

            <div class="p-3 border-t" style="border-color:var(--color-border-soft);">
                <div class="flex items-center gap-2 px-3 py-2 rounded-md" style="background:var(--color-surface-raised);">
                    <span class="relative flex h-2 w-2">
                        <span class="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping" style="background:var(--color-profit);"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2" style="background:var(--color-profit);"></span>
                    </span>
                    <span class="text-xs" style="color:var(--color-text-secondary);">Sistema activo</span>
                </div>
            </div>
        </aside>

        {{-- Main content --}}
        <div class="flex-1 flex flex-col overflow-hidden">

            @php
                $roleLabels = [
                    'admin' => 'Administrador',
                    'consultor' => 'Consultor',
                    'inversionista' => 'Inversionista',
                ];
            @endphp

            {{-- Top bar — mobile/tablet only --}}
            <header class="lg:hidden flex items-center justify-between px-4 py-3 border-b gap-3"
                    style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <div class="min-w-0">
                    <p class="text-[10px] uppercase tracking-wider" style="color:var(--color-text-muted);">tr-bot</p>
                    <p class="text-sm font-medium mt-0.5 truncate">@yield('header', 'Dashboard')</p>
                </div>

                @auth
                    <div class="flex items-center gap-2 shrink-0">
                        <div class="text-right min-w-0">
                            <p class="text-[11px] font-medium truncate max-w-[110px]" style="color:var(--color-text-primary);">{{ auth()->user()->name }}</p>
                            <p class="text-[10px]" style="color:var(--color-text-muted);">{{ $roleLabels[auth()->user()->role] ?? auth()->user()->role }}</p>
                        </div>
                        <button type="button" onclick="confirmLogout()" class="text-[11px] px-2 py-1 rounded shrink-0" style="color:var(--color-loss); border:1px solid var(--color-border-soft);">
                            Salir
                        </button>
                    </div>
                @endauth
            </header>

            {{-- Desktop header --}}
            <header class="hidden lg:flex items-center justify-between px-6 py-4 border-b" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                <h2 class="text-lg font-medium">@yield('header', 'Dashboard')</h2>

                @auth
                    <div class="flex items-center gap-3">
                        <div class="text-right">
                            <p class="text-sm font-medium" style="color:var(--color-text-primary);">{{ auth()->user()->name }}</p>
                            <p class="text-[11px]" style="color:var(--color-text-muted);">{{ $roleLabels[auth()->user()->role] ?? auth()->user()->role }}</p>
                        </div>
                        <button type="button" onclick="confirmLogout()" class="text-xs font-medium px-3 py-1.5 rounded-md transition-colors" style="color:var(--color-loss); border:1px solid var(--color-border-soft);"
                                onmouseover="this.style.background='#3A1A1C'" onmouseout="this.style.background='transparent'">
                            Salir
                        </button>
                    </div>
                @endauth
            </header>

            <main class="flex-1 overflow-y-auto p-4 lg:p-6 pb-20 lg:pb-6">
                @yield('content')
            </main>
        </div>
    </div>

    {{-- Bottom nav — mobile/tablet only --}}
    <nav class="lg:hidden fixed bottom-0 left-0 right-0 border-t z-50"
         style="background:var(--color-surface); border-color:var(--color-border-soft); padding-bottom: env(safe-area-inset-bottom);">
        @php
            $user = auth()->user();
            $navItems = collect([
                ['route' => 'dashboard', 'icon' => 'home', 'label' => 'General', 'visible' => true],
                ['route' => 'paper-trading.index', 'icon' => 'chart', 'label' => 'Paper', 'visible' => $user?->canViewPaperTrading() ?? false],
                ['route' => 'real-trading.accounts.index', 'icon' => 'wallet', 'label' => 'Real', 'visible' => $user?->canViewRealTrading() ?? false],
                ['route' => 'backtesting.index', 'icon' => 'flask', 'label' => 'Backtest', 'visible' => $user?->canViewAnalysisTools() ?? false],
                ['route' => 'users.index', 'icon' => 'users', 'label' => 'Usuarios', 'visible' => $user?->canManageUsers() ?? false],
            ])->filter(fn ($item) => $item['visible'])->values();
        @endphp
        <div class="grid" style="grid-template-columns: repeat({{ $navItems->count() }}, 1fr);">
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

    {{-- Formulario de logout, oculto, enviado tras confirmacion --}}
    @auth
        <form id="logout-form" method="POST" action="{{ route('logout') }}" class="hidden">
            @csrf
        </form>
    @endauth

    @stack('scripts')

    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
        function confirmLogout() {
            Swal.fire({
                title: 'Cerrar sesión',
                text: '¿Seguro que quieres salir de tr-bot?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Salir',
                cancelButtonText: 'Cancelar',
                background: '#11161F',
                color: '#E5E9F0',
                confirmButtonColor: '#F2545B',
                cancelButtonColor: '#232B38',
                customClass: {
                    popup: 'rounded-xl border',
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    document.getElementById('logout-form').submit();
                }
            });
        }
    </script>

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
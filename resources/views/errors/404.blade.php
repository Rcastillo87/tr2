<!DOCTYPE html>
<html lang="es" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#0A0E14">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <title>Página no encontrada — tr-bot</title>
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body class="font-sans antialiased" style="background:var(--color-base); color:var(--color-text-primary);">
    <div class="min-h-screen flex flex-col items-center justify-center px-4 py-10 relative overflow-hidden">

        {{-- Patron de fondo: grid sutil + glow --}}
        <div class="absolute inset-0 pointer-events-none" style="
            background-image:
                linear-gradient(var(--color-border-soft) 1px, transparent 1px),
                linear-gradient(90deg, var(--color-border-soft) 1px, transparent 1px);
            background-size: 48px 48px;
            opacity: 0.35;
            mask-image: radial-gradient(ellipse 60% 50% at 50% 35%, black 0%, transparent 70%);
        "></div>

        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[480px] h-[480px] rounded-full pointer-events-none"
             style="background: radial-gradient(circle, var(--color-info) 0%, transparent 70%); opacity: 0.10; filter: blur(40px);"></div>

        <div class="relative z-10 flex flex-col items-center w-full max-w-sm text-center">

            <div class="mb-6 w-16 h-16 rounded-2xl overflow-hidden shadow-lg" style="border:1px solid var(--color-border-soft); box-shadow: 0 8px 30px rgba(77,143,232,0.15);">
                <img src="/icons/icon-192x192.png" alt="tr-bot" class="w-full h-full object-cover">
            </div>

            <p class="font-mono text-5xl font-medium mb-2" style="color:var(--color-info);">404</p>
            <h1 class="text-lg font-semibold mb-2" style="color:var(--color-text-primary);">Página no encontrada</h1>
            <p class="text-sm mb-6" style="color:var(--color-text-muted);">
                La página que buscas no existe o fue movida.
            </p>

            <a href="{{ route('dashboard') }}"
               class="inline-flex items-center px-4 py-2 rounded-lg font-medium text-sm transition-colors"
               style="background:var(--color-info); color:#fff;">
                Volver a vista general
            </a>

            <div class="mt-6 flex items-center gap-2 px-3 py-1.5 rounded-full" style="background:var(--color-surface-raised); border:1px solid var(--color-border-soft);">
                <span class="relative flex h-2 w-2">
                    <span class="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping" style="background:var(--color-profit);"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2" style="background:var(--color-profit);"></span>
                </span>
                <span class="text-[11px]" style="color:var(--color-text-secondary);">Sistema activo</span>
            </div>
        </div>
    </div>
</body>
</html>

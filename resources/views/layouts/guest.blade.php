<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}" class="dark">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
        <meta name="theme-color" content="#0A0E14">
        <meta name="csrf-token" content="{{ csrf_token() }}">
        <link rel="manifest" href="/manifest.json">
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
        <link rel="apple-touch-icon" href="/apple-touch-icon.png">
        <title>{{ config('app.name', 'tr-bot') }}</title>
        @vite(['resources/css/app.css', 'resources/js/app.js'])
    </head>
    <body class="font-sans antialiased" style="background:var(--color-base); color:var(--color-text-primary);">
        <div class="min-h-screen flex flex-col items-center justify-center px-4 py-10">

            <div class="mb-6 flex flex-col items-center">
                <div class="w-14 h-14 rounded-xl flex items-center justify-center" style="background:var(--color-surface); border:1px solid var(--color-border-soft);">
                    <span class="font-mono text-lg font-medium" style="color:var(--color-info);">tr</span>
                </div>
                <p class="mt-3 text-sm font-medium" style="color:var(--color-text-secondary);">tr-bot</p>
            </div>

            <div class="w-full max-w-sm rounded-lg border p-6" style="background:var(--color-surface); border-color:var(--color-border-soft);">
                {{ $slot }}
            </div>

        </div>
    </body>
</html>

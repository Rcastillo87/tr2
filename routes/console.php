<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use App\Jobs\CollectOhlcvDataJob;
use Illuminate\Support\Facades\Schedule;
use App\Jobs\DetectMarketRegimeJob;
use App\Jobs\PaperTradingTickJob;
use App\Jobs\RealTradingTickJob;
use App\Jobs\RealTradingReconcileJob;
use App\Jobs\CircuitBreakerMaxLossJob;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Schedule::job(new CollectOhlcvDataJob)->everyMinute();
Schedule::job(new DetectMarketRegimeJob)->everyFifteenMinutes();
// Cada minuto: entrada y gestión a ≤ ~1 min del cierre de vela (como el backtest). Los jobs son únicos (sin solapes).
Schedule::job(new PaperTradingTickJob)->everyMinute();
Schedule::job(new RealTradingTickJob)->everyMinute();
Schedule::job(new RealTradingReconcileJob)->everyFiveMinutes();
Schedule::job(new CircuitBreakerMaxLossJob)->everyMinute();
// Usuarios inactivos: elimina sus suscripciones Real cuando sus operaciones vivas terminaron (UserDeactivation)
Schedule::call(fn () => app(\App\Services\UserDeactivation::class)->purgeFinished())
    ->everyFiveMinutes()->name('inactive-users-purge')->withoutOverlapping(10);

// Collector: vigilante por cron (no depende de Horizon), validación diaria contra Bybit y limpieza de avisos (30 días)
Schedule::command('collector:watchdog')->everyFiveMinutes()->withoutOverlapping(15)->runInBackground();
Schedule::job(new \App\Jobs\ValidateCollectorDataJob(repair: true), \App\Services\ParamSearchService::QUEUE,
    \App\Services\ParamSearchService::QUEUE_CONNECTION)
    ->dailyAt('04:00')->timezone('America/Bogota')->name('collector-validate-daily');
// p84 (R-21): ¿alguna estrategia o config activa mira el futuro? Aviso al admin (Validación) si aparece una
Schedule::command('strategies:lookahead-audit')->dailyAt('04:15')->timezone('America/Bogota')
    ->name('strategies-lookahead-audit')->withoutOverlapping(60)->runInBackground();
// C6-05: lotes comprimidos solapados en ohlcv_data (solo lectura, ~0,5 s); a los :10 cada 3 h UTC, así cae justo después
// de la compresión (policy_compression cada 12 h, hoy 05:38 y 17:38 UTC). Solo avisa; nunca repara.
Schedule::command('ohlcv:overlap-check')->cron('10 */3 * * *')->name('ohlcv-overlap-check')->withoutOverlapping(30)->runInBackground();
Schedule::call(fn () => app(\App\Services\SystemAlerts::class)->prune())
    ->dailyAt('04:30')->timezone('America/Bogota')->name('alerts-prune');

// Avisos de broker: el motor registra eventos (broker_events) y aquí se convierten en avisos al dueño de la cuenta.
// Por cron (no depende de Horizon). Retención de eventos: 90 días.
Schedule::command('broker:events')->everyMinute()->withoutOverlapping(5)->runInBackground();
Schedule::command('broker:events --prune')->dailyAt('04:35')->timezone('America/Bogota')->name('broker-events-prune');


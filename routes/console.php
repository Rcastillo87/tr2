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

// Collector: vigilante por cron (no depende de Horizon), validación diaria contra Bybit y limpieza de avisos (30 días)
Schedule::command('collector:watchdog')->everyFiveMinutes()->withoutOverlapping(15)->runInBackground();
Schedule::job(new \App\Jobs\ValidateCollectorDataJob, \App\Services\ParamSearchService::QUEUE,
    \App\Services\ParamSearchService::QUEUE_CONNECTION)
    ->dailyAt('04:00')->timezone('America/Bogota')->name('collector-validate-daily');
Schedule::call(fn () => app(\App\Services\SystemAlerts::class)->prune())
    ->dailyAt('04:30')->timezone('America/Bogota')->name('alerts-prune');


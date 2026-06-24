<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use App\Jobs\CollectOhlcvDataJob;
use Illuminate\Support\Facades\Schedule;
use App\Jobs\DetectMarketRegimeJob;
use App\Jobs\PaperTradingTickJob;
use App\Jobs\RealTradingTickJob;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Schedule::job(new CollectOhlcvDataJob)->everyMinute();
Schedule::job(new DetectMarketRegimeJob)->everyFifteenMinutes();
Schedule::job(new PaperTradingTickJob)->everyFiveMinutes();
Schedule::job(new RealTradingTickJob)->everyFiveMinutes();

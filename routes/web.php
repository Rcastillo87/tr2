<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PaperTradingController;
use App\Http\Controllers\BacktestingController;
use App\Http\Controllers\DataCollectorController;

Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

Route::prefix('paper-trading')->name('paper-trading.')->group(function () {
    Route::get('/', [PaperTradingController::class, 'index'])->name('index');
    Route::get('/{strategy}', [PaperTradingController::class, 'show'])->name('show');
});

Route::prefix('backtesting')->name('backtesting.')->group(function () {
    Route::get('/', [BacktestingController::class, 'index'])->name('index');
    Route::post('/', [BacktestingController::class, 'index'])->name('run');
});

Route::prefix('data-collector')->name('data-collector.')->group(function () {
    Route::get('/', [DataCollectorController::class, 'index'])->name('index');
});


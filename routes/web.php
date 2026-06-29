<?php

use App\Http\Controllers\BacktestingController;
use App\Http\Controllers\BrokerAccountController;
use App\Http\Controllers\CollectorConfigController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PaperTradingController;
use App\Http\Controllers\PaperStrategyConfigController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\RealStrategySubscriptionController;
use App\Http\Controllers\TradingController;
use App\Http\Controllers\UserManagementController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return redirect()->route('dashboard');
});

Route::middleware(['auth', 'verified'])->group(function () {

    Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

    // Paper trading
    Route::middleware('can:viewPaperTrading')->prefix('paper-trading')->name('paper-trading.')->group(function () {
        Route::get('/',     [PaperTradingController::class, 'index'])->name('index');
        Route::get('/live', [PaperTradingController::class, 'live'])->name('live');
    });

    // Configs de paper trading — usado desde backtesting
    Route::middleware('can:manageUsers')->prefix('paper-trading/configs')->name('paper-trading.configs.')->group(function () {
        Route::patch('/{config}/toggle', [PaperStrategyConfigController::class, 'toggleActive'])->name('toggle');
        Route::post('/implement',        [PaperStrategyConfigController::class, 'implement'])->name('implement');
        Route::post('/',                 [PaperStrategyConfigController::class, 'store'])->name('store');
        Route::delete('/{config}',       [PaperStrategyConfigController::class, 'destroy'])->name('destroy');
    });

    // Data Collector
    Route::middleware('can:manageUsers')->prefix('collector/configs')->name('collector.configs.')->group(function () {
        Route::get('/', [CollectorConfigController::class, 'index'])->name('index');
        Route::patch('/{config}/toggle', [CollectorConfigController::class, 'toggleActive'])->name('toggle');
    });

    // Backtesting
    Route::middleware('can:viewAnalysisTools')->prefix('backtesting')->name('backtesting.')->group(function () {
        Route::get('/',                               [BacktestingController::class, 'index'])->name('index');
        Route::get('/run',                            [BacktestingController::class, 'run'])->name('run');
        Route::post('/run',                           [BacktestingController::class, 'run'])->name('execute');
        Route::post('/run-ajax',                      [BacktestingController::class, 'runAjax'])->name('run-ajax');
        Route::get('/data-range/{symbol}/{interval}', [BacktestingController::class, 'dataRange'])->name('data-range');
        Route::post('/export-excel',                  [BacktestingController::class, 'exportExcel'])->name('export-excel');
        Route::get('/retest/{config}',                [BacktestingController::class, 'retest'])->name('retest');
    });

    // Usuarios
    Route::middleware('can:manageUsers')->prefix('users')->name('users.')->group(function () {
        Route::get('/', [UserManagementController::class, 'index'])->name('index');
        Route::patch('/{user}/toggle-active', [UserManagementController::class, 'toggleActive'])->name('toggle-active');
    });

    // Trading real
    Route::middleware('can:viewRealTrading')->prefix('trading')->name('trading.')->group(function () {
        Route::get('/',            [TradingController::class, 'index'])->name('index');
        Route::get('/live-prices', [TradingController::class, 'livePrices'])->name('live-prices');

        Route::get('/accounts',                                                 [TradingController::class, 'accounts'])->name('accounts');
        Route::post('/accounts',                                                [BrokerAccountController::class, 'store'])->name('accounts.store');
        Route::patch('/accounts/{account}/toggle-status',                       [BrokerAccountController::class, 'toggleStatus'])->name('accounts.toggle-status');
        Route::delete('/accounts/{account}',                                    [BrokerAccountController::class, 'destroy'])->name('accounts.destroy');

        Route::post('/accounts/{account}/subscriptions',                        [RealStrategySubscriptionController::class, 'store'])->name('subscriptions.store');
        Route::post('/accounts/{account}/subscriptions/all',                    [RealStrategySubscriptionController::class, 'storeAll'])->name('subscriptions.store-all');
        Route::patch('/accounts/{account}/subscriptions/{subscription}/toggle', [RealStrategySubscriptionController::class, 'toggle'])->name('subscriptions.toggle');
        Route::delete('/accounts/{account}/subscriptions/{subscription}',       [RealStrategySubscriptionController::class, 'destroy'])->name('subscriptions.destroy');
    });

    // Perfil
    Route::get('/profile',    [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile',  [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');
});

require __DIR__.'/auth.php';

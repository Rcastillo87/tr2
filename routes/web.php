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
    Route::get('/dashboard/live-prices', [DashboardController::class, 'livePrices'])->name('dashboard.live-prices');

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

    // Backtesting
    Route::middleware('can:viewAnalysisTools')->prefix('backtesting')->name('backtesting.')->group(function () {
        Route::get('/',                               [BacktestingController::class, 'index'])->name('index');
        Route::get('/run',                            [BacktestingController::class, 'run'])->name('run');
        Route::post('/run',                           [BacktestingController::class, 'run'])->name('execute');
        Route::post('/execute-ajax',                   [\App\Http\Controllers\BacktestingController::class, 'executeAjax'])->name('execute-ajax');
        Route::post('/save',                          [\App\Http\Controllers\BacktestingController::class, 'saveBacktest'])->name('save');
        Route::post('/run-ajax',                      [BacktestingController::class, 'runAjax'])->name('run-ajax');
        Route::get('/data-range/{symbol}/{interval}', [BacktestingController::class, 'dataRange'])->name('data-range');
        Route::post('/export-excel',                  [BacktestingController::class, 'exportExcel'])->name('export-excel');
                Route::get('/history/{strategy}',             [BacktestingController::class, 'history'])->name('history');
Route::get('/retest/{config}',                [BacktestingController::class, 'retest'])->name('retest');
        Route::patch('/backtest/{backtest}/approve', [\App\Http\Controllers\BacktestingController::class, 'approve'])->name('approve');
        Route::post('/backtest/{backtest}/implement-paper', [\App\Http\Controllers\BacktestingController::class, 'implementPaper'])->name('implement-paper');
        Route::post('/backtest/{backtest}/stop-paper', [\App\Http\Controllers\BacktestingController::class, 'stopPaper'])->name('stop-paper');
        Route::delete('/backtest/{backtest}', [\App\Http\Controllers\BacktestingController::class, 'destroyBacktest'])->name('destroy-backtest');
        Route::post('/backtest/{backtest}/stop-paper', [\App\Http\Controllers\BacktestingController::class, 'stopPaper'])->name('stop-paper');
        Route::post('/backtest/{backtest}/stop-paper', [\App\Http\Controllers\BacktestingController::class, 'stopPaper'])->name('stop-paper');
        Route::delete('/backtest/{backtest}', [\App\Http\Controllers\BacktestingController::class, 'destroyBacktest'])->name('destroy-backtest');
    });

    // Módulo de Estrategias
    Route::middleware('can:manageUsers')->prefix('strategies')->name('strategies.')->group(function () {
        Route::get('/', [\App\Http\Controllers\StrategyController::class, 'index'])->name('index');
        Route::get('/create', [\App\Http\Controllers\StrategyController::class, 'create'])->name('create');
        Route::post('/', [\App\Http\Controllers\StrategyController::class, 'store'])->name('store');
        Route::get('/{strategy}/edit', [\App\Http\Controllers\StrategyController::class, 'edit'])->name('edit');
        Route::put('/{strategy}', [\App\Http\Controllers\StrategyController::class, 'update'])->name('update');
        Route::patch('/{strategy}/toggle', [\App\Http\Controllers\StrategyController::class, 'toggle'])->name('toggle');
        Route::delete('/{strategy}', [\App\Http\Controllers\StrategyController::class, 'destroy'])->name('destroy');
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



// Módulo unificado /collector (2026-10-21)
Route::middleware('can:manageUsers')->prefix('collector')->name('collector.')->group(function () {
    Route::get('/', [CollectorConfigController::class, 'unified'])->name('unified');
    Route::post('/toggle-all/{broker}/{symbol}', [CollectorConfigController::class, 'toggleAll'])->name('toggle-all');
    Route::post('/toggle-one', [CollectorConfigController::class, 'toggleOne'])->name('toggle-one');
    Route::post('/backfill', [CollectorConfigController::class, 'backfill'])->name('backfill');
    Route::post('/invalidate', [CollectorConfigController::class, 'invalidate'])->name('invalidate');
    Route::post('/reload', [CollectorConfigController::class, 'reload'])->name('reload');
    Route::post('/add-symbol', [CollectorConfigController::class, 'addSymbol'])->name('add-symbol');
});

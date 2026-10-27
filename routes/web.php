<?php

use App\Http\Controllers\BacktestingController;
use App\Http\Controllers\BrokerAccountController;
use App\Http\Controllers\CollectorConfigController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PaperTradingController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\RealStrategySubscriptionController;
use App\Http\Controllers\TradingController;
use App\Http\Controllers\UserManagementController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return redirect()->route('dashboard');
});

Route::middleware(['auth', 'verified'])->group(function () {
    // Avisos en la plataforma (campana): cada usuario ve solo los suyos
    Route::get('/avisos', [\App\Http\Controllers\NotificationController::class, 'index'])->name('notifications.index');
    Route::get('/avisos/recientes', [\App\Http\Controllers\NotificationController::class, 'recent'])->name('notifications.recent');
    Route::post('/avisos/leidos', [\App\Http\Controllers\NotificationController::class, 'markRead'])->name('notifications.read');

    Route::get('/', [DashboardController::class, 'index'])->name('dashboard');
    Route::get('/dashboard/live-prices', [DashboardController::class, 'livePrices'])->name('dashboard.live-prices');

    // Paper trading
    Route::middleware('can:viewPaperTrading')->prefix('paper-trading')->name('paper-trading.')->group(function () {
        Route::get('/',     [PaperTradingController::class, 'index'])->name('index');
        Route::get('/live', [PaperTradingController::class, 'live'])->name('live');
    });

    // Backtesting
    Route::middleware('can:viewAnalysisTools')->prefix('backtesting')->name('backtesting.')->group(function () {
        Route::get('/',                               [BacktestingController::class, 'index'])->name('index');
        Route::get('/run',                            [BacktestingController::class, 'run'])->name('run');
        Route::post('/run',                           [BacktestingController::class, 'run'])->name('execute');
        Route::post('/execute-ajax',                   [\App\Http\Controllers\BacktestingController::class, 'executeAjax'])->name('execute-ajax');
        Route::post('/save',                          [\App\Http\Controllers\BacktestingController::class, 'saveBacktest'])->name('save');
        Route::get('/data-range/{symbol}/{interval}', [BacktestingController::class, 'dataRange'])->name('data-range');
        Route::post('/export-excel',                  [BacktestingController::class, 'exportExcel'])->name('export-excel');
                Route::get('/history/{strategy}',             [BacktestingController::class, 'history'])->name('history');
        Route::post('/backtest/{backtest}/implement-paper', [\App\Http\Controllers\BacktestingController::class, 'implementPaper'])->name('implement-paper');
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
        // Buscar configuración (búsqueda en segundo plano + crear en historial)
        Route::get('/{strategy}/buscar', [\App\Http\Controllers\ParamSearchController::class, 'options'])->name('search.options');
        Route::post('/{strategy}/buscar', [\App\Http\Controllers\ParamSearchController::class, 'start'])->name('search.start');
        Route::get('/busquedas/{run}/estado', [\App\Http\Controllers\ParamSearchController::class, 'status'])->name('search.status');
        Route::post('/busquedas/{run}/cancelar', [\App\Http\Controllers\ParamSearchController::class, 'cancel'])->name('search.cancel');
        Route::get('/busquedas/{run}/resultados', [\App\Http\Controllers\ParamSearchController::class, 'results'])->name('search.results');
        Route::post('/busquedas/{run}/crear', [\App\Http\Controllers\ParamSearchController::class, 'create'])->name('search.create');
        Route::get('/busquedas/{run}', [\App\Http\Controllers\ParamSearchController::class, 'show'])->name('search.show');
        Route::post('/buscar-todas', [\App\Http\Controllers\ParamSearchController::class, 'startAll'])->name('search.start-all');
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
    Route::post('/validar', [CollectorConfigController::class, 'validateData'])->name('validate');
    Route::get('/validacion', [CollectorConfigController::class, 'validationStatus'])->name('validation-status');
});

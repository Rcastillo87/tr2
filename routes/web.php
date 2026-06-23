<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PaperTradingController;
use App\Http\Controllers\BacktestingController;
use App\Http\Controllers\UserManagementController;
use App\Http\Controllers\BrokerAccountController;
use App\Http\Controllers\PaperStrategyConfigController;
use App\Http\Controllers\CollectorConfigController;
use App\Http\Controllers\ProfileController;

/*
|--------------------------------------------------------------------------
| Rutas publicas
|--------------------------------------------------------------------------
*/

Route::get('/', function () {
    return redirect()->route('dashboard');
});

/*
|--------------------------------------------------------------------------
| Rutas protegidas (requieren login)
|--------------------------------------------------------------------------
*/

Route::middleware(['auth', 'verified'])->group(function () {

    // Vista general: visible para todos los roles (cada uno ve un subconjunto
    // distinto de KPIs, esto se maneja dentro del controller/vista)
    Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

    // Paper trading: admin e inversionista
    Route::middleware('can:viewPaperTrading')->prefix('paper-trading')->name('paper-trading.')->group(function () {
        Route::get('/', [PaperTradingController::class, 'index'])->name('index');
        Route::get('/{strategy}/live', [PaperTradingController::class, 'live'])->name('live');
        Route::get('/{strategy}', [PaperTradingController::class, 'show'])->name('show');
    });

    // Configuracion del Data Collector: solo admin
    Route::middleware('can:manageUsers')->prefix('collector/configs')->name('collector.configs.')->group(function () {
        Route::get('/', [CollectorConfigController::class, 'index'])->name('index');
        Route::patch('/{config}/toggle', [CollectorConfigController::class, 'toggleActive'])->name('toggle');
    });
    // Backtesting: admin y consultor
    Route::middleware('can:viewAnalysisTools')->prefix('backtesting')->name('backtesting.')->group(function () {
        Route::get('/', [BacktestingController::class, 'index'])->name('index');
        Route::get('/run', [BacktestingController::class, 'run'])->name('run');
        Route::post('/run', [BacktestingController::class, 'run'])->name('execute');
        Route::get('/data-range/{symbol}/{interval}', [BacktestingController::class, 'dataRange'])->name('data-range');
        Route::post('/export-excel', [BacktestingController::class, 'exportExcel'])->name('export-excel');
        Route::get('/retest/{config}', [BacktestingController::class, 'retest'])->name('retest');
    });

    // Gestion de configs de paper trading: solo admin, solo acciones (sin vista propia, viven en /backtesting)
    Route::middleware('can:manageUsers')->prefix('paper-trading/configs')->name('paper-trading.configs.')->group(function () {
        Route::post('/implement', [PaperStrategyConfigController::class, 'implement'])->name('implement');
        Route::patch('/{config}/toggle', [PaperStrategyConfigController::class, 'toggleActive'])->name('toggle');
        Route::delete('/{config}', [PaperStrategyConfigController::class, 'destroy'])->name('destroy');
    });

    // Gestion de usuarios: solo admin
    Route::middleware('can:manageUsers')->prefix('users')->name('users.')->group(function () {
        Route::get('/', [UserManagementController::class, 'index'])->name('index');
        Route::patch('/{user}/toggle-active', [UserManagementController::class, 'toggleActive'])->name('toggle-active');
    });

    // Trading real: admin e inversionista, cada uno gestiona sus propias cuentas
    Route::middleware('can:viewRealTrading')->prefix('real-trading')->name('real-trading.')->group(function () {
        Route::prefix('accounts')->name('accounts.')->group(function () {
            Route::get('/', [BrokerAccountController::class, 'index'])->name('index');
            Route::get('/create', [BrokerAccountController::class, 'create'])->name('create');
            Route::post('/', [BrokerAccountController::class, 'store'])->name('store');
            Route::patch('/{account}/toggle-status', [BrokerAccountController::class, 'toggleStatus'])->name('toggle-status');
            Route::delete('/{account}', [BrokerAccountController::class, 'destroy'])->name('destroy');
        });
    });

    // Perfil de usuario (Breeze)
    Route::get('/profile', [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile', [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');
});

require __DIR__.'/auth.php';

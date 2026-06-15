<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\PaperTradingController;
use App\Http\Controllers\BacktestingController;
use App\Http\Controllers\DataCollectorController;
use App\Http\Controllers\UserManagementController;
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
        Route::get('/{strategy}', [PaperTradingController::class, 'show'])->name('show');
    });

    // Backtesting: admin y consultor
    Route::middleware('can:viewAnalysisTools')->prefix('backtesting')->name('backtesting.')->group(function () {
        Route::get('/', [BacktestingController::class, 'index'])->name('index');
        Route::post('/', [BacktestingController::class, 'index'])->name('run');
    });

    // Data collector: admin y consultor
    Route::middleware('can:viewAnalysisTools')->prefix('data-collector')->name('data-collector.')->group(function () {
        Route::get('/', [DataCollectorController::class, 'index'])->name('index');
    });

    // Gestion de usuarios: solo admin
    Route::middleware('can:manageUsers')->prefix('users')->name('users.')->group(function () {
        Route::get('/', [UserManagementController::class, 'index'])->name('index');
        Route::patch('/{user}/toggle-active', [UserManagementController::class, 'toggleActive'])->name('toggle-active');
    });

    // Perfil de usuario (Breeze)
    Route::get('/profile', [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile', [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');
});

require __DIR__.'/auth.php';

<?php

namespace App\Providers;

use App\Models\User;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        Gate::define('viewPaperTrading', function (User $user) {
            return $user->canViewPaperTrading();
        });

        Gate::define('viewAnalysisTools', function (User $user) {
            return $user->canViewAnalysisTools();
        });

        Gate::define('viewRealTrading', function (User $user) {
            return $user->canViewRealTrading();
        });

        Gate::define('manageUsers', function (User $user) {
            return $user->canManageUsers();
        });

        Gate::define('createDemoAccounts', function (User $user) {
            return $user->canCreateDemoAccounts();
        });
    }
}

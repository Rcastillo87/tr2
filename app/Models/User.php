<?php

namespace App\Models;

// use Illuminate\Contracts\Auth\MustVerifyEmail;
use Database\Factories\UserFactory;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Attributes\Hidden;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;

#[Fillable(['name', 'email', 'password', 'role', 'is_active'])]
#[Hidden(['password', 'remember_token'])]
class User extends Authenticatable
{
    /** @use HasFactory<UserFactory> */
    use HasFactory, Notifiable;

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
            'is_active' => 'boolean',
        ];
    }

    public function realStrategySubscriptions(): HasMany
    {
        return $this->hasMany(RealStrategySubscription::class);
    }

    public function realTrades(): HasMany
    {
        return $this->hasMany(RealTrade::class);
    }

    public function brokerAccounts(): HasMany
    {
        return $this->hasMany(BrokerAccount::class);
    }

    public function isAdmin(): bool
    {
        return $this->role === 'admin';
    }

    public function isConsultor(): bool
    {
        return $this->role === 'consultor';
    }

    public function isInversionista(): bool
    {
        return $this->role === 'inversionista';
    }

    /**
     * Modulos del paper trading / herramientas de analisis (backtesting, data collector).
     */
    public function canViewPaperTrading(): bool
    {
        return in_array($this->role, ['admin', 'inversionista'], true);
    }

    public function canViewAnalysisTools(): bool
    {
        return in_array($this->role, ['admin', 'consultor'], true);
    }

    /**
     * Trading real: admin opera su propia cuenta + administra usuarios,
     * inversionista opera solo la suya, consultor no tiene acceso.
     */
    public function canViewRealTrading(): bool
    {
        return in_array($this->role, ['admin', 'inversionista'], true);
    }

    public function canManageUsers(): bool
    {
        return $this->isAdmin();
    }

    /**
     * Solo el admin puede crear cuentas de broker tipo 'demo' (para si mismo).
     * Los inversionistas solo pueden crear cuentas 'real'.
     */
    public function canCreateDemoAccounts(): bool
    {
        return $this->isAdmin() || config('trading.allow_investor_demo_accounts', false);
    }
}

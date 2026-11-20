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
     * Permisos por rol (D-46, decisión del dueño 20-nov; R-02):
     *   Dashboard: todos (bloque de Real solo admin e inversionista; bloque de administración solo admin).
     *   Paper: admin y consultor (solo mirar). Real: admin e inversionista. Backtesting, búsquedas, estrategias,
     *   collector y usuarios: solo admin. Antes el consultor podía implementar, detener, borrar y editar backtests
     *   (y su guardado sincronizaba Paper → Real), y el inversionista veía Paper.
     */
    public function canViewPaperTrading(): bool
    {
        return in_array($this->role, ['admin', 'consultor'], true);
    }

    public function canViewAnalysisTools(): bool
    {
        return $this->isAdmin();
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

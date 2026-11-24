<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class BrokerAccount extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id',
        'broker',
        'account_type',
        'label',
        'api_key',
        'api_secret',
        'status',
        'single_position_per_symbol',
        'max_monthly_loss_pct',
        'max_open_trades',
        'monthly_loss_enabled',       // D-66: false = «sin límite»
        'open_trades_limit_enabled',  // D-66: false = «sin límite»
        'loss_pause_days',            // D-66: 1–30; null = hasta fin de mes
    ];

    protected $casts = [
        'api_key' => 'encrypted',
        'api_secret' => 'encrypted',
        'single_position_per_symbol' => 'boolean',
        'max_monthly_loss_pct' => 'float',
        'max_open_trades' => 'integer',
        'month_start_balance' => 'float',
        'month_start_at' => 'date',
        'monthly_loss_enabled' => 'boolean',
        'open_trades_limit_enabled' => 'boolean',
        'loss_pause_days' => 'integer',
        // loss_paused_until / loss_period_start: UTC sin zona (como exit_time); sin cast, se leen con Carbon::parse(…, 'UTC')
    ];

    /**
     * Ocultar credenciales por defecto al serializar (ej. en respuestas JSON).
     */
    protected $hidden = [
        'api_key',
        'api_secret',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function subscriptions(): HasMany
    {
        return $this->hasMany(RealStrategySubscription::class);
    }

    /**
     * ¿La cuenta tiene operaciones vivas o sin confirmar (RealTrade::RECONCILE_STATUSES)? La conciliación las recupera
     * con las claves de ESTA cuenta: si se borra, quedan sin gestión para siempre (R-04).
     */
    public function hasLiveTrades(): bool
    {
        return RealTrade::where('broker_account_id', $this->id)
            ->whereIn('status', RealTrade::RECONCILE_STATUSES)
            ->exists();
    }

    public function isDemo(): bool
    {
        return $this->account_type === 'demo';
    }

    public function isReal(): bool
    {
        return $this->account_type === 'real';
    }

    public function isActive(): bool
    {
        return $this->status === 'active';
    }

    public function scopeForUser($query, int $userId)
    {
        return $query->where('user_id', $userId);
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }
}

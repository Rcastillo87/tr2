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
    ];

    protected $casts = [
        'api_key' => 'encrypted',
        'api_secret' => 'encrypted',
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

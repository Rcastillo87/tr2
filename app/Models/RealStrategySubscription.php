<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class RealStrategySubscription extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id',
        'broker_account_id',
        'paper_strategy_config_id',
        'strategy',
        'symbol',
        'interval',
        'status',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function brokerAccount(): BelongsTo
    {
        return $this->belongsTo(BrokerAccount::class);
    }

    public function paperStrategyConfig(): BelongsTo
    {
        return $this->belongsTo(PaperStrategyConfig::class);
    }

    public function trades(): HasMany
    {
        return $this->hasMany(RealTrade::class, 'subscription_id');
    }

    public function openTrades(): HasMany
    {
        return $this->hasMany(RealTrade::class, 'subscription_id')
            ->whereIn('status', ['open', 'pending_open', 'pending_close']);
    }

    public function isActive(): bool
    {
        return $this->status === 'active';
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    public function scopeForUser($query, int $userId)
    {
        return $query->where('user_id', $userId);
    }

    public function pauseIfConfigInactive(): void
    {
        if ($this->paperStrategyConfig && !$this->paperStrategyConfig->active) {
            $this->update(['status' => 'paused']);
        }
    }
}

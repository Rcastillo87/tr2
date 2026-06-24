<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class RealTrade extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id', 'subscription_id', 'broker_account_id', 'paper_strategy_config_id',
        'order_id', 'close_order_id',
        'strategy', 'symbol', 'broker', 'interval', 'side',
        'entry_price', 'entry_price_signal', 'exit_price',
        'sl', 'tp', 'tp2', 'tp3', 'tp4',
        'be_level', 'be_activated',
        'size', 'leverage',
        'pnl', 'pnl_pct', 'net_pnl', 'commission', 'slippage_pct',
        'balance_before', 'balance_after',
        'exit_reason', 'regime',
        'entry_time', 'exit_time',
        'status', 'error_message', 'audit_log',
    ];

    protected $casts = [
        'entry_price'        => 'decimal:8',
        'entry_price_signal' => 'decimal:8',
        'exit_price'         => 'decimal:8',
        'sl'                 => 'decimal:8',
        'tp'                 => 'decimal:8',
        'tp2'                => 'decimal:8',
        'tp3'                => 'decimal:8',
        'tp4'                => 'decimal:8',
        'be_level'           => 'decimal:8',
        'be_activated'       => 'boolean',
        'size'               => 'decimal:8',
        'leverage'           => 'decimal:2',
        'pnl'                => 'decimal:8',
        'pnl_pct'            => 'decimal:4',
        'net_pnl'            => 'decimal:8',
        'commission'         => 'decimal:8',
        'slippage_pct'       => 'decimal:6',
        'balance_before'     => 'decimal:8',
        'balance_after'      => 'decimal:8',
        'entry_time'         => 'datetime',
        'exit_time'          => 'datetime',
        'audit_log'          => 'array',
    ];

    // Estados posibles
    const STATUS_PENDING_OPEN  = 'pending_open';
    const STATUS_OPEN          = 'open';
    const STATUS_PENDING_CLOSE = 'pending_close';
    const STATUS_CLOSED        = 'closed';
    const STATUS_ERROR         = 'error';

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function subscription(): BelongsTo
    {
        return $this->belongsTo(RealStrategySubscription::class, 'subscription_id');
    }

    public function brokerAccount(): BelongsTo
    {
        return $this->belongsTo(BrokerAccount::class);
    }

    public function paperStrategyConfig(): BelongsTo
    {
        return $this->belongsTo(PaperStrategyConfig::class);
    }

    public function isOpen(): bool
    {
        return in_array($this->status, [self::STATUS_OPEN, self::STATUS_PENDING_CLOSE]);
    }

    public function isClosed(): bool
    {
        return $this->status === self::STATUS_CLOSED;
    }

    public function isWinner(): bool
    {
        return $this->net_pnl !== null
            ? (float) $this->net_pnl > 0
            : ($this->pnl !== null && (float) $this->pnl > 0);
    }

    public function scopeOpen($query)
    {
        return $query->whereIn('status', [
            self::STATUS_OPEN,
            self::STATUS_PENDING_OPEN,
            self::STATUS_PENDING_CLOSE,
        ]);
    }

    public function scopeClosed($query)
    {
        return $query->where('status', self::STATUS_CLOSED);
    }

    public function scopeForUser($query, int $userId)
    {
        return $query->where('user_id', $userId);
    }

    public function scopeForAccount($query, int $accountId)
    {
        return $query->where('broker_account_id', $accountId);
    }

    public function scopeForStrategy($query, string $strategy)
    {
        return $query->where('strategy', $strategy);
    }

    /**
     * Agrega una entrada al log de auditoría sin sobreescribir las anteriores.
     */
    public function appendAuditLog(string $action, array $data = []): void
    {
        $log = $this->audit_log ?? [];
        $log[] = [
            'action'    => $action,
            'timestamp' => now()->toIso8601String(),
            'data'      => $data,
        ];
        $this->update(['audit_log' => $log]);
    }
}

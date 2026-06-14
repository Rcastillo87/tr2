<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class RiskControl extends Model
{
    use HasFactory;

    protected $fillable = [
        'strategy',
        'symbol',
        'reason',
        'value',
        'threshold',
        'active',
        'paused_at',
        'auto_resume_at',
        'resumed_at',
    ];

    protected $casts = [
        'value'          => 'decimal:4',
        'threshold'      => 'decimal:4',
        'active'         => 'boolean',
        'paused_at'      => 'datetime',
        'auto_resume_at' => 'datetime',
        'resumed_at'     => 'datetime',
    ];

    public function scopeActive($query)
    {
        return $query->where('active', true);
    }

    public function scopeGlobal($query)
    {
        return $query->whereNull('strategy')->whereNull('symbol');
    }

    public function scopeForStrategy($query, string $strategy)
    {
        return $query->where('strategy', $strategy);
    }

    public function resume(): void
    {
        $this->update([
            'active'     => false,
            'resumed_at' => now(),
        ]);
    }

    public static function reasonLabel(string $reason): string
    {
        return match ($reason) {
            'daily_drawdown'     => 'Drawdown diario excedido',
            'total_drawdown'     => 'Drawdown total excedido',
            'volatility_extreme' => 'Volatilidad extrema',
            'kill_switch_manual' => 'Kill Switch manual',
            default              => $reason,
        };
    }
}


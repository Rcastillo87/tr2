<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class PaperTrade extends Model
{
    use HasFactory;

    protected $fillable = [
        'strategy',
        'symbol',
        'interval',
        'side',
        'entry_price',
        'exit_price',
        'sl',
        'tp',
        'be_level',
        'be_activated',
        'size',
        'pnl',
        'pnl_pct',
        'exit_reason',
        'regime',
        'entry_time',
        'exit_time',
        'status',
    ];

    protected $casts = [
        'entry_price'  => 'decimal:8',
        'exit_price'   => 'decimal:8',
        'sl'           => 'decimal:8',
        'tp'           => 'decimal:8',
        'be_level'     => 'decimal:8',
        'be_activated' => 'boolean',
        'size'         => 'decimal:8',
        'pnl'          => 'decimal:8',
        'pnl_pct'      => 'decimal:4',
        'entry_time'   => 'datetime',
        'exit_time'    => 'datetime',
    ];

    public function isOpen(): bool
    {
        return $this->status === 'open';
    }

    public function isWinner(): bool
    {
        return $this->pnl !== null && (float) $this->pnl > 0;
    }

    public function scopeOpen($query)
    {
        return $query->where('status', 'open');
    }

    public function scopeClosed($query)
    {
        return $query->where('status', 'closed');
    }

    public function scopeForStrategy($query, string $strategy)
    {
        return $query->where('strategy', $strategy);
    }
}

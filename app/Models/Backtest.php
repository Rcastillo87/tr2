<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Backtest extends Model {
    protected $fillable = [
        'hash', 'strategy_id', 'symbols', 'interval', 'months', 
        'config_params', 'strategy_snapshot', 'metrics', 'approved'
    ];
    protected $casts = [
        'symbols' => 'array',
        'config_params' => 'array',
        'strategy_snapshot' => 'array',
        'metrics' => 'array',
        'approved' => 'boolean',
    ];

    public function strategy(): BelongsTo {
        return $this->belongsTo(Strategy::class);
    }
}

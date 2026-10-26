<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PaperStrategyConfig extends Model
{
    protected $table = 'paper_strategy_configs';
    protected $fillable = ['display_name',
        'strategy_class',
        'symbol',
        'interval',
        'params',
        'active',
        'audited_months',
        'avg_win_rate',
        'avg_monthly_pnl',
        'avg_monthly_trades',
        'total_return_pct',
        'star_wr', 'star_sharpe', 'star_ret', 'star_consistency', 'star_pf', 'star_rating',
        'backtest_range_from', 'backtest_range_to',
        'sharpe_ratio', 'consistency_pct', 'profit_factor', 'backtest_id'];
    protected $casts = [
        'params' => 'array',
        'active' => 'boolean',
    ];

    public function scopeActive($query)
    {
        return $query->where('active', true);
    }

    /**
     * Relación con el backtest que originó esta configuración.
     */
    public function backtest(): BelongsTo
    {
        return $this->belongsTo(Backtest::class);
    }

}

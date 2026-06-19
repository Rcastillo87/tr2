<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class PaperStrategyConfig extends Model
{
    protected $table = 'paper_strategy_configs';

    protected $fillable = [
        'display_name',
        'strategy_class',
        'symbol',
        'interval',
        'params',
        'active',
    ];

    protected $casts = [
        'params' => 'array',
        'active' => 'boolean',
    ];

    public function scopeActive($query)
    {
        return $query->where('active', true);
    }

    /**
     * Nombre de la clase Python completo con namespace relativo
     * para que el motor Python pueda importarla dinamicamente.
     */
    public function pythonModulePath(): string
    {
        return match ($this->strategy_class) {
            'VwapStrategy'         => 'backtesting.strategies.vwap_strategy',
            'MeanReversionStrategy'=> 'backtesting.strategies.mean_reversion',
            'EmaDonchianStrategy'  => 'backtesting.strategies.ema_donchian',
            default                => throw new \InvalidArgumentException("Clase desconocida: {$this->strategy_class}"),
        };
    }
}

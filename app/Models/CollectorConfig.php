<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CollectorConfig extends Model
{
    protected $table = 'collector_configs';

    protected $fillable = ['symbol', 'interval', 'active', 'notes'];

    protected $casts = ['active' => 'boolean'];

    public function scopeActive($query)
    {
        return $query->where('active', true);
    }

    public function scopeForSymbol($query, string $symbol)
    {
        return $query->where('symbol', $symbol);
    }

    /**
     * Devuelve los simbolos unicos activos (para el motor Python y el backtesting).
     */
    public static function activeSymbols(): array
    {
        return static::active()
            ->distinct()
            ->orderBy('symbol')
            ->pluck('symbol')
            ->toArray();
    }

    /**
     * Devuelve los intervalos unicos activos (para el motor Python y el backtesting).
     */
    public static function activeIntervals(): array
    {
        return static::active()
            ->distinct()
            ->orderBy('interval')
            ->pluck('interval')
            ->toArray();
    }

    /**
     * Devuelve los intervalos activos para un simbolo especifico.
     */
    public static function activeIntervalsForSymbol(string $symbol): array
    {
        return static::active()
            ->forSymbol($symbol)
            ->orderBy('interval')
            ->pluck('interval')
            ->toArray();
    }
}

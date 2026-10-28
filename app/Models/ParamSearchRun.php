<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Búsqueda de configuraciones (Estrategias → 🔍 Buscar). La escribe cli/param_search.py --run-id
 * (progreso, latido, resultados); Laravel solo la crea, la cancela y la lee.
 */
class ParamSearchRun extends Model
{
    public const ACTIVE = ['queued', 'running'];

    protected $table = 'param_search_runs';

    protected $fillable = [
        'strategy_id', 'user_id', 'status', 'intervals', 'search_symbols', 'validation_symbols',
        'months', 'samples', 'seed', 'cancel_requested', 'error', 'focus', 'mode',
    ];

    protected $casts = [
        'intervals'          => 'array',
        'search_symbols'     => 'array',
        'validation_symbols' => 'array',
        'results'            => 'array',
        'cancel_requested'   => 'boolean',
        'period_start'       => 'date',
        'split_date'         => 'date',
        'period_end'         => 'date',
        'heartbeat_at'       => 'datetime',
        'started_at'         => 'datetime',
        'finished_at'        => 'datetime',
    ];

    public function strategy(): BelongsTo
    {
        return $this->belongsTo(Strategy::class);
    }

    public function isActive(): bool
    {
        return in_array($this->status, self::ACTIVE, true);
    }

    /** El código de la estrategia cambió después de la búsqueda: sus resultados ya no describen lo que correría. */
    public function isOutdated(): bool
    {
        $code = $this->strategy?->code;

        return $this->strategy_code_md5 !== null && $code !== null && md5($code) !== $this->strategy_code_md5;
    }
}

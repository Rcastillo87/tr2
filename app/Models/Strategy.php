<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Strategy extends Model {
    /** Regímenes del motor (BaseStrategy.REGIMES), en el orden en que se muestran. */
    public const REGIMES = ['TRENDING', 'RANGING', 'VOLATILE'];

    protected $fillable = ['name', 'description', 'code', 'config', 'active'];
    protected $casts = [
        'active' => 'boolean',
        'config' => 'array'
    ];

    public function backtests(): HasMany {
        return $this->hasMany(Backtest::class);
    }

    /**
     * Regímenes en los que opera la estrategia según su código (`allowed_regimes = [...]` de la clase).
     * Sin esa línea, los 3 (el valor de BaseStrategy). Es lo que la pantalla marca por defecto.
     */
    public function allowedRegimes(): array
    {
        if (! preg_match('/^\s*allowed_regimes\s*(?::[^=\n]*)?=\s*\[([^\]]*)\]/m', (string) $this->code, $m)) {
            return self::REGIMES;
        }
        preg_match_all('/[\'"]([A-Z_]+)[\'"]/', $m[1], $names);
        $found = array_values(array_intersect(self::REGIMES, $names[1]));

        return $found ?: self::REGIMES;
    }
}

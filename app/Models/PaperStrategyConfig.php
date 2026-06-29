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
        'audited_months',
        'avg_win_rate',
        'avg_monthly_pnl',
        'avg_monthly_trades',
        'total_return_pct',
        'star_wr', 'star_sharpe', 'star_ret', 'star_consistency', 'star_pf', 'star_rating',
        'backtest_range_from', 'backtest_range_to',
        'sharpe_ratio', 'consistency_pct', 'profit_factor',
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

    /**
     * Mapea el nombre de estrategia usado en Backtesting (display generico,
     * ej. "VWAP Tendencia") a la clase Python real y el modo (si aplica).
     */
    public static function strategyNameToClassAndMode(string $strategyName): array
    {
        return match ($strategyName) {
            'VWAP Tendencia'         => ['class' => 'VwapStrategy', 'mode' => 'trend_follow'],
            'VWAP Reversión'         => ['class' => 'VwapStrategy', 'mode' => 'reversion'],
            'Reversión a la Media'   => ['class' => 'MeanReversionStrategy', 'mode' => null],
            'Tendencia EMA/Donchian' => ['class' => 'EmaDonchianStrategy', 'mode' => null],
            default => throw new \InvalidArgumentException("Estrategia no reconocida: {$strategyName}"),
        };
    }

    /**
     * Mapea clase+modo de vuelta al nombre de estrategia usado en Backtesting,
     * para precargar el formulario al re-testear.
     */
    public static function classAndModeToStrategyName(string $class, ?string $mode): string
    {
        if ($class === 'VwapStrategy') {
            return $mode === 'reversion' ? 'VWAP Reversión' : 'VWAP Tendencia';
        }
        return match ($class) {
            'MeanReversionStrategy' => 'Reversión a la Media',
            'EmaDonchianStrategy'   => 'Tendencia EMA/Donchian',
            default => $class,
        };
    }

    /**
     * Crea o actualiza (por unicidad strategy_class+symbol+interval) la config
     * de Paper Trading a partir de los parametros usados en un backtest.
     * Esta es la UNICA via para que una configuracion entre en produccion,
     * garantizando que Backtesting y Paper Trading comparten la misma fuente
     * de verdad (misma fila, mismos parametros exactos).
     */
    public static function implementFromBacktest(string $strategyName, string $symbol, string $interval,
                                                   array $params, ?string $displayNameOverride = null): self
    {
        $map = self::strategyNameToClassAndMode($strategyName);

        if ($map['mode']) {
            $params['mode'] = $map['mode'];
        }

        $intervalLabels = ['1' => '1m', '5' => '5m', '15' => '15m', '60' => 'H1', '120' => 'H2', '240' => 'H4', 'D' => 'D1'];
        $intervalLabel = $intervalLabels[$interval] ?? $interval;

        $displayName = $displayNameOverride ?: "{$strategyName} — {$symbol} {$intervalLabel}";

        // Buscar config existente con misma clase+simbolo+intervalo+modo
        // (el mode es parte de la identidad para VwapStrategy, donde
        // "VWAP Tendencia" y "VWAP Reversión" son distintas configs)
        $existing = self::where('strategy_class', $map['class'])
            ->where('symbol', $symbol)
            ->where('interval', $interval)
            ->when($map['mode'], fn ($q) => $q->where('params->mode', $map['mode']))
            ->first();

        if ($existing) {
            $existing->update([
                'display_name' => $displayName,
                'params'       => $params,
                'active'       => true,
            ]);
            return $existing->fresh();
        }

        return self::create([
            'display_name'   => $displayName,
            'strategy_class' => $map['class'],
            'symbol'         => $symbol,
            'interval'       => $interval,
            'params'         => $params,
            'active'         => true,
        ]);
    }
}

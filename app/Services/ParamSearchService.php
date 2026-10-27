<?php

namespace App\Services;

use App\Helpers\RatingHelper;
use App\Jobs\RunParamSearchJob;
use App\Models\CollectorConfig;
use App\Models\ParamSearchRun;
use App\Models\Strategy;
use DomainException;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;

/**
 * Módulo "Buscar configuración": crea, cancela, depura y resume búsquedas.
 * La búsqueda en sí corre en cli/param_search.py --run-id (cola research, 1 proceso, prioridad mínima).
 */
class ParamSearchService
{
    public const INTERVALS = ['15', '60', '120', '240', 'D'];
    public const MONTHS = 24;
    public const SAMPLES = 40;
    public const MIN_SYMBOLS = 3;
    public const MAX_SYMBOLS = 6;
    public const KEEP_PER_STRATEGY = 10;
    public const MAX_MINUTES = 60;
    public const QUEUE_CONNECTION = 'redis-research';
    public const QUEUE = 'research';
    /** Minutos medidos/estimados por intervalo (4 monedas + validación). 4h medido: ~3 min. */
    public const MINUTES_PER_INTERVAL = ['15' => 8, '60' => 5, '120' => 4, '240' => 3, 'D' => 1];

    /** Monedas de Bybit activas en el collector para TODOS los intervalos pedidos. */
    public function availableSymbols(array $intervals): array
    {
        $sets = [];
        foreach ($intervals as $iv) {
            $sets[] = CollectorConfig::active()->where('broker', 'bybit')->where('interval', $iv)
                ->orderBy('symbol')->pluck('symbol')->unique()->values()->all();
        }

        return $sets ? array_values(array_intersect(...$sets)) : [];
    }

    public function estimateMinutes(array $intervals): int
    {
        return (int) array_sum(array_map(fn ($iv) => self::MINUTES_PER_INTERVAL[$iv] ?? 5, $intervals));
    }

    /**
     * Crea la búsqueda y la encola. La base garantiza una sola activa en todo el sistema
     * (índice único param_search_runs_one_active).
     *
     * @throws DomainException con un mensaje para el usuario
     */
    public function start(Strategy $strategy, array $intervals, array $symbols, bool $validate, ?int $userId): ParamSearchRun
    {
        $intervals = array_values(array_unique(array_map('strval', $intervals)));
        $symbols = array_values(array_unique(array_map('strval', $symbols)));

        if ($intervals === [] || array_diff($intervals, self::INTERVALS)) {
            throw new DomainException('Temporalidad no permitida (solo 15m, 1h, 2h, 4h o 1D).');
        }
        if (count($symbols) < self::MIN_SYMBOLS || count($symbols) > self::MAX_SYMBOLS) {
            throw new DomainException('Elige entre ' . self::MIN_SYMBOLS . ' y ' . self::MAX_SYMBOLS . ' monedas para buscar.');
        }
        $available = $this->availableSymbols($intervals);
        if ($missing = array_diff($symbols, $available)) {
            throw new DomainException('Sin datos para esa temporalidad: ' . implode(', ', $missing) . '.');
        }
        if (! trim((string) $strategy->code)) {
            throw new DomainException('La estrategia no tiene código.');
        }

        $this->reapStale();
        $validation = $validate ? array_values(array_diff($available, $symbols)) : [];

        try {
            $run = ParamSearchRun::create([
                'strategy_id'        => $strategy->id,
                'user_id'            => $userId,
                'status'             => 'queued',
                'intervals'          => $intervals,
                'search_symbols'     => $symbols,
                'validation_symbols' => $validation,
                'months'             => self::MONTHS,
                'samples'            => self::SAMPLES,
                'seed'               => random_int(1, 1_000_000),   // cada búsqueda prueba combinaciones distintas
            ]);
        } catch (QueryException $e) {
            if (($e->errorInfo[0] ?? null) === '23505') {
                throw new DomainException('Ya hay una búsqueda en curso (solo una a la vez para no afectar la operación).');
            }
            throw $e;
        }

        RunParamSearchJob::dispatch($run->id)->onConnection(self::QUEUE_CONNECTION)->onQueue(self::QUEUE);
        $this->prune($strategy->id);

        return $run;
    }

    /** En cola: se cancela al instante. Corriendo: el proceso lo lee en su próximo latido (≤ 3 s) y se detiene. */
    public function cancel(ParamSearchRun $run): void
    {
        DB::transaction(function () use ($run) {
            $run->refresh();
            if ($run->status === 'queued') {
                $run->update(['status' => 'cancelled', 'error' => 'Cancelada antes de empezar.']);
            } elseif ($run->status === 'running') {
                $run->update(['cancel_requested' => true]);
            }
        });
    }

    /** Búsquedas sin señal de vida (proceso caído por reinicio) o que nunca arrancaron: se marcan fallidas. */
    public function reapStale(): int
    {
        return DB::update(
            "UPDATE param_search_runs SET status = 'failed', finished_at = now(), updated_at = now(),
                    error = CASE WHEN status = 'running'
                                 THEN 'Sin señal de vida del proceso (reinicio del servidor, del motor o de Horizon).'
                                 ELSE 'No arrancó: la cola de búsquedas no la tomó a tiempo.' END
             WHERE (status = 'running' AND coalesce(heartbeat_at, started_at, created_at) < now() - interval '3 minutes')
                OR (status = 'queued' AND created_at < now() - interval '30 minutes')"
        );
    }

    /** Conserva las últimas KEEP_PER_STRATEGY búsquedas terminadas por estrategia. */
    public function prune(int $strategyId): void
    {
        $keep = ParamSearchRun::where('strategy_id', $strategyId)->orderByDesc('id')
            ->limit(self::KEEP_PER_STRATEGY)->pluck('id');
        ParamSearchRun::where('strategy_id', $strategyId)->whereNotIn('id', $keep)
            ->whereNotIn('status', ParamSearchRun::ACTIVE)->delete();
    }

    /**
     * Métricas de una fila de resultados sobre un conjunto de monedas, calculadas EXACTAMENTE como el resultado del
     * backtest (partials/results.blade.php) y lo que guarda el historial: estrellas = promedio de RatingHelper por
     * moneda; retorno y consistencia sobre la suma mensual de todas las monedas; PF global por gp/gl.
     */
    public function summarize(array $row, ?array $symbols = null): array
    {
        $bySymbol = $row['symbols'] ?? [];
        $symbols = $symbols === null ? array_keys($bySymbol) : array_values(array_intersect($symbols, array_keys($bySymbol)));

        $ratings = $sharpes = [];
        $trades = $wins = 0;
        $gp = $gl = 0.0;
        $dd = 0.0;
        $monthly = [];
        foreach ($symbols as $sym) {
            $s = $bySymbol[$sym];
            $months = array_map(fn ($v) => (float) ($v ?? 0), $s['m'] ?? []);
            $avg = count($months) ? array_sum($months) / count($months) : 0.0;
            $consist = count($months) ? round(count(array_filter($months, fn ($v) => $v > 0)) / count($months) * 100, 1) : 0.0;
            $ratings[] = RatingHelper::calculate((float) ($s['wr'] ?? 0), (float) ($s['sharpe'] ?? 0),
                (float) ($s['pf'] ?? 0), $avg, $consist);
            $sharpes[] = (float) ($s['sharpe'] ?? 0);
            $trades += (int) ($s['n'] ?? 0);
            $wins += (int) ($s['wins'] ?? 0);
            $gp += (float) ($s['gp'] ?? 0);
            $gl += (float) ($s['gl'] ?? 0);
            $dd = max($dd, (float) ($s['dd'] ?? 0));
            foreach ($months as $k => $v) {
                $monthly[$k] = ($monthly[$k] ?? 0.0) + $v;
            }
        }
        $n = count($symbols);
        $positive = count(array_filter($monthly, fn ($v) => $v > 0));

        return [
            'symbols'          => $symbols,
            'rating'           => $n ? round(array_sum($ratings) / $n, 1) : 0.0,
            'total_trades'     => $trades,
            'win_rate'         => $trades ? round($wins / $trades * 100, 2) : 0.0,
            'sharpe_ratio'     => $n ? round(array_sum($sharpes) / $n, 2) : 0.0,
            'profit_factor'    => $gl > 0 ? round($gp / $gl, 2) : ($gp > 0 ? 999.99 : 0.0),
            'total_return_pct' => round(array_sum($monthly), 2),
            'avg_monthly_pnl'  => $monthly ? round(array_sum($monthly) / count($monthly), 2) : 0.0,
            'consist_pct'      => $monthly ? round($positive / count($monthly) * 100, 1) : 0.0,
            'max_drawdown_pct' => round($dd, 2),
            'winners'          => array_values(array_filter($symbols, fn ($s) => (float) ($bySymbol[$s]['ret'] ?? 0) > 0)),
        ];
    }

    /** Una fila se puede crear en el historial solo si es robusta y pasó la validación (o no se pidió validar). */
    public function creatable(ParamSearchRun $run, array $row): bool
    {
        return ! empty($row['robusta']) && ($row['validada'] === true || $run->validation_symbols === []);
    }
}

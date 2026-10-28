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
    public const MODES = ['interval', 'symbol'];
    /** Enfoque (v3): qué combinaciones se prueban (cli/param_search.py SPACES) y cómo se ordenan los resultados. */
    public const FOCUSES = ['gain' => 'Mayor ganancia', 'wr' => 'Win rate alto', 'cons' => 'Consistencia alta'];
    /** Orden de los resultados por enfoque: métrica principal de summarize() (desempate: retorno total, estrellas). */
    public const FOCUS_SORT = ['gain' => 'total_return_pct', 'wr' => 'win_rate', 'cons' => 'consist_pct'];
    /** Modo "por moneda": de 1 a MAX_SYMBOLS_SYMBOL_MODE monedas × todas las temporalidades con datos. */
    public const MAX_SYMBOLS_SYMBOL_MODE = 5;
    public const KEEP_PER_STRATEGY = 10;
    /** Tope técnico (no visible): una búsqueda nunca queda colgada. Job y cola tienen márgenes mayores. */
    public const MAX_MINUTES = 180;
    public const QUEUE_CONNECTION = 'redis-research';
    public const QUEUE = 'research';
    /** Minutos medidos/estimados por intervalo (4 monedas + validación). 4h medido: ~3 min. */
    public const MINUTES_PER_INTERVAL = ['15' => 8, '60' => 5, '120' => 3, '240' => 3, 'D' => 1];   // 2h y 4h medidos

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
     * Crea la búsqueda y la encola (cola research: corren de a una, en orden de llegada).
     *  - mode "interval": UNA temporalidad y de 1 a todas las monedas con datos en ella.
     *  - mode "symbol":   de 1 a MAX_SYMBOLS_SYMBOL_MODE monedas y TODAS las temporalidades con datos para ellas.
     *  - focus: gain | wr | cons (FOCUSES).
     * Una sola búsqueda en cola o corriendo por estrategia (índice único en la base).
     *
     * @throws DomainException con un mensaje para el usuario
     */
    public function start(Strategy $strategy, string $mode, array $intervals, array $symbols, ?int $userId,
                          string $focus = 'gain'): ParamSearchRun
    {
        $symbols = array_values(array_unique(array_map('strval', $symbols)));
        $intervals = array_values(array_unique(array_map('strval', $intervals)));
        if (! in_array($mode, self::MODES, true)) {
            throw new DomainException('Modo de búsqueda no válido.');
        }
        if (! array_key_exists($focus, self::FOCUSES)) {
            throw new DomainException('Enfoque de búsqueda no válido.');
        }
        if ($symbols === []) {
            throw new DomainException('Elige al menos una moneda.');
        }
        if ($mode === 'interval') {
            if (count($intervals) !== 1 || array_diff($intervals, self::INTERVALS)) {
                throw new DomainException('Elige una temporalidad (15m, 1h, 2h, 4h o 1D).');
            }
            if ($missing = array_diff($symbols, $this->availableSymbols($intervals))) {
                throw new DomainException('Sin datos en esa temporalidad: ' . implode(', ', $missing) . '.');
            }
        } else {
            if (count($symbols) > self::MAX_SYMBOLS_SYMBOL_MODE) {
                throw new DomainException('En el modo por moneda puedes elegir hasta ' . self::MAX_SYMBOLS_SYMBOL_MODE . ' monedas.');
            }
            // todas las temporalidades donde TODAS las monedas elegidas tienen datos
            $intervals = array_values(array_filter(self::INTERVALS,
                fn ($iv) => ! array_diff($symbols, $this->availableSymbols([$iv]))));
            if ($intervals === []) {
                throw new DomainException('Esas monedas no tienen datos en ninguna temporalidad común.');
            }
        }
        if (! trim((string) $strategy->code)) {
            throw new DomainException('La estrategia no tiene código.');
        }

        $this->reapStale();
        try {
            $run = ParamSearchRun::create([
                'strategy_id'        => $strategy->id,
                'user_id'            => $userId,
                'status'             => 'queued',
                'mode'               => $mode,
                'focus'              => $focus,
                'intervals'          => $intervals,
                'search_symbols'     => $symbols,
                'validation_symbols' => [],
                'months'             => self::MONTHS,
                'samples'            => self::SAMPLES,
                'seed'               => random_int(1, 1_000_000),   // cada búsqueda prueba combinaciones distintas
            ]);
        } catch (QueryException $e) {
            if (($e->errorInfo[0] ?? null) === '23505') {
                throw new DomainException("«{$strategy->name}» ya tiene una búsqueda en cola o en curso.");
            }
            throw $e;
        }

        RunParamSearchJob::dispatch($run->id)->onConnection(self::QUEUE_CONNECTION)->onQueue(self::QUEUE);
        $this->prune($strategy->id);

        return $run;
    }

    /**
     * "Buscar en todas las estrategias": una búsqueda en cola por estrategia activa con código; corren una tras otra.
     *
     * @return array{created: array<int, string>, skipped: array<string, string>}
     */
    public function startAll(string $mode, array $intervals, array $symbols, ?int $userId, string $focus = 'gain'): array
    {
        $created = $skipped = [];
        foreach (Strategy::where('active', true)->orderBy('name')->get() as $s) {
            try {
                $created[$this->start($s, $mode, $intervals, $symbols, $userId, $focus)->id] = $s->name;
            } catch (DomainException $e) {
                $skipped[$s->name] = $e->getMessage();
            }
        }

        return ['created' => $created, 'skipped' => $skipped];
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

    /**
     * Elimina una búsqueda terminada, fallida o cancelada (y sus resultados). Los backtests que ya se crearon desde
     * ella en el historial no se tocan. Una en cola o en curso primero se cancela.
     *
     * @throws DomainException
     */
    public function delete(ParamSearchRun $run): void
    {
        DB::transaction(function () use ($run) {
            $run = ParamSearchRun::whereKey($run->id)->lockForUpdate()->first();
            if (! $run) {
                return;
            }
            if ($run->isActive()) {
                throw new DomainException('La búsqueda está en cola o en curso: cancélala antes de eliminarla.');
            }
            $run->delete();
        });
    }

    /** Búsquedas sin señal de vida (proceso caído por reinicio) o que nunca arrancaron: se marcan fallidas. */
    public function reapStale(): int
    {
        return DB::update(
            "UPDATE param_search_runs SET status = 'failed', finished_at = now(), updated_at = now(),
                    error = CASE WHEN status = 'running'
                                 THEN 'Sin señal de vida del proceso (reinicio del servidor, del motor o de Horizon).'
                                 ELSE 'No arrancó en 24 h: la cola de búsquedas no la tomó.' END
             WHERE (status = 'running' AND coalesce(heartbeat_at, started_at, created_at) < now() - interval '3 minutes')
                OR (status = 'queued' AND created_at < now() - interval '24 hours')"
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
        $symbols ??= $row['survivors'] ?? array_keys($bySymbol);   // por defecto: las monedas que sobrevivieron
        $symbols = array_values(array_intersect($symbols, array_keys($bySymbol)));

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

    /**
     * Se puede crear en el historial: búsquedas nuevas (v2) = la configuración sobrevivió en al menos una moneda;
     * búsquedas anteriores (v1) = robusta y validada (la regla con la que se hicieron).
     */
    public function creatable(ParamSearchRun $run, array $row): bool
    {
        if (($run->results['version'] ?? 1) >= 2) {
            return ! empty($row['survivors']);
        }

        return ! empty($row['robusta']) && ($row['validada'] === true || $run->validation_symbols === []);
    }

    /**
     * Monedas con las que se resume y se crea una fila. v3: por moneda = su moneda; por temporalidad = TODAS las probadas
     * (ninguna se descarta después de ver el resultado). v2: sobrevivientes o todas las probadas.
     */
    public function symbolsFor(ParamSearchRun $run, array $row, string $mode): array
    {
        $all = array_keys($row['symbols'] ?? []);
        if (($run->results['version'] ?? 1) >= 3) {
            return isset($row['symbol']) ? [(string) $row['symbol']] : $all;
        }
        if ($mode === 'all') {
            return $all;
        }

        return $row['survivors'] ?? $this->summarize($row)['winners'];
    }
}

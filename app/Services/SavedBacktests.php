<?php

namespace App\Services;

use App\Helpers\RatingHelper;
use App\Models\Backtest;
use App\Support\BacktestOrigin;
use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Facades\DB;

/**
 * RQ-01.4: lista global de backtests guardados (todas las estrategias) con su estado en Paper.
 * Filtros y orden en SQL; la página se enriquece con DOS consultas agregadas (configs y trades Paper), sin N+1.
 *
 * Estado en Paper de un backtest: «active» si alguna de sus configs está activa, «stopped» si tiene configs y
 * ninguna activa, «none» si no tiene configs.
 */
class SavedBacktests
{
    public const PER_PAGE = 50;
    public const PAPER = ['active' => 'Operando', 'stopped' => 'Detenido', 'none' => 'Sin implementar'];
    public const ORIGINS = ['search' => 'Búsqueda', 'manual' => 'Manual', 'unknown' => 'No registrado'];
    public const SORTS = ['recent', 'rating', 'tpm'];

    /** Filtros saneados desde la petición (valores fuera de lista = sin filtro). */
    public static function filters(array $in): array
    {
        $symbol = strtoupper(preg_replace('/[^A-Za-z0-9]/', '', (string) ($in['symbol'] ?? '')));

        return [
            'strategy' => ctype_digit((string) ($in['strategy'] ?? '')) ? (int) $in['strategy'] : null,
            'paper'    => array_key_exists($in['paper'] ?? '', self::PAPER) ? $in['paper'] : null,
            'origin'   => array_key_exists($in['origin'] ?? '', self::ORIGINS) ? $in['origin'] : null,
            'symbol'   => $symbol !== '' ? substr($symbol, 0, 20) : null,
            'sort'     => in_array($in['sort'] ?? '', self::SORTS, true) ? $in['sort'] : 'recent',
        ];
    }

    public function query(array $f): Builder
    {
        $q = Backtest::query()->with('strategy:id,name')
            ->select(['id', 'strategy_id', 'symbols', 'interval', 'months', 'config_params', 'metrics', 'origin', 'origin_meta',
                      'created_at', 'updated_at']);
        $configs = fn ($active = null) => function ($s) use ($active) {
            $s->selectRaw('1')->from('paper_strategy_configs as c')->whereColumn('c.backtest_id', 'backtests.id');
            if ($active !== null) {
                $s->where('c.active', $active);
            }
        };

        if ($f['strategy'] !== null) {
            $q->where('strategy_id', $f['strategy']);
        }
        match ($f['paper']) {
            'active'  => $q->whereExists($configs(true)),
            'stopped' => $q->whereExists($configs())->whereNotExists($configs(true)),
            'none'    => $q->whereNotExists($configs()),
            default   => null,
        };
        match ($f['origin']) {
            'search', 'manual' => $q->where('origin', $f['origin']),
            'unknown'          => $q->whereNull('origin'),
            default            => null,
        };
        if ($f['symbol'] !== null) {
            // symbols es un arreglo JSON de textos: coincidencia parcial sobre sus elementos
            $q->whereRaw("EXISTS (SELECT 1 FROM json_array_elements_text(backtests.symbols::json) s WHERE s ILIKE ?)",
                ['%' . $f['symbol'] . '%']);
        }

        return $q->orderByDesc('updated_at')->orderByDesc('id');
    }

    /**
     * Página de filas listas para la vista. Orden por calificación o Trades/mes: se calcula en PHP sobre la página
     * (ambos dependen de métricas en JSON); el orden por defecto, el reciente, es SQL.
     */
    public function page(array $f, int $page = 1): LengthAwarePaginator
    {
        $p = $this->query($f)->paginate(self::PER_PAGE, ['*'], 'page', max(1, $page))->withQueryString();
        $ids = $p->getCollection()->pluck('id');

        $configs = $ids->isEmpty() ? collect() : DB::table('paper_strategy_configs')->whereIn('backtest_id', $ids)
            ->orderBy('id')->get(['id', 'backtest_id', 'symbol', 'active']);
        $trades = $configs->isEmpty() ? collect() : DB::table('paper_trades')
            ->whereIn('paper_strategy_config_id', $configs->pluck('id'))->where('status', 'closed')
            ->groupBy('paper_strategy_config_id')
            ->selectRaw('paper_strategy_config_id AS id, count(*) AS n, coalesce(sum(pnl_pct), 0) AS pnl_pct')
            ->get()->keyBy('id');
        $byBacktest = $configs->groupBy('backtest_id');

        $rows = $p->getCollection()->map(function (Backtest $b) use ($byBacktest, $trades) {
            $cfgs = $byBacktest->get($b->id, collect());
            $active = $cfgs->where('active', true);
            $m = $b->metrics ?? [];
            $symbols = $b->symbols ?? [];
            $tpm = collect($symbols)->mapWithKeys(fn ($s) => [$s => StrategyConfigSync::tradesPerMonth($m, $b->config_params ?? [],
                (int) $b->months, (string) $s, count($symbols))]);

            return [
                'id'          => $b->id,
                'date'        => $b->updated_at,
                'strategy'    => $b->strategy?->name ?? '—',
                'strategy_id' => $b->strategy_id,
                'symbols'     => $symbols,
                'interval'    => $b->interval,
                'origin'      => $b->origin,
                'origin_text' => BacktestOrigin::describe($b->origin, $b->origin_meta),
                'run_id'      => $b->origin === BacktestOrigin::SEARCH ? (int) ($b->origin_meta['run_id'] ?? 0) : 0,
                'rating'      => self::rating($m),
                'ret_month'   => self::normalized($m)['ret'],
                'tpm'         => $tpm->all(),
                'tpm_sort'    => $tpm->filter(fn ($v) => $v !== null)->sum(),
                'paper'       => $active->isNotEmpty() ? 'active' : ($cfgs->isNotEmpty() ? 'stopped' : 'none'),
                'config_ids'  => ($active->isNotEmpty() ? $active : $cfgs)->pluck('id')->all(),
                'paper_n'     => (int) $cfgs->sum(fn ($c) => $trades[$c->id]->n ?? 0),
                'paper_pnl'   => round((float) $cfgs->sum(fn ($c) => $trades[$c->id]->pnl_pct ?? 0), 2),
            ];
        });
        if ($f['sort'] !== 'recent') {
            $key = $f['sort'] === 'rating' ? 'rating' : 'tpm_sort';
            $rows = $rows->sortByDesc($key)->values();
        }

        return $p->setCollection($rows);
    }

    /**
     * Métricas en %. Win rate y consistencia guardados como fracción (backtests antiguos, 0–1) pasan a %: un 1 % real
     * no es plausible. El retorno mensual NO se escala: siempre se guardó en % y un 0,71 % es un valor normal (escalarlo
     * lo mostraba como 71 %; ver bitácora p53).
     */
    public static function normalized(array $m): array
    {
        $pct = fn (float $v) => $v > 0 && $v <= 1 ? $v * 100 : $v;

        return [
            'wr'      => $pct((float) ($m['win_rate'] ?? 0)),
            'ret'     => (float) ($m['avg_monthly_pnl'] ?? 0),
            'consist' => $pct((float) ($m['consist_pct'] ?? 0)),
        ];
    }

    /** Misma calificación que la tarjeta del historial. */
    public static function rating(array $m): float
    {
        if (isset($m['rating'])) {
            return (float) $m['rating'];
        }
        $n = self::normalized($m);
        $r = RatingHelper::calculate($n['wr'], (float) ($m['sharpe_ratio'] ?? 0), (float) ($m['profit_factor'] ?? 0), $n['ret'], $n['consist']);

        return $r > 0 ? (float) $r : 1.0;
    }
}

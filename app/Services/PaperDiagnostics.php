<?php

namespace App\Services;

use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

/**
 * RQ-01.5: diagnóstico de Paper para la pantalla. Lee lo que escribe el motor (paper_trader._record_evaluations):
 * paper_eval_state (última decisión por config) y paper_eval_log (historial agrupado). Solo lectura, 2 consultas.
 * Las horas de esas tablas son UTC sin zona.
 */
class PaperDiagnostics
{
    /** Más viejo que esto, la config no se está evaluando (el tick de Paper corre cada minuto). */
    public const STALE_AFTER_MIN = 15;

    /** Motivo del motor => [grupo, texto]. Grupos en orden de prioridad para la pantalla. */
    public const CODES = [
        'kill_switch'           => ['problem', 'Kill switch'],
        'build_error'           => ['problem', 'Error de la estrategia'],
        'collector_stale'       => ['problem', 'Collector atrasado'],
        'insufficient_data'     => ['problem', 'Datos insuficientes'],
        'no_price'              => ['problem', 'Sin precio'],
        'regime_blocked'        => ['blocked', 'Bloqueada por régimen'],
        'filter_blocked'        => ['filtered', 'Señal anulada por filtro'],
        'short_not_allowed'     => ['filtered', 'Corto no permitido'],
        'signal_already_traded' => ['filtered', 'Señal ya operada'],
        'open_position'         => ['position', 'Posición abierta'],
        'opened'                => ['trade', 'Abrió posición'],
        'reversal'              => ['trade', 'Invirtió posición'],
        'closed_opposite'       => ['trade', 'Cerró por señal opuesta'],
        'no_signal'             => ['quiet', 'Sin señal'],
    ];
    public const GROUPS = ['problem' => 'Problemas', 'blocked' => 'Bloqueadas por régimen', 'filtered' => 'Señal anulada',
                           'position' => 'Con posición abierta', 'trade' => 'Operaron', 'quiet' => 'Sin señal'];

    /** @return array{rows: array, counts: array<string,int>, last: ?Carbon} */
    public function overview(): array
    {
        $rows = DB::select("SELECT c.id, c.symbol, c.interval, c.display_name,
                   s.evaluated_at, s.code, s.detail, s.regime, s.signal, s.filters, s.candle_time, s.bars
              FROM paper_strategy_configs c
              LEFT JOIN paper_eval_state s ON s.paper_strategy_config_id = c.id
             WHERE c.active
             ORDER BY c.id");
        $ids = array_map(fn ($r) => (int) $r->id, $rows);
        $day = $ids === [] ? collect() : collect(DB::select(
            "SELECT paper_strategy_config_id AS id, code, sum(evaluations)::int AS n
               FROM paper_eval_log
              WHERE last_at >= (now() AT TIME ZONE 'UTC') - interval '24 hours'
                AND paper_strategy_config_id = ANY(?::bigint[])
              GROUP BY 1, 2", ['{' . implode(',', $ids) . '}']))->groupBy('id');

        $now = Carbon::now('UTC');
        $out = array_map(fn ($r) => self::row($r, $day->get($r->id, collect())->pluck('n', 'code')->all(), $now), $rows);
        $order = array_flip(array_keys(self::GROUPS));
        $rank = fn ($g) => in_array($g, ['missing', 'stale'], true) ? -1 : ($order[$g] ?? 99);
        usort($out, fn ($a, $b) => [$rank($a['group']), $a['id']] <=> [$rank($b['group']), $b['id']]);

        $counts = array_fill_keys(array_keys(self::GROUPS), 0);
        foreach ($out as $r) {
            $counts[in_array($r['group'], ['missing', 'stale'], true) ? 'problem' : $r['group']]++;
        }
        $last = collect($out)->pluck('evaluated_at')->filter()->max();

        return ['rows' => $out, 'counts' => $counts, 'last' => $last];
    }

    /** Fila de pantalla a partir del estado guardado (pura: sin base). */
    public static function row(object $r, array $day, Carbon $now): array
    {
        $at = $r->evaluated_at ? Carbon::parse($r->evaluated_at, 'UTC') : null;
        [$group, $label] = self::CODES[$r->code ?? ''] ?? ['problem', (string) ($r->code ?? '')];
        if ($at === null) {
            [$group, $label] = ['missing', 'Sin evaluar todavía'];
        } elseif ($at->diffInMinutes($now, true) > self::STALE_AFTER_MIN) {
            [$group, $label] = ['stale', 'Sin evaluar desde ' . $at->copy()->timezone('America/Bogota')->format('d-m H:i')];
        }
        $trace = self::trace(is_string($r->filters ?? null) ? json_decode($r->filters, true) : ($r->filters ?? null));
        arsort($day);

        return [
            'id'           => (int) $r->id,
            'name'         => (string) $r->display_name,
            'symbol'       => (string) $r->symbol,
            'interval'     => (string) $r->interval,
            'group'        => $group,
            'label'        => $label,
            'code'         => $r->code,
            'detail'       => (string) ($r->detail ?? ''),
            'regime'       => $r->regime,
            'signal'       => $r->signal === null ? null : (int) $r->signal,
            'candle_time'  => $r->candle_time ? Carbon::parse($r->candle_time, 'UTC') : null,
            'evaluated_at' => $at,
            'bars'         => $r->bars === null ? null : (int) $r->bars,
            'trace'        => $trace,
            'day'          => array_map(fn ($code, $n) => [self::CODES[$code][1] ?? $code, (int) $n], array_keys($day), $day),
        ];
    }

    /**
     * Traza de la señal: cada paso con su señal y si fue el que la anuló (el primer paso, después de la estrategia,
     * que deja en 0 una señal que venía distinta de 0). Misma regla que paper_trader.blocking_filter.
     */
    public static function trace(?array $filters): array
    {
        $out = [];
        $prev = null;
        $blocked = false;
        foreach (is_array($filters) ? $filters : [] as $f) {
            if (! is_array($f) || ! isset($f['step'])) {
                continue;
            }
            $sig = (int) ($f['signal'] ?? 0);
            $kills = ! $blocked && $prev !== null && $prev !== 0 && $sig === 0;
            $blocked = $blocked || $kills;
            $out[] = ['step' => preg_replace('/_filter$/', '', (string) $f['step']), 'signal' => $sig, 'kills' => $kills];
            $prev = $sig;
        }

        return $out;
    }
}

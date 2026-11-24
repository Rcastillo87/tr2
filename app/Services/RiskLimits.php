<?php

namespace App\Services;

use Illuminate\Support\Carbon;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

/**
 * Estado de los límites de riesgo de cada cuenta de broker (lo que muestra el panel «Límites de riesgo» de Trading).
 * La misma regla que aplica el motor antes de cada orden (RealTrader.entry_limit_reason):
 *   - pérdida = suma neta de los trades cerrados desde el día 1 (00:00 Bogotá), en % del saldo inicial del mes
 *     (month_start_balance); D-66: tras una pausa, desde que se reanudó y sobre el patrimonio de ese momento;
 *   - trades abiertos = pending_open + open + pending_close + orphaned (C5-16: las huérfanas pueden estar vivas);
 *   - D-66: cada límite se puede desactivar («sin límite») y la pérdida máxima puede pausar N días;
 *   - C6-02: sin saldo base del mes (D-51) o con una operación sin confirmar (D-50) el motor no abre: el panel lo dice.
 * Dos consultas agrupadas para todas las cuentas (sin N+1). La regla de cada cuenta es pura: evaluate().
 */
final class RiskLimits
{
    public const TZ = 'America/Bogota';

    public const OPEN_STATUSES = ['pending_open', 'open', 'pending_close', 'orphaned'];

    /** @return array{0:string,1:Carbon} primer día del mes en Bogotá (Y-m-d) y ese instante en UTC */
    public static function monthStart(?Carbon $now = null): array
    {
        $local = ($now ? $now->copy() : Carbon::now())->timezone(self::TZ)->startOfMonth();

        return [$local->toDateString(), $local->copy()->utc()];
    }

    /** D-66: interruptor general (RISK_LIMIT_OPTIONS_ENABLED; el motor lee el mismo nombre en su .env). */
    public static function optionsEnabled(): bool
    {
        return (bool) config('trading.risk_limit_options', true);
    }

    /** «13-nov 10:00» en hora de Bogotá, para un instante UTC. */
    public static function bogota(Carbon $utc): string
    {
        $months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
        $l = $utc->copy()->timezone(self::TZ);

        return $l->day . '-' . $months[$l->month - 1] . ' ' . $l->format('H:i');
    }

    /** @return array<int, array<string, mixed>> por id de cuenta */
    public function summary(Collection $accounts): array
    {
        if ($accounts->isEmpty()) {
            return [];
        }
        [$month, $sinceUtc] = self::monthStart();
        $options = self::optionsEnabled();
        $ids = $accounts->pluck('id')->all();
        $since = $sinceUtc->format('Y-m-d H:i:s');

        $open = DB::table('real_trades')->whereIn('broker_account_id', $ids)
            ->whereIn('status', self::OPEN_STATUSES)
            ->groupBy('broker_account_id')->selectRaw('broker_account_id, count(*) AS n')
            ->pluck('n', 'broker_account_id');
        // Desde el inicio del conteo de cada cuenta: el período tras una pausa (si empezó este mes) o el día 1
        $pnl = DB::table('real_trades as rt')->join('broker_accounts as ba', 'ba.id', '=', 'rt.broker_account_id')
            ->whereIn('rt.broker_account_id', $ids)->where('rt.status', 'closed')
            ->whereRaw('rt.exit_time >= CASE WHEN ?::boolean AND ba.loss_period_start > ?::timestamp AND ba.loss_period_balance > 0'
                . ' THEN ba.loss_period_start ELSE ?::timestamp END', [$options ? 'true' : 'false', $since, $since])
            ->groupBy('rt.broker_account_id')->selectRaw('rt.broker_account_id, COALESCE(SUM(COALESCE(rt.net_pnl, rt.pnl, 0)), 0) AS s')
            ->pluck('s', 'rt.broker_account_id');
        // C6-02 / D-50: la operación en estado dudoso más antigua de cada cuenta (misma regla que el motor)
        $unresolved = DB::table('real_trades')->whereIn('broker_account_id', $ids)
            ->where(fn ($q) => $q->where('status', 'orphaned')->orWhere(fn ($p) => $p->where('status', 'pending_open')
                ->where('created_at', '<', now()->subMinutes(\App\Models\RealTrade::PENDING_OPEN_STALE_MIN))))
            ->orderBy('id')->get(['id', 'broker_account_id', 'symbol', 'status'])
            ->groupBy('broker_account_id')->map(fn ($g) => (array) $g->first());

        $next = $sinceUtc->copy()->timezone(self::TZ)->addMonth()->locale('es')->isoFormat('D [de] MMMM');
        $out = [];
        foreach ($accounts as $a) {
            $until = $a->loss_paused_until ? Carbon::parse($a->loss_paused_until, 'UTC') : null;
            $start = $a->loss_period_start ? Carbon::parse($a->loss_period_start, 'UTC') : null;
            $out[$a->id] = self::evaluate([
                'max_loss'          => (float) $a->max_monthly_loss_pct,
                'max_open'          => (int) $a->max_open_trades,
                'month_at'          => $a->month_start_at ? Carbon::parse($a->month_start_at)->toDateString() : null,
                'month_balance'     => (float) $a->month_start_balance,
                'loss_enabled'      => $a->monthly_loss_enabled !== false,
                'open_enabled'      => $a->open_trades_limit_enabled !== false,
                'pause_days'        => $a->loss_pause_days !== null ? (int) $a->loss_pause_days : null,
                'paused_until'      => $until?->getTimestamp(),
                'paused_until_text' => $until ? self::bogota($until) : null,
                'period_start'      => $start?->getTimestamp(),
                'period_start_text' => $start ? explode(' ', self::bogota($start))[0] : null,
                'period_balance'    => $a->loss_period_balance !== null ? (float) $a->loss_period_balance : null,
            ], (float) ($pnl[$a->id] ?? 0), (int) ($open[$a->id] ?? 0), $month, $sinceUtc->getTimestamp(), time(), $options, $next,
                $unresolved[$a->id] ?? null);
        }

        return $out;
    }

    /**
     * Regla de una cuenta (pura, sin base ni Carbon; la misma del motor). $a: max_loss, max_open, month_at (Y-m-d),
     * month_balance, loss_enabled, open_enabled, pause_days, paused_until / period_start (segundos Unix) con sus textos
     * en hora de Bogotá, period_balance. $since / $now en segundos Unix; $next = «1 de diciembre». $unresolved = la
     * operación dudosa más antigua de la cuenta (id, symbol, status) o null. El orden es el del motor: pausa, saldo base,
     * operación dudosa, pérdida máxima, trades abiertos.
     */
    public static function evaluate(array $a, float $pnl, int $openN, string $month, int $since, int $now, bool $options, string $next,
                                    ?array $unresolved = null): array
    {
        $maxLoss = (float) $a['max_loss'];
        $maxOpen = max(1, (int) $a['max_open']);
        $lossOn = $maxLoss > 0 && (! $options || $a['loss_enabled']);
        $openOn = ! $options || $a['open_enabled'];
        $period = $options && $a['period_start'] !== null && $a['period_start'] > $since && ($a['period_balance'] ?? 0) > 0;
        $base = $period ? (float) $a['period_balance']
            : ($a['month_at'] === $month && $a['month_balance'] > 0 ? (float) $a['month_balance'] : null);
        $pct = $base ? $pnl / $base * 100 : null;
        $until = $options && $lossOn ? $a['paused_until'] : null;
        $days = $options ? $a['pause_days'] : null;

        [$state, $note] = match (true) {
            $until !== null && $now < $until    => ['paused', 'Llegó a la pérdida máxima: sin entradas nuevas hasta el '
                . $a['paused_until_text'] . '; las abiertas se siguen gestionando. Al reanudar, la pérdida se cuenta de cero.'],
            $until !== null                     => ['paused', 'Terminó la pausa: la pérdida se cuenta de cero en el próximo ciclo del motor.'],
            $lossOn && ! $base                  => ['waiting_baseline', 'Falta el saldo inicial del mes (Bybit no lo dio): sin él no se '
                . 'puede aplicar la pérdida máxima. Las abiertas se siguen gestionando; el motor lo reintenta cada minuto.'],
            $unresolved !== null                => ['unresolved', "#{$unresolved['id']} {$unresolved['symbol']} sin confirmar con Bybit: "
                . 'no se abre nada hasta que la conciliación la resuelva (cada minuto). Las abiertas se siguen gestionando.'],
            $lossOn && $pct !== null && $pct <= -$maxLoss => ['blocked', $days
                ? "Pérdida máxima alcanzada: pausa de {$days} día(s) desde el próximo ciclo del motor."
                : "Pérdida del mes alcanzada: sin entradas hasta el {$next}."],
            $openOn && $openN >= $maxOpen       => ['full', 'Máximo de trades abiertos: abre de nuevo al cerrarse uno.'],
            default                             => ['ok', ''],
        };
        $off = array_filter([$lossOn || $maxLoss <= 0 ? null : 'pérdida del mes', $openOn ? null : 'trades abiertos']);
        if ($off !== []) {
            $note = trim('Protecciones desactivadas: ' . implode(' y ', $off) . ' sin límite. ' . $note);
        }

        return [
            'pct'          => $pct,
            'pct_text'     => $pct === null ? '—' : (($pct > 0 ? '+' : ($pct < 0 ? '−' : '')) . number_format(abs($pct), 2, ',', '.') . ' %'),
            'base'         => $base,
            'label'        => $period ? 'Desde ' . $a['period_start_text'] : 'Mes',
            'max_loss'     => $maxLoss,
            'loss_on'      => $lossOn,
            'loss_use'     => $lossOn && $pct !== null && $pct < 0 ? min(100, -$pct / $maxLoss * 100) : 0,
            'open'         => $openN,
            'max_open'     => $maxOpen,
            'open_on'      => $openOn,
            'open_use'     => $openOn ? min(100, $openN / $maxOpen * 100) : 0,
            'pause_days'   => $a['pause_days'],
            'loss_enabled' => (bool) $a['loss_enabled'],
            'open_enabled' => (bool) $a['open_enabled'],
            'paused_text'  => $until !== null && $now < $until ? $a['paused_until_text'] : null,
            'state'        => $state,
            'note'         => $note,
        ];
    }
}

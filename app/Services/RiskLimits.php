<?php

namespace App\Services;

use Illuminate\Support\Carbon;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

/**
 * Estado de los límites de riesgo de cada cuenta de broker (lo que muestra /trading/accounts).
 * La misma regla que aplica el motor antes de cada orden (RealTrader.entry_limit_reason):
 *   - pérdida del mes = suma neta de los trades cerrados desde el día 1 (00:00 Bogotá), en % del saldo inicial
 *     del mes (month_start_balance, que el motor guarda al empezar el mes o al conectar la cuenta);
 *   - trades abiertos = pending_open + open + pending_close de la cuenta.
 * Dos consultas agrupadas para todas las cuentas (sin N+1).
 */
final class RiskLimits
{
    public const TZ = 'America/Bogota';

    /** @return array{0:string,1:Carbon} primer día del mes en Bogotá (Y-m-d) y ese instante en UTC */
    public static function monthStart(?Carbon $now = null): array
    {
        $local = ($now ? $now->copy() : Carbon::now())->timezone(self::TZ)->startOfMonth();

        return [$local->toDateString(), $local->copy()->utc()];
    }

    /** @return array<int, array<string, mixed>> por id de cuenta */
    public function summary(Collection $accounts): array
    {
        if ($accounts->isEmpty()) {
            return [];
        }
        [$month, $sinceUtc] = self::monthStart();
        $ids = $accounts->pluck('id')->all();

        $open = DB::table('real_trades')->whereIn('broker_account_id', $ids)
            ->whereIn('status', ['pending_open', 'open', 'pending_close'])
            ->groupBy('broker_account_id')->selectRaw('broker_account_id, count(*) AS n')
            ->pluck('n', 'broker_account_id');
        $pnl = DB::table('real_trades')->whereIn('broker_account_id', $ids)
            ->where('status', 'closed')->where('exit_time', '>=', $sinceUtc->format('Y-m-d H:i:s'))
            ->groupBy('broker_account_id')->selectRaw('broker_account_id, COALESCE(SUM(COALESCE(net_pnl, pnl, 0)), 0) AS s')
            ->pluck('s', 'broker_account_id');

        $next = Carbon::now(self::TZ)->startOfMonth()->addMonth()->locale('es')->isoFormat('D [de] MMMM');
        $out = [];
        foreach ($accounts as $a) {
            $maxLoss = (float) $a->max_monthly_loss_pct;
            $maxOpen = max(1, (int) $a->max_open_trades);
            $baseDate = $a->month_start_at ? Carbon::parse($a->month_start_at)->toDateString() : null;
            $base = $baseDate === $month && (float) $a->month_start_balance > 0 ? (float) $a->month_start_balance : null;
            $pct = $base ? (float) ($pnl[$a->id] ?? 0) / $base * 100 : null;
            $openN = (int) ($open[$a->id] ?? 0);

            [$state, $note] = match (true) {
                $pct !== null && $pct <= -$maxLoss => ['blocked', "Pérdida del mes alcanzada: sin entradas hasta el {$next}."],
                $openN >= $maxOpen                => ['full', 'Máximo de trades abiertos: abre de nuevo al cerrarse uno.'],
                default                           => ['ok', $base ? '' : 'Saldo inicial del mes pendiente: se toma en el próximo ciclo del motor.'],
            };
            $out[$a->id] = [
                'pct'      => $pct,
                'pct_text' => $pct === null ? '—' : (($pct > 0 ? '+' : ($pct < 0 ? '−' : '')) . number_format(abs($pct), 2, ',', '.') . ' %'),
                'base'     => $base,
                'max_loss' => $maxLoss,
                'loss_use' => $pct !== null && $pct < 0 ? min(100, -$pct / $maxLoss * 100) : 0,
                'open'     => $openN,
                'max_open' => $maxOpen,
                'open_use' => min(100, $openN / $maxOpen * 100),
                'state'    => $state,
                'note'     => $note,
            ];
        }

        return $out;
    }
}

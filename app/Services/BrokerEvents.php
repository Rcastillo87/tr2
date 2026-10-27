<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Convierte los eventos que registra el motor (tabla broker_events) en avisos para el dueño de cada cuenta.
 * Corre cada minuto (php artisan broker:events) desde el cron: no depende de Horizon.
 * Varios procesos a la vez no duplican avisos (FOR UPDATE SKIP LOCKED); cada evento se procesa una sola vez.
 */
final class BrokerEvents
{
    public const URL = '/trading';
    private const THROTTLE = 'broker_events:throttle:';

    public function __construct(private readonly SystemAlerts $alerts)
    {
    }

    /** @return array{processed:int, notified:int, skipped:int} */
    public function drain(int $limit = 200): array
    {
        $stats = ['processed' => 0, 'notified' => 0, 'skipped' => 0];
        DB::transaction(function () use ($limit, &$stats) {
            $rows = DB::select(
                'SELECT e.id, e.broker_account_id, e.trade_id, e.event, e.data::text AS data, a.user_id, a.label
                   FROM broker_events e
                   LEFT JOIN broker_accounts a ON a.id = e.broker_account_id
                  WHERE e.processed_at IS NULL
                  ORDER BY e.id
                  LIMIT ?
                  FOR UPDATE OF e SKIP LOCKED', [$limit]);
            foreach ($rows as $row) {
                $this->dispatch($row) ? $stats['notified']++ : $stats['skipped']++;
            }
            if ($rows) {
                DB::table('broker_events')->whereIn('id', array_map(fn ($r) => $r->id, $rows))
                    ->update(['processed_at' => now()]);
            }
            $stats['processed'] = count($rows);
        });

        return $stats;
    }

    /** Elimina eventos más viejos que la retención (rastro forense: 90 días por defecto). */
    public function prune(): int
    {
        $days = (int) config('trading.broker_events.retention_days', 90);

        return DB::table('broker_events')->where('created_at', '<', now()->subDays($days))->delete();
    }

    /** Aviso de "cuenta reactivada" (cierra el incidente abierto por el circuit breaker, si lo hay). */
    public function accountReactivated(int $userId, int $accountId, string $label): void
    {
        $m = BrokerEventMessages::reactivated($label);
        $this->alerts->resolveUserIncident($userId, "account_paused:{$accountId}", $m['title'], $m['body'], self::URL);
    }

    private function dispatch(object $row): bool
    {
        if (! $row->user_id) {   // cuenta eliminada: nada que avisar
            return false;
        }
        try {
            $data = json_decode((string) $row->data, true) ?: [];
            $label = (string) ($row->label ?: "Cuenta #{$row->broker_account_id}");
            $msg = BrokerEventMessages::for((string) $row->event, $data, $label, (int) $row->broker_account_id,
                $row->trade_id !== null ? (int) $row->trade_id : null);
            if ($msg === null) {
                Log::warning("[BROKER-EVENTS] evento sin aviso definido: {$row->event} (#{$row->id})");

                return false;
            }
            $user = (int) $row->user_id;

            return match ($msg['mode']) {
                'open'     => $this->alerts->openUserIncident($user, $msg['key'], $msg['level'], $msg['title'], $msg['body'], self::URL),
                'resolve'  => $this->alerts->resolveUserIncident($user, $msg['key'], $msg['title'], $msg['body'], self::URL),
                'throttle' => $this->firstInWindow($msg['key']) && $this->send($user, $msg),
                default    => $this->send($user, $msg),
            };
        } catch (Throwable $e) {
            Log::error("[BROKER-EVENTS] evento #{$row->id} ({$row->event}): " . $e->getMessage());

            return false;
        }
    }

    private function send(int $user, array $msg): bool
    {
        $this->alerts->notifyUser($user, $msg['level'], $msg['title'], $msg['body'], self::URL);

        return true;
    }

    /** Mismo problema repetido: un aviso por clave cada N minutos. Sin caché, mejor avisar que callar. */
    private function firstInWindow(string $key): bool
    {
        try {
            return Cache::add(self::THROTTLE . $key, now()->toIso8601String(),
                now()->addMinutes((int) config('trading.broker_events.throttle_minutes', 60)));
        } catch (Throwable) {
            return true;
        }
    }
}

<?php

namespace App\Services;

use App\Models\User;
use App\Notifications\SystemAlert;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Notification;
use Throwable;

/**
 * Avisos del sistema para admin y consultor (tabla notifications).
 * Sin spam: un incidente abre UN aviso y al cerrarse UNO más (recuperado). Retención: 30 días.
 * Nunca lanza: un fallo al avisar no puede tumbar al vigilante ni a la validación.
 */
class SystemAlerts
{
    public const RETENTION_DAYS = 30;
    /** Avisos del sistema (collector, validación, reparación, búsquedas): solo el admin. Los de broker van al dueño. */
    public const RECIPIENT_ROLES = ['admin'];
    private const INCIDENT = 'alert:incident:';

    public function notify(string $level, string $category, string $title, string $body = '',
                           ?string $url = null, ?string $incident = null): void
    {
        Log::log(match ($level) { 'error' => 'error', 'warning' => 'warning', default => 'info' },
            "[ALERTA] {$title}" . ($body !== '' ? " — {$body}" : ''));
        try {
            $users = User::whereIn('role', self::RECIPIENT_ROLES)->get();
            if ($users->isNotEmpty()) {
                Notification::send($users, new SystemAlert($level, $category, $title, $body, $url, $incident));
            }
        } catch (Throwable $e) {
            Log::error('[ALERTA] no se pudo guardar el aviso: ' . $e->getMessage());
        }
    }

    /** Aviso de broker para el dueño de la cuenta (cada usuario ve solo los suyos). */
    public function notifyUser(int $userId, string $level, string $title, string $body = '', ?string $url = null,
                               ?string $incident = null): void
    {
        Log::log(match ($level) { 'error' => 'error', 'warning' => 'warning', default => 'info' },
            "[ALERTA u{$userId}] {$title}" . ($body !== '' ? " — {$body}" : ''));
        try {
            User::find($userId)?->notify(new SystemAlert($level, 'broker', $title, $body, $url, $incident));
        } catch (Throwable $e) {
            Log::error('[ALERTA] no se pudo guardar el aviso: ' . $e->getMessage());
        }
    }

    /** Incidente de broker de un usuario: un aviso al abrir y uno al cerrar, sin spam. */
    public function openUserIncident(int $userId, string $key, string $level, string $title, string $body = '',
                                     ?string $url = null): bool
    {
        try {
            $added = Cache::add(self::INCIDENT . "u{$userId}:{$key}", ['since' => now()->toIso8601String(), 'title' => $title],
                now()->addDays(self::RETENTION_DAYS));
        } catch (Throwable) {
            $added = true;
        }
        if ($added) {
            $this->notifyUser($userId, $level, $title, $body, $url, $key);
        }

        return $added;
    }

    public function resolveUserIncident(int $userId, string $key, string $title, string $body = '', ?string $url = null): bool
    {
        try {
            $open = Cache::pull(self::INCIDENT . "u{$userId}:{$key}");
        } catch (Throwable) {
            return false;
        }
        if (! is_array($open)) {
            return false;
        }
        $this->notifyUser($userId, 'success', $title, trim($body . ' Duró ' . self::duration(Carbon::parse($open['since'])) . '.'), $url, $key);

        return true;
    }

    /** Abre el incidente y avisa solo si no estaba abierto. Devuelve true si avisó. */
    public function openIncident(string $key, string $level, string $category, string $title, string $body = '',
                                 ?string $url = null): bool
    {
        try {
            $added = Cache::add(self::INCIDENT . $key, ['since' => now()->toIso8601String(), 'title' => $title],
                now()->addDays(self::RETENTION_DAYS));
        } catch (Throwable $e) {
            Log::error('[ALERTA] caché no disponible: ' . $e->getMessage());
            $added = true;   // sin caché no hay deduplicación: mejor avisar que callar
        }
        if ($added) {
            $this->notify($level, $category, $title, $body, $url, $key);
        }

        return $added;
    }

    /** Cierra el incidente y avisa "recuperado" solo si estaba abierto. */
    public function resolveIncident(string $key, string $category, string $title, string $body = '',
                                    ?string $url = null): bool
    {
        try {
            $open = Cache::pull(self::INCIDENT . $key);
        } catch (Throwable) {
            return false;
        }
        if (! is_array($open)) {
            return false;
        }
        $took = self::duration(Carbon::parse($open['since']));
        $this->notify('success', $category, $title, trim($body . " Duró {$took}."), $url, $key);

        return true;
    }

    public function isOpen(string $key): bool
    {
        return Cache::has(self::INCIDENT . $key);
    }

    /** Resultado de una validación del collector (programada o manual). */
    public function validationResult(array $data): void
    {
        $s = $data['summary'] ?? [];
        $bad = (int) ($s['series'] ?? 0) - (int) ($s['ok'] ?? 0);
        $r = $data['repair'] ?? null;
        if ($r && empty($r['dry_run']) && ($r['recent_written'] + $r['days_written'] + $r['bybit_gaps_new'] + $r['errors']) > 0) {
            $this->notify($r['errors'] ? 'warning' : 'info', 'repair', 'Reparación automática del collector',
                sprintf('%d serie(s) · %d velas recientes corregidas · %d día(s) revisados (+%d velas) · pendientes %d día(s)'
                    . ' · %d día(s) sin datos en Bybit · errores %d · antes %d/%d OK, ahora %d/%d OK',
                    count($r['series']), $r['recent_written'], $r['days_fixed'], $r['days_written'], $r['pending_days'],
                    $r['bybit_gaps_new'], $r['errors'], $r['before']['ok'] ?? 0, $r['before']['series'] ?? 0,
                    $s['ok'] ?? 0, $s['series'] ?? 0), '/collector');
        }
        if ($bad > 0) {
            $this->openIncident('validation_failed', 'warning', 'validation',
                "Validación del collector: {$bad} serie(s) con fallas",
                sprintf('huecos %d · distintas a Bybit %d · faltan %d · sobran %d · desactualizadas %d · errores %d',
                    $s['missing_hist'] ?? 0, $s['diff_recent'] ?? 0, $s['missing_recent'] ?? 0,
                    $s['extra_recent'] ?? 0, $s['stale'] ?? 0, $s['errors'] ?? 0), '/collector');
        } else {
            $this->resolveIncident('validation_failed', 'validation', 'Validación del collector: todo OK',
                ($s['series'] ?? 0) . ' series idénticas a Bybit y sin huecos.', '/collector');
        }
    }

    public function prune(): int
    {
        return DB::table('notifications')->where('created_at', '<', now()->subDays(self::RETENTION_DAYS))->delete();
    }

    public static function duration(Carbon $since): string
    {
        $m = (int) round(abs(now()->getTimestamp() - $since->getTimestamp()) / 60);

        return match (true) {
            $m < 1    => 'menos de 1 min',
            $m < 120  => "{$m} min",
            $m < 2880 => round($m / 60, 1) . ' h',
            default   => round($m / 1440, 1) . ' días',
        };
    }
}

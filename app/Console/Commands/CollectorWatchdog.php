<?php

namespace App\Console\Commands;

use App\Jobs\CollectOhlcvDataJob;
use App\Services\SystemAlerts;
use Illuminate\Console\Command;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use Throwable;

/**
 * Vigilante del collector. Corre cada 5 min desde el scheduler (cron de root): NO depende de Horizon.
 *  1. Motor: GET /health. Tras 2 fallas seguidas avisa; tras `fails_to_restart` y si está habilitado reinicia
 *     trading2-engine (una vez por enfriamiento).
 *  2. Datos: atraso real de cada serie activa en ohlcv_data y edad de la última corrida hecha por la cola.
 *     Si algo está atrasado corre el collector directo en el motor (sin cola) y vuelve a medir.
 *  3. Cola: si Horizon no corre el collector avisa y, si está habilitado, reinicia trading2-horizon.
 * Avisos sin spam: uno al abrir cada incidente y uno al cerrarlo.
 */
class CollectorWatchdog extends Command
{
    protected $signature = 'collector:watchdog {--dry : solo diagnostica: no recupera ni reinicia}';

    protected $description = 'Vigila el collector y lo recupera sin depender de Horizon';

    private const ENGINE_FAILS = 'watchdog:engine_fails';
    private const ENGINE_STUCK = 'watchdog:engine_stuck';
    private const QUEUE_FAILS = 'watchdog:queue_fails';
    private const STATE = 'watchdog:last';

    private SystemAlerts $alerts;
    private array $cfg;

    public function handle(SystemAlerts $alerts): int
    {
        $this->alerts = $alerts;
        $this->cfg = (array) config('trading.watchdog');
        $dry = (bool) $this->option('dry');

        if (! $this->engineHealthy()) {
            $this->engineFailed('no responde a /health', $dry, self::ENGINE_FAILS, 'engine_down');
            $this->remember('motor sin respuesta');

            return self::FAILURE;
        }
        $this->engineOk();

        $stale = $this->staleSeries();
        $runAge = $this->lastRunAge();
        $queueStalled = $runAge > (int) $this->cfg['queue_stale_s'];
        $this->line(sprintf('motor OK · series atrasadas %d · última corrida por la cola: %s',
            count($stale), $runAge === PHP_INT_MAX ? 'nunca' : "hace {$runAge} s"));

        if (! $queueStalled) {
            Cache::forget(self::QUEUE_FAILS);
            $this->alerts->resolveIncident('queue_stalled', 'collector', 'La cola volvió a correr el collector',
                'Horizon procesa de nuevo el collector cada minuto.', '/collector');
        }
        if (! $stale && ! $queueStalled) {
            $this->engineUnstuck();
            $this->alerts->resolveIncident('collector_stalled', 'collector', 'Collector recuperado',
                'Todas las series están al día.', '/collector');
            $this->remember('ok');

            return self::SUCCESS;
        }
        if ($dry) {
            $this->warn('modo --dry: no se recupera nada');
            if ($stale) {
                $this->line('  ' . implode("\n  ", $stale));
            }

            return self::SUCCESS;
        }

        $run = $this->runCollectorDirect();
        $this->line('corrida directa: ' . ($run['status'] ?? '?') . (isset($run['error']) ? " ({$run['error']})" : '')
            . (isset($run['duration_s']) ? " · {$run['duration_s']} s" : ''));
        $staleAfter = $stale ? $this->staleSeries() : [];

        if ($staleAfter) {
            if (($run['status'] ?? '') === 'busy') {
                // el motor dice "ocupado" pero los datos no avanzan: su collector está trabado
                $this->engineFailed('su collector sigue ocupado y los datos no avanzan', false, self::ENGINE_STUCK,
                    'engine_stuck');
            }
            $this->alerts->openIncident('collector_stalled', 'error', 'collector', 'Collector detenido',
                count($staleAfter) . ' serie(s) sin actualizar: ' . implode(', ', array_slice($staleAfter, 0, 8))
                . (count($staleAfter) > 8 ? '…' : '') . '. El vigilante lo reintenta cada 5 min'
                . (isset($run['error']) ? " (motor: {$run['error']})" : '') . '.', '/collector');
        } elseif ($stale) {
            $this->engineUnstuck();
            Log::info('[WATCHDOG] series atrasadas recuperadas con una corrida directa', $stale);
            $this->alerts->resolveIncident('collector_stalled', 'collector', 'Collector recuperado',
                'Todas las series están al día.', '/collector');
        }
        if ($queueStalled) {
            $this->queueStalled($runAge);
        }
        $this->remember($staleAfter ? 'series atrasadas' : ($queueStalled ? 'cola detenida (datos al día)' : 'recuperado'));

        return self::SUCCESS;
    }

    // ── motor ────────────────────────────────────────────────────────────────

    private function engineHealthy(): bool
    {
        try {
            return Http::timeout(8)->get(config('trading.python_engine_url') . '/health')->successful();
        } catch (Throwable) {
            return false;
        }
    }

    private function engineFailed(string $why, bool $dry, string $counter, string $incident): void
    {
        $fails = $this->bump($counter);
        $this->warn("motor: {$why} ({$fails} revisión(es) seguidas)");
        if ($fails >= 2) {
            $this->alerts->openIncident($incident, 'error', 'collector',
                $incident === 'engine_down' ? 'El motor no responde' : 'El collector del motor está trabado',
                "Motor: {$why}. Sin el motor no se actualizan velas ni corren los ticks de paper y real."
                . ($this->cfg['restart_engine'] ? ' El vigilante lo reiniciará si sigue así.' : ''), '/collector');
        }
        if ($dry || $fails < (int) $this->cfg['fails_to_restart'] || ! $this->cfg['restart_engine']
            || ! $this->canRestart('engine')) {
            return;
        }
        $ok = $this->restart('trading2-engine');
        Cache::forget($counter);
        $this->alerts->notify($ok ? 'warning' : 'error', 'collector',
            $ok ? 'Motor reiniciado automáticamente' : 'No se pudo reiniciar el motor',
            "Llevaba {$fails} revisiones seguidas con fallas ({$why})."
            . ($ok ? ' Paper y real se pausan unos segundos durante el reinicio.' : ' Revisa: systemctl status trading2-engine'),
            '/collector');
    }

    private function engineOk(): void
    {
        Cache::forget(self::ENGINE_FAILS);
        $this->alerts->resolveIncident('engine_down', 'collector', 'El motor volvió a responder', '', '/collector');
    }

    private function engineUnstuck(): void
    {
        Cache::forget(self::ENGINE_STUCK);
        $this->alerts->resolveIncident('engine_stuck', 'collector', 'El collector del motor volvió a avanzar', '',
            '/collector');
    }

    private function runCollectorDirect(): array
    {
        try {
            $r = Http::withHeaders(['X-Internal-API-Key' => config('trading.python_internal_api_key')])
                ->timeout(75)->post(config('trading.python_engine_url') . '/v1/collector/run');

            return $r->successful() ? (array) $r->json() : ['status' => 'error', 'error' => 'HTTP ' . $r->status()];
        } catch (Throwable $e) {
            return ['status' => 'error', 'error' => mb_substr($e->getMessage(), 0, 150)];
        }
    }

    // ── cola (Horizon) ───────────────────────────────────────────────────────

    private function lastRunAge(): int
    {
        $at = Cache::get(CollectOhlcvDataJob::LAST_RUN_KEY)['at'] ?? null;

        return $at ? max(0, now()->getTimestamp() - Carbon::parse($at)->getTimestamp()) : PHP_INT_MAX;
    }

    private function queueStalled(int $age): void
    {
        $fails = $this->bump(self::QUEUE_FAILS);
        $when = $age === PHP_INT_MAX ? 'nunca' : 'hace ' . intdiv($age, 60) . ' min';
        $this->alerts->openIncident('queue_stalled', 'warning', 'collector', 'La cola no está corriendo el collector',
            "Última corrida por la cola (Horizon): {$when}. Mientras tanto el vigilante mantiene los datos al día "
            . 'cada 5 min. Paper y real también dependen de la cola.', '/collector');
        if ($fails < (int) $this->cfg['fails_to_restart'] || ! $this->cfg['restart_horizon']
            || ! $this->canRestart('horizon')) {
            return;
        }
        $search = DB::table('param_search_runs')->where('status', 'running')->value('id');
        $ok = $this->restart('trading2-horizon');
        Cache::forget(self::QUEUE_FAILS);
        $this->alerts->notify($ok ? 'warning' : 'error', 'collector',
            $ok ? 'Horizon reiniciado automáticamente' : 'No se pudo reiniciar Horizon',
            "La cola llevaba {$fails} revisiones seguidas sin correr el collector."
            . ($search && $ok ? " La búsqueda #{$search} se interrumpió: vuelve a lanzarla." : '')
            . ($ok ? '' : ' Revisa: systemctl status trading2-horizon'), '/collector');
    }

    // ── datos ────────────────────────────────────────────────────────────────

    /** Series activas cuya última vela guardada tiene más atraso que 1 intervalo + margen. */
    private function staleSeries(): array
    {
        $grace = (int) $this->cfg['series_grace_s'];
        $rows = DB::select(<<<'SQL'
            SELECT c.symbol, c.interval, extract(epoch FROM now() - l.last)::bigint AS lag_s
            FROM collector_configs c
            LEFT JOIN LATERAL (
                SELECT o.time AS last FROM ohlcv_data o
                WHERE o.broker = c.broker AND o.symbol = c.symbol AND o.interval = c.interval
                ORDER BY o.time DESC LIMIT 1
            ) l ON true
            WHERE c.active AND c.broker = 'bybit'
            ORDER BY c.symbol, c.interval
            SQL);
        $out = [];
        foreach ($rows as $r) {
            if ($r->lag_s === null || (int) $r->lag_s > self::stepSeconds((string) $r->interval) + $grace) {
                $out[] = "{$r->symbol} {$r->interval} ("
                    . ($r->lag_s === null ? 'sin datos' : SystemAlerts::duration(now()->subSeconds((int) $r->lag_s))) . ')';
            }
        }

        return $out;
    }

    public static function stepSeconds(string $interval): int
    {
        return match (true) {
            ctype_digit($interval) => (int) $interval * 60,
            $interval === 'D'      => 86400,
            $interval === 'W'      => 604800,
            default                => 2678400,
        };
    }

    // ── utilidades ───────────────────────────────────────────────────────────

    private function bump(string $key): int
    {
        Cache::add($key, 0, now()->addHours(6));

        return (int) Cache::increment($key);
    }

    /** Un reinicio por servicio por enfriamiento (evita bucles de reinicio). */
    private function canRestart(string $what): bool
    {
        return Cache::add("watchdog:restarted:{$what}", now()->toIso8601String(),
            now()->addSeconds((int) $this->cfg['restart_cooldown_s']));
    }

    private function restart(string $unit): bool
    {
        $r = Process::timeout(90)->run(['systemctl', 'restart', $unit]);
        Log::warning("[WATCHDOG] systemctl restart {$unit}: " . ($r->successful() ? 'ok' : trim($r->errorOutput())));

        return $r->successful();
    }

    private function remember(string $state): void
    {
        Cache::put(self::STATE, ['at' => now()->toIso8601String(), 'state' => $state], now()->addDay());
    }
}

<?php

namespace App\Jobs;

use App\Models\BrokerAccount;
use App\Models\RealTrade;
use App\Services\SystemAlerts;
use App\Support\ReconcileHealth;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

class RealTradingReconcileJob implements ShouldQueue
{
    use Queueable;

    public int $tries   = 1;
    // R-08 (p68): HTTP 75 s < trabajo 85 s < retry_after 90 s de la conexión redis. Antes 120 s: un trabajo de más de
    // 90 s volvía a la cola mientras seguía corriendo y la copia terminaba como fallida (MaxAttemptsExceeded).
    public int $timeout = 85;

    /** C5-07 (p100): hora del primer fallo de la racha actual de conciliaciones con fallos. */
    public const FAILING_SINCE_KEY = 'real_reconcile_failing_since';

    public function handle(): void
    {
        $url = config('trading.python_engine_url') . '/v1/real/reconcile';

        // Activas con suscripciones, y cualquier cuenta con trades por reconciliar (también pausada): incluye los
        // 'pending_open' interrumpidos, que solo se recuperan aquí
        $accounts = BrokerAccount::query()
            ->where(fn ($q) => $q
                ->where(fn ($a) => $a->where('status', 'active')
                    ->whereHas('subscriptions', fn ($s) => $s->where('status', 'active')))
                ->orWhereExists(fn ($e) => $e->selectRaw('1')->from('real_trades')
                    ->whereColumn('real_trades.broker_account_id', 'broker_accounts.id')
                    ->whereIn('real_trades.status', RealTrade::RECONCILE_STATUSES)))
            ->with(['subscriptions' => fn ($q) => $q->where('status', 'active')
                ->with('paperStrategyConfig')])
            ->get();

        if ($accounts->isEmpty()) {
            return;
        }

        $payload = [
            'accounts' => $accounts->map(function ($account) {
                return [
                    'id'           => $account->id,
                    'broker'       => $account->broker,
                    'account_type' => $account->account_type,
                    'api_key'      => $account->api_key,
                    'api_secret'   => $account->api_secret,
                    'subscriptions' => $account->subscriptions->map(function ($sub) {
                        return [
                            'subscription_id'          => $sub->id,
                            'user_id'                  => $sub->user_id,
                            'broker_account_id'        => $sub->broker_account_id,
                            'paper_strategy_config_id' => $sub->paper_strategy_config_id,
                            'strategy'                 => $sub->strategy,
                            'symbol'                   => $sub->symbol,
                            'interval'                 => $sub->interval,
                            'strategy_class'           => $sub->paperStrategyConfig?->strategy_class,
                            'config_params'            => $sub->paperStrategyConfig?->params,
                        ];
                    })->values()->toArray(),
                ];
            })->values()->toArray(),
        ];

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(75)->post($url, $payload);

            if (!$response->successful()) {
                Log::warning('RealTradingReconcileJob: respuesta no exitosa', [
                    'status' => $response->status(),
                    'body'   => \App\Support\SafeLogBody::of($response->body()),
                ]);
                $this->track(true, ["el motor respondió HTTP {$response->status()}"]);
                return;
            }

            $data = $response->json();
            $results = $data['results'] ?? [];
            // C5-07: los errores del motor (Bybit falló, cuenta ocupada, sin config…) ya no quedan escondidos tras el 200
            $errors = ReconcileHealth::errors(is_array($data) ? $data : null);
            foreach ($errors as $err) {
                Log::warning("Reconciliacion: sin verificar — {$err}");
            }
            $this->track($errors !== [], $errors);

            if (!empty($results['reconciled'])) {
                foreach ($results['reconciled'] as $r) {
                    Log::warning("Reconciliacion: trade #{$r['trade_id']} {$r['symbol']} cerrado — {$r['reason']}");
                }
            }

            if (!empty($results['orphaned'])) {
                foreach ($results['orphaned'] as $r) {
                    Log::error("Reconciliacion: posicion huerfana en Bybit — {$r['symbol']} size={$r['size']} side={$r['side']}");
                }
            }

            $ok        = count($results['ok'] ?? []);
            $reconciled = count($results['reconciled'] ?? []);
            $orphaned   = count($results['orphaned'] ?? []);

            if ($reconciled > 0 || $orphaned > 0) {
                Log::info("Reconciliacion completada: {$ok} ok, {$reconciled} reconciliados, {$orphaned} huerfanos");
            }

        } catch (\Throwable $e) {
            Log::error('RealTradingReconcileJob: error — ' . $e->getMessage());
            $this->track(true, ['la conciliación no terminó: ' . mb_substr($e->getMessage(), 0, 200)]);
        }
    }

    /**
     * C5-07 (p100): con fallos más de ReconcileHealth::ALERT_AFTER_MIN minutos seguidos, aviso al admin (una vez por
     * racha); al volver a completarse, aviso de normalizado. Un problema de la caché o de los avisos nunca tumba el job.
     */
    private function track(bool $failed, array $errors): void
    {
        try {
            $d = ReconcileHealth::decide(Cache::get(self::FAILING_SINCE_KEY), $failed, now());
            $d['since'] === null ? Cache::forget(self::FAILING_SINCE_KEY)
                : Cache::put(self::FAILING_SINCE_KEY, $d['since'], now()->addDay());
            $alerts = app(SystemAlerts::class);
            if ($d['action'] === 'open') {
                $alerts->openIncident('real_reconcile', 'error', 'broker', 'Conciliación de Real con fallos',
                    'Hace más de ' . ReconcileHealth::ALERT_AFTER_MIN . ' min la conciliación con Bybit no se completa: '
                    . implode('; ', array_slice($errors, 0, 3)) . (count($errors) > 3 ? ' (y ' . (count($errors) - 3) . ' más)' : '')
                    . '. Las posiciones siguen con su SL/TP en Bybit; revisa el log del motor.', '/trading');
            } elseif ($d['action'] === 'resolve') {
                $alerts->resolveIncident('real_reconcile', 'broker', 'Conciliación de Real normalizada',
                    'La conciliación con Bybit vuelve a completarse sin fallos.', '/trading');
            }
        } catch (Throwable $e) {
            Log::error('RealTradingReconcileJob: no se pudo registrar el estado de la conciliación — ' . $e->getMessage());
        }
    }
}

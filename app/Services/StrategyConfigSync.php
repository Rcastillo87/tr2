<?php

declare(strict_types=1);

namespace App\Services;

use App\Helpers\RatingHelper;
use App\Models\Backtest;
use App\Models\BrokerAccount;
use App\Models\PaperStrategyConfig;
use App\Models\RealStrategySubscription;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * Única vía de escritura de paper_strategy_configs.
 *
 * Modelo: 1 backtest -> N símbolos -> N configs (UNIQUE backtest_id, symbol).
 * Paper y Real leen la misma fila, así que sincronizar la config equivale a
 * sincronizar ambos. Las posiciones abiertas se gestionan con su
 * config_snapshot (no con la config viva), por eso un cambio aquí solo
 * afecta a entradas nuevas.
 */
final class StrategyConfigSync
{
    public const SOURCE_IMPLEMENT     = 'implement';
    public const SOURCE_BACKTEST_SAVE = 'backtest_save';
    public const SOURCE_STOP          = 'stop';

    /** Claves que describen la ejecución del backtest, no la estrategia. */
    private const RUN_ONLY_KEYS = [
        'symbol', 'interval', 'start_date', 'end_date',
        'walk_forward', 'n_windows', 'monthly_breakdown',
        'use_max_duration', 'use_trailing', // legacy: ningún motor las lee
    ];

    private const INTERVAL_LABELS = [
        '1' => '1m', '5' => '5m', '15' => '15m', '60' => 'H1',
        '120' => 'H2', '240' => 'H4', 'D' => 'D1',
    ];

    // ───────────────────────── Canonicalización e integridad ─────────────────────────

    public static function canonicalParams(array $runParams): array
    {
        return self::ksortRecursive(array_diff_key($runParams, array_flip(self::RUN_ONLY_KEYS)));
    }

    /**
     * HMAC del payload que viaja al navegador y vuelve en "Guardar".
     * Sin flags de precisión a propósito: el round-trip json_encode/json_decode
     * del navegador convierte 1.0 en 1, y ambos deben producir la misma firma.
     */
    public static function sign(array $data): string
    {
        $json = json_encode(self::ksortRecursive($data), JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);

        return hash_hmac('sha256', $json, (string) config('app.key'));
    }

    public static function verify(array $data, mixed $signature): bool
    {
        return is_string($signature) && hash_equals(self::sign($data), $signature);
    }

    /** Hash de identidad de un backtest: misma estrategia + símbolos + rango + parámetros. */
    public static function backtestHash(int $strategyId, array $symbols, string $interval, int $months, array $configParams): string
    {
        sort($symbols);
        $json = json_encode(
            [$strategyId, $symbols, $interval, $months, self::canonicalParams($configParams)],
            JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
        );

        return md5($json); // backtests.hash es varchar(32)
    }

    // ───────────────────────── Sincronización ─────────────────────────

    /**
     * Crea/actualiza las configs de un backtest (una por símbolo).
     *
     * @param bool|null $activate true = activar todas (Implementar en Paper);
     *                            null = conservar el estado de cada config (auto-sync al guardar).
     * @return array{created: string[], updated: array<string, string[]>, unchanged: string[], deactivated: string[]}
     */
    public function syncFromBacktest(Backtest $backtest, string $source, ?bool $activate = null, ?int $userId = null): array
    {
        $backtest->loadMissing('strategy');

        $symbols = array_values(array_unique(array_map('strval', (array) $backtest->symbols)));
        if ($symbols === []) {
            throw new \DomainException("Backtest #{$backtest->id} no tiene símbolos.");
        }

        $runParams   = (array) $backtest->config_params;
        $params      = self::canonicalParams($runParams);
        $metricAttrs = $this->metricAttributes((array) ($backtest->metrics ?? []), $runParams, (int) $backtest->months);
        $summary     = ['created' => [], 'updated' => [], 'unchanged' => [], 'deactivated' => []];

        DB::transaction(function () use ($backtest, $symbols, $params, $metricAttrs, $source, $activate, $userId, &$summary) {
            $existing = PaperStrategyConfig::where('backtest_id', $backtest->id)
                ->lockForUpdate()
                ->get()
                ->keyBy('symbol');

            // Un símbolo nuevo en un backtest que ya opera entra activo (opción A acordada).
            $backtestIsLive = $existing->contains(fn (PaperStrategyConfig $c) => $c->active);

            // Cuentas donde el backtest ya opera en Real: la moneda nueva entra activa ahí también.
            $liveAccounts = $existing->isEmpty() ? [] : RealStrategySubscription::query()
                ->whereIn('paper_strategy_config_id', $existing->pluck('id'))
                ->where('status', 'active')
                ->distinct()
                ->pluck('broker_account_id')
                ->all();

            foreach ($symbols as $symbol) {
                $displayName = $this->displayName($backtest, $symbol);
                $config      = $existing->get($symbol);

                if ($config === null) {
                    $config = PaperStrategyConfig::create(array_merge($metricAttrs, [
                        'backtest_id'    => $backtest->id,
                        'display_name'   => $displayName,
                        'strategy_class' => 'DynamicStrategy',
                        'symbol'         => $symbol,
                        'interval'       => (string) $backtest->interval,
                        'params'         => $params,
                        'active'         => $activate ?? $backtestIsLive,
                    ]));
                    $this->audit($config, 'created', null, $params, array_keys($params), $source, $userId);
                    $this->ensureSubscriptions($config, $liveAccounts);
                    $summary['created'][] = $symbol;
                    continue;
                }

                $oldParams = self::canonicalParams((array) $config->params);
                $changed   = self::diffKeys($oldParams, $params);
                if ((string) $config->interval !== (string) $backtest->interval) {
                    $changed[] = 'interval';
                }
                $oldName = $config->display_name;

                $config->fill(array_merge($metricAttrs, [
                    'display_name' => $displayName,
                    'interval'     => (string) $backtest->interval,
                    'params'       => $params,
                ]));
                if ($activate !== null) {
                    $config->active = $activate;
                }
                $config->save();

                if ($oldName !== $displayName) {
                    $this->renameReferences($config, $oldName);
                }

                if ($changed !== []) {
                    $this->audit($config, 'updated', $oldParams, $params, $changed, $source, $userId);
                    $summary['updated'][$symbol] = $changed;
                } else {
                    $summary['unchanged'][] = $symbol;
                }
            }

            // Símbolos que el backtest ya no incluye: se desactivan, nunca se borran
            // (pueden tener historial de trades y posiciones abiertas que monitorear).
            foreach ($existing as $symbol => $config) {
                if (in_array((string) $symbol, $symbols, true) || ! $config->active) {
                    continue;
                }
                $config->update(['active' => false]);
                $this->audit($config, 'deactivated', (array) $config->params, null, [], $source, $userId);
                $summary['deactivated'][] = (string) $symbol;
            }
        });

        Log::info('[CONFIG-SYNC] backtest #' . $backtest->id, ['source' => $source] + $summary);

        return $summary;
    }

    /** Detiene un backtest en Paper y, por consiguiente, en Real (real_trader filtra psc.active). */
    public function deactivateBacktest(Backtest $backtest, ?int $userId = null): int
    {
        return DB::transaction(function () use ($backtest, $userId) {
            $configs = PaperStrategyConfig::where('backtest_id', $backtest->id)
                ->where('active', true)
                ->lockForUpdate()
                ->get();

            foreach ($configs as $config) {
                $config->update(['active' => false]);
                $this->audit($config, 'deactivated', (array) $config->params, null, [], self::SOURCE_STOP, $userId);
            }

            return $configs->count();
        });
    }

    /**
     * Crea (si no existe) una suscripción por cada cuenta broker activa.
     * Activa solo en las cuentas listadas en $liveAccounts (donde el backtest ya
     * opera en Real); en el resto queda PAUSADA hasta acción explícita.
     *
     * @param int[] $liveAccounts
     */
    public function ensureSubscriptions(PaperStrategyConfig $config, array $liveAccounts = []): void
    {
        BrokerAccount::where('status', 'active')->get()->each(function (BrokerAccount $account) use ($config, $liveAccounts) {
            RealStrategySubscription::firstOrCreate(
                ['broker_account_id' => $account->id, 'paper_strategy_config_id' => $config->id],
                [
                    'user_id'  => $account->user_id,
                    'strategy' => $config->display_name,
                    'symbol'   => $config->symbol,
                    'interval' => $config->interval,
                    'status'   => in_array($account->id, $liveAccounts, false) ? 'active' : 'paused',
                ]
            );
        });
    }

    public function ensurePausedSubscriptions(PaperStrategyConfig $config): void
    {
        $this->ensureSubscriptions($config, []);
    }

    // ───────────────────────── Internos ─────────────────────────

    private function displayName(Backtest $backtest, string $symbol): string
    {
        $interval = (string) $backtest->interval;
        $label    = self::INTERVAL_LABELS[$interval] ?? $interval;
        $name     = $backtest->strategy?->name ?? "Backtest #{$backtest->id}";

        return "{$name} — {$symbol} {$label}";
    }

    /**
     * Mantiene coherentes las referencias por texto mientras paper_trader siga
     * identificando trades por display_name (se elimina en la fase 0.6).
     */
    private function renameReferences(PaperStrategyConfig $config, string $oldName): void
    {
        RealStrategySubscription::where('paper_strategy_config_id', $config->id)
            ->update(['strategy' => $config->display_name, 'interval' => $config->interval]);

        DB::table('paper_trades')
            ->where('status', 'open')
            ->where(fn ($q) => $q->where('paper_strategy_config_id', $config->id)->orWhere('strategy', $oldName))
            ->update(['strategy' => $config->display_name, 'paper_strategy_config_id' => $config->id]);
    }

    private function audit(PaperStrategyConfig $config, string $action, ?array $old, ?array $new,
                           array $changedKeys, string $source, ?int $userId): void
    {
        DB::table('strategy_config_changes')->insert([
            'paper_strategy_config_id' => $config->id,
            'backtest_id'              => $config->backtest_id,
            'symbol'                   => $config->symbol,
            'action'                   => $action,
            'old_params'               => $old === null ? null : json_encode($old, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
            'new_params'               => $new === null ? null : json_encode($new, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
            'changed_keys'             => self::toPgTextArray($changedKeys),
            'source'                   => $source,
            'user_id'                  => $userId,
        ]);
    }

    /** Mapea métricas del backtest a columnas de la config, respetando la precisión de cada numeric. */
    private function metricAttributes(array $m, array $runParams, int $months): array
    {
        $num = static fn (string $k): ?float => isset($m[$k]) && is_numeric($m[$k]) ? (float) $m[$k] : null;
        $clamp = static fn (?float $v, float $max): ?float => $v === null ? null : max(-$max, min($max, $v));

        $winRate = $num('win_rate');
        $sharpe  = $num('sharpe_ratio');
        $pf      = $num('profit_factor');
        $avgPnl  = $num('avg_monthly_pnl');
        $consist = $num('consist_pct');

        $toMonth = static fn ($d): ?string => is_string($d) && preg_match('/^\d{4}-\d{2}/', $d) ? substr($d, 0, 7) : null;

        return [
            'audited_months'      => $months > 0 ? $months : null,
            'avg_win_rate'        => $clamp($winRate, 999.99),     // numeric(5,2)
            'sharpe_ratio'        => $clamp($sharpe, 9999.99),     // numeric(6,2)
            'profit_factor'       => $clamp($pf, 999.99),          // numeric(5,2) - PF sin pérdidas desborda
            'total_return_pct'    => $clamp($num('total_return_pct'), 9999.9999), // numeric(8,4)
            'avg_monthly_pnl'     => $clamp($avgPnl, 999.9999),    // numeric(7,4)
            'consistency_pct'     => $clamp($consist, 9999.9),     // numeric(5,1)
            'backtest_range_from' => $toMonth($runParams['start_date'] ?? null),
            'backtest_range_to'   => $toMonth($runParams['end_date'] ?? null),
            'star_rating'         => RatingHelper::calculate(
                $winRate ?? 0.0, $sharpe ?? 0.0, $pf ?? 0.0, $avgPnl ?? 0.0, $consist ?? 0.0
            ),
        ];
    }

    /** @return string[] claves cuyo valor difiere (incluye añadidas y eliminadas). */
    private static function diffKeys(array $old, array $new): array
    {
        $changed = [];
        foreach (array_unique(array_merge(array_keys($old), array_keys($new))) as $key) {
            $a = array_key_exists($key, $old) ? json_encode($old[$key]) : null;
            $b = array_key_exists($key, $new) ? json_encode($new[$key]) : null;
            if ($a !== $b) {
                $changed[] = (string) $key;
            }
        }
        sort($changed);

        return $changed;
    }

    private static function ksortRecursive(array $data): array
    {
        foreach ($data as $k => $v) {
            if (is_array($v)) {
                $data[$k] = self::ksortRecursive($v);
            }
        }
        if (! array_is_list($data)) {
            ksort($data, SORT_STRING);
        }

        return $data;
    }

    private static function toPgTextArray(array $values): string
    {
        $quoted = array_map(static fn ($v) => '"' . addcslashes((string) $v, '"\\') . '"', $values);

        return '{' . implode(',', $quoted) . '}';
    }
}

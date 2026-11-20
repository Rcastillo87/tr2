<?php

namespace App\Console\Commands;

use App\Services\SystemAlerts;
use App\Support\SafeLogBody;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * p84 (R-21): revisión diaria de si alguna config activa de Paper o estrategia «mira el futuro» (usa velas posteriores
 * a la vela que decide: el backtest muestra operaciones que en vivo no existen). Solo lectura; la prueba la hace el motor
 * (`/v1/strategies/lookahead-audit`, backtesting/lookahead.py). Aviso al admin en «Validación» (categoría existente):
 * un incidente al aparecer y uno al resolverse, sin repetir cada día.
 */
class StrategyLookaheadAudit extends Command
{
    public const INCIDENT = 'strategy-lookahead';

    protected $signature = 'strategies:lookahead-audit';

    protected $description = 'Revisa si alguna estrategia o config activa de Paper mira el futuro (R-21)';

    public function handle(SystemAlerts $alerts): int
    {
        try {
            $response = Http::withHeaders(['X-Internal-API-Key' => config('trading.python_internal_api_key')])
                ->timeout(900)->post(config('trading.python_engine_url') . '/v1/strategies/lookahead-audit');
        } catch (Throwable $e) {
            Log::warning('[LOOKAHEAD] revisión diaria sin respuesta del motor: ' . $e->getMessage());
            $this->error('el motor no respondió');

            return self::FAILURE;
        }
        if (! $response->successful()) {
            Log::warning('[LOOKAHEAD] revisión diaria HTTP ' . $response->status() . ': ' . SafeLogBody::of($response->body()));
            $this->error('HTTP ' . $response->status());

            return self::FAILURE;
        }

        $data = (array) $response->json();
        $bad = (array) ($data['bad'] ?? []);
        $checked = (int) ($data['checked'] ?? 0);
        $errors = count((array) ($data['errors'] ?? []));
        foreach ((array) ($data['results'] ?? []) as $r) {
            $this->line(($r['label'] ?? '?') . ': ' . ($r['verdict'] ?? ''));
        }

        if ($bad !== []) {
            $list = implode(' · ', array_map(fn ($b) => ($b['label'] ?? '?') . ' — ' . ($b['verdict'] ?? ''), $bad));
            $alerts->openIncident(self::INCIDENT, 'error', 'validation',
                'Estrategia que mira el futuro (' . count($bad) . ')',
                "Usa velas posteriores a la que decide: su backtest muestra operaciones que en vivo no existen. {$list}",
                url('/strategies'));
            Log::error('[LOOKAHEAD] ' . count($bad) . " de {$checked} miran el futuro: {$list}");

            return self::FAILURE;
        }

        $alerts->resolveIncident(self::INCIDENT, 'validation', 'Estrategias: ninguna mira el futuro',
            "Revisadas {$checked}.", url('/strategies'));
        Log::info("[LOOKAHEAD] revisión diaria: {$checked} revisadas, ninguna mira el futuro"
            . ($errors ? ", {$errors} sin evaluar (sin datos o con error)" : ''));
        $this->info("{$checked} revisadas: ninguna mira el futuro");

        return self::SUCCESS;
    }
}

<?php

namespace App\Console\Commands;

use App\Models\BrokerAccount;
use App\Support\SafeLogBody;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;

/**
 * MEJ-004 (p89): partes (fills) de Bybit de las operaciones Real anteriores al libro de ejecuciones ('historical').
 * Sin --apply solo muestra lo que guardaría. Solo LEE de Bybit; con --apply el motor guarda las partes, completa el
 * número de la orden de cierre si falta (R-23) y deja 'executions_recorded' en el historial de cada operación.
 * PnL, saldo y motivos de salida no cambian. Las claves viajan al motor como en cada tick (descifradas por el modelo).
 */
class RealExecutionsBackfill extends Command
{
    protected $signature = 'real:executions-backfill {--apply : guardar las partes encontradas}';

    protected $description = 'Registra las ejecuciones de Bybit de las operaciones Real anteriores al libro (MEJ-004)';

    public function handle(): int
    {
        $ids = DB::table('real_trades')->where('executions_status', 'historical')
            ->whereNotNull('broker_account_id')->distinct()->pluck('broker_account_id');
        $accounts = BrokerAccount::whereIn('id', $ids)->get();
        if ($accounts->isEmpty()) {
            $this->line('sin operaciones anteriores al libro: nada que registrar');

            return self::SUCCESS;
        }

        $payload = [
            'apply'    => (bool) $this->option('apply'),
            'accounts' => $accounts->map(fn ($a) => [
                'id' => $a->id, 'broker' => $a->broker, 'account_type' => $a->account_type,
                'api_key' => $a->api_key, 'api_secret' => $a->api_secret, 'subscriptions' => [],
            ])->values()->all(),
        ];

        $response = Http::withHeaders(['X-Internal-API-Key' => config('trading.python_internal_api_key')])
            ->timeout(300)->post(config('trading.python_engine_url') . '/v1/real/executions/backfill', $payload);
        if (! $response->successful()) {
            $this->error('el motor respondió ' . $response->status() . ': ' . SafeLogBody::of($response->body(), 500));

            return self::FAILURE;
        }

        $leg = fn ($s) => is_array($s) ? sprintf('%d partes · %s @ %s · comisión %s', $s['parts'], $s['qty'],
            round((float) $s['vwap'], 8), round((float) $s['fee'], 6)) : '—';
        $rows = collect($response->json('results', []))->map(fn ($r) => [
            $r['trade_id'] ?? '?', $r['symbol'] ?? '?', $leg($r['open'] ?? null), $leg($r['close'] ?? null),
            ($r['error'] ?? null) ?: (empty($r['checks']) ? 'coincide' : implode('; ', $r['checks'])),
            $r['close_order_id'] ?? '—', $r['status'] ?? 'pendiente',
        ]);
        $this->table(['#', 'símbolo', 'apertura (Bybit)', 'cierre (Bybit)', 'control', 'orden de cierre completada',
            'estado'], $rows->all());
        $ok = $rows->filter(fn ($r) => $r[4] === 'coincide')->count();
        $this->line(($payload['apply'] ? 'guardadas: ' : 'se guardarían: ') . $rows->count() . " operaciones · {$ok} coinciden con lo registrado");

        return self::SUCCESS;
    }
}

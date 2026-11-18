<?php

namespace App\Console\Commands;

use App\Models\BrokerAccount;
use App\Support\SafeLogBody;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;

/**
 * R-16 (p70): motivo de salida de los cierres registrados como 'closed_other', según la orden de cierre de Bybit
 * (TakeProfit / StopLoss / TrailingStop). Sin --apply solo muestra lo que cambiaría. Solo LEE de Bybit (historial de
 * cierres y de órdenes); con --apply el motor actualiza exit_reason y deja 'exit_reason_corrected' en el historial.
 * PnL y saldo no cambian. Las claves viajan al motor como en cada tick (descifradas por el modelo).
 */
class RealReclassifyExits extends Command
{
    protected $signature = 'real:reclassify-exits {--apply : guardar los motivos encontrados}';

    protected $description = 'Corrige el motivo de salida de los cierres Real «closed_other» con la orden de cierre de Bybit (R-16)';

    public function handle(): int
    {
        $ids = DB::table('real_trades')->where('status', 'closed')->where('exit_reason', 'closed_other')
            ->whereNotNull('broker_account_id')->distinct()->pluck('broker_account_id');
        $accounts = BrokerAccount::whereIn('id', $ids)->get();
        if ($accounts->isEmpty()) {
            $this->line('sin operaciones closed_other: nada que revisar');

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
            ->timeout(120)->post(config('trading.python_engine_url') . '/v1/real/reclassify-exits', $payload);
        if (! $response->successful()) {
            $this->error('el motor respondió ' . $response->status() . ': ' . SafeLogBody::of($response->body(), 500));

            return self::FAILURE;
        }

        $rows = collect($response->json('results', []))->map(fn ($r) => [
            $r['trade_id'], $r['symbol'], $r['stop_order_type'] ?? '-', $r['create_type'] ?? '-',
            $r['to'] ?? 'sin dato de Bybit (no se toca)', ! empty($r['applied']) ? 'sí' : 'no',
        ]);
        $this->table(['#', 'símbolo', 'stopOrderType', 'createType', 'motivo según Bybit', 'guardado'], $rows->all());
        $this->line(($payload['apply'] ? 'guardados: ' : 'se guardarían: ')
            . $rows->filter(fn ($r) => ! str_starts_with($r[4], 'sin dato') && $r[4] !== 'closed_other')->count()
            . ' de ' . $rows->count());

        return self::SUCCESS;
    }
}

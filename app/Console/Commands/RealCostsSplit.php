<?php

namespace App\Console\Commands;

use App\Models\BrokerAccount;
use App\Support\SafeLogBody;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;

/**
 * R-24 (p90): separa comisión y funding de las operaciones Real cerradas que ya tienen el libro de ejecuciones
 * completo ('ok') y aún no tienen funding. commission = comisiones exactas de las partes de Bybit; funding = bruto −
 * neto − comisiones (positivo = pagado, como Paper). Solo con el neto confirmado por el closed-pnl de Bybit.
 * Sin --apply solo muestra el reparto. Neto, PnL y saldo no cambian.
 */
class RealCostsSplit extends Command
{
    protected $signature = 'real:costs-split {--apply : guardar comisión y funding separados}';

    protected $description = 'Separa comisión y funding de las operaciones Real cerradas (R-24)';

    public function handle(): int
    {
        $ids = DB::table('real_trades')->where('status', 'closed')->where('executions_status', 'ok')
            ->whereNull('funding')->whereNotNull('broker_account_id')->distinct()->pluck('broker_account_id');
        $accounts = BrokerAccount::whereIn('id', $ids)->get();
        if ($accounts->isEmpty()) {
            $this->line('sin operaciones por separar');

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
            ->timeout(300)->post(config('trading.python_engine_url') . '/v1/real/costs/split', $payload);
        if (! $response->successful()) {
            $this->error('el motor respondió ' . $response->status() . ': ' . SafeLogBody::of($response->body(), 500));

            return self::FAILURE;
        }

        $num = fn ($v) => $v === null ? '—' : number_format((float) $v, 4, '.', '');
        $results = collect($response->json('results', []));
        $rows = $results->map(fn ($r) => [
            $r['trade_id'] ?? '?', $r['symbol'] ?? '?', $num($r['pnl'] ?? null), $num($r['net_pnl'] ?? null),
            $num($r['split']['commission_before'] ?? null), $num($r['split']['commission'] ?? null),
            $num($r['split']['funding'] ?? null),
            ($r['error'] ?? null) ?: ($r['split_note'] ?? null) ?: 'separada',
        ]);
        $this->table(['#', 'símbolo', 'bruto', 'neto (no cambia)', 'comisión registrada', 'comisión Bybit',
            'funding (+ pagado)', 'nota'], $rows->all());
        $done = $results->filter(fn ($r) => ! empty($r['split']))->count();
        $funding = $results->sum(fn ($r) => (float) ($r['split']['funding'] ?? 0));
        $this->line(($payload['apply'] ? 'separadas: ' : 'se separarían: ') . "{$done} de {$rows->count()} · funding neto "
            . number_format($funding, 4, '.', '') . ' USDT (+ pagado)');

        return self::SUCCESS;
    }
}

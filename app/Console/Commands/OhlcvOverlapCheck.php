<?php

namespace App\Console\Commands;

use App\Services\SystemAlerts;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;

/**
 * C6-05: revisión periódica (solo lectura) de lotes comprimidos solapados en ohlcv_data (TimescaleDB). En octubre una
 * recompresión dejó lotes que se pisaban en el tiempo y la lectura ordenada devolvía velas desordenadas (BITACORA,
 * 28-oct); el motor las ordena y avisa `[BARS]`, pero el origen queda en la base. Este comando NO repara: con solapes
 * abre el aviso `ohlcv-overlap` (fragmento, moneda, temporalidad); sin solapes lo cierra. La reparación
 * (decompress_chunk + compress_chunk) es una operación aparte, con respaldo y aprobación del dueño.
 */
class OhlcvOverlapCheck extends Command
{
    protected $signature = 'ohlcv:overlap-check';

    protected $description = 'Busca lotes comprimidos solapados en ohlcv_data (solo lectura) y avisa';

    public const INCIDENT = 'ohlcv-overlap';

    public const SQL_FILE = 'database/sql/ohlcv_overlap_batches.sql';

    public const CHUNKS_SQL = "SELECT c.table_name AS chunk, format('%I.%I', c2.schema_name, c2.table_name) AS comp"
        . ' FROM _timescaledb_catalog.chunk c'
        . ' JOIN _timescaledb_catalog.chunk c2 ON c2.id = c.compressed_chunk_id'
        . ' JOIN _timescaledb_catalog.hypertable h ON h.id = c.hypertable_id'
        . " WHERE h.table_name = 'ohlcv_data' ORDER BY c.id";

    /** Temporalidad legible: 1 → 1m, 60 → 1h, 240 → 4h, D → 1D. */
    public static function tf(string $interval): string
    {
        if (! ctype_digit($interval)) {
            return '1' . $interval;
        }
        $m = (int) $interval;

        return $m % 60 === 0 ? ($m / 60) . 'h' : $m . 'm';
    }

    /** @param list<array{chunk:string, symbol:string, interval:string, lotes:int}> $found */
    public static function summarize(array $found): string
    {
        $byChunk = [];
        foreach ($found as $f) {
            $byChunk[$f['chunk']][] = "{$f['symbol']} " . self::tf((string) $f['interval']) . " ({$f['lotes']})";
        }
        $parts = [];
        foreach ($byChunk as $chunk => $series) {
            $parts[] = "{$chunk}: " . implode(', ', $series);
        }

        return implode(' · ', $parts);
    }

    public function handle(SystemAlerts $alerts): int
    {
        $template = file_get_contents(base_path(self::SQL_FILE));
        try {
            $found = DB::transaction(function () use ($template) {
                DB::statement('SET TRANSACTION READ ONLY');   // nunca escribe
                $out = [];
                foreach (DB::select(self::CHUNKS_SQL) as $c) {
                    foreach (DB::select(str_replace('{comp}', $c->comp, $template)) as $r) {
                        $out[] = ['chunk' => $c->chunk, 'broker' => $r->broker, 'symbol' => $r->symbol,
                                  'interval' => (string) $r->interval, 'lotes' => (int) $r->lotes, 'desde' => (string) $r->desde];
                    }
                }

                return $out;
            });
        } catch (\Throwable $e) {
            Log::error('[OHLCV-OVERLAP] no se pudo revisar: ' . $e->getMessage());
            $this->error('No se pudo revisar: ' . $e->getMessage());

            return self::FAILURE;
        }

        if ($found !== []) {
            $summary = self::summarize($found);
            Log::warning('[OHLCV-OVERLAP] ' . count($found) . " serie(s) con lotes solapados: {$summary}");
            $alerts->openIncident(self::INCIDENT, 'warning', 'collector', 'Velas: lotes comprimidos solapados',
                count($found) . " serie(s): {$summary}. El bot las ordena al leerlas (aviso [BARS]); la reparación es aparte"
                . ' y con aprobación (C6-05).');
            $this->warn(count($found) . " serie(s) con lotes solapados: {$summary}");

            return self::SUCCESS;
        }
        $alerts->resolveIncident(self::INCIDENT, 'collector', 'Velas: sin lotes comprimidos solapados');
        $this->info('Sin lotes comprimidos solapados');

        return self::SUCCESS;
    }
}

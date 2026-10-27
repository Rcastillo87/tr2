<?php

namespace App\Console\Commands;

use App\Services\BrokerEvents;
use Illuminate\Console\Command;

/** Avisos de broker: drena broker_events (cada minuto por cron) y, con --prune, aplica la retención. */
class BrokerEventsDrain extends Command
{
    protected $signature = 'broker:events {--limit=200 : eventos por corrida} {--prune : borrar eventos viejos}';

    protected $description = 'Convierte los eventos del motor (broker_events) en avisos para el dueño de cada cuenta';

    public function handle(BrokerEvents $events): int
    {
        if ($this->option('prune')) {
            $this->line('eventos eliminados por retención: ' . $events->prune());
        }
        $s = $events->drain(max(1, (int) $this->option('limit')));
        $this->line("procesados {$s['processed']} · avisos {$s['notified']} · sin aviso {$s['skipped']}");

        return self::SUCCESS;
    }
}

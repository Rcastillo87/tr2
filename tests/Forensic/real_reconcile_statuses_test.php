<?php
/**
 * N-01: la reconciliación Real revisa toda cuenta con un trade 'pending_open' (además de open/pending_close/orphaned),
 * aunque la cuenta esté pausada o sin suscripciones: es el único camino que recupera una apertura interrumpida.
 * PHP puro (sin Laravel): clases base mínimas para cargar el modelo; el selector del job se revisa en su código.
 * La prueba con Laravel y la base real (transacción revertida) es real_reconcile_selector_test.php.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/real_reconcile_statuses_test.php
 */
declare(strict_types=1);

namespace Illuminate\Database\Eloquent {
    if (! class_exists(Model::class)) {
        abstract class Model {}
    }
}

namespace Illuminate\Database\Eloquent\Factories {
    if (! trait_exists(HasFactory::class)) {
        trait HasFactory {}
    }
}

namespace {
    $fails = 0;
    $check = function (string $name, bool $ok, $d = '') use (&$fails): void {
        $fails += $ok ? 0 : 1;
        printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
    };

    require getcwd() . '/app/Models/RealTrade.php';
    $const = 'App\Models\RealTrade::RECONCILE_STATUSES';
    $statuses = defined($const) ? constant($const) : null;

    $check('R1: RealTrade::RECONCILE_STATUSES existe', is_array($statuses), $statuses);
    $statuses = (array) $statuses;
    foreach (['pending_open', 'open', 'pending_close', 'orphaned'] as $st) {
        $check("R2: incluye '{$st}'", in_array($st, $statuses, true), $statuses);
    }
    foreach (['closed', 'failed', 'ignored', 'error'] as $st) {
        $check("R3: no incluye el estado final '{$st}'", ! in_array($st, $statuses, true), $statuses);
    }

    $job = file_get_contents(getcwd() . '/app/Jobs/RealTradingReconcileJob.php');
    $check('R4: el selector del job usa RealTrade::RECONCILE_STATUSES',
        (bool) preg_match("/whereIn\('real_trades\.status',\s*RealTrade::RECONCILE_STATUSES\)/", $job));
    $check('R5: el job no tiene una lista de estados escrita a mano (una sola fuente)',
        ! preg_match("/whereIn\('real_trades\.status',\s*\[/", $job));
    $check('R6: el job importa App\Models\RealTrade', str_contains($job, "use App\\Models\\RealTrade;"));

    echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
    exit($fails === 0 ? 0 : 1);
}

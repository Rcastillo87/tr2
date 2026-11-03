<?php
/**
 * C-06: el vigilante detecta que la validación diaria del collector no corre (CollectorWatchdog::validationStaleness).
 * PHP puro: una clase base mínima reemplaza a la de Laravel para cargar el comando sin el framework.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/collector_watchdog_validation_test.php
 */
declare(strict_types=1);

namespace Illuminate\Console {
    if (! class_exists(Command::class)) {
        abstract class Command {}
    }
}

namespace {
    require getcwd() . '/app/Console/Commands/CollectorWatchdog.php';

    use App\Console\Commands\CollectorWatchdog as W;

    $fails = 0;
    $check = function (string $name, bool $ok, $d = '') use (&$fails): void {
        $fails += $ok ? 0 : 1;
        printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
    };
    if (! method_exists(W::class, 'validationStaleness')) {
        $check('el vigilante revisa la validación diaria (validationStaleness)', false, 'no existe');
        echo "\nRESULTADO: {$fails} FALLO(S)\n";
        exit(1);
    }
    $now = strtotime('2026-11-04T12:00:00+00:00');
    $at = fn (int $hoursAgo) => ['at' => gmdate('Y-m-d\TH:i:s.uP', $now - $hoursAgo * 3600 - 60)];

    $check('validación de hace 2 h: al día', W::validationStaleness($at(2), $now, 26) === null);
    $check('validación de hace 25 h: al día (margen para el job de las 04:00)', W::validationStaleness($at(25), $now, 26) === null);
    $r = W::validationStaleness($at(27), $now, 26);
    $check('validación de hace 27 h: atrasada y dice cuánto', is_string($r) && str_contains($r, '27 h'), $r);
    $r = W::validationStaleness(null, $now, 26);
    $check('nunca corrió (sin resultado guardado): atrasada', is_string($r) && str_contains($r, 'ninguna'), $r);
    $r = W::validationStaleness(['at' => 'ayer por la mañana'], $now, 26);
    $check('fecha ilegible: atrasada (no se da por buena)', is_string($r) && str_contains($r, 'no se puede leer'), $r);
    $r = W::validationStaleness(['series' => []], $now, 26);
    $check('resultado sin fecha: atrasada', is_string($r), $r);
    $check('el umbral es configurable (48 h)', W::validationStaleness($at(30), $now, 48) === null);
    $check('formato real del job (ISO con microsegundos y +00:00)',
        W::validationStaleness(['at' => '2026-11-04T09:00:05.333305+00:00'], $now, 26) === null);

    echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
    exit($fails ? 1 : 0);
}

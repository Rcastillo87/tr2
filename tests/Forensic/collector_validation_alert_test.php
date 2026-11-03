<?php
/**
 * C-01: el aviso de la validación del collector no da «todo OK» con 0 series activas (App\Services\SystemAlerts::
 * validationResult). PHP puro: una subclase registra los avisos en vez de enviarlos (sin Laravel ni base de datos).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/collector_validation_alert_test.php
 */
declare(strict_types=1);

require getcwd() . '/app/Services/SystemAlerts.php';

final class RecordingAlerts extends App\Services\SystemAlerts
{
    public array $calls = [];

    public function notify(string $level, string $category, string $title, string $body = '', ?string $url = null, ?string $incident = null): void
    {
        $this->calls[] = ['notify', $level, $title];
    }

    public function openIncident(string $key, string $level, string $category, string $title, string $body = '', ?string $url = null): bool
    {
        $this->calls[] = ['open', $key, $title];
        return true;
    }

    public function resolveIncident(string $key, string $category, string $title, string $body = '', ?string $url = null): bool
    {
        $this->calls[] = ['resolve', $key, $title];
        return true;
    }
}

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$run = function (array $summary): array {
    $a = new RecordingAlerts();
    $a->validationResult(['summary' => $summary]);
    return $a->calls;
};

$c = $run(['series' => 0, 'ok' => 0]);
$check('0 series activas: abre incidente «sin series activas» (no «todo OK»)',
    count($c) === 1 && $c[0][0] === 'open' && $c[0][1] === 'validation_failed' && str_contains($c[0][2], 'sin series activas'), $c);
$c = $run(['series' => 84, 'ok' => 84]);
$check('84 de 84 OK: cierra el incidente (todo OK)', count($c) === 1 && $c[0][0] === 'resolve', $c);
$c = $run(['series' => 84, 'ok' => 80, 'missing_hist' => 3]);
$check('4 series con fallas: abre incidente con el número', count($c) === 1 && $c[0][0] === 'open' && str_contains($c[0][2], '4 serie(s)'), $c);
$c = $run([]);
$check('resultado sin resumen: tratado como 0 series (falla)', count($c) === 1 && $c[0][0] === 'open', $c);

echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);

<?php
/**
 * C-12: aviso de funding atrasado en la campana (App\Services\SystemAlerts::validationResult). Abre el incidente
 * funding_stale si la reparación diaria informa monedas con más de 30 h sin funding; lo cierra solo al ponerse al día.
 * PHP puro: una subclase registra los avisos en vez de enviarlos (sin Laravel ni base de datos).
 * Uso: cd <raíz del proyecto> && php tests/Forensic/funding_alert_test.php
 * Antes del parche: FALLA (no hay aviso de funding).
 */
declare(strict_types=1);

require getcwd() . '/app/Services/SystemAlerts.php';

final class RecordingFundingAlerts extends App\Services\SystemAlerts
{
    public array $calls = [];

    public function notify(string $level, string $category, string $title, string $body = '', ?string $url = null, ?string $incident = null): void
    {
        $this->calls[] = ['notify', $level, $title, $body];
    }

    public function openIncident(string $key, string $level, string $category, string $title, string $body = '', ?string $url = null): bool
    {
        $this->calls[] = ['open', $key, $title, $body, $level];
        return true;
    }

    public function resolveIncident(string $key, string $category, string $title, string $body = '', ?string $url = null): bool
    {
        $this->calls[] = ['resolve', $key, $title, $body];
        return true;
    }
}

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$summary = ['series' => 84, 'ok' => 84];
$run = function (?array $funding) use ($summary): array {
    $a = new RecordingFundingAlerts();
    $data = ['summary' => $summary];
    if ($funding !== null) {
        $data['funding'] = $funding;
    }
    $a->validationResult($data);
    return array_values(array_filter($a->calls, fn ($c) => ($c[1] ?? '') === 'funding_stale'));
};

$c = $run(['symbols' => [['symbol' => 'BTCUSDT'], ['symbol' => 'ETHUSDT']], 'errors' => 1, 'stale_hours' => 30,
           'stale' => [['symbol' => 'ETHUSDT', 'lag_h' => 165.0]]]);
$check('moneda atrasada -> abre el incidente funding_stale (warning)', count($c) === 1 && $c[0][0] === 'open' && $c[0][4] === 'warning', $c);
$check('título con la cantidad y cuerpo con moneda, horas, umbral y errores',
    ($c[0][2] ?? '') === 'Funding atrasado: 1 moneda(s)' && str_contains($c[0][3] ?? '', 'ETHUSDT 165 h')
    && str_contains($c[0][3] ?? '', 'más de 30 h') && str_contains($c[0][3] ?? '', 'Errores al actualizar: 1'), $c[0] ?? null);

$c = $run(['symbols' => [['symbol' => 'NEWUSDT']], 'errors' => 1, 'stale_hours' => 30,
           'stale' => [['symbol' => 'NEWUSDT', 'lag_h' => null]]]);
$check('moneda sin cobertura -> «sin datos»', str_contains($c[0][3] ?? '', 'NEWUSDT sin datos'), $c[0] ?? null);

$c = $run(['symbols' => [['symbol' => 'BTCUSDT'], ['symbol' => 'ETHUSDT']], 'errors' => 0, 'stale_hours' => 30, 'stale' => []]);
$check('todas al día -> resuelve el incidente (se cierra solo)', count($c) === 1 && $c[0][0] === 'resolve'
    && str_contains($c[0][3], '2 moneda(s)'), $c);

$c = $run(null);
$check('validación sin reparación (sin sección funding) -> no toca el incidente', $c === [], $c);

$c = $run(['symbols' => [], 'errors' => 0, 'stale_hours' => 30, 'dry_run' => true, 'stale' => [['symbol' => 'X', 'lag_h' => 99]]]);
$check('simulación (dry_run) -> no toca el incidente', $c === [], $c);

$a = new RecordingFundingAlerts();
$a->validationResult(['summary' => $summary, 'funding' => ['symbols' => [], 'errors' => 0, 'stale_hours' => 30, 'stale' => []]]);
$check('el resto de la validación no cambia (todo OK se resuelve como siempre)',
    in_array(['resolve', 'validation_failed', 'Validación del collector: todo OK', '84 series idénticas a Bybit y sin huecos.'], $a->calls, true), $a->calls);

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "$fails FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

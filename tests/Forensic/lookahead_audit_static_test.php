<?php
/**
 * p84 (R-21): revisión diaria de estrategias que «miran el futuro». El comando llama al motor, avisa al admin con un
 * incidente (uno al aparecer, uno al resolverse) en la categoría existente «Validación» (sin pestaña nueva en la
 * pantalla de avisos) y está programado una vez al día sin solaparse. El guardado de estrategias sigue con el smoke test
 * de 120 s, dentro del cual el motor hace la prueba (2 combinaciones).
 * PHP puro, sin Laravel. Uso: cd <raíz del proyecto> && php tests/Forensic/lookahead_audit_static_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$cmdFile = $root . '/app/Console/Commands/StrategyLookaheadAudit.php';
$cmd = is_file($cmdFile) ? (string) file_get_contents($cmdFile) : '';
$check('existe el comando strategies:lookahead-audit', str_contains($cmd, "\$signature = 'strategies:lookahead-audit'"));
$check('llama a /v1/strategies/lookahead-audit del motor con la clave interna',
    str_contains($cmd, "'/v1/strategies/lookahead-audit'") && str_contains($cmd, 'X-Internal-API-Key'));
preg_match('/->timeout\((\d+)\)/', $cmd, $m);
$check('espera la revisión completa (timeout ≥ 600 s)', (int) ($m[1] ?? 0) >= 600, $m[1] ?? null);
$check('con alguna mala: abre el incidente en «validation» (error)',
    (bool) preg_match("/openIncident\(self::INCIDENT, 'error', 'validation'/", $cmd));
$check('sin malas: cierra el incidente (aviso de recuperado solo si estaba abierto)',
    (bool) preg_match("/resolveIncident\(self::INCIDENT, 'validation'/", $cmd));
$check('sin respuesta del motor: no abre ni cierra el incidente (no confunde «no se pudo» con «está bien»)',
    (bool) preg_match('/catch \(Throwable \$e\) \{[^}]*return self::FAILURE;/s', $cmd)
    && (bool) preg_match('/if \(! \$response->successful\(\)\) \{[^}]*return self::FAILURE;/s', $cmd));
$check('el cuerpo del error se registra sin datos sensibles (SafeLogBody)', str_contains($cmd, 'SafeLogBody::of('));
// C5-02 (p101): «sin evaluar» con aviso propio; el aviso principal no se cierra mientras falte evaluar alguna
$check('C5-02: con alguna sin evaluar abre el aviso «sin evaluar» (warning) y lo cierra cuando se evalúan todas',
    (bool) preg_match('/if \(\$unverified !== \[\]\) \{.*?openIncident\(self::INCIDENT_UNVERIFIED, \'warning\', \'validation\'.*?\} else \{.*?resolveIncident\(self::INCIDENT_UNVERIFIED, \'validation\'/s', $cmd));
$check('C5-02: el aviso «mira el futuro» solo se cierra si se evaluaron todas',
    (bool) preg_match('/if \(\$errors === 0\) \{[^}]*resolveIncident\(self::INCIDENT, \'validation\'/s', $cmd));
$check('C5-02: con alguna sin evaluar el comando termina en FAILURE', str_contains($cmd, 'return $errors ? self::FAILURE : self::SUCCESS;'));

$notif = (string) file_get_contents($root . '/app/Http/Controllers/NotificationController.php');
$check('«validation» es una categoría que la pantalla de avisos ya muestra (sin pestaña nueva)',
    str_contains($notif, "'validation' => 'Validación'"));

$console = (string) file_get_contents($root . '/routes/console.php');
$check('programada una vez al día, sin solaparse y en segundo plano',
    (bool) preg_match("/Schedule::command\('strategies:lookahead-audit'\)->dailyAt\('\d\d:\d\d'\)->timezone\('America\/Bogota'\)\s*->name\('strategies-lookahead-audit'\)->withoutOverlapping\(\d+\)->runInBackground\(\)/", $console));

$ctl = (string) file_get_contents($root . '/app/Http/Controllers/StrategyController.php');
$check('el guardado sigue usando el smoke test del motor (120 s), que ahora incluye la prueba',
    str_contains($ctl, "->timeout(120)->post(") && str_contains($ctl, "'/v1/strategies/validate'"));
$api = (string) file_get_contents($root . '/python-engine/api/v1/backtest.py');
$check('el smoke test corre la prueba antes de los backtests y rechaza con el motivo',
    (bool) preg_match('/if req\.run_backtest:.*?lookahead\.guard_code\(.*?raise HTTPException\(status_code=400, detail=reason.*?end = datetime/s', $api));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

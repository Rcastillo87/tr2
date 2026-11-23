<?php
/**
 * D-45 (p93) — SL y TP por separado en Laravel: lo que viaja al motor (y queda en config_params, de donde salen Paper y
 * Real), las etiquetas de las pantallas, el formulario, la búsqueda y la migración. PHP puro, sin base ni Laravel.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/levels_laravel_test.php
 */
declare(strict_types=1);

$root = getcwd();
$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};
$read = fn (string $p): string => is_file("$root/$p") ? (string) file_get_contents("$root/$p") : '';

require "$root/app/Services/BacktestPayload.php";
$lvl = is_file("$root/app/Support/LevelsLabel.php");
$check('existe App\Support\LevelsLabel', $lvl);
if ($lvl) {
    require "$root/app/Support/LevelsLabel.php";
}
$levels = [\App\Services\BacktestPayload::class, 'levels'];
$hasLevels = method_exists(\App\Services\BacktestPayload::class, 'levels');
$check('existe BacktestPayload::levels', $hasLevels);

if ($hasLevels) {
    $form = ['sl_pct' => '1.5', 'tp_pct' => '3', 'sl_mode' => 'fixed', 'tp_mode' => 'fixed', 'sl_atr_mult' => '2', 'tp_r_mult' => '2'];
    $check('L1: Fijo + Fijo: no viaja nada (payload y hash de backtest iguales que antes)', $levels($form) === [] && $levels([]) === []);
    $got = $levels(['sl_mode' => 'atr', 'tp_mode' => 'r', 'sl_atr_mult' => '2.5', 'sl_min_pct' => '0.8', 'sl_max_pct' => '4',
                    'be_r_mult' => '1', 'tp_r_mult' => '3', 'tp_atr_mult' => '9']);
    $check('L2: SL automático + TP veces el SL: modos y solo sus multiplicadores (sin tp_atr_mult)', $got === [
        'sl_mode' => 'atr', 'tp_mode' => 'r', 'sl_atr_mult' => 2.5, 'sl_min_pct' => 0.8, 'sl_max_pct' => 4.0, 'be_r_mult' => 1.0,
        'tp_r_mult' => 3.0], $got);
    $got = $levels(['sl_mode' => 'fixed', 'tp_mode' => 'atr', 'tp_atr_mult' => '4', 'sl_atr_mult' => '2']);
    $check('L3: SL fijo + TP automático: sin campos del SL automático', $got === ['sl_mode' => 'fixed', 'tp_mode' => 'atr',
        'tp_atr_mult' => 4.0], $got);
    $got = $levels(['sl_mode' => 'atr', 'tp_mode' => 'fixed']);
    $check('L4: SL automático + TP fijo: valores por defecto 2 · 0,8 · 5 · 1', $got === ['sl_mode' => 'atr', 'tp_mode' => 'fixed',
        'sl_atr_mult' => 2.0, 'sl_min_pct' => 0.8, 'sl_max_pct' => 5.0, 'be_r_mult' => 1.0], $got);
    $check('L5: modo desconocido = fijo', $levels(['sl_mode' => 'xx', 'tp_mode' => 'yy']) === []);
    $err = \App\Services\BacktestPayload::validate(['sl_mode' => 'atr', 'sl_min_pct' => 6, 'sl_max_pct' => 5]);
    $err2 = \App\Services\BacktestPayload::validate(['tp_mode' => 'zz']);
    $check('L6: las mismas reglas que Python: mínimo > máximo y modo inválido se rechazan', $err !== null && $err2 !== null, [$err, $err2]);
}

if ($lvl) {
    $L = \App\Support\LevelsLabel::class;
    $fix = ['sl_pct' => 1.5, 'tp_pct' => 3, 'be_pct' => 2];
    $check('E1: fijo: «1.5%», «3%», «2%» (como hoy)', [$L::sl($fix), $L::tp($fix), $L::be($fix)] === ['1.5%', '3%', '2%']
        && ! $L::isAuto($fix));
    $a = ['sl_mode' => 'atr', 'tp_mode' => 'r', 'sl_atr_mult' => 2, 'sl_min_pct' => 0.8, 'sl_max_pct' => 5, 'tp_r_mult' => 2,
          'be_r_mult' => 1, 'sl_pct' => 1.5];
    $check('E2: automático: «ATR ×2 (0.8–5%)», «2 × SL», «1 × SL»',
        [$L::sl($a), $L::tp($a), $L::be($a)] === ['ATR ×2 (0.8–5%)', '2 × SL', '1 × SL'] && $L::isAuto($a), [$L::sl($a), $L::tp($a), $L::be($a)]);
    $check('E3: TP automático: «ATR ×4»; BE a 20 veces el SL = «Sin BE»',
        $L::tp(['tp_mode' => 'atr', 'tp_atr_mult' => 4]) === 'ATR ×4' && $L::be(['sl_mode' => 'atr', 'be_r_mult' => 20]) === 'Sin BE');
    $check('E4: p92 «sl_tp_mode: atr» = SL automático + TP veces el SL', $L::modes(['sl_tp_mode' => 'atr']) === ['atr', 'r']);
}

$ctl = $read('app/Http/Controllers/BacktestingController.php');
$check('C1: el backtest agrega los niveles al payload (de ahí config_params → Paper y Real)',
    str_contains($ctl, '$payloads[$sym] += \App\Services\BacktestPayload::levels($request->all());'));
$check('C2: aviso «SL automático con TP fijo» y el aviso BE ≥ TP solo en modo fijo',
    str_contains($ctl, 'SL automático con TP fijo') && str_contains($ctl, '! $autoLevels && $bePct > 0'));
$from = $read('app/Services/BacktestFromSearch.php');
$check('C3: un backtest creado desde la búsqueda conserva el SL/TP automático', str_contains($from, 'BacktestPayload::LEVEL_KEYS'));

$run = $read('resources/views/backtesting/run.blade.php');
$check('V1: formulario: dos menús (Stop Loss / Take Profit) con sus opciones y campos',
    str_contains($run, 'name="sl_mode"') && str_contains($run, 'name="tp_mode"') && str_contains($run, '<option value="r"')
    && str_contains($run, 'name="sl_atr_mult"') && str_contains($run, 'name="tp_atr_mult"') && str_contains($run, 'name="be_r_mult"')
    && str_contains($run, 'name="sl_min_pct"') && str_contains($run, 'name="sl_max_pct"') && str_contains($run, 'name="tp_r_mult"'));
$check('V2: formulario: los campos de hoy siguen (sl_pct, tp_pct, be_pct) y «Fijo» viene por defecto en configs viejas',
    str_contains($run, 'name="sl_pct"') && str_contains($run, 'name="tp_pct"') && str_contains($run, 'name="be_pct"')
    && str_contains($run, 'LevelsLabel::modes($lvCp)'));
$acc = $read('resources/views/trading/accounts.blade.php');
$hist = $read('resources/views/backtesting/history.blade.php');
$res = $read('resources/views/backtesting/partials/results.blade.php');
$check('V3: Real (cuentas), historial y resultados muestran cómo se calcula el SL/TP automático',
    substr_count($acc, 'LevelsLabel::isAuto((array) $params)') === 3 && str_contains($hist, "\$p['sl_label']")
    && str_contains($res, 'LevelsLabel::isAuto($cfg)'));

$svc = $read('app/Services/ParamSearchService.php');
$pc = $read('app/Http/Controllers/ParamSearchController.php');
$modal = $read('resources/views/param-search/_modal.blade.php');
$help = $read('resources/views/param-search/_helpers.blade.php');
$check('S1: búsqueda: opción sltp (fijos por defecto) validada y guardada en la búsqueda',
    str_contains($svc, "'sltp'               => \$sltp") && str_contains($svc, "string \$sltp = 'fixed'")
    && str_contains($pc, "\$data['sltp'] ??= 'fixed'") && str_contains($pc, 'ParamSearchService::SLTPS'));
$check('S2: ventana de búsqueda: bloque «SL y TP a probar» que envía la opción; resultados con etiquetas del automático',
    str_contains($modal, 'id="sbSltp"') && str_contains($modal, '{ mode, focus, sltp, intervals') && str_contains($help, "'SL ATR ×'"));
$mig = $read('database/sql-migrations/2026_11_23_01_param_search_sltp.up.sql');
$check('M1: migración: columna sltp con default fixed (las búsquedas anteriores quedan «fijos»)',
    str_contains($mig, "sltp varchar(8) NOT NULL DEFAULT 'fixed'") && str_contains($mig, "CHECK (sltp IN ('fixed', 'auto', 'both'))"));

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "$fails FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

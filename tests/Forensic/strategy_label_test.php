<?php
/**
 * N-09 (PHP puro): la etiqueta «{estrategia} — {símbolo} {intervalo}» es solo texto; la identidad es el id.
 * - StrategyLabel::likePrefix: nombre exacto + separador, con % _ \ escapados («VWAP» no abarca «VWAP Tendencia»).
 * - renameReferences reasigna por nombre solo trades de legado SIN config_id.
 * - Borrar una estrategia comprueba sus configs activas por id (Strategy::hasActivePaper), no por LIKE del nombre.
 * La prueba contra la base real (transacción revertida) es strategy_identity_test.php.
 * Uso: cd <raíz del proyecto> && php tests/Forensic/strategy_label_test.php
 */
declare(strict_types=1);

$fails = 0;
$check = function (string $name, bool $ok, $d = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $d !== '' ? '  -> ' . json_encode($d, JSON_UNESCAPED_UNICODE) : '');
};

$root = getcwd();
$file = "{$root}/app/Support/StrategyLabel.php";
$check('L0: existe App\Support\StrategyLabel', is_file($file));
if (is_file($file)) {
    require $file;
}
$has = class_exists('App\Support\StrategyLabel');

/** LIKE de PostgreSQL (ESCAPE '\' por defecto) traducido a regex, para probar el patrón sin base. */
$like = function (string $pattern, string $value): bool {
    $re = '';
    for ($i = 0, $n = strlen($pattern); $i < $n; $i++) {
        $c = $pattern[$i];
        if ($c === '\\' && $i + 1 < $n) { $re .= preg_quote($pattern[++$i], '/'); continue; }
        $re .= $c === '%' ? '.*' : ($c === '_' ? '.' : preg_quote($c, '/'));
    }
    return (bool) preg_match('/^' . $re . '$/su', $value);
};

if ($has) {
    $L = 'App\Support\StrategyLabel';
    $check('L1: compose = «VWAP Tendencia — ETHUSDT H4»', $L::compose('VWAP Tendencia', 'ETHUSDT', 'H4') === 'VWAP Tendencia — ETHUSDT H4');
    $p = $L::likePrefix('VWAP');
    $check('L2: «VWAP» abarca «VWAP — BTCUSDT H1»', $like($p, 'VWAP — BTCUSDT H1'), $p);
    $check('L3: «VWAP» NO abarca «VWAP Tendencia — ETHUSDT H4»', ! $like($p, 'VWAP Tendencia — ETHUSDT H4'), $p);
    $p = $L::likePrefix('RSI_2%');
    $check('L4: % y _ del nombre son literales', $like($p, 'RSI_2% — BTCUSDT H1') && ! $like($p, 'RSIx2abc — BTCUSDT H1'), $p);
    $p = $L::likePrefix('A\\B');
    $check('L5: la barra invertida del nombre es literal', $like($p, 'A\\B — BTCUSDT H1') && ! $like($p, 'AB — BTCUSDT H1'), $p);
}

$sync = file_get_contents("{$root}/app/Services/StrategyConfigSync.php");
preg_match('/function renameReferences\(.*?\n    \}/s', $sync, $m);
$body = $m[0] ?? '';
$check('R1: renameReferences reasigna por nombre solo trades SIN config_id',
    (bool) preg_match("/whereNull\('paper_strategy_config_id'\)\s*->where\('strategy',\s*\\\$oldName\)/", $body));
$check("R2: renameReferences ya no hace orWhere('strategy', \$oldName) suelto",
    ! preg_match("/orWhere\('strategy',\s*\\\$oldName\)/", $body));
$check('R3: displayName arma la etiqueta con StrategyLabel::compose', str_contains($sync, 'StrategyLabel::compose('));

$ctl = file_get_contents("{$root}/app/Http/Controllers/StrategyController.php");
$check('D1: destroy usa $strategy->hasActivePaper()', str_contains($ctl, '$strategy->hasActivePaper()'));
$check('D2: destroy ya no busca por LIKE del nombre', ! preg_match("/display_name',\s*'like',\s*\\\$strategy->name/", $ctl));
$model = file_get_contents("{$root}/app/Models/Strategy.php");
$check("D3: hasActivePaper compara por strategy_id del backtest",
    (bool) preg_match("/whereHas\('backtest',\s*fn \(\\\$b\) => \\\$b->where\('strategy_id',\s*\\\$this->id\)\)/", $model));

foreach (['PaperTradingController', 'TradingController'] as $c) {
    $src = file_get_contents("{$root}/app/Http/Controllers/{$c}.php");
    $check("F1: {$c} filtra con StrategyLabel::likePrefix (2 veces)", substr_count($src, 'StrategyLabel::likePrefix($filterStrategy)') === 2);
    $check("F2: {$c} sin LIKE armado a mano", ! preg_match("/\\\$filterStrategy \. '/", $src));
}

echo "\nRESULTADO: " . ($fails === 0 ? 'TODO OK' : "{$fails} FALLO(S)") . "\n";
exit($fails === 0 ? 0 : 1);

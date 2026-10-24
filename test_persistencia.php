<?php
require __DIR__.'/vendor/autoload.php';
$app = require_once __DIR__.'/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

$bt = new \App\Models\Backtest();
$bt->strategy_id = 5;
$bt->symbols = ['BTCUSDT'];
$bt->interval = '240';
$bt->months = 3;
$bt->config_params = [
    'sl_pct' => 2.5,
    'tp_pct' => 5.0,
    'risk_per_trade_pct' => 2.0,
    'commission_pct' => 0.1,
    'be_pct' => 1.5,
    'max_duration' => 48,
    'regime_adx_trending' => 35,
    'regime_adx_ranging' => 15,
    'regime_ambiguous_as' => 'TRENDING',
    'volume_filter_period' => 50,
    'volume_filter_mult' => 2.5,
    'trailing_mode' => 'atr',
    'trailing_atr_mult' => 3.5,
    'trailing_distance_pct' => 2.0,
    'trailing_activation_buffer_pct' => 1.5,
    'volume_filter' => true,
    'macro_trend_filter' => true,
    'regime_filter' => true,
    'max_duration_profit' => true,
    'close_on_opposite' => true
];
$bt->metrics = [];
$bt->strategy_snapshot = ['code' => 'test', 'config' => []]; // <-- CAMPO AGREGADO AQUÍ
$bt->hash = 'test_persist_' . time();
$bt->save();

echo "✅ Backtest creado con ID: " . $bt->id . "\n";
echo "⏳ Renderizando vista...\n";

$strategy = \App\Models\Strategy::find($bt->strategy_id);
$html = view('backtesting.run', [
    'strategies' => collect(),
    'symbols' => [],
    'intervals' => [],
    'symbolBrokerMap' => [],
    'paperConfigsForPreload' => collect(),
    'result' => null,
    'implementParams' => [],
    'error' => null,
    'backtestToLoad' => $bt,
    'selectedSymbols' => $bt->symbols,
    'strategyToLoad' => $strategy,
])->render();

$checks = [
    'SL = 2.5%' => 'name="sl_pct"[^>]*value="2\.5"',
    'TP = 5.0%' => 'name="tp_pct"[^>]*value="5\.0"',
    'Riesgo = 2.0%' => 'name="risk_per_trade_pct"[^>]*value="2\.0"',
    'Comisión = 0.1%' => 'name="commission_pct"[^>]*value="0\.1"',
    'BE = 1.5%' => 'name="be_pct"[^>]*value="1\.5"',
    'Duración = 48' => 'name="max_duration"[^>]*value="48"',
    'ADX Trending = 35' => 'name="regime_adx_trending"[^>]*value="35"',
    'ADX Ranging = 15' => 'name="regime_adx_ranging"[^>]*value="15"',
    'Caso Ambiguo = TRENDING' => '<option value="TRENDING"[^>]*selected',
    'Volumen Período = 50' => 'name="volume_filter_period"[^>]*value="50"',
    'Volumen Mult = 2.5' => 'name="volume_filter_mult"[^>]*value="2\.5"',
    'Trailing Mode = atr' => '<option value="atr"[^>]*selected',
    'Trailing ATR Mult = 3.5' => 'name="trailing_atr_mult"[^>]*value="3\.5"',
    'Trailing Dist = 2.0' => 'name="trailing_distance_pct"[^>]*value="2\.0"',
    'Trailing Buffer = 1.5' => 'name="trailing_activation_buffer_pct"[^>]*value="1\.5"',
    'Checkbox Volumen' => 'name="volume_filter"[^>]*checked',
    'Checkbox Macro H4' => 'name="macro_trend_filter"[^>]*checked',
    'Checkbox Régimen ADX' => 'name="regime_filter"[^>]*checked',
    'Checkbox Cierre Inteligente' => 'name="max_duration_profit"[^>]*checked',
    'Checkbox Señal Opuesta' => 'name="close_on_opposite"[^>]*checked',
];

echo "\n🔬 VERIFICANDO VALORES EN LA VISTA:\n";
echo "----------------------------------------------------------------------\n";
$all_ok = true;
foreach ($checks as $label => $pattern) {
    if (preg_match('/' . $pattern . '/', $html)) {
        echo "  ✅ $label\n";
    } else {
        echo "  ❌ $label (NO SE CARGÓ)\n";
        $all_ok = false;
    }
}
echo "----------------------------------------------------------------------\n";
if ($all_ok) {
    echo "🏆 ¡TODAS LAS CONFIGURACIONES SE GUARDAN Y SE RETORNAN CORRECTAMENTE!\n";
} else {
    echo "⚠️ Algunas configuraciones NO se están guardando. Revisa los ❌.\n";
}

$bt->delete();
echo "🧹 Backtest de prueba eliminado.\n";

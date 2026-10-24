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
    'sl_pct' => 2.5, 'tp_pct' => 5.0, 'risk_per_trade_pct' => 2.0,
    'commission_pct' => 0.1, 'be_pct' => 1.5, 'max_duration' => 48,
    'regime_adx_trending' => 35, 'regime_adx_ranging' => 15,
    'regime_ambiguous_as' => 'TRENDING', 'volume_filter_period' => 50,
    'volume_filter_mult' => 2.5, 'trailing_mode' => 'atr',
    'trailing_atr_mult' => 3.5, 'trailing_distance_pct' => 2.0,
    'trailing_activation_buffer_pct' => 1.5, 'volume_filter' => true,
    'macro_trend_filter' => true, 'regime_filter' => true,
    'max_duration_profit' => true, 'close_on_opposite' => true
];
$bt->metrics = [];
$bt->strategy_snapshot = ['code' => 'test', 'config' => []];
$bt->hash = 'test_persist_' . time();
$bt->save();

$strategy = \App\Models\Strategy::find($bt->strategy_id);
$html = view('backtesting.run', [
    'strategies' => collect(), 'symbols' => [], 'intervals' => [],
    'symbolBrokerMap' => [], 'paperConfigsForPreload' => collect(),
    'result' => null, 'implementParams' => [], 'error' => null,
    'backtestToLoad' => $bt, 'selectedSymbols' => $bt->symbols,
    'strategyToLoad' => $strategy,
])->render();

// Extraer el HTML exacto de los 4 campos
$fields = ['tp_pct', 'risk_per_trade_pct', 'commission_pct', 'trailing_distance_pct'];
foreach ($fields as $f) {
    if (preg_match('/<input[^>]*name="' . $f . '"[^>]*>/', $html, $m)) {
        echo "🔍 $f: " . $m[0] . "\n";
    } else {
        echo "❌ $f: NO ENCONTRADO\n";
    }
}

$bt->delete();

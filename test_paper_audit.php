<?php
require __DIR__.'/vendor/autoload.php';
$app = require_once __DIR__.'/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

// Desactivar temporalmente las otras para que el log no se ensucie
\App\Models\PaperStrategyConfig::query()->update(['active' => false]);

$strategy = \App\Models\Strategy::where('name', 'Cruce de Medias Móviles')->first() ?? \App\Models\Strategy::first();

$config = \App\Models\PaperStrategyConfig::create([
    'display_name' => 'AUDIT TEST — BTCUSDT 60',
    'strategy_class' => 'DynamicStrategy',
    'symbol' => 'BTCUSDT',
    'interval' => '60',
    'active' => true,
    'params' => [
        'sl_pct' => 8.8,
        'tp_pct' => 9.9,
        'be_pct' => 3.3,
        'max_duration' => 77,
        'risk_per_trade_pct' => 4.4,
        'regime_filter' => true,
        'regime_adx_trending' => 33,
        'regime_adx_ranging' => 11,
        'regime_ambiguous_as' => 'TRENDING',
        'volume_filter' => true,
        'volume_filter_period' => 40,
        'volume_filter_mult' => 2.2,
        'macro_trend_filter' => true,
        'trailing_mode' => 'atr',
        'trailing_atr_mult' => 4.4,
        'trailing_distance_pct' => 2.2,
        'trailing_activation_buffer_pct' => 1.1,
        'close_on_opposite' => true,
        'max_duration_profit' => true,
        'strategy_code' => $strategy->code,
        'strategy_config' => $strategy->config,
    ]
]);

echo "✅ Configuración de auditoría creada con ID: {$config->id}\n";

<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('paper_strategy_configs', function (Blueprint $table) {
            $table->id();
            // Nombre para mostrar en el dashboard (ej. "VWAP Tendencia ETH H2")
            $table->string('display_name');
            // Clase Python a instanciar (ej. "VwapStrategy", "MeanReversionStrategy")
            $table->string('strategy_class');
            $table->string('symbol');
            $table->string('interval', 10);
            // Parametros completos en JSON: mode, sl_pct, tp_pct, be_pct, max_duration,
            // allowed_regimes, y cualquier parametro especifico de la estrategia
            $table->jsonb('params');
            $table->boolean('active')->default(true);
            $table->timestamps();

            // Una estrategia no puede repetir la misma clase+simbolo+intervalo+modo
            $table->unique(['strategy_class', 'symbol', 'interval']);
        });

        // Configuraciones iniciales basadas en los resultados del backtest comparativo
        DB::table('paper_strategy_configs')->insert([
            // VWAP modo tendencia: mejor en ETH H2
            [
                'display_name'   => 'VWAP Tendencia — ETHUSDT H2',
                'strategy_class' => 'VwapStrategy',
                'symbol'         => 'ETHUSDT',
                'interval'       => '120',
                'params'         => json_encode([
                    'mode'             => 'trend_follow',
                    'ema_trend_period' => 50,
                    'vwap_std_filter'  => 1.5,
                    'sl_pct'           => 1.5,
                    'tp_pct'           => 3.0,
                    'be_pct'           => 2.0,
                    'max_duration'     => 12,
                    'regime_filter'    => true,
                    'allowed_regimes'  => ['TRENDING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            // VWAP modo reversion (E-13): mejor en BTC H1 TRENDING
            [
                'display_name'   => 'VWAP Reversión — BTCUSDT H1',
                'strategy_class' => 'VwapStrategy',
                'symbol'         => 'BTCUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'mode'             => 'reversion',
                    'vwap_std_entry'   => 2.0,
                    'zone_bars'        => 4,
                    'sl_pct'           => 1.5,
                    'tp_pct'           => 3.0,
                    'be_pct'           => 2.0,
                    'max_duration'     => 24,
                    'regime_filter'    => true,
                    'allowed_regimes'  => ['TRENDING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            // VWAP modo reversion (E-13): mejor en SOL H1 TRENDING
            [
                'display_name'   => 'VWAP Reversión — SOLUSDT H1',
                'strategy_class' => 'VwapStrategy',
                'symbol'         => 'SOLUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'mode'             => 'reversion',
                    'vwap_std_entry'   => 2.0,
                    'zone_bars'        => 4,
                    'sl_pct'           => 1.5,
                    'tp_pct'           => 3.0,
                    'be_pct'           => 2.0,
                    'max_duration'     => 24,
                    'regime_filter'    => true,
                    'allowed_regimes'  => ['TRENDING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            // Reversión a la Media: los 3 simbolos H1
            [
                'display_name'   => 'Reversión a la Media — BTCUSDT H1',
                'strategy_class' => 'MeanReversionStrategy',
                'symbol'         => 'BTCUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'bb_period'      => 20,
                    'bb_std'         => 2.0,
                    'rsi_period'     => 14,
                    'rsi_ob'         => 70,
                    'rsi_os'         => 30,
                    'sl_pct'         => 1.5,
                    'tp_pct'         => 3.0,
                    'be_pct'         => 2.0,
                    'max_duration'   => 24,
                    'regime_filter'  => true,
                    'allowed_regimes'=> ['RANGING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            [
                'display_name'   => 'Reversión a la Media — ETHUSDT H1',
                'strategy_class' => 'MeanReversionStrategy',
                'symbol'         => 'ETHUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'bb_period'      => 20,
                    'bb_std'         => 2.0,
                    'rsi_period'     => 14,
                    'rsi_ob'         => 70,
                    'rsi_os'         => 30,
                    'sl_pct'         => 1.5,
                    'tp_pct'         => 3.0,
                    'be_pct'         => 2.0,
                    'max_duration'   => 24,
                    'regime_filter'  => true,
                    'allowed_regimes'=> ['RANGING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            [
                'display_name'   => 'Reversión a la Media — SOLUSDT H1',
                'strategy_class' => 'MeanReversionStrategy',
                'symbol'         => 'SOLUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'bb_period'      => 20,
                    'bb_std'         => 2.0,
                    'rsi_period'     => 14,
                    'rsi_ob'         => 70,
                    'rsi_os'         => 30,
                    'sl_pct'         => 1.5,
                    'tp_pct'         => 3.0,
                    'be_pct'         => 2.0,
                    'max_duration'   => 24,
                    'regime_filter'  => true,
                    'allowed_regimes'=> ['RANGING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            // Tendencia EMA/Donchian: los 3 simbolos H1
            [
                'display_name'   => 'Tendencia EMA/Donchian — BTCUSDT H1',
                'strategy_class' => 'EmaDonchianStrategy',
                'symbol'         => 'BTCUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'ema_fast'       => 9,
                    'ema_slow'       => 21,
                    'donchian_period'=> 20,
                    'trend_window'   => 10,
                    'sl_pct'         => 1.5,
                    'tp_pct'         => 3.0,
                    'be_pct'         => 2.0,
                    'max_duration'   => 24,
                    'regime_filter'  => true,
                    'allowed_regimes'=> ['TRENDING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            [
                'display_name'   => 'Tendencia EMA/Donchian — ETHUSDT H1',
                'strategy_class' => 'EmaDonchianStrategy',
                'symbol'         => 'ETHUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'ema_fast'       => 9,
                    'ema_slow'       => 21,
                    'donchian_period'=> 20,
                    'trend_window'   => 10,
                    'sl_pct'         => 1.5,
                    'tp_pct'         => 3.0,
                    'be_pct'         => 2.0,
                    'max_duration'   => 24,
                    'regime_filter'  => true,
                    'allowed_regimes'=> ['TRENDING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
            [
                'display_name'   => 'Tendencia EMA/Donchian — SOLUSDT H1',
                'strategy_class' => 'EmaDonchianStrategy',
                'symbol'         => 'SOLUSDT',
                'interval'       => '60',
                'params'         => json_encode([
                    'ema_fast'       => 9,
                    'ema_slow'       => 21,
                    'donchian_period'=> 20,
                    'trend_window'   => 10,
                    'sl_pct'         => 1.5,
                    'tp_pct'         => 3.0,
                    'be_pct'         => 2.0,
                    'max_duration'   => 24,
                    'regime_filter'  => true,
                    'allowed_regimes'=> ['TRENDING'],
                    'risk_per_trade_pct' => 1.0,
                ]),
                'active'         => true,
                'created_at'     => now(),
                'updated_at'     => now(),
            ],
        ]);
    }

    public function down(): void
    {
        Schema::dropIfExists('paper_strategy_configs');
    }
};

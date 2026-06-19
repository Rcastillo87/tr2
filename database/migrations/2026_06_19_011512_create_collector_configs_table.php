<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('collector_configs', function (Blueprint $table) {
            $table->id();
            $table->string('symbol', 20);
            $table->string('interval', 10);
            $table->boolean('active')->default(true);
            $table->text('notes')->nullable(); // descripcion opcional para el admin
            $table->timestamps();

            $table->unique(['symbol', 'interval']);
        });

        // Datos iniciales basados en los resultados de backtesting:
        // Simbolos operativos: BTC, ETH, SOL (BNB y XRP descartados)
        // Intervalos: 1, 5, 15 (colector tiempo real), 60 (H1 estrategias), 120 (H2 ETH VWAP)
        // H4 y D1 se dejan inactivos — disponibles para backtests puntuales si se activan
        $now = now();
        $configs = [];

        foreach (['BTCUSDT', 'ETHUSDT', 'SOLUSDT'] as $symbol) {
            foreach ([
                '1'   => ['active' => true,  'notes' => 'Tiempo real — 1 min'],
                '5'   => ['active' => true,  'notes' => 'Tiempo real — 5 min'],
                '15'  => ['active' => true,  'notes' => 'Tiempo real — 15 min'],
                '60'  => ['active' => true,  'notes' => 'H1 — usado por estrategias paper trading'],
                '120' => ['active' => true,  'notes' => 'H2 — usado por VWAP Tendencia ETH'],
                '240' => ['active' => false, 'notes' => 'H4 — solo para backtests puntuales'],
                'D'   => ['active' => false, 'notes' => 'D1 — solo para backtests puntuales'],
            ] as $interval => $cfg) {
                $configs[] = [
                    'symbol'     => $symbol,
                    'interval'   => $interval,
                    'active'     => $cfg['active'],
                    'notes'      => $cfg['notes'],
                    'created_at' => $now,
                    'updated_at' => $now,
                ];
            }
        }

        // BNB y XRP inactivos — datos historicos preservados para backtests
        foreach (['BNBUSDT', 'XRPUSDT'] as $symbol) {
            foreach ([
                '1' => '1 min', '5' => '5 min', '15' => '15 min',
                '60' => 'H1', '120' => 'H2', '240' => 'H4', 'D' => 'D1',
            ] as $interval => $label) {
                $configs[] = [
                    'symbol'     => $symbol,
                    'interval'   => $interval,
                    'active'     => false,
                    'notes'      => "Inactivo — $label (datos históricos preservados)",
                    'created_at' => $now,
                    'updated_at' => $now,
                ];
            }
        }

        DB::table('collector_configs')->insert($configs);
    }

    public function down(): void
    {
        Schema::dropIfExists('collector_configs');
    }
};

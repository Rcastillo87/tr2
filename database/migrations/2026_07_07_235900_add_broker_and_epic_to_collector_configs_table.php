<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('collector_configs', function (Blueprint $table) {
            $table->string('broker', 20)->default('bybit')->after('interval');
            // epic: identificador propietario de IG (ej. CS.D.EURUSD.CFD.IP).
            // Nulo para bybit, donde 'symbol' ya sirve como identificador nativo.
            $table->string('epic', 40)->nullable()->after('broker');
        });

        // Symbolos IG — H1 (60) y H4 (240) unicamente, por la cuota semanal
        // de precios historicos de IG (10,000 puntos/semana). 1 año de historia,
        // no 2, por la misma razon. Inactivos hasta correr el backfill inicial.
        $now = now();
        $igSymbols = [
            'EURUSD' => 'CS.D.EURUSD.CFD.IP',
            'GBPUSD' => 'CS.D.GBPUSD.CFD.IP',
            'XAUUSD' => 'CS.D.IN_GOLD.MFI.IP',
        ];

        $configs = [];
        foreach ($igSymbols as $symbol => $epic) {
            foreach ([
                '60'  => 'H1 — entrada estrategias IG',
                '240' => 'H4 — filtro de tendencia macro IG',
            ] as $interval => $notes) {
                $configs[] = [
                    'symbol'     => $symbol,
                    'interval'   => $interval,
                    'broker'     => 'ig',
                    'epic'       => $epic,
                    'active'     => true,
                    'notes'      => $notes,
                    'created_at' => $now,
                    'updated_at' => $now,
                ];
            }
        }

        DB::table('collector_configs')->insert($configs);
    }

    public function down(): void
    {
        DB::table('collector_configs')->where('broker', 'ig')->delete();
        Schema::table('collector_configs', function (Blueprint $table) {
            $table->dropColumn(['broker', 'epic']);
        });
    }
};

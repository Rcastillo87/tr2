<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('broker_accounts', function (Blueprint $table) {
            // Regla configurable, no hardcodeada: refleja si el broker/modo de
            // cuenta permite solo UNA posicion neta por simbolo (caso actual de
            // Bybit en modo One-Way). El dia que se agregue un broker o modo
            // (ej. hedge mode) que permita varias posiciones simultaneas del
            // mismo simbolo, se ajusta este flag por cuenta sin tocar codigo.
            $table->boolean('single_position_per_symbol')->default(true)->after('status');
        });
    }

    public function down(): void
    {
        Schema::table('broker_accounts', function (Blueprint $table) {
            $table->dropColumn('single_position_per_symbol');
        });
    }
};

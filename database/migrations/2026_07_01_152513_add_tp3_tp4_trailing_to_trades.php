<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Agrega soporte de TP3/TP4 y trailing stop a paper_trades y real_trades.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_trades', function (Blueprint $table) {
            $table->decimal('tp3', 20, 8)->nullable()->after('tp2');
            $table->decimal('tp4', 20, 8)->nullable()->after('tp3');
            $table->boolean('trailing_applied')->default(false)->after('be_activated');
        });

        Schema::table('real_trades', function (Blueprint $table) {
            $table->boolean('trailing_applied')->default(false)->after('be_activated');
        });
    }

    public function down(): void
    {
        Schema::table('paper_trades', function (Blueprint $table) {
            $table->dropColumn(['tp3', 'tp4', 'trailing_applied']);
        });

        Schema::table('real_trades', function (Blueprint $table) {
            $table->dropColumn(['trailing_applied']);
        });
    }
};

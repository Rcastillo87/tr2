<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_trades', function (Blueprint $table) {
            // Maximum Favorable/Adverse Excursion, en % sobre el balance virtual de referencia.
            // Se actualizan en cada tick mientras el trade esta abierto.
            $table->decimal('max_profit_pct', 10, 4)->default(0)->after('pnl_pct');
            $table->decimal('max_loss_pct', 10, 4)->default(0)->after('max_profit_pct');
        });
    }

    public function down(): void
    {
        Schema::table('paper_trades', function (Blueprint $table) {
            $table->dropColumn(['max_profit_pct', 'max_loss_pct']);
        });
    }
};
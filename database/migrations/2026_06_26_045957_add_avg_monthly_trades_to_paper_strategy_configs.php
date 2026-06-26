<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->decimal('avg_monthly_trades', 6, 2)->nullable()->after('avg_monthly_pnl')
                ->comment('Promedio de operaciones por mes del ultimo backtest');
        });
    }

    public function down(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->dropColumn('avg_monthly_trades');
        });
    }
};

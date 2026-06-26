<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->decimal('total_return_pct', 8, 4)->nullable()->after('avg_monthly_trades')
                ->comment('Retorno total acumulado del ultimo backtest (%)');
        });
    }

    public function down(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->dropColumn('total_return_pct');
        });
    }
};

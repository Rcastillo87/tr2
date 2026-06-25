<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->integer('audited_months')->nullable()->after('params')
                ->comment('Meses auditados en el ultimo backtest');
            $table->decimal('avg_win_rate', 5, 2)->nullable()->after('audited_months')
                ->comment('Win rate promedio mensual del ultimo backtest (%)');
            $table->decimal('avg_monthly_pnl', 7, 4)->nullable()->after('avg_win_rate')
                ->comment('P&L promedio mensual del ultimo backtest (%)');
        });
    }

    public function down(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->dropColumn(['audited_months', 'avg_win_rate', 'avg_monthly_pnl']);
        });
    }
};

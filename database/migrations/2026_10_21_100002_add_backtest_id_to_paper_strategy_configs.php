<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->foreignId('backtest_id')->nullable()->constrained('backtests')->nullOnDelete();
        });
    }
    public function down(): void {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->dropForeign(['backtest_id']);
            $table->dropColumn('backtest_id');
        });
    }
};

<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->decimal('star_wr',           3, 1)->nullable()->after('total_return_pct');
            $table->decimal('star_sharpe',       3, 1)->nullable()->after('star_wr');
            $table->decimal('star_ret',          3, 1)->nullable()->after('star_sharpe');
            $table->decimal('star_consistency',  3, 1)->nullable()->after('star_ret');
            $table->decimal('star_pf',           3, 1)->nullable()->after('star_consistency');
            $table->decimal('star_rating',       3, 1)->nullable()->after('star_pf');
            $table->string('backtest_range_from', 7)->nullable()->after('star_rating');
            $table->string('backtest_range_to',   7)->nullable()->after('backtest_range_from');
        });
    }

    public function down(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->dropColumn([
                'star_wr','star_sharpe','star_ret','star_consistency',
                'star_pf','star_rating','backtest_range_from','backtest_range_to'
            ]);
        });
    }
};

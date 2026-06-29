<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->decimal('sharpe_ratio',    6, 2)->nullable()->after('total_return_pct');
            $table->decimal('consistency_pct', 5, 1)->nullable()->after('sharpe_ratio');
            $table->decimal('profit_factor',   5, 2)->nullable()->after('consistency_pct');
        });
    }

    public function down(): void
    {
        Schema::table('paper_strategy_configs', function (Blueprint $table) {
            $table->dropColumn(['sharpe_ratio','consistency_pct','profit_factor']);
        });
    }
};

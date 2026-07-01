<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('real_trades', function (Blueprint $table) {
            $table->decimal('original_size', 20, 8)->nullable()->after('size');
            $table->boolean('tp2_hit')->default(false)->after('tp4');
            $table->boolean('tp3_hit')->default(false)->after('tp2_hit');
            $table->boolean('tp4_hit')->default(false)->after('tp3_hit');
            $table->decimal('realized_pnl_partial', 20, 8)->default(0)->after('tp4_hit');
        });
    }

    public function down(): void
    {
        Schema::table('real_trades', function (Blueprint $table) {
            $table->dropColumn(['original_size', 'tp2_hit', 'tp3_hit', 'tp4_hit', 'realized_pnl_partial']);
        });
    }
};

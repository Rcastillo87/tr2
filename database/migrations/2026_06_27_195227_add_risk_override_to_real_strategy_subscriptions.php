<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->decimal('risk_override_pct', 5, 2)->nullable()->after('interval')
                ->comment('Sobrescribe risk_per_trade_pct de la config para esta suscripcion especifica');
        });
    }

    public function down(): void
    {
        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->dropColumn('risk_override_pct');
        });
    }
};

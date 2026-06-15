<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->dropUnique('real_subs_unique');
            $table->dropColumn(['broker', 'account_label']);

            $table->foreignId('broker_account_id')
                  ->after('user_id')
                  ->constrained()
                  ->cascadeOnDelete();

            $table->unique(['broker_account_id', 'strategy', 'symbol'], 'real_subs_unique');
        });
    }

    public function down(): void
    {
        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->dropUnique('real_subs_unique');
            $table->dropConstrainedForeignId('broker_account_id');

            $table->string('broker')->default('bybit');
            $table->string('account_label')->nullable();

            $table->unique(['user_id', 'strategy', 'symbol', 'broker'], 'real_subs_unique');
        });
    }
};

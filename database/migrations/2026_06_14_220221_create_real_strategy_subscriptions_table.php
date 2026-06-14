<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('real_strategy_subscriptions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();

            $table->string('strategy');            // "VWAP Intradía", etc.
            $table->string('symbol');               // BTCUSDT
            $table->string('broker')->default('bybit'); // abierto para futuro multi-broker
            $table->string('account_label')->nullable(); // ej. "Cuenta principal"

            $table->enum('status', ['active', 'paused'])->default('active');

            $table->timestamps();

            $table->unique(['user_id', 'strategy', 'symbol', 'broker'], 'real_subs_unique');
            $table->index(['user_id', 'status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('real_strategy_subscriptions');
    }
};

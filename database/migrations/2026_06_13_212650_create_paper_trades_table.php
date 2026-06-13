<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('paper_trades', function (Blueprint $table) {
            $table->id();
            $table->string('strategy');           // "VWAP Intradía", etc.
            $table->string('symbol');              // BTCUSDT
            $table->string('interval');            // 60
            $table->enum('side', ['long', 'short']);
            $table->decimal('entry_price', 20, 8);
            $table->decimal('exit_price', 20, 8)->nullable();
            $table->decimal('sl', 20, 8);
            $table->decimal('tp', 20, 8);
            $table->decimal('be_level', 20, 8);
            $table->boolean('be_activated')->default(false);
            $table->decimal('size', 20, 8);
            $table->decimal('pnl', 20, 8)->nullable();
            $table->decimal('pnl_pct', 10, 4)->nullable();
            $table->string('exit_reason')->nullable(); // stop_loss, take_profit, time_exit
            $table->string('regime')->nullable();
            $table->timestamp('entry_time');
            $table->timestamp('exit_time')->nullable();
            $table->enum('status', ['open', 'closed'])->default('open');
            $table->timestamps();

            $table->index(['strategy', 'symbol', 'status']);
            $table->index(['status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('paper_trades');
    }
};

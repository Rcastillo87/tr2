<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('risk_controls', function (Blueprint $table) {
            $table->id();
            $table->string('strategy')->nullable();   // null = aplica a todo (kill switch global)
            $table->string('symbol')->nullable();      // null = aplica a toda la estrategia
            $table->enum('reason', [
                'daily_drawdown',
                'total_drawdown',
                'volatility_extreme',
                'kill_switch_manual',
            ]);
            $table->decimal('value', 10, 4)->nullable();   // valor que disparó (ej. -3.5%)
            $table->decimal('threshold', 10, 4)->nullable(); // umbral configurado (ej. 3%)
            $table->boolean('active')->default(true);
            $table->timestamp('paused_at');
            $table->timestamp('auto_resume_at')->nullable(); // para drawdown diario (medianoche siguiente)
            $table->timestamp('resumed_at')->nullable();
            $table->timestamps();

            $table->index(['strategy', 'symbol', 'active']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('risk_controls');
    }
};

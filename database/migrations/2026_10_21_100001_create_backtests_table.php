<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void {
        Schema::create('backtests', function (Blueprint $table) {
            $table->id();
            $table->foreignId('strategy_id')->constrained()->onDelete('cascade');
            $table->json('symbols'); // Array de símbolos
            $table->string('interval');
            $table->integer('months'); // 1 a 24
            $table->json('config_params'); // SL, TP, Riesgo, Filtros
            $table->json('strategy_snapshot'); // El código/JSON exacto usado
            $table->json('metrics')->nullable(); // Sharpe, PF, WR, etc.
            $table->boolean('approved')->default(false);
            $table->timestamps();
        });
    }
    public function down(): void { Schema::dropIfExists('backtests'); }
};

<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('broker_accounts', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();

            $table->string('broker')->default('bybit'); // abierto para futuro multi-broker
            $table->enum('account_type', ['real', 'demo'])->default('real');
            $table->string('label'); // ej. "Mi cuenta principal"

            $table->text('api_key')->nullable();    // encriptado (cast 'encrypted')
            $table->text('api_secret')->nullable();  // encriptado (cast 'encrypted')

            $table->enum('status', ['active', 'paused'])->default('active');

            $table->timestamps();

            $table->index(['user_id', 'status']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('broker_accounts');
    }
};

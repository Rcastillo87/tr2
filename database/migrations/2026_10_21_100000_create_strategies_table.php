<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void {
        Schema::create('strategies', function (Blueprint $table) {
            $table->id();
            $table->string('name')->unique();
            $table->text('description')->nullable();
            $table->enum('type', ['python', 'json'])->default('python');
            $table->longText('code')->nullable(); // Código Python o JSON
            $table->boolean('active')->default(true);
            $table->timestamps();
        });
    }
    public function down(): void { Schema::dropIfExists('strategies'); }
};

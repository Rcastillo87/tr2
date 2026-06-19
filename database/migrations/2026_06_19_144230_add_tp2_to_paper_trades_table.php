<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('paper_trades', function (Blueprint $table) {
            // TP2 opcional: si la estrategia lo define, el motor cierra en TP2
            // con prioridad sobre TP1 (columna 'tp' existente). Null si la
            // estrategia no usa TP1/TP2 (comportamiento de TP unico sin cambios).
            $table->decimal('tp2', 15, 8)->nullable()->after('tp');
        });
    }

    public function down(): void
    {
        Schema::table('paper_trades', function (Blueprint $table) {
            $table->dropColumn('tp2');
        });
    }
};

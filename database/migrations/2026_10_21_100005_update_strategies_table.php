<?php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void {
        Schema::table('strategies', function (Blueprint $table) {
            $table->json('config')->nullable()->after('code');
            // Eliminamos 'type' porque ya no hay dos tipos de código, solo Python.
            if (Schema::hasColumn('strategies', 'type')) {
                $table->dropColumn('type');
            }
        });
    }
    public function down(): void {
        Schema::table('strategies', function (Blueprint $table) {
            $table->dropColumn('config');
        });
    }
};

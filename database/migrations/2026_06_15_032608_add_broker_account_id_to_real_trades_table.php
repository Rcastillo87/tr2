<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('real_trades', function (Blueprint $table) {
            $table->foreignId('broker_account_id')
                  ->nullable()
                  ->after('subscription_id')
                  ->constrained()
                  ->nullOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('real_trades', function (Blueprint $table) {
            $table->dropConstrainedForeignId('broker_account_id');
        });
    }
};

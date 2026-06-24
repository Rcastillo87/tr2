<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Autogenerar label para cuentas existentes antes de aplicar la constraint
        DB::table('broker_accounts')->get()->each(function ($account) {
            DB::table('broker_accounts')->where('id', $account->id)->update([
                'label' => ucfirst($account->broker) . ' ' . ucfirst($account->account_type),
            ]);
        });

        Schema::table('broker_accounts', function (Blueprint $table) {
            // Unicidad: un usuario solo puede tener 1 real y 1 demo por broker
            $table->unique(['user_id', 'broker', 'account_type'], 'broker_accounts_user_broker_type_unique');
        });
    }

    public function down(): void
    {
        Schema::table('broker_accounts', function (Blueprint $table) {
            $table->dropUnique('broker_accounts_user_broker_type_unique');
        });
    }
};

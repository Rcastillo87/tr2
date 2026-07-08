<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('broker_accounts', function (Blueprint $table) {
            // JSON generico para credenciales adicionales que no encajan en
            // api_key/api_secret (ej. IG requiere usuario+contraseña de sesion
            // ademas de la API key). Encriptado igual que api_key/api_secret.
            $table->text('credentials_extra')->nullable()->after('api_secret');
        });
    }

    public function down(): void
    {
        Schema::table('broker_accounts', function (Blueprint $table) {
            $table->dropColumn('credentials_extra');
        });
    }
};

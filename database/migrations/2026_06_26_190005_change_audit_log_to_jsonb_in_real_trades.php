<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('ALTER TABLE real_trades ALTER COLUMN audit_log TYPE jsonb USING audit_log::jsonb');
    }

    public function down(): void
    {
        DB::statement('ALTER TABLE real_trades ALTER COLUMN audit_log TYPE json USING audit_log::json');
    }
};

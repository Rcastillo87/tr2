<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement('ALTER TABLE real_trades DROP CONSTRAINT real_trades_status_check');
        DB::statement("ALTER TABLE real_trades ADD CONSTRAINT real_trades_status_check CHECK (status::text = ANY (ARRAY['pending_open','open','pending_close','closed','error','orphaned','failed','ignored']::text[]))");
    }

    public function down(): void
    {
        DB::statement('ALTER TABLE real_trades DROP CONSTRAINT real_trades_status_check');
        DB::statement("ALTER TABLE real_trades ADD CONSTRAINT real_trades_status_check CHECK (status::text = ANY (ARRAY['pending_open','open','pending_close','closed','error']::text[]))");
    }
};

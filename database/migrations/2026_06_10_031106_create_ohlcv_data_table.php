<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        DB::statement("
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                time        TIMESTAMPTZ     NOT NULL,
                symbol      TEXT            NOT NULL,
                interval    TEXT            NOT NULL,
                open        NUMERIC(20,8)   NOT NULL,
                high        NUMERIC(20,8)   NOT NULL,
                low         NUMERIC(20,8)   NOT NULL,
                close       NUMERIC(20,8)   NOT NULL,
                volume      NUMERIC(30,8)   NOT NULL
            )
        ");

        DB::statement("
            SELECT create_hypertable('ohlcv_data', 'time', if_not_exists => TRUE)
        ");

        DB::statement("
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlcv_symbol_interval_time
            ON ohlcv_data (symbol, interval, time DESC)
        ");
    }

    public function down(): void
    {
        DB::statement('DROP TABLE IF EXISTS ohlcv_data CASCADE');
    }
};

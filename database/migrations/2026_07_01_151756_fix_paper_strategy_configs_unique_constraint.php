<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Formaliza la constraint de unicidad de paper_strategy_configs.
 *
 * La migracion original (2026_06_18_201634_create_paper_strategy_configs_table)
 * declaraba unique(['strategy_class', 'symbol', 'interval']) pero esto permitia
 * colisiones incorrectas entre configs que comparten strategy_class pero difieren
 * en 'mode' dentro del JSON params (ej. VwapStrategy modo 'trend_follow' vs
 * 'reversion' para el mismo simbolo/intervalo).
 *
 * En algun momento se corrigio manualmente en produccion agregando 'mode' (leido
 * desde el JSON params) a la constraint, pero ese cambio nunca quedo versionado
 * en una migracion. Esta migracion formaliza esa constraint ya existente.
 *
 * Usa IF NOT EXISTS para ser segura de correr tanto en produccion (donde ya
 * existe) como en cualquier entorno nuevo (donde se crea por primera vez).
 */
return new class extends Migration
{
    public function up(): void
    {
        DB::statement(
            'ALTER TABLE paper_strategy_configs DROP CONSTRAINT IF EXISTS paper_strategy_configs_strategy_class_symbol_interval_unique'
        );

        DB::statement(<<<SQL
            CREATE UNIQUE INDEX IF NOT EXISTS paper_strategy_configs_unique
            ON paper_strategy_configs (strategy_class, symbol, "interval", (params ->> 'mode'))
        SQL);
    }

    public function down(): void
    {
        DB::statement('DROP INDEX IF EXISTS paper_strategy_configs_unique');
    }
};

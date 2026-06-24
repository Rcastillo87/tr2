<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // ── real_trades: campos nuevos para trading real robusto ──────────
        Schema::table('real_trades', function (Blueprint $table) {
            // FK directa a la config (fuente de verdad)
            $table->foreignId('paper_strategy_config_id')
                  ->nullable()
                  ->after('broker_account_id')
                  ->constrained('paper_strategy_configs')
                  ->nullOnDelete();

            // IDs de órdenes en Bybit
            $table->string('order_id')->nullable()->after('paper_strategy_config_id');
            $table->string('close_order_id')->nullable()->after('order_id');

            // Balance de la cuenta
            $table->decimal('balance_before', 20, 8)->nullable()->after('close_order_id');
            $table->decimal('balance_after', 20, 8)->nullable()->after('balance_before');

            // Comisiones y PnL neto
            $table->decimal('commission', 20, 8)->nullable()->after('balance_after');
            $table->decimal('net_pnl', 20, 8)->nullable()->after('commission');

            // Slippage (diferencia precio señal vs precio ejecutado)
            $table->decimal('entry_price_signal', 20, 8)->nullable()->after('net_pnl');
            $table->decimal('slippage_pct', 10, 6)->nullable()->after('entry_price_signal');

            // Apalancamiento
            $table->decimal('leverage', 10, 2)->default(1)->after('slippage_pct');

            // TP múltiples (igual que paper trading)
            $table->decimal('tp2', 20, 8)->nullable()->after('tp');
            $table->decimal('tp3', 20, 8)->nullable()->after('tp2');
            $table->decimal('tp4', 20, 8)->nullable()->after('tp3');

            // Estado extendido
            $table->dropColumn('status');
        });

        Schema::table('real_trades', function (Blueprint $table) {
            $table->enum('status', [
                'pending_open',
                'open',
                'pending_close',
                'closed',
                'error',
            ])->default('pending_open')->after('exit_time');

            $table->text('error_message')->nullable()->after('status');
            $table->json('audit_log')->nullable()->after('error_message');

            $table->index(['broker_account_id', 'status']);
        });

        // ── real_strategy_subscriptions: FK a paper_strategy_configs ─────
        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->foreignId('paper_strategy_config_id')
                  ->nullable()
                  ->after('broker_account_id')
                  ->constrained('paper_strategy_configs')
                  ->nullOnDelete();

            // Intervalo para completar la unicidad junto con config
            $table->string('interval')->nullable()->after('symbol');

            // Reemplazar unicidad: ahora es por config_id + cuenta
            $table->dropUnique('real_subs_unique');
        });

        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->unique(
                ['broker_account_id', 'paper_strategy_config_id'],
                'real_subs_unique_v2'
            );
        });
    }

    public function down(): void
    {
        Schema::table('real_trades', function (Blueprint $table) {
            $table->dropColumn([
                'paper_strategy_config_id', 'order_id', 'close_order_id',
                'balance_before', 'balance_after', 'commission', 'net_pnl',
                'entry_price_signal', 'slippage_pct', 'leverage',
                'tp2', 'tp3', 'tp4', 'error_message', 'audit_log',
            ]);
            $table->dropColumn('status');
        });
        Schema::table('real_trades', function (Blueprint $table) {
            $table->enum('status', ['open', 'closed'])->default('open');
        });

        Schema::table('real_strategy_subscriptions', function (Blueprint $table) {
            $table->dropUnique('real_subs_unique_v2');
            $table->dropColumn(['paper_strategy_config_id', 'interval']);
            $table->unique(
                ['broker_account_id', 'strategy', 'symbol'],
                'real_subs_unique'
            );
        });
    }
};

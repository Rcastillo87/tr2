<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class RealStrategySubscription extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id',
        'broker_account_id',
        'paper_strategy_config_id',
        'strategy',
        'symbol',
        'interval',
        'status',
        'retire_on_close',
    ];

    protected $casts = ['retire_on_close' => 'boolean'];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function brokerAccount(): BelongsTo
    {
        return $this->belongsTo(BrokerAccount::class);
    }

    public function paperStrategyConfig(): BelongsTo
    {
        return $this->belongsTo(PaperStrategyConfig::class);
    }

    public function trades(): HasMany
    {
        return $this->hasMany(RealTrade::class, 'subscription_id');
    }

    public function openTrades(): HasMany
    {
        return $this->hasMany(RealTrade::class, 'subscription_id')
            ->whereIn('status', ['open', 'pending_open', 'pending_close']);
    }

    public function isActive(): bool
    {
        return $this->status === 'active';
    }

    public function scopeActive($query)
    {
        return $query->where('status', 'active');
    }

    /**
     * Suscripciones que pueden ABRIR posiciones: la suscripcion esta activa Y su configuracion
     * Paper tambien. Asi 'Detener', desactivar o borrar la config corta las entradas Real.
     * Las posiciones ya abiertas se gestionan aparte y no dependen de este filtro.
     */
    public function scopeRunnable($query)
    {
        return $query->where('status', 'active')
            ->whereHas('paperStrategyConfig', fn ($c) => $c->where('active', true))
            // Usuario activo (U-1): un usuario inactivo nunca abre, aunque se inactive por SQL o una suscripción
            // vuelva a quedar activa por error. Sus operaciones vivas se gestionan con windingDown().
            ->whereHas('user', fn ($u) => $u->where('is_active', true));
    }

    /**
     * Suscripciones que NO abren (pausadas, o de un usuario inactivo) pero tienen operaciones abiertas: el tick las
     * envía al motor SIN entradas (entries_allowed=false) para que esas operaciones terminen su ciclo completo
     * (gestión y salida por señal opuesta). Decisión del dueño (13-nov, docs/DECISIONES_DUENO.md D-03/D-04).
     * Con la config Paper apagada no viajan (regla vigente, igual que Paper).
     */
    public function scopeWindingDown($query)
    {
        return $query->where(fn ($q) => $q->where('status', 'paused')
                ->orWhereHas('user', fn ($u) => $u->where('is_active', false)))
            ->whereHas('paperStrategyConfig', fn ($c) => $c->where('active', true))
            ->whereExists(fn ($e) => $e->selectRaw('1')->from('real_trades')
                ->whereColumn('real_trades.subscription_id', 'real_strategy_subscriptions.id')
                ->whereIn('real_trades.status', ['open', 'pending_close']));
    }

    public function scopeForUser($query, int $userId)
    {
        return $query->where('user_id', $userId);
    }

    public function pauseIfConfigInactive(): void
    {
        if ($this->paperStrategyConfig && !$this->paperStrategyConfig->active) {
            $this->update(['status' => 'paused']);
        }
    }
}

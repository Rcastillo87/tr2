<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Strategy extends Model {
    protected $fillable = ['name', 'description', 'code', 'config', 'active'];
    protected $casts = [
        'active' => 'boolean',
        'config' => 'array'
    ];

    public function backtests(): HasMany {
        return $this->hasMany(Backtest::class);
    }
}

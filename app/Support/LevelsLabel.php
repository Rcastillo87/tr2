<?php

namespace App\Support;

/**
 * D-45 (p93): cómo se calcula el SL, el TP y el break-even de una config, en texto corto para las pantallas.
 * Fijo: «1.5%». Automático: «ATR ×2 (0.8–5%)», «2 × SL», «ATR ×4», «1 × SL». Misma regla que backtesting/auto_levels.py.
 */
class LevelsLabel
{
    /** @param array<string, mixed> $p parámetros de la config (config_params o params) */
    public static function modes(array $p): array
    {
        $sl = $p['sl_mode'] ?? null;
        $tp = $p['tp_mode'] ?? null;
        if (($p['sl_tp_mode'] ?? null) === 'atr') {   // p92: SL automático + TP veces el SL
            $sl ??= 'atr';
            $tp ??= 'r';
        }

        return [in_array($sl, ['fixed', 'atr'], true) ? $sl : 'fixed', in_array($tp, ['fixed', 'r', 'atr'], true) ? $tp : 'fixed'];
    }

    public static function sl(array $p): string
    {
        if (self::modes($p)[0] === 'atr') {
            return 'ATR ×' . self::n($p['sl_atr_mult'] ?? 2) . ' (' . self::n($p['sl_min_pct'] ?? 0.8) . '–'
                . self::n($p['sl_max_pct'] ?? 5) . '%)';
        }

        return self::pct($p['sl_pct'] ?? null);
    }

    public static function tp(array $p): string
    {
        return match (self::modes($p)[1]) {
            'r'     => self::n($p['tp_r_mult'] ?? 2) . ' × SL',
            'atr'   => 'ATR ×' . self::n($p['tp_atr_mult'] ?? 4),
            default => self::pct($p['tp_pct'] ?? null),
        };
    }

    public static function be(array $p): string
    {
        if (self::modes($p)[0] === 'atr') {
            $r = (float) ($p['be_r_mult'] ?? 1);

            return $r >= 20 ? 'Sin BE' : self::n($r) . ' × SL';
        }
        $be = $p['be_pct'] ?? null;

        return is_numeric($be) && (float) $be >= 99 ? 'Sin BE' : self::pct($be);
    }

    public static function isAuto(array $p): bool
    {
        return self::modes($p) !== ['fixed', 'fixed'];
    }

    private static function pct(mixed $v): string
    {
        return is_numeric($v) ? self::n($v) . '%' : '-';
    }

    private static function n(mixed $v): string
    {
        return rtrim(rtrim(number_format((float) $v, 2, '.', ''), '0'), '.');
    }
}

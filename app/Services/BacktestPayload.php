<?php

namespace App\Services;

/**
 * Partes del payload de /v1/backtest/run que dependen de si el campo llegó o no (PHP puro, sin Laravel: se prueba
 * con tests/Forensic/backtest_payload_volatility_test.php).
 */
final class BacktestPayload
{
    /**
     * Protección por volatilidad (F-01). El formulario de Backtesting no tiene estos campos: si se enviaran siempre
     * con valores por defecto, Python los tomaría como «enviados» y pisarían lo que diga el JSON de la estrategia
     * (y de ahí el config_params guardado y las configs de Paper/Real que se implementan desde él).
     * Solo se envía lo que vino en el request; 'none' = apagada explícitamente.
     *
     * @param array<string, mixed> $input  $request->all()
     * @return array<string, mixed>
     */
    public static function volatility(array $input): array
    {
        $out = [];
        $filled = static fn (string $k): bool => array_key_exists($k, $input) && $input[$k] !== null && $input[$k] !== '';
        if ($filled('volatility_protection_mode')) {
            $mode = strtolower(trim((string) $input['volatility_protection_mode']));
            $out['volatility_protection_mode'] = $mode === 'none' ? null : $mode;
        }
        foreach (['volatility_atr_multiplier', 'volatility_widen_pct'] as $k) {
            if ($filled($k)) {
                $out[$k] = (float) $input[$k];
            }
        }

        return $out;
    }
}

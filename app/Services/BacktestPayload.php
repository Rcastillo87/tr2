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

    /**
     * F-03: primer error de un payload de /v1/backtest/run según backtesting/request_rules.json (las mismas reglas
     * que valida Python en BacktestRequest), o null si es válido. Solo se validan los campos presentes.
     *
     * @param array<string, mixed> $payload
     */
    public static function validate(array $payload, ?string $rulesFile = null): ?string
    {
        $rules = self::rules($rulesFile);
        foreach ($rules['fields'] as $name => $r) {
            if (! array_key_exists($name, $payload)) {
                continue;
            }
            $err = self::fieldError($r, $payload[$name]);
            if ($err !== null) {
                return $err;
            }
        }
        foreach ($rules['cross'] as $c) {
            if ($c['rule'] === 'le') {
                $a = $payload[$c['a']] ?? null;
                $b = $payload[$c['b']] ?? null;
                if (is_numeric($a) && is_numeric($b) && (float) $a > (float) $b) {
                    return $c['message'];
                }
            } elseif ($c['rule'] === 'requires_when' && ($payload[$c['field']] ?? null) === $c['equals']) {
                $need = $payload[$c['needs']] ?? ($payload['strategy_config'][$c['needs']] ?? null);
                if (! is_array($need) || $need === []) {
                    return $c['message'];
                }
            }
        }

        return null;
    }

    /**
     * F-05: el JSON editado en el formulario se FUSIONA sobre la configuración de la estrategia (por clave de primer
     * nivel): las claves que no se escriben se conservan. Antes lo reemplazaba entero y una clave omitida se perdía.
     *
     * @param array<string, mixed> $base
     * @param array<string, mixed> $override
     * @return array<string, mixed>
     */
    public static function mergeConfig(array $base, array $override): array
    {
        return array_replace($base, $override);
    }

    /** @return array{fields: array<string, array<string, mixed>>, cross: list<array<string, mixed>>} */
    private static function rules(?string $file): array
    {
        static $cache = [];
        $file ??= dirname(__DIR__, 2) . '/python-engine/backtesting/request_rules.json';
        return $cache[$file] ??= json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
    }

    private static function fieldError(array $r, mixed $v): ?string
    {
        $label = $r['label'];
        if ($r['type'] === 'enum') {
            if (in_array($v, $r['values'], true)) {
                return null;
            }
            $ok = implode(', ', array_map(fn ($x) => $x === null ? 'ninguno' : (string) $x, $r['values']));
            return sprintf("%s: valor no válido (%s); se admite: %s.", $label, var_export($v, true), $ok);
        }
        if ($v === null) {
            return ! empty($r['nullable']) ? null : "{$label}: es obligatorio.";
        }
        if (is_bool($v) || ! is_numeric($v) || ! is_finite((float) $v)) {
            return sprintf('%s: debe ser un número (recibido: %s).', $label, var_export($v, true));
        }
        $x = (float) $v;
        if ($r['type'] === 'int' && floor($x) !== $x) {
            return sprintf('%s: debe ser un número entero (recibido: %s).', $label, self::num($x));
        }
        $bounds = ['gt' => [fn ($a, $b) => $a > $b, 'mayor que'], 'ge' => [fn ($a, $b) => $a >= $b, 'mayor o igual que'],
                   'lt' => [fn ($a, $b) => $a < $b, 'menor que'], 'le' => [fn ($a, $b) => $a <= $b, 'menor o igual que']];
        $want = [];
        $bad = false;
        foreach ($bounds as $k => [$ok, $word]) {
            if (array_key_exists($k, $r)) {
                $want[] = $word . ' ' . self::num((float) $r[$k]);
                $bad = $bad || ! $ok($x, (float) $r[$k]);
            }
        }

        return $bad ? sprintf('%s: debe ser %s (recibido: %s).', $label, implode(' y ', $want), self::num($x)) : null;
    }

    private static function num(float $x): string
    {
        return rtrim(rtrim(sprintf('%.10F', $x), '0'), '.') ?: '0';
    }
}

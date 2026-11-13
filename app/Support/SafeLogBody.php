<?php

namespace App\Support;

/**
 * R-07 (p65): respuesta del motor apta para el log. Los pedidos Real llevan las claves del broker; si el motor las
 * devolviera (p. ej. un 422 que repite el pedido), no deben llegar a laravel.log. Tapa el valor de cualquier clave
 * cuyo nombre contenga api_key, api_secret, secret, password o token (JSON o texto «clave=valor») y recorta el largo.
 */
final class SafeLogBody
{
    public const MAX = 2000;

    private const KEYS = 'api[_-]?key|api[_-]?secret|secret|password|passwd|token';

    public static function of(?string $body, int $max = self::MAX): string
    {
        $body = (string) $body;
        $k = self::KEYS;
        // "clave": "valor"   (JSON, con o sin espacios; valores con comillas escapadas incluidos)
        $body = preg_replace('/("[^"]*(?:' . $k . ')[^"]*"\s*:\s*)"(?:[^"\\\\]|\\\\.)*"/i', '$1"***"', $body) ?? '';
        // clave=valor / clave: valor   (texto plano)
        $body = preg_replace('/\b([\w-]*(?:' . $k . ')[\w-]*)(\s*[=:]\s*)(?!["\s*])[^\s,&;"}]+/i', '$1$2***', $body) ?? '';

        return mb_strlen($body) > $max ? mb_substr($body, 0, $max) . '…[recortado]' : $body;
    }
}

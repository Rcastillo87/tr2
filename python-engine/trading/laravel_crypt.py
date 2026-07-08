"""
Descifrado de valores encriptados por Laravel (cast 'encrypted' de Eloquent).
Necesario porque el collector lee credenciales de broker_accounts directo
de Postgres via asyncpg, sin pasar por Laravel (que normalmente desencripta
via el cast del modelo antes de exponer el valor).

Formato Laravel: el valor en DB es base64(json({iv, value, mac, tag})),
donde 'value' es el ciphertext en base64, 'iv' el vector de inicializacion
en base64, y 'mac' un HMAC-SHA256 sobre iv+value (usando APP_KEY) para
verificar integridad antes de desencriptar.
"""

import base64
import hashlib
import hmac
import json
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def _get_app_key() -> bytes:
    app_key = os.getenv('APP_KEY', '')
    if app_key.startswith('base64:'):
        app_key = app_key[len('base64:'):]
    return base64.b64decode(app_key)


def laravel_decrypt(encrypted_value: str) -> str:
    """
    Desencripta un valor guardado por Laravel con cast 'encrypted'
    (AES-256-CBC + HMAC-SHA256, segun config('app.cipher')).
    Lanza ValueError si el MAC no coincide (integridad comprometida)
    o el formato es invalido.
    """
    key = _get_app_key()

    try:
        payload = json.loads(base64.b64decode(encrypted_value))
    except Exception as e:
        raise ValueError(f"payload no es JSON base64 valido: {e}") from e

    iv        = base64.b64decode(payload['iv'])
    value_b64 = payload['value']
    mac       = payload['mac']

    # Verificar MAC: HMAC-SHA256(iv_b64 + value_b64, key)
    iv_b64 = base64.b64encode(iv).decode()
    computed_mac = hmac.new(key, (iv_b64 + value_b64).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_mac, mac):
        raise ValueError("MAC invalido - el valor pudo haber sido alterado o el APP_KEY no coincide")

    ciphertext = base64.b64decode(value_b64)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()

    # Laravel serializa el valor original con serialize() de PHP antes de
    # encriptar (incluso para strings). Para un string simple, el formato
    # es s:{len}:"{contenido}";  - lo parseamos aca.
    text = plaintext.decode('utf-8')
    return _unserialize_php_string(text)


def _unserialize_php_string(s: str) -> str:
    """
    Parsea el formato serialize() de PHP para strings: s:{len}:"{contenido}";
    Si no matchea ese patron, devuelve el string tal cual (fallback).
    """
    import re
    m = re.match(r'^s:(\d+):"(.*)";$', s, re.DOTALL)
    if m:
        return m.group(2)
    return s

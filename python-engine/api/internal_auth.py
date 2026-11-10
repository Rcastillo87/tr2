"""
Autenticación interna Laravel → motor (cabecera X-Internal-API-Key). Falla CERRADA: sin INTERNAL_API_KEY configurada
ningún pedido pasa (N-12: antes, variable y cabecera ausentes daban None == None y pasaban). Comparación en tiempo
constante.
"""
import hmac
import os

HEADER = 'X-Internal-API-Key'


def configured_key() -> str:
    return os.getenv('INTERNAL_API_KEY') or ''


def key_ok(received: str | None, expected: str | None = None) -> bool:
    expected = configured_key() if expected is None else expected
    if not expected or not received:
        return False
    return hmac.compare_digest(received.encode('utf-8'), expected.encode('utf-8'))

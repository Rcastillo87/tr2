"""
Firma de los GET a Bybit: el query string que se FIRMA debe ser exactamente el que se ENVÍA.
Intercepta httpx (no sale nada a internet) y recalcula la firma HMAC con el query real de cada pedido.

Uso (desde python-engine/): venv/bin/python ../tests/Forensic/bybit_sign_test.py
"""
import asyncio
import hashlib
import hmac
import os
import sys
from urllib.parse import urlsplit

sys.path.insert(0, os.getcwd())

import httpx  # noqa: E402

from trading.real_trader import BybitClient  # noqa: E402

KEY, SECRET = 'clave_prueba', 'secreto_prueba'
calls = []
fails = 0


class FakeResp:
    status_code, text = 200, '{}'

    def json(self):
        return {'retCode': 0, 'result': {'list': []}}


class FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, headers=None):
        sent = str(httpx.URL(url, params=params).query, 'utf-8') if params else urlsplit(url).query
        calls.append((urlsplit(url).path, sent, headers))
        return FakeResp()


def check(name, ok, detail=''):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + detail if detail else ''}")


async def main() -> int:
    httpx.AsyncClient = FakeClient
    c = BybitClient(KEY, SECRET, 'demo')
    await c.get_balance()
    await c.get_order('BTCUSDT', 'abc-123')
    try:
        await c.get_open_position('BTCUSDT')
    except Exception:
        pass
    await c.get_closed_pnl_history('BTCUSDT', 0, 0)
    await c.get_native_trailing_level('BTCUSDT')
    for path, sent, h in calls:
        expected = hmac.new(SECRET.encode(), (h['X-BAPI-TIMESTAMP'] + KEY + h['X-BAPI-RECV-WINDOW'] + sent).encode(),
                            hashlib.sha256).hexdigest()
        check(f"firma = query enviado · {path}", expected == h['X-BAPI-SIGN'], f"enviado '{sent}'")
    check('get_order consulta realtime y, si no está, history', [p for p, _, _ in calls].count('/v5/order/history') == 1)
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

"""
Endurecimiento del motor (auditoría 07-nov):
- N-12: autenticación interna que falla CERRADA. Sin INTERNAL_API_KEY: todo pedido salvo /health -> 503 (antes, variable
  y cabecera ausentes daban None == None y pasaban). Con clave: sin cabecera, vacía o distinta -> 401.
- N-14: /collector/add-symbol solo acepta los intervalos de request_rules.json y símbolos con formato de Bybit;
  'inserted' cuenta filas nuevas («INSERT 0 0» no suma).
- N-15: fechas sin zona de /collector/backfill y /collector/invalidate = UTC, sin importar la zona del proceso.
Sin DB ni red. Uso: cd python-engine && venv/bin/python ../tests/Forensic/engine_hardening_test.py
"""
import asyncio
import importlib
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())   # python-engine/
logging.disable(logging.CRITICAL)

import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *a, **k: False   # el .env del servidor no debe colarse en los casos «sin clave»

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def load_app(key):
    if key is None:
        os.environ.pop('INTERNAL_API_KEY', None)
    else:
        os.environ['INTERNAL_API_KEY'] = key
    import main
    return importlib.reload(main).app


# Ruta que no toca la base cuando el pedido es inválido: si llega al router, contesta 400 (no 401/503)
PROBE = ('/v1/collector/add-symbol', {'symbol': 'BTCUSDT', 'broker': 'bybit', 'intervals': ['30']})

# ── N-12 ──
c = TestClient(load_app(None))
check('K1: sin INTERNAL_API_KEY -> /health 200', c.get('/health').status_code == 200)
r = c.post(PROBE[0], json=PROBE[1])
check('K1: sin INTERNAL_API_KEY ni cabecera -> 503 (antes pasaba: None == None)', r.status_code == 503, r.status_code)
r = c.post(PROBE[0], json=PROBE[1], headers={'X-Internal-API-Key': 'cualquiera'})
check('K1: sin INTERNAL_API_KEY y cabecera inventada -> 503', r.status_code == 503, r.status_code)

c = TestClient(load_app('clave-de-prueba'))
for name, hdr in (('sin cabecera', {}), ('cabecera vacía', {'X-Internal-API-Key': ''}),
                  ('clave distinta', {'X-Internal-API-Key': 'otra'}), ('prefijo de la clave', {'X-Internal-API-Key': 'clave'})):
    r = c.post(PROBE[0], json=PROBE[1], headers=hdr)
    check(f'K2: con clave configurada, {name} -> 401', r.status_code == 401, r.status_code)
r = c.post(PROBE[0], json=PROBE[1], headers={'X-Internal-API-Key': 'clave-de-prueba'})
check('K3: clave correcta -> llega al router (400 por el intervalo, no 401/503)', r.status_code == 400, r.status_code)

from api.internal_auth import key_ok  # noqa: E402
check('K4: key_ok(None, None) y key_ok("", "") son False', key_ok(None, None) is False and key_ok('', '') is False)

# ── N-14 ──
import api.v1.collector as col  # noqa: E402


class Conn:
    def __init__(self, s):
        self.s = s

    def transaction(self):                    # delete_bars (p44) borra dentro de una transacción
        class _T:
            async def __aenter__(self_):
                return self_

            async def __aexit__(self_, *e):
                return False
        return _T()

    async def fetchval(self, sql, *a):
        self.s.append(a)
        return 0

    async def fetch(self, sql, *a):
        self.s.append(a)
        return []

    async def execute(self, sql, *a):
        self.s.append(a)
        if 'INSERT INTO collector_configs' in sql:
            return 'INSERT 0 0' if a[1] == '60' else 'INSERT 0 1'     # 60 ya existía
        return 'DELETE 0'


class Pool:
    def __init__(self, s):
        self.s = s

    def acquire(self):
        pool = self

        class _C:
            async def __aenter__(self_):
                return Conn(pool.s)

            async def __aexit__(self_, *e):
                return False
        return _C()

    async def close(self):
        pass


calls: list = []


async def fake_pool():
    return Pool(calls)


col.get_pool = fake_pool


async def add(symbol, intervals):
    calls.clear()
    try:
        return await col.collector_add_symbol(col.AddSymbolRequest(symbol=symbol, broker='bybit', intervals=intervals))
    except HTTPException as e:
        return e


r = asyncio.run(add('BTCUSDT', ['30']))
check('S1: intervalo 30 -> 400 con la lista admitida y sin escribir', isinstance(r, HTTPException) and r.status_code == 400
      and 'se admite: 1, 5, 15, 60, 120, 240, D' in str(r.detail) and not calls, getattr(r, 'detail', r))
r = asyncio.run(add('BTC/USDT', ['60']))
check('S2: símbolo con «/» -> 400 sin escribir', isinstance(r, HTTPException) and r.status_code == 400 and not calls,
      getattr(r, 'detail', r))
r = asyncio.run(add(' ethusdt ', ['1', '60', '60', '240']))
check('S3: símbolo normalizado a ETHUSDT e intervalos sin repetir (1, 60, 240)',
      isinstance(r, dict) and [x[1] for x in calls] == ['1', '60', '240'] and all(x[0] == 'ETHUSDT' for x in calls),
      calls)
check('S4: inserted = 2 (60 ya existía: «INSERT 0 0» no cuenta)', isinstance(r, dict) and r.get('inserted') == 2,
      r.get('inserted') if isinstance(r, dict) else r)
r = asyncio.run(add('ETHUSDT', []))
check('S5: lista de intervalos vacía -> 400', isinstance(r, HTTPException) and r.status_code == 400, getattr(r, 'detail', r))

# ── N-15 ──
os.environ['TZ'] = 'America/Bogota'
time.tzset()
check('T1: fecha sin zona = medianoche UTC aunque el proceso esté en Bogotá',
      col.utc_datetime('2026-03-01') == datetime(2026, 3, 1, tzinfo=timezone.utc)
      and int(col.utc_datetime('2026-03-01').timestamp()) == 1772323200, col.utc_datetime('2026-03-01'))
check('T2: fecha con zona -05:00 se convierte (00:00 Bogotá = 05:00 UTC)',
      col.utc_datetime('2026-03-01T00:00:00-05:00') == datetime(2026, 3, 1, 5, tzinfo=timezone.utc))

seen = {}


class FakeCollector:
    def __init__(self, pool):
        pass

    async def fetch_from_bybit(self, symbol, interval, start_ts, end_ts):
        seen['range'] = (start_ts, end_ts)
        return []

    async def insert_bars(self, *a, **k):
        return 0


import collectors.ohlcv_collector as oc  # noqa: E402
oc.OhlcvCollector = FakeCollector
try:
    asyncio.run(col.collector_backfill(col.BackfillRequest(symbol='BTCUSDT', interval='60', broker='bybit',
                                                           start_date='2026-03-01', end_date='2026-03-02')))
except Exception:
    pass
check('T3: backfill pide a Bybit desde 2026-03-01 00:00 UTC hasta 2026-03-02 00:00 UTC (no hora de Bogotá)',
      seen.get('range') == (1772323200, 1772409600), seen.get('range'))

calls.clear()
asyncio.run(col.collector_invalidate(col.InvalidateRequest(symbol='BTCUSDT', interval='60', broker='bybit',
                                                           start_date='2026-03-01T00:00:00-05:00', confirm=True)))
arg = calls[0][3] if calls and len(calls[0]) > 3 else None
check('T4: invalidate compara la columna (timestamptz) con 05:00 UTC', arg == datetime(2026, 3, 1, 5, 0, tzinfo=timezone.utc), arg)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

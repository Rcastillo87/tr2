"""
Funding en la reparación diaria (C-12): collector_repair pone al día el funding de Bybit de las monedas activas del
collector (desde lo ya cubierto) e informa el atraso; > FUNDING_STALE_HOURS (30 h) va a `stale` (aviso en la campana).
Un fallo de una moneda no frena las demás ni la reparación. Sin base de datos ni Bybit.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/funding_refresh_test.py
Antes del parche: FALLA (la reparación no refresca el funding).
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/

import cli.collector_repair as cr  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
ACTIVE = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'NEWUSDT']
COV = {}
CALLS = []


class Conn:
    async def fetch(self, sql, *a):
        assert "collector_configs WHERE broker = 'bybit' AND active" in sql, sql
        return [{'symbol': x} for x in ACTIVE]


class Pool:
    def acquire(self):
        class _C:
            async def __aenter__(self):
                return Conn()

            async def __aexit__(self, *e):
                return False
        return _C()

    async def close(self):
        pass


async def _create_pool(*a, **k):
    return Pool()


async def _coverage(pool, symbol):
    return (None, COV.get(symbol)) if symbol in COV else (None, None)


MODE = {}


async def _load(pool, symbol, start, end, client=None, now=None):
    CALLS.append((symbol, start, end))
    m = MODE.get(symbol, 'ok')
    if m == 'raise':
        raise RuntimeError('timeout de red')
    if m == 'fail':
        return None, [f'Aviso: funding de {symbol} no descargado de Bybit (HTTP 503).']
    COV[symbol] = NOW - timedelta(minutes=5)   # al día (menos el margen de publicación)
    return None, []


if not hasattr(cr, 'refresh_funding'):
    check('collector_repair.refresh_funding existe', False, 'no existe (código anterior)')
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)

cr.asyncpg.create_pool, cr._coverage, cr.load_funding = _create_pool, _coverage, _load


def reset(cov, mode=None):
    COV.clear()
    COV.update(cov)
    CALLS.clear()
    MODE.clear()
    MODE.update(mode or {})


async def main():
    old = NOW - timedelta(days=6, hours=21)
    # 1. Todas al día: se descarga desde lo ya cubierto hasta ahora
    reset({'BTCUSDT': old, 'ETHUSDT': NOW - timedelta(hours=9), 'SOLUSDT': old, 'NEWUSDT': old})
    f = await cr.refresh_funding(None, False, NOW)
    check('refresca las 4 monedas activas desde su covered_to hasta ahora',
          [(c[0], c[1]) for c in CALLS] == [('BTCUSDT', old), ('ETHUSDT', NOW - timedelta(hours=9)), ('SOLUSDT', old),
                                             ('NEWUSDT', old)] and all(c[2] == NOW for c in CALLS), CALLS)
    check('tras refrescar: ninguna atrasada, 0 errores, atraso ~0,1 h',
          f['stale'] == [] and f['errors'] == 0 and all(r['lag_h'] == 0.1 and r['refreshed'] for r in f['symbols']), f)

    # 2. Bybit falla para una moneda: error, se mantiene su atraso y va a stale; las demás siguen
    reset({'BTCUSDT': old, 'ETHUSDT': old, 'SOLUSDT': old, 'NEWUSDT': old}, {'ETHUSDT': 'fail', 'SOLUSDT': 'raise'})
    f = await cr.refresh_funding(None, False, NOW)
    st = {x['symbol']: x['lag_h'] for x in f['stale']}
    check('fallo de Bybit (aviso) y excepción: 2 errores, las otras 2 al día',
          f['errors'] == 2 and set(st) == {'ETHUSDT', 'SOLUSDT'} and len(CALLS) == 4, (f['errors'], st))
    check('atraso de la moneda que falló = 165 h (6 d 21 h)', st.get('ETHUSDT') == 165.0, st)

    # 3. Moneda que nunca tuvo funding: empieza en FUNDING_SINCE; si sigue sin cobertura, stale con lag None
    reset({'BTCUSDT': old, 'ETHUSDT': old, 'SOLUSDT': old}, {'NEWUSDT': 'fail'})
    f = await cr.refresh_funding(None, False, NOW)
    first = [c for c in CALLS if c[0] == 'NEWUSDT']
    check('sin cobertura previa: descarga desde 2024-06-01', first and first[0][1] == cr.FUNDING_SINCE, first)
    check('sin cobertura tras fallar: stale con lag None', {'symbol': 'NEWUSDT', 'lag_h': None} in f['stale'], f['stale'])

    # 4. Simulación (--dry-run): no descarga, solo informa el atraso
    reset({'BTCUSDT': old, 'ETHUSDT': old, 'SOLUSDT': old, 'NEWUSDT': old})
    f = await cr.refresh_funding(None, True, NOW)
    check('dry-run: no descarga y reporta las 4 atrasadas', not CALLS and len(f['stale']) == 4 and f['dry_run'], CALLS)

    # 5. --solo filtra
    reset({'BTCUSDT': old, 'ETHUSDT': old, 'SOLUSDT': old, 'NEWUSDT': old})
    f = await cr.refresh_funding({'BTCUSDT'}, False, NOW)
    check('--solo BTCUSDT: solo esa moneda', [c[0] for c in CALLS] == ['BTCUSDT'] and len(f['symbols']) == 1, CALLS)

    # 6. Integrado en run(): el resultado trae `funding`, y corre ANTES de la auditoría histórica
    seen = {}

    async def _validate(n, only):
        return {'at': 'x', 'series': [], 'summary': {'series': 0, 'ok': 0}}

    async def _audit(result, *a, **k):
        seen['funding_before_audit'] = 'funding' in result
        return result
    cr.validate, cr._audit = _validate, _audit
    reset({'BTCUSDT': old, 'ETHUSDT': old, 'SOLUSDT': old, 'NEWUSDT': old})
    res = await cr.run(300, 7, None, False, lambda r: None, audit_budget=10)
    check('run(): el resultado trae funding (4 monedas)', len(res.get('funding', {}).get('symbols', [])) == 4, res.keys())
    check('run(): el funding se refresca antes de la auditoría histórica', seen.get('funding_before_audit') is True, seen)
    res = await cr.run(300, 7, None, False, lambda r: None, audit_budget=0, funding=False)
    check('run(funding=False): sin sección funding', 'funding' not in res, res.keys())

    check('umbral por defecto 30 h (FUNDING_STALE_HOURS)', cr.FUNDING_STALE_HOURS == 30.0, cr.FUNDING_STALE_HOURS)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

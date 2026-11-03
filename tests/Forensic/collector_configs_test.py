"""
C-01: collector_configs es la ÚNICA fuente de series del collector y del detector de régimen. Sin series activas no se
descarga nada; si la base falla, ese ciclo no corre (sin lista de respaldo del .env). El validador no da «TODO OK» con
0 series. Sin base de datos ni red: pool simulado.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/collector_configs_test.py
"""
import asyncio
import io
import logging
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import api.v1.collector as api_collector  # noqa: E402
import cli.collector_validate as validate_cli  # noqa: E402
from collectors.ohlcv_collector import OhlcvCollector  # noqa: E402
from collectors.regime_detector import RegimeDetector  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Conn:
    def __init__(self, rows, err):
        self.rows, self.err = rows, err

    async def fetch(self, *a):
        if self.err:
            raise RuntimeError('DB caída')
        return self.rows


class Pool:
    def __init__(self, rows=None, err=False):
        self.conn, self.closed = Conn(rows or [], err), False

    def acquire(self):
        c = self.conn

        class _C:
            async def __aenter__(self):
                return c

            async def __aexit__(self, *e):
                return False
        return _C()

    async def close(self):
        self.closed = True


def collector(pool):
    c = OhlcvCollector.__new__(OhlcvCollector)
    c.pool = pool
    return c


ROWS = [{'symbol': 'BTCUSDT', 'interval': '60', 'broker': 'bybit'}, {'symbol': 'ETHUSDT', 'interval': '240', 'broker': 'bybit'}]


async def main():
    # Collector
    r = await collector(Pool(ROWS)).get_active_configs()
    check('K1 series activas: exactamente las de collector_configs',
          r == [('BTCUSDT', '60', 'bybit'), ('ETHUSDT', '240', 'bybit')], r)
    r = await collector(Pool([])).get_active_configs()
    check('K2 0 series activas: no descarga nada (antes 15 series del .env)', r == [], r)
    try:
        await collector(Pool(err=True)).get_active_configs()
        check('K3 base caída: el error sube (sin lista de respaldo)', False, 'no lanzó')
    except RuntimeError:
        check('K3 base caída: el error sube (sin lista de respaldo)', True)

    c = collector(Pool([]))
    called = []

    async def _update(*a, **k):
        called.append(a)
        return 1
    c.update = _update
    r = await c.run_all({})
    check('K4 run_all con 0 series: no toca Bybit', r == {} and not called, (r, called))

    # Detector de régimen
    det = RegimeDetector.__new__(RegimeDetector)
    det.pool = Pool([{'symbol': 'BTCUSDT'}])
    check('G1 régimen: símbolos de collector_configs', await det.get_active_symbols() == ['BTCUSDT'])
    det.pool = Pool([])
    check('G2 régimen con 0 series: [] (antes BTC/ETH/SOL del .env)', await det.get_active_symbols() == [])
    det.pool = Pool(err=True)
    try:
        await det.get_active_symbols()
        check('G3 régimen con base caída: el error sube', False, 'no lanzó')
    except RuntimeError:
        check('G3 régimen con base caída: el error sube', True)

    # Endpoint /collector/run: error de base -> 500 y el pool se cierra
    pool = Pool(err=True)

    async def _get_pool():
        return pool
    api_collector.get_pool = _get_pool
    try:
        await api_collector.run_collector()
        check('E1 /collector/run con base caída: responde error', False, 'no lanzó')
    except Exception as e:  # noqa: BLE001 - HTTPException
        check('E1 /collector/run con base caída: responde error 500', getattr(e, 'status_code', None) == 500, repr(e))
    check('E2 /collector/run con error: cierra el pool (antes quedaba abierto)', pool.closed)



def validator_case():
    """Fuera del bucle async: el validador usa asyncio.run por dentro."""
    async def _validate(*a, **k):
        return {'summary': validate_cli.summarize([]), 'duration_s': 0.1, 'series': []}
    validate_cli.validate = _validate
    sys.argv = ['collector_validate.py', '--quiet']
    out = io.StringIO()
    with redirect_stdout(out):
        rc = validate_cli.main()
    check('V1 validador con 0 series: código 1 y lo dice', rc == 1 and 'sin series activas' in out.getvalue(),
          (rc, out.getvalue().strip()[-80:]))



if __name__ == '__main__':
    asyncio.run(main())
    validator_case()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)

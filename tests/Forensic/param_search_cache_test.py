"""
Caché de velas de 1m de la búsqueda (load_backtest_data minute_cache): una sola carga por moneda, el MISMO DataFrame
para todas las temporalidades e idéntico a cargarlo sin caché. Solo lectura sobre la DB real.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/param_search_cache_test.py [SÍMBOLO]
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

import cli.param_search as ps  # noqa: E402
from api.v1.backtest import load_backtest_data  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


async def main(symbol):
    from db import close_pools, get_pool
    pool = await get_pool('backtest')
    start, end = ps.ui_period(24)
    try:
        t = time.time()
        plain = {iv: await load_backtest_data(pool, symbol, iv, start, end, macro=True) for iv in ('60', '240')}
        t_plain = time.time() - t
        cache: dict = {}
        t = time.time()
        cached = {iv: await load_backtest_data(pool, symbol, iv, start, end, macro=True, minute_cache=cache)
                  for iv in ('60', '120', '240', 'D')}
        t_cached = time.time() - t
    finally:
        await close_pools()

    m = {iv: d.minute_df for iv, d in cached.items()}
    check('hay velas de 1m', m['60'] is not None and len(m['60']) > 100_000, None if m['60'] is None else len(m['60']))
    check('una sola carga para las 4 temporalidades', len(cache) == 1, len(cache))
    check('mismo DataFrame en 1h, 2h, 4h y 1D (sin copias)', all(m[iv] is m['60'] for iv in m))
    for iv in ('60', '240'):
        a, b = plain[iv], cached[iv]
        check(f'{iv}: velas de 1m idénticas a la carga sin caché', a.minute_df.equals(b.minute_df))
        check(f'{iv}: velas principales y H4 idénticas', a.df.equals(b.df) and a.macro_df.equals(b.macro_df))
        check(f'{iv}: misma cobertura y mismos avisos', a.coverage == b.coverage and a.warnings == b.warnings)
    print(f"\nTiempo: sin caché 2 temporalidades {t_plain:.1f}s · con caché 4 temporalidades {t_cached:.1f}s")


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'BTCUSDT'))
    print('RESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)

"""
D-36 (dueño, 19-nov): con huecos en las velas el backtest se hace igual y el «Log de Errores» (warnings) dice cuántos
huecos hay, cuántas velas faltan y el mayor, con fechas, aunque la completitud supere el 98 %. D-37: la regla
«< 98 % = no apto para Paper» no cambia (aviso de cobertura de siempre). Sin DB.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/backtest_gaps_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import pandas as pd  # noqa: E402

import api.v1.backtest as api  # noqa: E402
from collectors.broker_resolver import SourceCoverage  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


UTC = timezone.utc
H = timedelta(hours=1)
T0 = datetime(2026, 1, 1, tzinfo=UTC)
cg = getattr(api, 'candle_gaps', None)
gw = getattr(api, 'gaps_warning', None)
check('G0 existen candle_gaps y gaps_warning', cg is not None and gw is not None)
if cg is None or gw is None:
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)

full = [T0 + k * H for k in range(1000)]
drop = set(range(100, 103)) | {500} | set(range(700, 710))     # 3 + 1 + 10 = 14 faltantes (98,6 % completo)
times = [t for k, t in enumerate(full) if k not in drop]
g = cg(times, H, T0, T0 + 1000 * H)
check('G1 detecta los 3 huecos con sus velas faltantes', [x[2] for x in g] == [3, 1, 10], g)
check('G2 fechas: primera y última vela faltante', g[2][0] == pd.Timestamp(T0 + 700 * H) and g[2][1] == pd.Timestamp(T0 + 709 * H), g[2])
w = gw('BTCUSDT 60', g)
check('G3 aviso: cuántos, total y el mayor con fechas', w and '3 hueco(s)' in w and '14 vela(s) faltantes' in w
      and 'el mayor: 10 vela(s) del 2026-01-30 04:00 al 2026-01-30 13:00 UTC' in w, w)
check('G4 sin huecos: sin aviso', gw('X', cg(full, H, T0, T0 + 1000 * H)) is None)
check('G5 solo dentro del rango pedido (el calentamiento no cuenta)', cg(times, H, T0 + 200 * H, T0 + 600 * H) == [(pd.Timestamp(T0 + 500 * H), pd.Timestamp(T0 + 500 * H), 1)],
      cg(times, H, T0 + 200 * H, T0 + 600 * H))
check('G6 fechas sin zona se toman como UTC', cg(times, H, (T0 + 200 * H).replace(tzinfo=None), (T0 + 600 * H).replace(tzinfo=None))[0][2] == 1)


# ── Integración con load_backtest_data: el aviso llega a warnings, el backtest no se corta ──
async def integ():
    df = pd.DataFrame({'time': pd.to_datetime(times, utc=True), 'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.0,
                       'volume': 1.0})
    src = SourceCoverage('bybit', 'BTCUSDT', '60', T0, T0 + 1000 * H, T0, T0 + 999 * H, len(times))

    async def _resolve(pool, symbol, interval, start, end):
        return src if interval == '60' else None

    async def _load(pool, symbol, interval, broker, a, b):
        return df

    async def _funding(*a, **k):
        from collectors.funding_collector import FundingData
        import numpy as np
        return FundingData(a[1] if len(a) > 1 else 'BTCUSDT', np.array([], dtype='datetime64[ns]'), np.array([], dtype=float), T0, T0)

    api.resolve_backtest_source, api.load_ohlcv = _resolve, _load
    if hasattr(api, 'load_funding'):
        api.load_funding = _funding
    data = await api.load_backtest_data(None, 'BTCUSDT', '60', T0, T0 + 1000 * H, macro=False)
    gaps = [x for x in data.warnings if 'hueco(s) en las velas' in x]
    check('I1 el aviso de huecos llega al Log de Errores aunque esté 98,6 % completo', len(gaps) == 1, data.warnings)
    check('I2 D-37: con ≥ 98 % no hay aviso de cobertura «huecos» (no se marca no apto)',
          not any('velas faltantes (' in x for x in data.warnings), data.warnings)
    check('I3 los datos se cargan completos (el backtest se hace igual)', len(data.df) == len(times))

try:
    asyncio.run(integ())
except Exception as e:
    check('I0 integración con load_backtest_data', False, repr(e)[:300])

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

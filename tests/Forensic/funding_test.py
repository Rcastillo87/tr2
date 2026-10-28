"""
Funding de Bybit en el backtest: cálculo por trade (motor) y descarga/caché (collector).
El collector usa la DB real con un símbolo de prueba (TESTFUNDUSDT) que se borra al terminar; Bybit es simulado.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/funding_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())  # python-engine/

import asyncpg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

import collectors.funding_collector as fc  # noqa: E402
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.metrics import calculate_metrics  # noqa: E402
from backtesting.strategies.base_strategy import BaseStrategy  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


# ─────────────────────────────── motor ───────────────────────────────

class Sig(BaseStrategy):
    idx: set = set()
    side = 1

    def generate_signals(self, df):
        df = df.copy()
        df['signal'] = 0
        df.loc[df.index.isin(self.idx), 'signal'] = self.side
        return df


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
P = dict(symbol='X', interval='60', sl_pct=1.0, tp_pct=50.0, be_pct=40.0, max_duration=10, regime_filter=False,
         commission_pct=0.0)


def mk(n=40):
    return pd.DataFrame({'time': [T0 + timedelta(hours=i) for i in range(n)], 'open': 100.0, 'high': 100.5,
                         'low': 99.5, 'close': 100.0, 'volume': 1.0})


def fd(points):
    """FundingData de [(hora desde T0, tasa)]."""
    times = np.array([np.datetime64((T0 + timedelta(hours=h)).replace(tzinfo=None), 'ns') for h, _ in points],
                     dtype='datetime64[ns]')
    return fc.FundingData('X', times, np.array([r for _, r in points], dtype=float), None, None)


def run(points, side=1, df=None, minute_df=None, **extra):
    s = Sig({**P, **extra})
    s.idx, s.side = {10}, side
    return BacktestEngine(s, df if df is not None else mk(), minute_df=minute_df,
                          funding=fd(points) if points is not None else None).run()


def engine_tests():
    # Señal en 10 -> entrada 11:00 al open (100); max_duration 10 -> salida al cierre de la vela 20 (21:00)
    base = run(None)['trades'][0]
    size = base['size']
    check('sin funding: campo funding = 0 y pnl igual que antes', base['funding'] == 0.0 and base['pnl'] == base['gross_pnl'])
    check('salida por tiempo a las 21:00', base['exit_reason'] == 'time_exit' and pd.Timestamp(base['exit_time']).hour == 21,
          (base['exit_reason'], base['exit_time']))

    t = run([(16, 0.0001)])['trades'][0]
    exp = size * 100.0 * 0.0001
    check('long con funding +0,01 % a las 16:00 -> paga size·precio·tasa', abs(t['funding'] - exp) < 1e-9, (t['funding'], exp))
    check('pnl = bruto − comisión − funding', abs(t['pnl'] - (t['gross_pnl'] - t['commission'] - t['funding'])) < 1e-3)

    t = run([(16, 0.0001)], side=-1, allow_short=True)['trades'][0]
    check('short con funding + -> cobra (funding negativo)', abs(t['funding'] + exp) < 1e-9, t['funding'])

    t = run([(8, 0.01), (22, 0.01)])['trades'][0]
    check('liquidaciones fuera del trade no cuentan', t['funding'] == 0.0, t['funding'])

    t = run([(11, 0.0001)])['trades'][0]
    check('borde entrada: el pago a la hora exacta de entrada cuenta (pesimista)', abs(t['funding'] - exp) < 1e-9, t['funding'])
    t = run([(11, -0.0001)])['trades'][0]
    check('borde entrada: el cobro a la hora exacta de entrada NO cuenta', t['funding'] == 0.0, t['funding'])
    t = run([(21, 0.0001)])['trades'][0]
    check('borde salida: el pago a la hora exacta de salida cuenta', abs(t['funding'] - exp) < 1e-9, t['funding'])
    t = run([(21, -0.0001)])['trades'][0]
    check('borde salida: el cobro a la hora exacta de salida NO cuenta', t['funding'] == 0.0, t['funding'])

    t = run([(12, 0.0001), (16, -0.0002), (20, 0.0001)])['trades'][0]
    check('neto de varias liquidaciones (+1 −2 +1 = 0)', abs(t['funding']) < 1e-9, t['funding'])

    # SL dentro de la vela 13 (13:00-14:00) sin 1m: momento exacto desconocido
    df = mk()
    df.loc[13, 'low'] = 98.0
    t = run([(13, 0.0001), (14, 0.0001)], df=df)['trades'][0]
    check('SL dentro de la vela: paga la de 13:00, no la de 14:00', t['exit_reason'] == 'stop_loss'
          and abs(t['funding'] - exp) < 1e-9, (t['exit_reason'], t['funding']))
    t = run([(13, -0.0001)], df=df)['trades'][0]
    check('SL dentro de la vela: el cobro de 13:00 NO cuenta (pudo salir antes)', t['funding'] == 0.0, t['funding'])

    # Con velas de 1m: SL en el minuto 13:40 -> el cobro de 13:00 sí cuenta; precio = cierre del minuto previo
    df = mk()
    df.loc[13, 'low'] = 98.0
    mins = [T0 + timedelta(hours=11, minutes=k) for k in range(180)]
    mdf = pd.DataFrame({'time': mins, 'open': 100.0, 'high': 100.4, 'low': 99.6, 'close': 100.0, 'volume': 1.0})
    mdf.loc[mdf['time'] == T0 + timedelta(hours=12, minutes=59), 'close'] = 110.0   # precio a las 13:00
    mdf.loc[mdf['time'] == T0 + timedelta(hours=13, minutes=40), 'low'] = 98.0
    t = run([(13, -0.0001)], df=df, minute_df=mdf)['trades'][0]
    check('1m: SL a las 13:40 -> cobra la de 13:00 al precio del minuto previo (110)',
          t['exit_reason'] == 'stop_loss' and abs(t['funding'] + size * 110.0 * 0.0001) < 1e-9, (t['exit_reason'], t['funding']))

    r = run([(16, 0.0001)])
    check('métrica total_funding', r['metrics']['total_funding'] == round(exp, 2), r['metrics']['total_funding'])
    check('métricas vacías incluyen total_funding', calculate_metrics([])['total_funding'] == 0.0)


# ─────────────────────────────── collector ───────────────────────────────

SYM = 'TESTFUNDUSDT'
SETTLE = [datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=8 * k) for k in range(3 * 400)]   # 400 días


class FakeResp:
    def __init__(self, data, status=200):
        self.status_code, self._data, self.request = status, data, None

    def json(self):
        return self._data


class FakeBybit:
    def __init__(self, fail=None):
        self.calls, self.fail = [], list(fail or [])   # fail: lista de respuestas a devolver antes de las buenas

    async def get(self, url, params=None):
        self.calls.append(dict(params))
        if self.fail:
            f = self.fail.pop(0)
            if isinstance(f, Exception):
                raise f
            return FakeResp(f)
        lo, hi = params['startTime'], params['endTime']
        rows = [t for t in SETTLE if lo <= int(t.timestamp() * 1000) <= hi]
        rows = sorted(rows, reverse=True)[:params['limit']]   # Bybit: más recientes primero
        return FakeResp({'retCode': 0, 'result': {'list': [
            {'symbol': SYM, 'fundingRate': str(rate_of(t)), 'fundingRateTimestamp': str(int(t.timestamp() * 1000))}
            for t in rows]}})


def rate_of(t):
    return round(0.0001 * ((t.hour // 8) + 1) * (1 if t.day % 2 else -1), 8)


async def collector_tests(pool):
    async def nosleep(*_):
        return None
    fc.asyncio.sleep = nosleep
    d = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731
    NOW = d(2026, 3, 1)

    # 1. Primera carga: 120 días = 360 liquidaciones -> 2 páginas
    bb = FakeBybit()
    f, w = await fc.load_funding(pool, SYM, d(2025, 3, 1), d(2025, 6, 29), client=bb, now=NOW)
    exp = [t for t in SETTLE if d(2025, 3, 1) <= t <= d(2025, 6, 29)]
    check('carga inicial: todas las liquidaciones del rango', len(f.times) == len(exp) == 361, (len(f.times), len(exp)))
    check('carga inicial: paginado (2 llamadas de 200)', len(bb.calls) == 2, len(bb.calls))
    check('carga inicial: tasas correctas', abs(f.rates[0] - rate_of(exp[0])) < 1e-12 and abs(f.rates[-1] - rate_of(exp[-1])) < 1e-12)
    check('carga inicial: sin avisos y tramo cubierto', not w and f.covered_from == d(2025, 3, 1) and f.covered_to == d(2025, 6, 29), (w, f.covered_from, f.covered_to))

    # 2. Mismo rango -> sin llamadas (caché en la DB)
    bb = FakeBybit()
    f2, w = await fc.load_funding(pool, SYM, d(2025, 3, 1), d(2025, 6, 29), client=bb, now=NOW)
    check('mismo rango: no consulta Bybit', not bb.calls and len(f2.times) == 361, len(bb.calls))

    # 3. Extensión a la derecha: solo el borde nuevo
    bb = FakeBybit()
    f3, w = await fc.load_funding(pool, SYM, d(2025, 4, 1), d(2025, 7, 10), client=bb, now=NOW)
    check('extensión: solo descarga desde el borde cubierto', bb.calls and min(c['startTime'] for c in bb.calls) == int(d(2025, 6, 29).timestamp() * 1000), bb.calls[:1])
    check('extensión: tramo cubierto crece', f3.covered_to == d(2025, 7, 10) and not w, (f3.covered_to, w))

    # 4. Rango anterior sin contacto: descarga hasta el borde cubierto (sin huecos)
    bb = FakeBybit()
    f4, w = await fc.load_funding(pool, SYM, d(2025, 1, 10), d(2025, 1, 20), client=bb, now=NOW)
    check('rango anterior: descarga contigua hasta el tramo cubierto',
          f4.covered_from == d(2025, 1, 10) and f4.covered_to == d(2025, 7, 10) and len(f4.times) == 31, (f4.covered_from, len(f4.times)))
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM funding_rates WHERE symbol = $1 AND funding_time BETWEEN $2 AND $3",
                                SYM, d(2025, 1, 10), d(2025, 7, 10))
    check('rango anterior: sin huecos en la DB', n == len([t for t in SETTLE if d(2025, 1, 10) <= t <= d(2025, 7, 10)]), n)

    # 5. Menos de una hora después del borde, sin hora en punto -> sin llamada
    bb = FakeBybit()
    await fc.load_funding(pool, SYM, d(2025, 5, 1), datetime(2025, 7, 10, 0, 40, tzinfo=timezone.utc), client=bb, now=NOW)
    check('borde sin hora en punto: no consulta Bybit', not bb.calls, bb.calls)

    # 6. El presente: no pide liquidaciones futuras ni sin publicar
    bb = FakeBybit()
    await fc.load_funding(pool, SYM, d(2025, 7, 1), d(2025, 7, 20), client=bb, now=d(2025, 7, 15))
    check('no pide más allá de ahora − 5 min', max(c['endTime'] for c in bb.calls) == int((d(2025, 7, 15) - fc.SETTLE_LAG).timestamp() * 1000))

    # 7. Reintentos: 10006 (límite) y 503 y luego OK
    bb = FakeBybit(fail=[{'retCode': 10006, 'retMsg': 'Too many visits'}, fc.httpx.ConnectTimeout('timeout')])
    f7, w = await fc.load_funding(pool, SYM, d(2025, 7, 1), d(2025, 7, 25), client=bb, now=NOW)
    check('reintenta límite y timeout, luego descarga', not w and f7.covered_to == d(2025, 7, 25), w)

    # 8. Error definitivo -> usa la DB y avisa el tramo sin funding
    bb = FakeBybit(fail=[{'retCode': 10001, 'retMsg': 'params error'}])
    f8, w = await fc.load_funding(pool, SYM, d(2025, 7, 1), d(2025, 8, 5), client=bb, now=NOW)
    check('error de parámetros: un solo intento (no reintenta)', len(bb.calls) == 1, len(bb.calls))
    check('error: avisa el tramo sin funding y usa lo guardado',
          any('sin funding de Bybit' in x and '2025-07-25' in x for x in w) and len(f8.times) > 0, w)

    # 9. Bybit caído -> 3 intentos y aviso
    fc._FAILED.clear()
    bb = FakeBybit(fail=[fc.httpx.ConnectError('down')] * 3)
    f9, w = await fc.load_funding(pool, SYM, d(2025, 7, 1), d(2025, 8, 5), client=bb, now=NOW)
    check('Bybit caído: 3 intentos y aviso', len(bb.calls) == 3 and any('3 intentos' in x for x in w), (len(bb.calls), w))
    bb = FakeBybit()
    f10, w = await fc.load_funding(pool, SYM, d(2025, 7, 1), d(2025, 8, 5), client=bb, now=NOW)
    check('tras un fallo: no reintenta el símbolo durante 10 min (usa lo guardado)',
          not bb.calls and any('falló hace menos' in x for x in w) and len(f10.times) > 0, (len(bb.calls), w))
    fc._FAILED.clear()
    f11, w = await fc.load_funding(pool, SYM, d(2025, 7, 1), d(2025, 8, 5), client=bb, now=NOW)
    check('pasado el bloqueo: descarga y cubre el tramo', bb.calls and not w and f11.covered_to == d(2025, 8, 5), w)


async def main():
    engine_tests()
    dsn = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
           f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM funding_rates WHERE symbol = $1", SYM)
            await conn.execute("DELETE FROM funding_coverage WHERE symbol = $1", SYM)
        await collector_tests(pool)
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM funding_rates WHERE symbol = $1", SYM)
            await conn.execute("DELETE FROM funding_coverage WHERE symbol = $1", SYM)
        await pool.close()
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

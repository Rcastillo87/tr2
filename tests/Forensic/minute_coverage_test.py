"""
Velas con minutos de 1m faltantes en el backtest (NUEVO-01): una vela grande a la que le faltan minutos NO está cubierta;
se evalúa como vela completa con SL primero (igual que sin 1m y que Paper ante un hueco permanente, p20). Antes el motor
revisaba solo los minutos presentes y podía no ver un SL tocado en los que faltan. Sin base de datos.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/minute_coverage_test.py
Antes del parche: FALLAN los casos con minutos faltantes y el aviso.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import minute_gap_test as mg  # noqa: E402   (Paper con hueco permanente, para la homologación)
from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


UTC = timezone.utc
T0 = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
CODE = ("class S(BaseStrategy):\n    def generate_signals(self, df):\n        df = df.copy()\n"
        "        df['signal'] = df['sig'].fillna(0).astype(int)\n        return df\n")
P = dict(symbol='BTCUSDT', interval='60', sl_pct=1.0, tp_pct=2.0, be_pct=50.0, max_duration=0, regime_filter=False,
         commission_pct=0.0, slippage_pct=0.0, strategy_code=CODE)


def data(n=14, entry_hour=10, minute_low=None, minute_high=None, skip=(), bar_low=None, bar_high=None):
    """H1 planas en 100; señal larga en la vela entry_hour-1 (entra al open de entry_hour). 1m completo salvo `skip`.
    minute_low/high: {minuto: precio} toques dentro del 1m; bar_low/high: {hora: precio} extremos de la vela grande."""
    rows = []
    for h in range(n):
        for m in range(60):
            t = T0 + timedelta(hours=h, minutes=m)
            if t in skip:
                continue
            rows.append((t, 100.0, (minute_high or {}).get(t, 100.2), (minute_low or {}).get(t, 99.8), 100.0))
    mins = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close'])
    hours = []
    for h in range(n):
        t = T0 + timedelta(hours=h)
        seg = mins[(mins['time'] >= t) & (mins['time'] < t + timedelta(hours=1))]
        lo = min(seg['low'].min(), (bar_low or {}).get(h, 1e9))
        hi = max(seg['high'].max(), (bar_high or {}).get(h, -1e9))
        hours.append((t, 100.0, hi, lo, 100.0, 1.0, 1 if h == entry_hour - 1 else 0))
    return pd.DataFrame(hours, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'sig']), mins


def run(hours, mins, params=P, trade_from=None):
    eng = BacktestEngine(build_strategy(params), hours, minute_df=mins, trade_from=trade_from)
    return eng.run(), eng


def hm(h, m):
    return T0 + timedelta(hours=h, minutes=m)


async def main():
    # 1. 1m completo: sin respaldo, mismo resultado de siempre (el TP del minuto 10:20 gana)
    hours, mins = data(minute_high={hm(10, 20): 102.5})
    r, eng = run(hours, mins)
    t = r['trades']
    check('1m completo: 0 velas con respaldo', r.get('minute_fallback_bars') == 0, r.get('minute_fallback_bars'))
    check('1m completo: TP en el minuto 10:20 (sin cambios)', len(t) == 1 and t[0]['exit_reason'] == 'take_profit_1',
          [x['exit_reason'] for x in t])

    # 2. El SL se tocó en minutos que FALTAN en el 1m (10:40–10:44): la vela grande sí lo muestra
    gap = {hm(10, 40 + k) for k in range(5)}
    hours, mins = data(skip=gap, bar_low={10: 98.5})
    r, eng = run(hours, mins)
    t = r['trades']
    check('minutos faltantes con el SL adentro: stop_loss en la vela 10:00 (antes no se veía)',
          len(t) == 1 and t[0]['exit_reason'] == 'stop_loss' and abs(t[0]['exit_price'] - 99.0) < 1e-9
          and pd.Timestamp(t[0]['exit_time']) == pd.Timestamp(hm(10, 0)),
          [(x['exit_reason'], x['exit_price'], str(x['exit_time'])) for x in t])
    check('se informa 1 vela con respaldo', r.get('minute_fallback_bars') == 1, r.get('minute_fallback_bars'))

    # 3. Minutos presentes con TP, vela grande con SL también: SL primero (pesimista, como sin 1m)
    hours, mins = data(skip=gap, minute_high={hm(10, 20): 102.5}, bar_low={10: 98.5})
    r, _ = run(hours, mins)
    t = r['trades']
    check('vela incompleta con TP en los minutos y SL en la vela: SL primero',
          len(t) == 1 and t[0]['exit_reason'] == 'stop_loss', [x['exit_reason'] for x in t])

    # 4. Vela incompleta que no toca nada: la posición sigue y la vela siguiente (completa) usa el 1m
    hours, mins = data(skip=gap, minute_high={hm(11, 30): 102.5})
    r, _ = run(hours, mins)
    t = r['trades']
    check('vela incompleta sin toque: sigue y el TP de la vela siguiente sale por 1m',
          len(t) == 1 and t[0]['exit_reason'] == 'take_profit_1' and pd.Timestamp(t[0]['exit_time']) == pd.Timestamp(hm(11, 0)),
          [(x['exit_reason'], str(x['exit_time'])) for x in t])

    # 5. Conteo: solo velas del tramo operado; la vela sin ningún minuto también cuenta
    whole = {hm(12, m) for m in range(60)}
    early = {hm(3, 5)}
    hours, mins = data(skip=gap | whole | early)
    r, _ = run(hours, mins, trade_from=pd.Timestamp(hm(5, 0)))
    check('conteo: 2 velas en el tramo operado (10:00 incompleta, 12:00 sin minutos); la de calentamiento no',
          r.get('minute_fallback_bars') == 2, r.get('minute_fallback_bars'))

    # 6. Sin 1m (intervalo sin minutos): nada que informar
    r, _ = run(hours, None)
    check('sin 1m: minute_fallback_bars = 0', r.get('minute_fallback_bars') == 0, r.get('minute_fallback_bars'))

    # 7. Homologación con Paper (p20): mismo hueco permanente, misma salida
    hours, mins = data(skip=gap, bar_low={10: 98.5})
    r, _ = run(hours, mins)
    bt = r['trades'][0] if r['trades'] else {}
    late = datetime(2026, 3, 3, 13, 0, tzinfo=UTC)
    pmins = [mg.mm(t.to_pydatetime(), low=lo, high=hi) for t, hi, lo in zip(mins['time'], mins['high'], mins['low'])
             if t.to_pydatetime() < late]
    s = mg.store(pmins, candles=[mg.hour(datetime(2026, 3, 2, 10, 0), low=98.5, high=100.2)])
    s['trade'].update(entry_time=datetime(2026, 3, 2, 10, 0), sl=99.0, tp=102.0, be_level=150.0)
    await mg.monitor(s, late)
    pa = s['trade']
    check('homologado con Paper: mismo motivo, precio y hora de salida que el backtest',
          bt and pa['status'] == 'closed' and pa['exit_reason'] == bt['exit_reason']
          and abs(pa['exit_price'] - bt['exit_price']) < 1e-9
          and pa['exit_time'] == pd.Timestamp(bt['exit_time']).tz_convert(None).to_pydatetime(),
          ((pa.get('exit_reason'), pa.get('exit_price'), pa.get('exit_time')),
           (bt.get('exit_reason'), bt.get('exit_price'), str(bt.get('exit_time')))))

    # 8. El aviso llega a la pantalla (/backtest/run)
    import api.v1.backtest as api
    from collectors.funding_collector import FundingData
    hours, mins = data(skip=gap, bar_low={10: 98.5})

    async def _load(pool, symbol, interval, start, end, **k):
        return api.BacktestData(df=hours, macro_df=None, minute_df=mins, warnings=[], coverage={},
                                funding=FundingData(symbol, np.array([], dtype='datetime64[ns]'), np.array([], dtype=float),
                                                    start, end))

    class _Pool:
        async def close(self):
            pass

    async def _pool():
        return _Pool()
    api.load_backtest_data, api.get_pool = _load, _pool
    req = api.BacktestRequest(strategy='S', strategy_code=CODE, symbol='BTCUSDT', interval='60', sl_pct=1.0, tp_pct=2.0,
                              be_pct=50.0, max_duration=0, regime_filter=False, start_date='2026-03-02',
                              end_date='2026-03-02', walk_forward=False)
    out = await api.run_backtest(req)
    w = [x for x in out['warnings'] if 'minutos de 1m faltantes' in x]
    check('aviso en pantalla: «1 vela(s) … con minutos de 1m faltantes … SL primero»',
          len(w) == 1 and w[0].startswith('Aviso: 1 vela(s) de BTCUSDT'), out['warnings'])

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

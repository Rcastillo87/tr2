"""
Posición abierta al final del rango en el backtest (BP-04): antes desaparecía del resultado (ni trade, ni balance, ni
métricas). Ahora se cierra al cierre de la última vela con motivo end_of_data, con slippage, comisión y funding como
cualquier salida, y cuenta en trades y métricas. Sin base de datos.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/end_of_data_test.py
Antes del parche: FALLAN los casos con posición abierta al final y el aviso.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())  # python-engine/

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from backtesting.engine import BacktestEngine  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402
from collectors.funding_collector import FundingData  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


UTC = timezone.utc
T0 = datetime(2026, 3, 2, 0, 0, tzinfo=UTC)
CODE = ("class S(BaseStrategy):\n    def generate_signals(self, df):\n        df = df.copy()\n"
        "        df['signal'] = df['sig'].fillna(0).astype(int)\n        return df\n")
P = dict(symbol='BTCUSDT', interval='60', sl_pct=5.0, tp_pct=10.0, be_pct=50.0, max_duration=0, regime_filter=False,
         commission_pct=0.055, slippage_pct=0.05, strategy_code=CODE)


def bars(n=12, sig=None, last_close=101.0):
    """H1 que suben suave (no tocan SL/TP); sig = {vela: ±1}; el cierre de la última vela es last_close."""
    rows = []
    for h in range(n):
        o = 100.0 + 0.05 * h
        c = last_close if h == n - 1 else o + 0.05
        rows.append((T0 + timedelta(hours=h), o, max(o, c) + 0.1, min(o, c) - 0.1, c, 1.0, (sig or {}).get(h, 0)))
    return pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'sig'])


def run(df, params=P, funding=None):
    eng = BacktestEngine(build_strategy(params), df, initial_balance=10000.0, risk_per_trade_pct=1.0, funding=funding)
    return eng.run()


def main_sync():
    # 1. Long abierto en la vela 5 y nunca cerrado: end_of_data al cierre de la última vela
    df = bars(sig={4: 1})
    r = run(df)
    t = r['trades']
    last = t[-1] if t else {}
    check('long abierto al final: aparece como trade end_of_data (antes desaparecía)',
          len(t) == 1 and last.get('exit_reason') == 'end_of_data', [x['exit_reason'] for x in t])
    if last:
        t_end = pd.Timestamp(df['time'].iloc[-1]) + pd.Timedelta(hours=1)
        check('exit_time = cierre de la última vela', pd.Timestamp(last['exit_time']) == t_end, (last['exit_time'], t_end))
        check('exit_level = cierre de la última vela; precio con slippage en contra (venta más barata)',
              last['exit_level'] == 101.0 and abs(last['exit_price'] - 101.0 * (1 - 0.0005)) < 1e-9,
              (last['exit_level'], last['exit_price']))
        comm = (last['entry_price'] + last['exit_price']) * last['size'] * 0.00055
        check('comisión de entrada + salida', abs(last['commission'] - round(comm, 4)) < 1e-4, (last['commission'], comm))
        check('bars_open cuenta hasta la última vela (5..11 = 7)', last['bars_open'] == 7, last['bars_open'])
    check('cuenta en las métricas y el balance (1 trade; equity final = balance)',
          r['metrics']['total_trades'] == 1 and r.get('closed_at_end') == 1
          and abs(r['metrics']['equity_curve'][-1] - (10000.0 + (last.get('pnl') or 0))) < 1e-3,
          (r['metrics']['total_trades'], r.get('closed_at_end')))

    # 2. Short: slippage al revés (compra más cara)
    r = run(bars(sig={4: -1}, last_close=100.2))
    last = r['trades'][-1] if r['trades'] else {}
    check('short abierto al final: end_of_data con compra más cara',
          last.get('exit_reason') == 'end_of_data' and abs(last['exit_price'] - 100.2 * 1.0005) < 1e-9,
          (last.get('exit_reason'), last.get('exit_price')))

    # 3. Funding: un cobro entre la entrada y el final se paga en el cierre end_of_data
    df = bars(sig={4: 1})
    f_t = np.array([np.datetime64((T0 + timedelta(hours=8)).replace(tzinfo=None), 'ns')])
    fund = FundingData('BTCUSDT', f_t, np.array([0.001]), T0, T0 + timedelta(days=1))
    r = run(df, funding=fund)
    last = r['trades'][-1] if r['trades'] else {}
    check('funding del tramo abierto se cobra en el cierre end_of_data',
          last.get('exit_reason') == 'end_of_data' and last.get('funding', 0) > 0
          and abs(last['pnl'] - round(last['gross_pnl'] - last['commission'] - last['funding'], 4)) < 1e-3,
          (last.get('funding'), last.get('pnl')))

    # 4. Sin posición abierta al final: nada cambia
    df = bars(sig={2: 1, 6: -1}, last_close=100.6)
    r = BacktestEngine(build_strategy(dict(P, exit_on_opposite=True)), df, initial_balance=10000.0).run()
    check('sin posición al final: ningún end_of_data, closed_at_end = 0',
          all(x['exit_reason'] != 'end_of_data' for x in r['trades']) and r.get('closed_at_end') == 0,
          ([x['exit_reason'] for x in r['trades']], r.get('closed_at_end')))

    # 5. Entrada en la última vela: también se cierra (bars_open = 1)
    r = run(bars(sig={10: 1}))
    last = r['trades'][-1] if r['trades'] else {}
    check('entrada en la última vela: end_of_data con bars_open = 1',
          last.get('exit_reason') == 'end_of_data' and last.get('bars_open') == 1, (last.get('exit_reason'), last.get('bars_open')))

    # 6. Cierre normal + reentrada que queda abierta: solo el último es end_of_data
    df = bars(sig={2: 1, 6: -1})
    r = BacktestEngine(build_strategy(dict(P, close_on_opposite=True)), df, initial_balance=10000.0).run()
    reasons = [x['exit_reason'] for x in r['trades']]
    check('reversa por señal opuesta y el short queda abierto: [opposite_signal, end_of_data]',
          reasons == ['opposite_signal', 'end_of_data'], reasons)


async def endpoint():
    import api.v1.backtest as api
    df = bars(sig={4: 1})

    async def _load(pool, symbol, interval, start, end, **k):
        return api.BacktestData(df=df, macro_df=None, minute_df=None, warnings=[], coverage={},
                                funding=FundingData(symbol, np.array([], dtype='datetime64[ns]'), np.array([], dtype=float),
                                                    start, end))

    class _Pool:
        async def close(self):
            pass

    async def _pool():
        return _Pool()
    api.load_backtest_data, api.get_pool = _load, _pool
    req = api.BacktestRequest(strategy='S', strategy_code=CODE, symbol='BTCUSDT', interval='60', sl_pct=5.0, tp_pct=10.0,
                              be_pct=50.0, max_duration=0, regime_filter=False, start_date='2026-03-02',
                              end_date='2026-03-02', walk_forward=False, slippage_pct=0.05)
    out = await api.run_backtest(req)
    w = [x for x in out['warnings'] if 'abierta al final del rango' in x]
    check('aviso en pantalla: «1 posición seguía abierta al final del rango … end_of_data»', len(w) == 1, out['warnings'])
    check('/backtest/run: el trade end_of_data está en el resultado',
          [x['exit_reason'] for x in out['result']['trades']][-1:] == ['end_of_data'],
          [x['exit_reason'] for x in out['result']['trades']])


if __name__ == '__main__':
    main_sync()
    asyncio.run(endpoint())
    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)

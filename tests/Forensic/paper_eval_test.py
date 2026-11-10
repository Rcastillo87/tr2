"""
RQ-01.5: diagnóstico de Paper. Cada evaluación de cada config deja su decisión con un motivo normalizado:
estado actual (paper_eval_state, una fila por config) e historial agrupado por (config, vela, motivo) con la cantidad
de evaluaciones (paper_eval_log). La traza de filtros dice QUÉ filtro anuló una señal. Nada de esto cambia el
trading: mismas señales, mismos trades y mismo texto para Laravel; si el registro falla, el tick sigue igual.
Sin base ni red: el arnés de paper_opposite_test.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/paper_eval_test.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import numpy as np  # noqa: E402

import paper_opposite_test as po  # noqa: E402  (reloj, precio, velas y base simulados)
import trading.paper_trader as pt  # noqa: E402
from backtesting.strategies.loader import build_strategy  # noqa: E402

fails = 0
L = 'T [#1]'   # etiqueta de la config de prueba en el resultado del tick


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class EvalStore(po.Store):
    def __init__(self, kill=False, broken=False):
        super().__init__(kill=kill)
        self.state, self.log, self.purges, self.broken = {}, {}, 0, broken


class EvalConn(po.FakeConn):
    """Ejecuta los UPSERT del diagnóstico con su semántica (estado reemplazado; historial agrupado por clave)."""

    async def executemany(self, sql, rows):
        if self.s.broken:
            raise RuntimeError('base caída (simulada)')
        for r in rows:
            if 'INSERT INTO paper_eval_state' in sql:
                cid, at, code, detail, regime, sig, filters, candle, last_bar, bars = r
                self.s.state[cid] = dict(evaluated_at=at, code=code, detail=detail, regime=regime, signal=sig,
                                         filters=json.loads(filters) if filters else None, candle_time=candle,
                                         last_bar_time=last_bar, bars=bars)
            elif 'INSERT INTO paper_eval_log' in sql:
                cid, bucket, code, detail, regime, sig, filters, at = r
                k = (cid, bucket, code)
                if k in self.s.log:
                    self.s.log[k].update(last_at=at, evaluations=self.s.log[k]['evaluations'] + 1, detail=detail)
                else:
                    self.s.log[k] = dict(first_at=at, last_at=at, evaluations=1, detail=detail, regime=regime, signal=sig)

    async def execute(self, sql, *a):
        if 'DELETE FROM paper_eval_log' in sql:
            self.s.purges += 1
            return 'DELETE 0'
        return await super().execute(sql, *a)


class EvalPool(po.FakePool):
    def acquire(self):
        s = self.s

        class _C:
            async def __aenter__(self_):
                return EvalConn(s)

            async def __aexit__(self_, *e):
                return False
        return _C()


def mk(params, store):
    cfg = {'id': 1, 'display_name': 'T', 'symbol': 'BTCUSDT', 'interval': '60', 'params': json.dumps(params)}
    return pt.PaperTrader(EvalPool(store), {}, {1: cfg})


def df_with(sig_at: dict, n=120):
    df = po.candles(n=n, p_sig=0.0)
    df['sig'] = 0.0
    for k, v in sig_at.items():
        df.loc[k, 'sig'] = v
    return df


async def tick(trader, df, k, minute=2):
    return await po.tick(trader, df, k, minute)


async def main():
    # 2026-01-01 00:00 es jueves y las velas son de 1 h: la 75 es domingo 03:00, la 100 es lunes 04:00
    # E1. Sin señal: motivo no_signal, traza de la estrategia y los filtros, vela y velas disponibles
    s = EvalStore()
    tr = mk(po.BASE, s)
    r = await tick(tr, df_with({}), 80)
    st = s.state.get(1, {})
    check('E1: sin señal -> code no_signal, mismo texto de siempre para Laravel',
          st.get('code') == 'no_signal' and r.get(L) == 'BTCUSDT: sin senal', (st.get('code'), r))
    steps = [f['step'] for f in st.get('filters') or []]
    check('E1: traza = estrategia + los 7 filtros, en orden', steps[:1] == ['estrategia'] and len(steps) == 8
          and steps[-1] == 'btc_trend_filter', steps)
    check('E1: guarda vela evaluada (79), última vela y cantidad de velas', st.get('candle_time') is not None
          and st['candle_time'].hour == 7 and st.get('bars') == 80, (st.get('candle_time'), st.get('bars')))

    # E2. Señal anulada por un filtro: weekend_filter con la señal del sábado -> filter_blocked y cuál
    s = EvalStore()
    tr = mk(dict(po.BASE, weekend_filter=True), s)
    r = await tick(tr, df_with({75: 1}), 76)
    st = s.state.get(1, {})
    check('E2: señal del domingo con filtro de fin de semana -> filter_blocked (weekend_filter)',
          st.get('code') == 'filter_blocked' and 'weekend_filter' in st.get('detail', ''), (st.get('code'), st.get('detail')))
    check('E2: no se abrió nada', not s.trades, len(s.trades))

    # E3. Apertura: opened con régimen y señal
    s = EvalStore()
    tr = mk(po.BASE, s)
    r = await tick(tr, df_with({100: 1}), 101)
    st = s.state.get(1, {})
    check('E3: señal sin filtros -> opened y el trade existe', st.get('code') == 'opened' and len(s.trades) == 1
          and st.get('signal') == 1, (st.get('code'), len(s.trades)))
    check('E3: el texto para Laravel no cambió', r.get(L, '').startswith('BTCUSDT: ABIERTA long @'), r)

    # E4. Ticks siguientes con la posición abierta: open_position, agrupados en una fila del historial
    for m in (3, 4, 5):
        await tick(tr, df_with({100: 1}), 101, m)
    op = [v for (cid, b, code), v in s.log.items() if code == 'open_position']
    check('E4: con posición abierta -> open_position; 3 evaluaciones en UNA fila del historial',
          s.state[1]['code'] == 'open_position' and len(op) == 1 and op[0]['evaluations'] == 3,
          (s.state[1]['code'], [x['evaluations'] for x in op]))

    # E5. Kill switch
    s = EvalStore(kill=True)
    await tick(mk(po.BASE, s), df_with({100: 1}), 101)
    check('E5: kill switch -> kill_switch y sin trade', s.state.get(1, {}).get('code') == 'kill_switch' and not s.trades,
          s.state.get(1, {}).get('code'))

    # E6. Datos insuficientes (menos de 64 velas cerradas)
    s = EvalStore()
    await tick(mk(po.BASE, s), df_with({}, n=40), 39)
    check('E6: 39 velas cerradas (< 64) -> insufficient_data con la cantidad de velas', s.state.get(1, {}).get('code') == 'insufficient_data'
          and s.state[1]['bars'] == 39, (s.state.get(1, {}).get('code'), s.state.get(1, {}).get('bars')))

    # E7. Collector atrasado: tick 5 h después de la última vela disponible
    s = EvalStore()
    tr = mk(po.BASE, s)
    df = df_with({})
    po.CLOCK[0] = df['time'][90].to_pydatetime() + timedelta(hours=5)

    async def _bars(symbol, interval, broker=None):
        return df.iloc[:91].copy()
    tr.get_bars = _bars
    await tr.check_new_signals()
    check('E7: última vela vieja -> collector_stale', s.state.get(1, {}).get('code') == 'collector_stale',
          s.state.get(1, {}).get('code'))

    # E8. Error al construir la estrategia
    s = EvalStore()
    await tick(mk(dict(po.BASE, strategy_code='class X:\n  pass\n'), s), df_with({}), 80)
    check('E8: código roto -> build_error', s.state.get(1, {}).get('code') == 'build_error', s.state.get(1, {}).get('code'))

    # E9. Régimen no permitido
    s = EvalStore()
    tr = mk(dict(po.BASE, regime_filter=True, allowed_regimes=['TRENDING']), s)

    async def _regime(*a, **k):
        return 'RANGING'
    tr.get_current_regime = _regime
    await tick(tr, df_with({100: 1}), 101)
    st = s.state.get(1, {})
    check('E9: régimen RANGING con solo TRENDING permitido -> regime_blocked y guarda el régimen',
          st.get('code') == 'regime_blocked' and st.get('regime') == 'RANGING' and not s.trades, (st.get('code'), st.get('regime')))

    # E10. El registro falla (base caída): el tick opera igual y devuelve lo mismo
    s = EvalStore(broken=True)
    r = await tick(mk(po.BASE, s), df_with({100: 1}), 101)
    check('E10: diagnóstico caído -> el trade se abre igual y el texto es el mismo', len(s.trades) == 1
          and r.get(L, '').startswith('BTCUSDT: ABIERTA long'), (len(s.trades), r))

    # E11. Limpieza del historial una vez por día
    pt._eval_purged_on = None
    s = EvalStore()
    tr = mk(po.BASE, s)
    for m in (2, 3, 4):
        await tick(tr, df_with({}), 80, m)
    check('E11: la retención borra el historial viejo una sola vez por día', s.purges == 1, s.purges)

    # E12. La traza no cambia las señales: compute_signals idéntico con y sin traza (filtros activos)
    df = df_with({k: (1 if k % 7 else -1) for k in range(66, 118, 3)})
    p = dict(po.BASE, weekend_filter=True, hour_filter=True, allowed_hours=list(range(6, 20)))
    a = build_strategy(p).compute_signals(df.copy())
    sb = build_strategy(p)
    sb.signal_trace = []
    b = sb.compute_signals(df.copy())
    check('E12: compute_signals con traza = sin traza (mismas señales en todas las velas)',
          np.array_equal(a['signal'].to_numpy(), b['signal'].to_numpy()) and len(sb.signal_trace) == 8,
          int((a['signal'] != b['signal']).sum()))

    # E13. Mismos trades con y sin diagnóstico en una simulación larga
    P13 = dict(po.BASE, close_on_opposite=True)   # el arnés no corre el monitor: cada señal opuesta invierte
    df = po.candles(n=220, seed=11, p_sig=0.2)
    base = await po.simulate(P13, df, 70)
    s = EvalStore()
    tr = mk(P13, s)
    for k in range(70, len(df)):
        for m in (2, 3, 4):
            await tick(tr, df, k, m)
    key = lambda t: (t['side'], t['entry_time'], t.get('exit_reason'), t['status'])   # noqa: E731
    check('E13: 150 velas × 3 ticks: mismos trades con y sin registro del diagnóstico',
          [key(t) for t in base.trades] == [key(t) for t in s.trades] and len(s.trades) > 3,
          (len(base.trades), len(s.trades)))
    codes = {c for (_, _, c) in s.log}
    check('E13: el historial tiene los motivos esperados (opened, open_position, no_signal, …)',
          {'opened', 'open_position', 'no_signal'} <= codes, sorted(codes))
    check('E13: el historial agrupa (filas << evaluaciones)', len(s.log) < 150 * 3 / 2
          and sum(v['evaluations'] for v in s.log.values()) == 150 * 3, (len(s.log), sum(v['evaluations'] for v in s.log.values())))

    # E14. blocking_filter
    T = lambda *xs: [{'step': n, 'signal': v} for n, v in xs]   # noqa: E731
    check('E14: blocking_filter: estrategia 0 -> None; anula el 2.º filtro -> su nombre; traza vacía -> None',
          pt.blocking_filter(T(('estrategia', 0), ('a', 0))) is None
          and pt.blocking_filter(T(('estrategia', 1), ('a', 1), ('b', 0), ('c', 0))) == 'b'
          and pt.blocking_filter([]) is None and pt.blocking_filter(None) is None)

    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return fails


if __name__ == '__main__':
    sys.exit(1 if asyncio.run(main()) else 0)

"""
p84 (R-21): protección contra estrategias que «miran el futuro».
A. La prueba (`backtesting/lookahead.py`): detecta el código viejo de VWAP Tendencia (desviación del día completo) y un
   shift(-1); el código corregido sale limpio.
B. Al guardar (`/v1/strategies/validate` con smoke test): una estrategia que mira el futuro se rechaza con el motivo y
   sin correr el backtest; una limpia sigue al smoke test; sin datos o si la estrategia falla, decide el smoke test.
C. Revisión diaria (`/v1/strategies/lookahead-audit`): señala la config que mira el futuro y no la limpia.
Sin base de datos: velas sintéticas en una base simulada.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/lookahead_guard_test.py
"""
import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


try:
    from backtesting import lookahead as la
except ImportError as e:
    check('existe backtesting/lookahead.py', False, f'no ({e})')
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)
import api.v1.backtest as api  # noqa: E402
from fastapi import HTTPException  # noqa: E402

spec = importlib.util.spec_from_file_location('r21', ROOT / 'ops' / 'datafix' / '2026_11_19_r21_vwap_std.py')
r21 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r21)
OLD = (ROOT / 'tests' / 'Forensic' / 'fixtures' / 'vwap_tendencia_19nov.py').read_text(encoding='utf-8')
NEW = r21.patch_code(OLD)
EMA = "df['ema_trend']  = df['close'].ewm(span=self.ema_trend_period, adjust=False).mean()"
assert EMA in NEW
SHIFT = NEW.replace(EMA, "df['ema_trend']  = df['close'].shift(-1).ewm(span=self.ema_trend_period, adjust=False).mean()")
BROKEN = NEW.replace("    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:",
                     "    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:\n        raise ValueError('rota')", 1)   # falla
assert BROKEN != NEW


def candles(n, freq, seed=3):
    rng = np.random.default_rng(seed)
    t = pd.date_range('2026-06-01', periods=n, freq=freq, tz='UTC')
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return [(t[i].to_pydatetime(), float(c[i - 1] if i else 100), float(c[i] * 1.005), float(c[i] * 0.995), float(c[i]),
             float(rng.uniform(1, 10))) for i in range(n)]


DATA = {('BTCUSDT', '60'): candles(420, 'h'), ('BTCUSDT', '240'): candles(420, '4h', 5), ('ETHUSDT', '60'): candles(420, 'h', 7),
        ('DOGEUSDT', '240'): candles(420, '4h', 9)}
CFG = {'vwap_std_filter': 1.0}


class FakeDB:
    def __init__(self, data=DATA, configs=(), strategies=()):
        self.data, self.configs, self.strategies, self.bar_reads = data, list(configs), list(strategies), 0

    async def fetch(self, sql, *a):
        if 'FROM ohlcv_data' in sql:
            self.bar_reads += 1
            rows = self.data.get((a[0], str(a[1])), [])
            return list(reversed(rows[-a[2]:]))   # DESC LIMIT, como la base
        if 'FROM paper_strategy_configs' in sql:
            return self.configs
        if 'FROM strategies' in sql:
            return self.strategies
        raise AssertionError(sql)

    async def close(self):
        pass


def df_of(key, n=400):
    from collectors.bars import bars_frame
    return bars_frame(list(reversed(DATA[key][-n:])), 't').sort_values('time').reset_index(drop=True)


P = dict(strategy_config=CFG, symbol='BTCUSDT', interval='240')

# ── A. La prueba ──
r_old = la.lookahead_check(OLD, P, df_of(('BTCUSDT', '240')), 80)
r_new = la.lookahead_check(NEW, P, df_of(('BTCUSDT', '240')), 80)
r_sh = la.lookahead_check(SHIFT, P, df_of(('BTCUSDT', '240')), 80)
check('A1: el código viejo de VWAP Tendencia mira el futuro (vwap_std_dev distinto)',
      la.looks_ahead(r_old) and 'vwap_std_dev' in r_old['column_diff'], la.verdict(r_old))
check('A2: el código corregido no mira el futuro', not la.looks_ahead(r_new) and r_new['checked'] == 80, la.verdict(r_new))
check('A3: un shift(-1) se detecta', la.looks_ahead(r_sh) and 'ema_trend' in r_sh['column_diff'], la.verdict(r_sh))
check('A4: el veredicto lo dice en palabras', la.verdict(r_old).startswith('MIRA EL FUTURO') and
      la.verdict(r_new).startswith('OK'))


# ── B. Al guardar ──
def validate(code, db, config=CFG):
    calls = []

    async def fake_pool():   # misma firma que api.get_pool (p84 la llamó con un argumento: 500 en el servidor)
        return db

    async def fake_run(req):
        calls.append((req.symbol, req.interval))
        return {'result': {'metrics': {'total_trades': 3}}, 'warnings': []}

    api.get_pool, api.run_backtest = fake_pool, fake_run
    try:
        out = asyncio.run(api.validate_strategy_code(api.ValidateStrategyRequest(code=code, config=config, run_backtest=True)))
        return out, None, calls
    except HTTPException as e:
        return None, e, calls


orig = (api.get_pool, api.run_backtest)
import inspect  # noqa: E402
check('B0: la base simulada tiene la misma firma que la real (si no, la prueba no ve un error de llamada)',
      str(inspect.signature(orig[0])) == '()', str(inspect.signature(orig[0])))
try:
    out, err, calls = validate(OLD, FakeDB())
    check('B1: guardar el código viejo: rechazado (400) con el motivo', err is not None and err.status_code == 400
          and 'mira el futuro' in err.detail and 'vwap_std_dev' in err.detail, err.detail if err else out)
    check('B2: … y sin correr el backtest del smoke test', calls == [], calls)
    check('B3: el motivo empieza con mayúscula y explica qué hacer', err is not None and err.detail.startswith('La estrategia')
          and 'expanding()' in err.detail, err.detail[:80] if err else '')
    out, err, calls = validate(NEW, FakeDB())
    check('B4: el código corregido pasa la prueba y sigue al smoke test', err is None and out['trades'] == 3 and calls,
          (err.detail if err else out, calls))
    # C5-02 (p101, D-55): «no se pudo probar» no es «aprobada» (antes B5/B6 aprobaban y decidía el smoke test)
    db = FakeDB(data={})
    out, err, calls = validate(NEW, db)
    check('B5: sin velas para probar: NO se guarda (400), dice por qué y no corre el smoke test',
          err is not None and err.status_code == 400 and 'No se pudo comprobar' in err.detail and 'BTCUSDT 60' in err.detail
          and 'velas' in err.detail and calls == [], (err.detail if err else out, calls))
    out, err, calls = validate(BROKEN, FakeDB())
    check('B6: si la estrategia falla al calcularse vela a vela: NO se guarda y el motivo trae el error',
          err is not None and err.status_code == 400 and 'No se pudo comprobar' in err.detail and 'ValueError' in err.detail
          and calls == [], (err.detail if err else out, calls))
    db = FakeDB(data={('BTCUSDT', '60'): DATA[('BTCUSDT', '60')]})
    out, err, calls = validate(NEW, db)
    check('B9: la primera combinación pasa pero la segunda (H4) no tiene velas: NO se guarda (las 2 son obligatorias)',
          err is not None and 'BTCUSDT 240' in err.detail and calls == [] and db.bar_reads == 2, (err.detail if err else out))
    check('B10a: el mínimo sigue siendo 160 velas (300 // 2 + 10, el mismo de la revisión diaria)', la.min_bars() == 160,
          la.min_bars())
    few = {('BTCUSDT', '60'): DATA[('BTCUSDT', '60')][:la.min_bars() - 1], ('BTCUSDT', '240'): DATA[('BTCUSDT', '240')]}
    out, err, calls = validate(NEW, FakeDB(data=few))
    check(f'B10: una vela menos que el mínimo ({la.min_bars()}): NO se guarda', err is not None and 'BTCUSDT 60' in err.detail
          and f'solo hay {la.min_bars() - 1} velas' in err.detail, err.detail if err else out)
    edge = {('BTCUSDT', '60'): DATA[('BTCUSDT', '60')][:la.min_bars()], ('BTCUSDT', '240'): DATA[('BTCUSDT', '240')]}
    out, err, calls = validate(NEW, FakeDB(data=edge))
    check('B11: con el mínimo justo de velas sí se prueba y sigue al smoke test', err is None and calls,
          (err.detail if err else out, calls))
    r = asyncio.run(la.guard_code(FakeDB(), asyncio.Semaphore(1), NEW, CFG, []))
    check('B12: sin combinaciones para probar: rechazada', r is not None and 'no hay combinaciones' in r, r)
    db = FakeDB()
    validate(NEW, db)
    check('B7: al guardar se revisan solo las 2 primeras combinaciones (H1 y H4 de BTC), por el tiempo del smoke test',
          db.bar_reads == 2, db.bar_reads)
    out = asyncio.run(api.validate_strategy_code(api.ValidateStrategyRequest(code=OLD, run_backtest=False)))
    check('B8: sin smoke test (solo sintaxis) no se corre la prueba', out['message'] == 'Sintaxis Python válida', out)

    # ── C. Revisión diaria ──
    cfg_old = dict(id=59, display_name='VWAP Tendencia — DOGEUSDT H4', symbol='DOGEUSDT', interval='240',
                   params=json.dumps(dict(strategy_code=OLD, strategy_config=CFG)))
    cfg_new = dict(id=61, display_name='VWAP Tendencia — BTCUSDT H4', symbol='BTCUSDT', interval='240',
                   params=json.dumps(dict(strategy_code=NEW, strategy_config=CFG)))
    st = [dict(id=1, name='VWAP Tendencia', code=NEW, config='{}'), dict(id=4, name='Otra', code=SHIFT, config=json.dumps(CFG))]
    db = FakeDB(configs=[cfg_old, cfg_new], strategies=st)

    async def fake_pool():   # misma firma que api.get_pool (p84 la llamó con un argumento: 500 en el servidor)
        return db
    api.get_pool = fake_pool
    out = asyncio.run(api.strategies_lookahead_audit())
    labels = {x['label']: x['ok'] for x in out['results']}
    check('C1: revisa las configs activas y las estrategias sin config activa con ese código (3)', out['checked'] == 3,
          list(labels))
    check('C2: señala la config con el código viejo y la estrategia con shift(-1); no la limpia',
          sorted(x['label'] for x in out['bad']) == ['config #59 VWAP Tendencia — DOGEUSDT H4', 'estrategia #4 Otra (BTCUSDT H1)']
          and labels.get('config #61 VWAP Tendencia — BTCUSDT H4') is True, out['bad'])
    db.data = {}
    out = asyncio.run(api.strategies_lookahead_audit())
    check('C3: sin velas: «sin evaluar», ni buena ni mala', out['bad'] == [] and len(out['errors']) == 3
          and all(x['status'] == 'unverified' and x['verdict'].startswith('sin evaluar') for x in out['errors'])
          and out['evaluated'] == 0, out['errors'][:1])
    db.data = DATA
    db.strategies = st + [dict(id=9, name='Rota', code=BROKEN, config='{}')]
    out = asyncio.run(api.strategies_lookahead_audit())
    st_of = {x['label']: x['status'] for x in out['results']}
    check('C4: cada una queda aprobada, mira el futuro o sin evaluar (la rota: sin evaluar, con el error)',
          st_of.get('config #61 VWAP Tendencia — BTCUSDT H4') == 'ok' and st_of.get('config #59 VWAP Tendencia — DOGEUSDT H4') == 'bad'
          and st_of.get('estrategia #9 Rota (BTCUSDT H1)') == 'unverified' and out['evaluated'] == 3 and out['checked'] == 4
          and 'ValueError' in out['errors'][0]['verdict'], (st_of, out['errors']))
finally:
    api.get_pool, api.run_backtest = orig

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

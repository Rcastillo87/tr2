"""
N-04: «lista para Paper» separa dos compuertas. 'passed' = métricas mínimas (sin cambios); 'quality_ok' = sin
condiciones que hagan OPTIMISTA el resultado (slippage 0, comisión menor que la taker de Bybit, sin funding, velas
principales incompletas). 'ready_for_paper' exige las dos. Las pesimistas (vela completa sin 1m, cierre al final del
rango) no cuentan. Sin DB: /backtest/run con datos sintéticos (arnés de end_of_data_test).
Uso: cd python-engine && venv/bin/python ../tests/Forensic/quality_gate_test.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import numpy as np  # noqa: E402

import end_of_data_test as eod  # noqa: E402  (velas sintéticas y estrategia de prueba)
import api.v1.backtest as api  # noqa: E402
from collectors.funding_collector import FundingData  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


GOOD = {'total_trades': 40, 'sharpe_ratio': 1.5, 'win_rate': 55.0, 'max_drawdown_pct': 8.0, 'profit_factor': 1.6}
BAD = dict(GOOD, sharpe_ratio=0.2)
dq = getattr(api, 'data_quality_issues', None)

# ── Función pura ──
v = api.evaluate_for_paper(GOOD, []) if dq else api.evaluate_for_paper(GOOD)
check('Q1: métricas buenas y datos limpios -> passed, quality_ok y ready_for_paper',
      v.get('passed') is True and v.get('quality_ok') is True and v.get('ready_for_paper') is True, v)
iss = dq(0.0, 0.055, True, []) if dq else None
check('Q2: slippage 0 -> problema de calidad', bool(iss) and 'slippage' in iss[0], iss)
iss = dq(0.05, 0.02, True, []) if dq else None
check('Q3: comisión 0.02% (< taker 0.055%) -> problema de calidad', bool(iss) and 'comisión' in iss[0], iss)
iss = dq(0.05, 0.055, False, []) if dq else None
check('Q4: sin funding -> problema de calidad', bool(iss) and 'funding' in iss[0], iss)
iss = dq(0.05, 0.055, True, ['Aviso: ... huecos']) if dq else None
check('Q5: velas principales incompletas -> problema de calidad', bool(iss) and 'incompletas' in iss[0], iss)
iss = dq(0.05, 0.055, True, []) if dq else None
check('Q6: slippage > 0, comisión taker, funding y datos completos -> sin problemas', iss == [], iss)
v = api.evaluate_for_paper(GOOD, ['slippage en 0%']) if dq else {}
check('Q7: métricas buenas + problema de calidad -> passed pero NO ready_for_paper, con el motivo «Calidad: …»',
      v.get('passed') is True and v.get('quality_ok') is False and v.get('ready_for_paper') is False
      and any(r.startswith('Calidad: slippage') for r in v.get('reasons', []))
      and 'no lista para Paper' in v.get('reasons', [''])[0], v)
v = api.evaluate_for_paper(BAD, []) if dq else api.evaluate_for_paper(BAD)
check('Q8: métricas malas -> no passed ni ready (los criterios estadísticos no cambian)',
      v.get('passed') is False and v.get('ready_for_paper') is False
      and any('Sharpe' in r for r in v.get('reasons', [])), v)


# ── /backtest/run ──
async def run(slippage=0.05, commission=0.055, funding=True, problems=()):
    df = eod.bars(sig={4: 1})

    async def _load(pool, symbol, interval, start, end, **k):
        fd = FundingData(symbol, np.array([], dtype='datetime64[ns]'), np.array([], dtype=float), start, end) if funding else None
        kw = {'data_problems': list(problems)} if 'data_problems' in api.BacktestData.__dataclass_fields__ else {}
        return api.BacktestData(df=df, macro_df=None, minute_df=None, warnings=list(problems), coverage={}, funding=fd, **kw)

    class _Pool:
        async def close(self):
            pass

    async def _pool():
        return _Pool()
    api.load_backtest_data, api.get_pool = _load, _pool
    req = api.BacktestRequest(strategy='S', strategy_code=eod.CODE, symbol='BTCUSDT', interval='60', sl_pct=5.0,
                              tp_pct=10.0, be_pct=50.0, max_duration=0, regime_filter=False, start_date='2026-03-02',
                              end_date='2026-03-02', walk_forward=False, slippage_pct=slippage, commission_pct=commission)
    return (await api.run_backtest(req))['result']


r = asyncio.run(run())
check('E1: /backtest/run con datos limpios -> quality_ok True y sin quality_reasons',
      r.get('quality_ok') is True and r.get('quality_reasons') == [], (r.get('quality_ok'), r.get('quality_reasons')))
check('E1: ready_for_paper = passed (con datos limpios solo deciden las métricas)',
      'ready_for_paper' in r and r['ready_for_paper'] == r['passed'], (r.get('passed'), r.get('ready_for_paper')))
r = asyncio.run(run(slippage=0.0, funding=False, problems=['Aviso: BTCUSDT 60 tiene 12 velas faltantes: huecos.']))
check('E2: slippage 0 + sin funding + huecos -> quality_ok False con 3 motivos y ready_for_paper False',
      r.get('quality_ok') is False and len(r.get('quality_reasons') or []) == 3 and r.get('ready_for_paper') is False,
      (r.get('quality_ok'), r.get('quality_reasons'), r.get('ready_for_paper')))
check('E2: los motivos de calidad aparecen en pass_reasons (los muestra el Excel)',
      sum(1 for x in r.get('pass_reasons', []) if x.startswith('Calidad:')) == 3, r.get('pass_reasons'))
r = asyncio.run(run(commission=0.02))
check('E3: comisión 0.02% -> no lista para Paper', r.get('quality_ok') is False and r.get('ready_for_paper') is False,
      r.get('quality_reasons'))

xl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app', 'Exports', 'BacktestMonthlyExport.php'),
          encoding='utf-8').read()
check("X1: el Excel muestra «Aprobada» con ready_for_paper (y passed solo para resultados anteriores)",
      "$result['ready_for_paper'] ?? $result['passed'] ?? false" in xl)

print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
sys.exit(1 if fails else 0)

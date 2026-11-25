"""
C6-07 (D-45): tools/analysis/compare_levels.py compara SL/TP fijo vs automático con TODO lo demás igual.
P1 las dos pruebas solo difieren en el SL/TP          P2 multiplicadores: los de D-45 o los pedidos
P3 métricas del informe (retorno, PF, caída, trades, % ganadas, ganancia media, meses, duración, salidas)
P4 quién gana (caída: menor es mejor)                 P5 resumen por métrica y por moneda
P6 main: una config que falla no frena las demás; JSON; interruptor apagado -> no compara
P7 backtest real sobre velas sintéticas: «fijo» = el backtest de la config tal cual; «auto» cambia el SL por ATR;
   las dos usan las mismas velas sin pisarse
S  solo lee (transacción de solo lectura, sin escrituras) y corre en baja prioridad antes de las pruebas
Uso: cd python-engine && venv/bin/python ../tests/Forensic/compare_levels_test.py
"""
import asyncio
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / 'python-engine' / 'tools' / 'analysis' / 'compare_levels.py').read_text(encoding='utf-8')
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


from tools.analysis import compare_levels as cl  # noqa: E402
from backtesting import auto_levels  # noqa: E402

CODE = """class T(BaseStrategy):
    def generate_signals(self, df):
        df['signal'] = 0
        df.iloc[60::9, df.columns.get_loc('signal')] = 1
        df.iloc[64::18, df.columns.get_loc('signal')] = -1
        return df
"""
PARAMS = dict(strategy_code=CODE, sl_pct=1.0, tp_pct=2.0, be_pct=99.0, max_duration=0, regime_filter=False,
              commission_pct=0.055, slippage_pct=0.02, volume_filter=False,
              sl_level_mode='atr', tp_level_mode='atr', sl_atr_mult=9.0, tp_atr_mult=7.0, sl_tp_mode='atr')   # ya automática: «fijo» debe quitarlo
CFG = dict(id=7, display_name='Prueba', symbol='BTCUSDT', interval='240', params=json.dumps(PARAMS), active=True)
A0 = SimpleNamespace(sl_atr_mult=None, tp_r_mult=None, be_r_mult=None, sl_min_pct=None, sl_max_pct=None)

# ── P1 / P2 ──
ov = cl.auto_overrides(A0)
d = auto_levels.DEFAULTS
check('P2a: por defecto, los multiplicadores de D-45 (SL k×ATR acotado, TP veces el SL, BE veces el SL)',
      ov == dict(sl_level_mode='atr', tp_level_mode='r', sl_atr_mult=d['sl_atr_mult'], tp_r_mult=d['tp_r_mult'],
                 be_r_mult=d['be_r_mult'], sl_min_pct=d['sl_min_pct'], sl_max_pct=d['sl_max_pct']), ov)
ov2 = cl.auto_overrides(SimpleNamespace(sl_atr_mult=1.5, tp_r_mult=3.0, be_r_mult=None, sl_min_pct=None, sl_max_pct=4.0))
check('P2b: el dueño puede pedir otros', ov2['sl_atr_mult'] == 1.5 and ov2['tp_r_mult'] == 3.0 and ov2['sl_max_pct'] == 4.0
      and ov2['be_r_mult'] == d['be_r_mult'], ov2)
pl = cl.variant_payloads(CFG, '2024-11-01', '2026-10-31', ov)
f, a = pl['fijo'], pl['auto']
same = {k: v for k, v in f.items() if k not in cl.LEVEL_KEYS} == {k: v for k, v in a.items() if k not in cl.LEVEL_KEYS}
check('P1a: fuera del SL/TP las dos pruebas son idénticas (datos, periodo, costos, entrada, filtros)', same)
check('P1b: «fijo» = SL/TP fijo aunque la config fuera automática', f['sl_level_mode'] == 'fixed'
      and f['tp_level_mode'] == 'fixed' and 'sl_atr_mult' not in f, f.get('sl_level_mode'))
check('P1c: «auto» lleva solo los multiplicadores pedidos (no los viejos de la config)',
      all(a[k] == v for k, v in ov.items()) and a['sl_atr_mult'] == d['sl_atr_mult'] and 'tp_atr_mult' not in a
      and 'sl_tp_mode' not in a)
check('P1d: periodo, moneda, temporalidad y desglose mensual', f['start_date'] == '2024-11-01' and f['end_date'] == '2026-10-31'
      and f['symbol'] == 'BTCUSDT' and f['interval'] == '240' and f['monthly_breakdown'] is True and f['walk_forward'] is False)

# ── P3 ──
res = dict(metrics=dict(total_return_pct=12.345, profit_factor=1.456, max_drawdown_pct=7.1, total_trades=3, win_rate=66.67,
                        expectancy=4.1),
           trades=[dict(pnl=5, pnl_pct=0.5, bars_open=2, exit_reason='take_profit_1'),
                   dict(pnl=-2, pnl_pct=-0.2, bars_open=4, exit_reason='stop_loss'),
                   dict(pnl=9, pnl_pct=0.9, bars_open=6, exit_reason='take_profit_1'),
                   dict(pnl=1, pnl_pct=0.1, bars_open=1, exit_reason='end_of_data')],
           monthly_breakdown=[dict(month='2026-01', total_pnl_pct=1.2), dict(month='2026-02', total_pnl_pct=-0.4),
                              dict(month='2026-03', total_pnl_pct=0.0)])
s = cl.summarize(res, '240')
check('P3a: retorno, PF, caída, trades, % ganadas, ganancia media', (s['retorno_pct'], s['profit_factor'], s['drawdown_pct'],
      s['trades'], s['win_rate'], s['expectancy']) == (12.35, 1.46, 7.1, 3, 66.67, 4.1), s)
check('P3b: ganancia media % y duración (velas × temporalidad), sin la abierta al final (D-35)',
      s['expectancy_pct'] == 0.4 and s['duracion_media_h'] == 16.0, (s['expectancy_pct'], s['duracion_media_h']))
check('P3c: meses (positivos, peor, mejor) y motivos de salida', s['meses'] == 3 and s['meses_positivos'] == 1
      and s['peor_mes_pct'] == -0.4 and s['mejor_mes_pct'] == 1.2 and s['salidas'] == {'take_profit_1': 2, 'stop_loss': 1}, s)
check('P3d: sin trades no revienta', cl.summarize(dict(metrics={}, trades=[], monthly_breakdown=[]), '60')['expectancy_pct'] is None)

# ── P4 / P5 ──
check('P4: quién gana', (cl.better('retorno_pct', 1, 2), cl.better('drawdown_pct', 5, 3), cl.better('drawdown_pct', 3, 5),
                         cl.better('profit_factor', 1.2, 1.2), cl.better('profit_factor', None, 1)) == ('auto', 'auto', 'fijo', '=', None))
rows = [dict(symbol='BTCUSDT', fijo=dict(retorno_pct=10, profit_factor=1.5, drawdown_pct=5),
             auto=dict(retorno_pct=12, profit_factor=1.4, drawdown_pct=5)),
        dict(symbol='BTCUSDT', fijo=dict(retorno_pct=-2, profit_factor=None, drawdown_pct=9),
             auto=dict(retorno_pct=-4, profit_factor=0.8, drawdown_pct=4)),
        dict(symbol='SOLUSDT', fijo=dict(retorno_pct=3, profit_factor=1.1, drawdown_pct=2),
             auto=dict(retorno_pct=1, profit_factor=1.0, drawdown_pct=3))]
o = cl.overall(rows)
check('P5a: conteo por métrica', o['por_metrica']['retorno_pct'] == dict(auto=1, fijo=2, empate=0, sin_dato=0)
      and o['por_metrica']['drawdown_pct'] == dict(auto=1, fijo=1, empate=1, sin_dato=0)
      and o['por_metrica']['profit_factor']['sin_dato'] == 1, o['por_metrica'])
check('P5b: por moneda', o['por_moneda']['BTCUSDT'] == dict(configs=2, fijo_retorno=8.0, auto_retorno=8.0)
      and o['por_moneda']['SOLUSDT']['configs'] == 1, o['por_moneda'])

# ── P6 ──
fake_res = dict(fijo=res, auto=dict(res, metrics=dict(res['metrics'], total_return_pct=15.0)))
cfg2 = dict(CFG, id=8, symbol='SOLUSDT')


async def loader(ids):
    return [CFG, cfg2]


async def runner(cfg, payloads):
    if cfg['id'] == 8:
        raise ValueError('No hay velas de SOLUSDT')
    assert payloads['auto']['sl_level_mode'] == 'atr'
    return fake_res, ['Aviso: x']


with tempfile.TemporaryDirectory() as td:
    out_json = os.path.join(td, 'c.json')
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cl.main(['--json-out', out_json], loader=loader, runner=runner, today=date(2026, 11, 24))
    txt = buf.getvalue()
    j = json.load(open(out_json, encoding='utf-8'))
check('P6a: una config que falla no frena las demás y se informa', rc == 0 and 'Config #8: no se pudo probar' in txt
      and 'No se pudieron probar: #8' in txt and j['failed'] == [8], txt[-400:])
check('P6b: periodo D-58 de la pantalla (24 meses completos hasta fin del mes anterior)',
      j['start'] == '2024-11-01' and j['end'] == '2026-10-31', (j['start'], j['end']))
check('P6c: reporte lado a lado y resumen', 'Retorno neto %' in txt and '12.35' in txt and '15' in txt
      and 'gana automático en 1' in txt and 'ningún modo se activa' in txt, txt[:600])
os.environ['SLTP_AUTO_ENABLED'] = 'false'
with redirect_stdout(io.StringIO()) as b2:
    rc2 = cl.main([], loader=loader, runner=runner, today=date(2026, 11, 24))
os.environ.pop('SLTP_AUTO_ENABLED')
check('P6d: con el interruptor general apagado no compara (saldrían iguales)', rc2 == 2 and 'apagado' in b2.getvalue())

# ── P7: backtest real (mismo _simulate que /backtest/run) sobre velas sintéticas ──
from api.v1.backtest import BacktestData, BacktestRequest, _simulate, parse_range  # noqa: E402

rng = np.random.default_rng(11)
n = 900
close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
dfx = pd.DataFrame({'time': pd.date_range('2024-08-01', periods=n, freq='4h', tz='UTC'), 'open': np.r_[close[0], close[:-1]],
                    'high': close * (1 + rng.uniform(0.001, 0.008, n)), 'low': close * (1 - rng.uniform(0.001, 0.008, n)),
                    'close': close, 'volume': 1.0 + rng.uniform(0, 1, n)})
start, end = parse_range('2024-11-01', '2025-01-31')
data = BacktestData(df=dfx, macro_df=None, minute_df=None, warnings=[], coverage={})
snap = dfx.copy()
pl7 = cl.variant_payloads(dict(CFG, params=json.dumps(dict(PARAMS, sl_level_mode='fixed', tp_level_mode='fixed'))),
                          '2024-11-01', '2025-01-31', ov)
out, _ = cl.simulate_pair(pl7, data, start, end)
ref = _simulate(BacktestRequest(**{**pl7['fijo']}), BacktestData(df=dfx.copy(), macro_df=None, minute_df=None, warnings=[],
                                                                 coverage={}), start, end, [])
tf, ta = out['fijo']['trades'], out['auto']['trades']


def dist(t):
    return round(abs(t['entry_price'] - t['sl']) / t['entry_price'] * 100, 4)


check('P7a: «fijo» da exactamente el backtest de la config tal cual', len(tf) > 5
      and [(t['entry_time'], t['exit_reason'], t['pnl']) for t in tf] == [(t['entry_time'], t['exit_reason'], t['pnl']) for t in ref['trades']],
      (len(tf), len(ref['trades'])))
check('P7b: en «fijo» el SL es el 1 % de la config', all(abs(dist(t) - 1.0) < 0.05 for t in tf if not t['trailing_applied']),
      sorted({dist(t) for t in tf})[:5])
ta0 = [t for t in ta if not t['be_activated'] and not t['trailing_applied']]   # SL todavía el de la entrada
check('P7c: en «auto» el SL sale del ATR (varía por operación, dentro de los topes)', len(ta0) > 5
      and len({dist(t) for t in ta0}) > 3 and all(d['sl_min_pct'] - 0.05 <= dist(t) <= d['sl_max_pct'] + 0.05 for t in ta0),
      sorted({dist(t) for t in ta0})[:6])
check('P7d: misma primera entrada en las dos (mismas reglas y filtros; después cambia cuándo sale cada una)',
      ta[0]['entry_time'] == tf[0]['entry_time'] and ta[0]['side'] == tf[0]['side'] and tf != ta)
check('P7e: las velas cargadas no se tocan (cada prueba con su copia)', data.df.equals(snap) and list(data.df.columns) == list(snap.columns))

# ── S ──
code = '\n'.join(l for l in SRC.splitlines() if not l.lstrip().startswith('#'))
check('S1: solo lee la base (transacción de solo lectura, sin escrituras)', 'TRANSACTION READ ONLY' in code
      and not any(w in code.upper() for w in ('INSERT ', 'UPDATE ', 'DELETE ', 'ALTER ')))
check('S2: baja prioridad antes de cargar velas y una config a la vez', 0 < code.find('low_priority()') < code.find('asyncio.run(loader(ids))')
      and 'for cfg in cfgs:' in code)

print('TODO OK' if fails == 0 else f'{fails} FALLOS')
sys.exit(1 if fails else 0)

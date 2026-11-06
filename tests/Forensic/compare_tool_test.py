"""
Comparador Paper vs backtest (BP-06): empareja por (lado, vela de entrada) y compara motivo y hora EXACTA de salida,
precios y PnL %; usa los parámetros congelados del snapshot (DynamicStrategy incluida: manda strategy_code); fechas por
defecto coherentes; una posición abierta en Paper frente a end_of_data no es divergencia. Sin base de datos ni motor.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/compare_tool_test.py
Antes del parche: FALLA (fechas invertidas, solo clases viejas, PnL absoluto, sin hora de salida).
"""
import asyncio
import io
import json
import os
import sys
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta

sys.path.insert(0, os.getcwd())  # python-engine/
os.environ.setdefault('INTERNAL_API_KEY', 'prueba')

import tools.analysis.compare_paper_vs_backtest as cmp  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


if not hasattr(cmp, 'match_trades'):
    check('el comparador expone match_trades/summarize/backtest_payload', False, 'no (código anterior)')
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)

H = timedelta(hours=1)
T = datetime(2026, 11, 2, 10, 0)
CODE = 'class S(BaseStrategy):\n    pass\n'
SNAP = dict(strategy_code=CODE, strategy_config={'x': 1}, sl_pct=1.5, tp_pct=3.0, symbol='BTCUSDT', interval='60',
            strategy_class='DynamicStrategy')
CFG = dict(id=54, display_name='Mi estrategia — BTCUSDT H1', symbol='BTCUSDT', interval='60', params=json.dumps(SNAP))


def pt(i, side, entry_t, et=None, reason=None, status='closed', ep=100.0, xp=101.0, pnl_pct=1.0, snap=SNAP):
    return dict(id=i, side=side, entry_price=ep, exit_price=xp if status == 'closed' else None, entry_time=entry_t,
                exit_time=et if status == 'closed' else None, exit_reason=reason if status == 'closed' else None,
                pnl_pct=pnl_pct if status == 'closed' else None, status=status, config_snapshot=json.dumps(snap))


def bt(side, entry_t, et, reason, ep=100.0, xp=101.0, pnl_pct=0.9):
    return dict(side=side, entry_time=entry_t.isoformat() + '+00:00', exit_time=et.isoformat() + '+00:00',
                exit_reason=reason, entry_price=ep, exit_price=xp, pnl_pct=pnl_pct)


PAPER = [
    pt(1, 'long', T + timedelta(minutes=1), T + timedelta(minutes=47), 'stop_loss'),              # igual
    pt(2, 'short', T + 3 * H + timedelta(seconds=40), T + 4 * H + timedelta(minutes=5), 'take_profit_1'),  # motivo distinto
    pt(3, 'long', T + 6 * H + timedelta(minutes=1), T + 7 * H + timedelta(minutes=12), 'stop_loss'),       # hora distinta
    pt(4, 'long', T + 9 * H + timedelta(minutes=1), T + 12 * H + timedelta(minutes=1), 'time_exit'),       # tiempo: +1 min
    pt(5, 'long', T + 14 * H + timedelta(minutes=1), status='open'),                                       # abierta
    pt(6, 'short', T + 16 * H + timedelta(minutes=1), T + 17 * H, 'stop_loss'),                            # solo Paper
]
BT = [
    bt('long', T, T + timedelta(minutes=47), 'stop_loss'),
    bt('short', T + 3 * H, T + 4 * H + timedelta(minutes=5), 'stop_loss'),
    bt('long', T + 6 * H, T + 7 * H + timedelta(minutes=10), 'stop_loss'),
    bt('long', T + 9 * H, T + 12 * H, 'time_exit'),
    bt('long', T + 14 * H, T + 20 * H, 'end_of_data'),
    bt('long', T + 16 * H, T + 17 * H, 'stop_loss'),                                                        # solo backtest (lado distinto)
]

rows = cmp.match_trades(PAPER, BT, H)
kinds = [(r['side'], r['candle'].strftime('%H:%M'), r['kind']) for r in rows]
check('empareja por (lado, vela de entrada): 7 filas en orden',
      kinds == [('long', '10:00', 'igual'), ('short', '13:00', 'distinta'), ('long', '16:00', 'distinta'),
                ('long', '19:00', 'igual'), ('long', '00:00', 'abierta'), ('long', '02:00', 'solo_backtest'),
                ('short', '02:00', 'solo_paper')], kinds)
r = {(x['side'], x['candle'].strftime('%H:%M')): x for x in rows}
check('motivo distinto se informa', r[('short', '13:00')]['why'] == ['motivo take_profit_1 vs stop_loss'], r[('short', '13:00')]['why'])
check('hora de salida distinta (+2 min) se informa: la hora es exacta (p19/p24)',
      r[('long', '16:00')]['why'] == ['hora de salida +2.0 min'], r[('long', '16:00')]['why'])
check('salida por tiempo máximo: +1 min dentro de la tolerancia (Paper la ejecuta en el tick siguiente)',
      r[('long', '19:00')]['kind'] == 'igual', r[('long', '19:00')].get('why'))
check('Paper abierta frente a end_of_data: «abierta», no divergencia', r[('long', '00:00')]['kind'] == 'abierta')
check('lados distintos en la misma vela no se emparejan', r[('short', '02:00')]['kind'] == 'solo_paper'
      and r[('long', '02:00')]['kind'] == 'solo_backtest')
s = cmp.summarize(rows)
check('resumen: 2 iguales, 2 distintas, 1 abierta, 1 solo Paper, 1 solo backtest, 4 divergencias',
      (s['igual'], s['distinta'], s['abierta'], s['solo_paper'], s['solo_backtest'], s['divergencias']) == (2, 2, 1, 1, 1, 4), s)
check('resumen: mismo motivo 3/4 y misma hora 3/4 entre las cerradas emparejadas',
      (s['emparejadas_cerradas'], s['mismo_motivo'], s['misma_hora']) == (4, 3, 3), s)

# Vela diaria (antes: int('D') se caía) y vela de 4 h alineada a 00:00 UTC
check("intervalo 'D': vela del día", cmp.candle(datetime(2026, 11, 2, 15, 7), timedelta(days=1)) == datetime(2026, 11, 2))
check('intervalo 240: vela 12:00', cmp.candle(datetime(2026, 11, 2, 15, 7), timedelta(hours=4)) == datetime(2026, 11, 2, 12))

# Payload: parámetros congelados del snapshot, con strategy_code (DynamicStrategy), sin duplicar símbolo/intervalo
p = cmp.backtest_payload(CFG, SNAP, '2026-11-02', '2026-11-06')
check('payload con strategy_code y strategy_config del snapshot (DynamicStrategy)',
      p['strategy_code'] == CODE and p['strategy_config'] == {'x': 1} and p['sl_pct'] == 1.5, p)
check('payload: nombre, símbolo e intervalo de la config; rango; sin walk forward',
      (p['strategy'], p['symbol'], p['interval'], p['start_date'], p['end_date'], p['walk_forward']) ==
      ('Mi estrategia — BTCUSDT H1', 'BTCUSDT', '60', '2026-11-02', '2026-11-06', False), p)

# Fechas por defecto: desde el primer trade hasta hoy (antes: inicio > fin)
check('rango por defecto: primer trade de Paper → hoy',
      cmp.default_range(PAPER, None, None, date(2026, 11, 6)) == ('2026-11-02', '2026-11-06'))
check('rango explícito se respeta', cmp.default_range(PAPER, '2026-10-01', '2026-10-31', date(2026, 11, 6)) == ('2026-10-01', '2026-10-31'))

# Cambio de config dentro del rango: se usa el primer snapshot y se avisa
other = PAPER + [pt(7, 'long', T + 30 * H, T + 31 * H, 'stop_loss', snap=dict(SNAP, sl_pct=2.0))]
snap, n_other = cmp.pick_snapshot(other)
check('pick_snapshot: el del primer trade y 1 con otros parámetros', snap['sl_pct'] == 1.5 and n_other == 1, n_other)

# main() de punta a punta con base y motor simulados
sent = {}


async def _load(cid, start, end):
    return CFG, PAPER


def _bt(payload):
    sent.update(payload)
    return {'result': {'trades': BT}, 'warnings': ['Aviso: prueba']}


buf = io.StringIO()
with redirect_stdout(buf):
    code = cmp.main(['--config', '54'], loader=_load, backtester=_bt, today=date(2026, 11, 6))
txt = buf.getvalue()
check('main(): código 1 con divergencias', code == 1, code)
check('main(): el backtest corrió con el snapshot y el rango por defecto',
      sent.get('strategy_code') == CODE and sent.get('start_date') == '2026-11-02' and sent.get('end_date') == '2026-11-06', sent)
check('main(): el informe trae la cuenta de divergencias y los avisos del backtest',
      'DIVERGENCIAS: 4' in txt and 'Aviso: prueba' in txt, txt[-300:])
check('main(): no compara PnL absoluto (solo PnL %)', 'PnL total' not in txt and 'pnl=' not in txt)

with redirect_stdout(io.StringIO()):
    code = cmp.main(['--config', '54'], loader=_load, backtester=lambda p: {'result': {'trades': BT[:4] + [BT[4]]}},
                    today=date(2026, 11, 6))
check('main(): sigue en 1 mientras haya divergencias (otro escenario)', code == 1, code)


async def _load_eq(cid, start, end):
    return CFG, PAPER[:1]


with redirect_stdout(io.StringIO()):
    code = cmp.main(['--config', '54'], loader=_load_eq, backtester=lambda p: {'result': {'trades': BT[:1]}},
                    today=date(2026, 11, 6))
check('main(): código 0 sin divergencias', code == 0, code)


async def _load_none(cid, start, end):
    return None, []


with redirect_stdout(io.StringIO()):
    code = cmp.main(['--config', '99'], loader=_load_none, backtester=_bt)
check('main(): config inexistente -> código 2', code == 2, code)

# De punta a punta con salidas REALES: Paper simulado (monitor + señales con 1m) y el motor sobre el mismo mercado
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_reuse_test as sr  # noqa: E402

hours, mins = sr.market()
pp = dict(sr.po.BASE, sl_pct=0.5, tp_pct=0.8, close_on_opposite=True)
eng = sr.engine_run(pp, hours, mins, 70)
store = asyncio.run(sr.paper_parity(pp, hours, mins, 70))
rows = cmp.match_trades(store.trades, eng, H)
s = cmp.summarize(rows)
check(f"Paper real vs motor real: {s['emparejadas_cerradas']} cerradas emparejadas, 0 divergencias, hora y motivo iguales",
      s['divergencias'] == 0 and s['emparejadas_cerradas'] >= 20 and s['misma_hora'] == s['emparejadas_cerradas']
      and s['mismo_motivo'] == s['emparejadas_cerradas'] and s['abierta'] <= 1, s)

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)

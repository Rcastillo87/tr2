"""
Comparador Paper vs backtest (BP-06): empareja por (lado, vela de entrada) y compara motivo y hora EXACTA de salida,
precios y PnL %; usa los parámetros congelados del snapshot (DynamicStrategy incluida: manda strategy_code); fechas por
defecto coherentes; una posición abierta en Paper frente a end_of_data no es divergencia. Sin base de datos ni motor.
p81 (19-nov): el rango termina en el último día completo (ayer UTC; un --end de hoy se recorta) y un cambio de
parámetros parte la comparación en tramos, cada uno con su backtest (límite = cambio registrado de la config).
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

# Fechas por defecto: desde el primer trade hasta AYER, el último día completo (p81; antes hoy, con el día sin terminar)
check('rango por defecto: primer trade de Paper → ayer (último día completo)',
      cmp.default_range(PAPER, None, None, date(2026, 11, 6)) == ('2026-11-02', '2026-11-05'),
      cmp.default_range(PAPER, None, None, date(2026, 11, 6)))
check('rango explícito anterior a hoy se respeta',
      cmp.default_range(PAPER, '2026-10-01', '2026-10-31', date(2026, 11, 6)) == ('2026-10-01', '2026-10-31'))
e, note = cmp.last_full_day('2026-11-06', date(2026, 11, 6))
check('--end de hoy se recorta a ayer, con aviso', e == '2026-11-05' and note and 'último día completo' in note, (e, note))
check('--end futuro se recorta a ayer', cmp.last_full_day('2026-12-01', date(2026, 11, 6))[0] == '2026-11-05')
check('--end de ayer no se toca ni avisa', cmp.last_full_day('2026-11-05', date(2026, 11, 6)) == ('2026-11-05', None))

# Tramos por snapshot (p81; antes: un solo backtest con el primer snapshot y un aviso)
S2 = dict(SNAP, sl_pct=2.0)
A1 = pt(11, 'long', T, T + H, 'stop_loss')
A2 = pt(12, 'long', T + 5 * H, T + 6 * H, 'stop_loss')
B1 = pt(13, 'long', T + 20 * H, T + 21 * H, 'stop_loss', snap=S2)
A3 = pt(14, 'long', T + 40 * H, T + 41 * H, 'stop_loss')
CH = T + 9 * H   # cambio de la config registrado entre A2 y B1
seg = cmp.snapshot_segments([B1, A2, A1], [CH, T - 48 * H, T + 30 * H])
check('dos snapshots → dos tramos en orden de entrada, con sus trades',
      [(len(x['trades']), x['params']['sl_pct']) for x in seg] == [(2, 1.5), (1, 2.0)], [(len(x['trades']), x['key']) for x in seg])
check('límite = el cambio registrado entre el último trade de un tramo y el primero del siguiente',
      seg[0]['lo'] is None and seg[0]['hi'] == CH and seg[1]['lo'] == CH and seg[1]['hi'] is None, (seg[0]['hi'], seg[1]['lo']))
seg = cmp.snapshot_segments([A1, A2, B1])
check('sin cambio registrado: el límite es la entrada del primer trade del tramo nuevo', seg[1]['lo'] == B1['entry_time'])
seg = cmp.snapshot_segments([A1, A2, B1, A3], [CH, T + 30 * H, T + 35 * H])
check('A → B → A: tres tramos (los parámetros que vuelven son un tramo nuevo); el último cambio dentro del hueco manda',
      [x['key'] for x in seg] == [cmp.snapshot_key(SNAP), cmp.snapshot_key(S2), cmp.snapshot_key(SNAP)]
      and seg[2]['lo'] == T + 35 * H, [(x['lo'], x['hi']) for x in seg])
seg = cmp.snapshot_segments([dict(A1, config_snapshot=None)], fallback=SNAP)
check('trade sin snapshot: usa los parámetros de la config', seg[0]['params']['sl_pct'] == 1.5)

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
check('main(): el backtest corrió con el snapshot y el rango por defecto (hasta ayer)',
      sent.get('strategy_code') == CODE and sent.get('start_date') == '2026-11-02' and sent.get('end_date') == '2026-11-05', sent)
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

# main() con un cambio de parámetros: un backtest por tramo, cada uno compara solo sus operaciones
calls, ends = [], []
BT_A = [bt('long', T, T + H, 'stop_loss'), bt('long', T + 5 * H, T + 6 * H, 'stop_loss'),
        bt('long', T + 12 * H, T + 13 * H, 'stop_loss')]    # 12:00 cae después del cambio: no es del tramo A
BT_B = [bt('long', T + 7 * H, T + 8 * H, 'stop_loss'),      # antes del cambio: no es del tramo B
        bt('long', T + 20 * H, T + 21 * H, 'stop_loss')]


async def _load_seg(cid, start, end):
    ends.append(end)
    return dict(CFG, change_times=[CH]), [A1, A2, B1]


def _bt_seg(payload):
    calls.append((payload['sl_pct'], payload['start_date'], payload['end_date']))
    return {'result': {'trades': BT_A if payload['sl_pct'] == 1.5 else BT_B}}


buf = io.StringIO()
jout = '/tmp/compare_tool_test.json'
with redirect_stdout(buf):
    code = cmp.main(['--config', '54', '--end', '2026-11-06', '--json-out', jout], loader=_load_seg, backtester=_bt_seg,
                    today=date(2026, 11, 6))
txt = buf.getvalue()
check('main(): --end de hoy se recorta antes de leer Paper (la carga pide hasta ayer) y se avisa',
      ends == ['2026-11-05'] and 'último día completo' in txt, (ends, txt[:200]))
check('main(): un backtest por tramo con sus parámetros, cada uno hasta el fin del rango',
      calls == [(1.5, '2026-11-02', '2026-11-05'), (2.0, '2026-11-02', '2026-11-05')], calls)
check('main(): cada tramo compara solo las entradas de su ventana → 0 divergencias, código 0',
      code == 0 and 'tramo 1/2' in txt and 'tramo 2/2' in txt and 'DIVERGENCIAS: 0' in txt, txt[-400:])
j = json.load(open(jout))
check('main(): el JSON trae el total, las filas con su snapshot y los tramos',
      j['summary']['igual'] == 3 and len(j['segments']) == 2 and {r['snapshot'] for r in j['rows']} ==
      {cmp.snapshot_key(SNAP), cmp.snapshot_key(S2)}, j['summary'])
calls.clear()
with redirect_stdout(io.StringIO()):
    code = cmp.main(['--config', '54', '--latest-only'], loader=_load_seg, backtester=_bt_seg, today=date(2026, 11, 6))
check('main(): --latest-only corre solo el tramo vigente', calls == [(2.0, '2026-11-02', '2026-11-05')] and code == 0, calls)


# ── C5-06 (p104): el reporte dice qué versión compara y avisa si la config cambió después de la última operación ──
LATER = B1['entry_time'] + timedelta(days=1) if isinstance(B1['entry_time'], datetime) else None
check('V1: changed_after: cambio posterior a la última entrada -> esa fecha; anteriores -> None',
      cmp.changed_after(cmp.snapshot_segments([A1, A2, B1], [CH]), [CH, LATER]) == cmp.naive_utc(LATER)
      and cmp.changed_after(cmp.snapshot_segments([A1, A2, B1], [CH]), [CH]) is None
      and cmp.changed_after([], [LATER]) is None, LATER)
segA = cmp.snapshot_segments([A1, A2])   # un solo tramo con dos operaciones
mid = cmp.naive_utc(A1['entry_time']) + (cmp.naive_utc(A2['entry_time']) - cmp.naive_utc(A1['entry_time'])) / 2
check('V1b: cambio justo a la hora de la última entrada: no es «después» (esa operación ya es de la versión nueva)',
      cmp.changed_after(segA, [cmp.naive_utc(A2['entry_time'])]) is None)
check('V1c: cambio entre dos operaciones del mismo último tramo: no es «después» (cuenta la última entrada)',
      cmp.changed_after(segA, [mid]) is None, mid)
vl = cmp.version_line(CFG)
check('V2: version_line: id, huella de los parámetros y del código de la config de hoy',
      f"#{CFG['id']}" in vl and cmp.snapshot_key(cmp.as_dict(CFG.get('params'))) in vl and 'código' in vl, vl)


async def _load_stale(cid, start, end):
    return dict(CFG, change_times=[CH, LATER]), [A1, A2, B1]


for flags in ([], ['--latest-only']):
    buf = io.StringIO()
    calls.clear()
    with redirect_stdout(buf):
        code = cmp.main(['--config', '54', '--json-out', jout] + flags, loader=_load_stale, backtester=_bt_seg,
                        today=date(2026, 11, 6))
    txt = buf.getvalue()
    j = json.load(open(jout))
    check(f'V3{" --latest-only" if flags else ""}: la config cambió después: aviso en grande y el tramo dice «NO es la vigente»',
          'el último tramo NO es la configuración vigente' in txt and 'NO es la vigente' in txt
          and j['segments'][-1]['vigente'] is False and j['config_changed_after'] is not None, txt[:300])
buf = io.StringIO()
with redirect_stdout(buf):
    cmp.main(['--config', '54', '--latest-only', '--json-out', jout], loader=_load_seg, backtester=_bt_seg,
             today=date(2026, 11, 6))
txt = buf.getvalue()
j = json.load(open(jout))
check('V4: sin cambios después: sin aviso, el tramo dice «vigente», con su huella de parámetros y de código',
      'NO es la configuración vigente' not in txt and '· vigente' in txt and 'config vigente #' in txt
      and f"parámetros {cmp.snapshot_key(S2)}" in txt and j['segments'][-1]['vigente'] is True
      and j['config_changed_after'] is None and j['config_params_key'], txt[:300])
src = (ROOT / 'python-engine' / 'tools' / 'analysis' / 'compare_paper_vs_backtest.py').read_text(encoding='utf-8') \
    if 'ROOT' in globals() else open(os.path.join(os.getcwd(), 'tools', 'analysis', 'compare_paper_vs_backtest.py'),
                                     encoding='utf-8').read()
check("V5: solo los cambios que tocan parámetros cuentan (created / updated; no activar ni desactivar)",
      "AND action IN ('created', 'updated')" in src)


async def _load_today(cid, start, end):
    return CFG, []


with redirect_stdout(io.StringIO()):
    code = cmp.main(['--config', '54'], loader=_load_today, backtester=_bt, today=date(2026, 11, 6))
check('main(): sin trades hasta ayer -> código 2', code == 2, code)

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

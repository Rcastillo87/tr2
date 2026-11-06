"""
Snapshot sin strategy_code (BP-07): sin el código la estrategia no se construye y Paper saltaba la posición en cada ciclo
(sin SL/TP); Real saltaba la gestión del bot. Ahora se toma SOLO el código de la config viva y los parámetros siguen
siendo los congelados del snapshot. Sin config viva, el error de siempre (sin cambios). Sin base de datos.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/snapshot_code_test.py
Antes del parche: FALLAN los casos con config viva.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import minute_gap_test as mg  # noqa: E402   (Paper con pool en memoria, reloj y 1m)
import trading.real_trader as rt_mod  # noqa: E402
from trading.paper_trader import PaperTrader  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


RLOGS: list = []


class _Cap(logging.Handler):
    def emit(self, record):
        RLOGS.append((record.levelname, record.getMessage()))


logging.getLogger(rt_mod.__name__).addHandler(_Cap())

UTC = timezone.utc
FROZEN = {k: v for k, v in mg.P.items() if k != 'strategy_code'}            # snapshot viejo: sin código
LIVE = {'id': 1, 'symbol': 'BTCUSDT', 'interval': '60',
        'params': dict(mg.P, sl_pct=3.0, slippage_pct=1.0)}                  # config viva: otros parámetros


async def paper_case(config_map, snapshot):
    t0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    now = datetime(2026, 3, 2, 11, 0, tzinfo=UTC)
    s = mg.store(mg.minutes(t0 + timedelta(minutes=1), now - timedelta(minutes=1),
                            touch={datetime(2026, 3, 2, 10, 20, tzinfo=UTC): 98.9}))
    s['trade']['config_snapshot'] = json.dumps(snapshot)
    mg.CLOCK[0] = now
    mg.LOGS.clear()
    await PaperTrader(mg.Pool(s), {}, config_map).monitor_open_trades()
    return s['trade']


async def main():
    # ── Paper ──
    tr = await paper_case({1: LIVE}, FROZEN)
    check('Paper: snapshot sin código + config viva -> gestiona y cierra por SL (antes se saltaba la posición)',
          tr['status'] == 'closed' and tr.get('exit_reason') == 'stop_loss', (tr['status'], tr.get('exit_reason')))
    check('Paper: con los parámetros CONGELADOS (sin el slippage 1 % de la config viva)',
          tr['status'] == 'closed' and abs(tr.get('exit_price', 0) - 99.0) < 1e-9, tr.get('exit_price'))
    check('Paper: aviso en el log', any('no trae strategy_code' in m for lvl, m in mg.LOGS if lvl == 'WARNING'),
          [m for _, m in mg.LOGS][:3])

    tr = await paper_case({}, FROZEN)
    check('Paper: sin config viva -> como antes (no se gestiona, error en el log, no se cae)',
          tr['status'] == 'open' and any('no se puede construir' in m for lvl, m in mg.LOGS if lvl == 'ERROR'),
          (tr['status'], [m for _, m in mg.LOGS][:2]))

    other = dict(mg.P, strategy_code=mg.CODE.replace('class T', 'class U'))
    pt = PaperTrader(None, {}, {1: dict(LIVE, params=other)})
    got = pt._trade_params({'id': 7, 'paper_strategy_config_id': 1, 'config_snapshot': json.dumps(mg.P)})
    check('Paper: snapshot CON código -> usa el suyo (no el de la config viva)', got['strategy_code'] == mg.P['strategy_code'])
    got = pt._trade_params({'id': 7, 'paper_strategy_config_id': 1, 'config_snapshot': json.dumps(dict(FROZEN, strategy_code='  '))})
    check('Paper: strategy_code en blanco cuenta como faltante', got['strategy_code'] == other['strategy_code'])

    # ── Real ──
    trd = RealTrader(None)
    trade = {'id': 9, 'symbol': 'BTCUSDT', 'interval': '60', 'config_snapshot': json.dumps(FROZEN),
             'live_strategy_code': mg.CODE}
    RLOGS.clear()
    s = trd._trade_strategy(trade)
    check('Real: snapshot sin código + código de la suscripción -> estrategia construida (antes None)', s is not None)
    check('Real: con los parámetros congelados (sl_pct 1.0 del snapshot)', s is not None and float(s.sl_pct) == 1.0,
          getattr(s, 'sl_pct', None))
    check('Real: aviso en el log', any('no trae strategy_code' in m for lvl, m in RLOGS if lvl == 'WARNING'), RLOGS[:2])
    RLOGS.clear()
    s = trd._trade_strategy(dict(trade, live_strategy_code=None))
    check('Real: sin código vivo -> None con el error de siempre',
          s is None and any('no se puede construir' in m for _, m in RLOGS), RLOGS[:2])

    src = open('trading/real_trader.py').read()
    check('Real: las dos consultas de trades abiertos traen live_strategy_code',
          src.count("psc.params->>'strategy_code' AS live_strategy_code") == 2)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())

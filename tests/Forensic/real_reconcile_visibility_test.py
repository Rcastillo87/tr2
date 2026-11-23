"""
C5-07 (p100): la conciliación de Real no esconde fallos.
R. Respuesta: complete/status dicen si quedó completa; un error de Bybit va a 'errors' (no a 'ok'); esperar el
   closed-pnl va a 'pending' (no es fallo); un error inesperado en una cuenta no deja sin conciliar a las demás.
H. Huérfanas: el tipo (cierre / apertura) sale de una marca fija al comienzo de error_message, no del texto; las filas
   anteriores a p100 (texto viejo) siguen reconociéndose; todos los que marcan 'orphaned' usan la marca.
Sin base ni Bybit: dobles de real_recovery_test.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_reconcile_visibility_test.py
"""
import asyncio
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402
import real_recovery_test as rr  # noqa: E402
import api.v1.real_trading as api  # noqa: E402
import trading.real_trader as rt  # noqa: E402
from trading.real_trader import RealTrader  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def orphan(tid, msg):
    return dict(rp.trade(), id=tid, status='orphaned', entry_time=NOW - timedelta(hours=2), order_link_id=f'tr2-{tid}',
                error_message=msg, snapshot=dict(rp.P))


async def run(s, client, orphans=(), open_trades=(), boom_accounts=(), accounts=(7,), settle=None):
    """Concilia las cuentas con dobles: orphans = filas 'orphaned'; boom_accounts = cuentas cuya lectura explota."""
    class Conn(rr.RecConn):
        async def fetch(self, sql, *a):
            if "rt.status = 'orphaned'" in sql:
                return list(orphans)
            return await super().fetch(sql, *a)

    class Pool(rr.RecPool):
        def acquire(self):
            pool = self

            class _C:
                async def __aenter__(self_):
                    return Conn(pool.s)

                async def __aexit__(self_, *e):
                    return False
            return _C()

    class _Trader(RealTrader):
        async def get_open_trades(self, account_id):
            if account_id in boom_accounts:
                raise RuntimeError('fallo inesperado simulado')
            return list(open_trades)

        async def settle_exchange_close(self, *a, **k):
            return settle

        async def log_audit(self, *a, **k):
            return None

    pool = Pool(s)

    async def _pool():
        return pool
    api.get_json_pool = _pool
    api.RealTrader = _Trader
    api._build_broker_client = lambda acc: client
    accs = [api.AccountPayload(id=i, broker='bybit', account_type='demo', api_key='k', api_secret='s', subscriptions=[])
            for i in accounts]
    return await api.reconcile(api.RealTickRequest(accounts=accs), x_internal_api_key=api.INTERNAL_API_KEY)


async def part_response():
    out = await run({'exec': []}, rr.RecClient())
    check('R1: sin nada que conciliar: complete=True, status ok, listas vacías (errors y pending presentes)',
          out['complete'] is True and out['status'] == 'ok' and out['results']['errors'] == [] and out['results']['pending'] == [],
          out)
    # huérfana de apertura sin posición y Bybit falla al consultar la orden: error visible, no 'ok'
    o = orphan(41, rt.orphan_message('open', 'No confirmada tras 3 verificaciones (38s)'))
    out = await run({'exec': []}, rr.RecClient(order='ERR', positions=[None]), orphans=[o])
    res = out['results']
    check('R2: Bybit falla con una huérfana: va a errors (antes a ok con nota) y complete=False / status partial',
          [e.get('note') for e in res['errors']] == ['orphaned_api_error'] and not res['ok'] and out['complete'] is False
          and out['status'] == 'partial', out)
    # huérfana de cierre que sigue sin closed-pnl: pendiente, no fallo
    o = orphan(42, rt.orphan_message('close', 'Posicion cerrada en Bybit, sin closed-pnl tras reintento'))
    out = await run({'exec': []}, rr.RecClient(), orphans=[o], settle=None)
    res = out['results']
    check('R3: huérfana de cierre esperando el closed-pnl: va a pending (antes a ok), complete=True',
          [p['trade_id'] for p in res['pending']] == [42] and not res['ok'] and out['complete'] is True, out)
    # una cuenta explota: la otra se concilia igual y el error queda en la respuesta
    out = await run({'exec': []}, rr.RecClient(), boom_accounts=(7,), accounts=(7, 8),
                    open_trades=[dict(rp.trade(), id=50, entry_time=datetime.now(timezone.utc))])
    res = out['results']
    check('R4: error inesperado en la cuenta 7: la 8 se concilia igual (su trade en ok) y el error queda visible',
          [e.get('account_id') for e in res['errors']] == [7] and 'RuntimeError' in res['errors'][0]['error']
          and [x['trade_id'] for x in res['ok']] == [50] and out['complete'] is False, out)
    # pending_open y Bybit falla al consultar su orden: error visible
    s = {'exec': [], 'pending': [rr.pending()]}
    out = await run(s, rr.RecClient(order='ERR'))
    check('R5: pending_open y Bybit falla: va a errors (antes a ok con nota)',
          [e.get('note') for e in out['results']['errors']] == ['pending_open_api_error'] and not out['results']['ok'], out)


async def part_orphans():
    check('H1: marca de cierre / apertura', rt.is_close_orphan({'error_message': rt.orphan_message('close', 'x')})
          and not rt.is_close_orphan({'error_message': rt.orphan_message('open', 'x')}))
    check('H2: filas anteriores a p100: el texto viejo sigue siendo de cierre; «No confirmada…» de apertura',
          rt.is_close_orphan({'error_message': 'Posicion cerrada en Bybit, no se pudo obtener pnl real (get_closed_pnl sin match)'})
          and not rt.is_close_orphan({'error_message': 'No confirmada tras 3 verificaciones (38s)'})
          and not rt.is_close_orphan({'error_message': None}))
    check('H8: la de cierre conserva el texto anterior (si se revierte p100, el código previo la sigue reconociendo)',
          'no se pudo obtener pnl real' in rt.orphan_message('close', 'x')
          and 'no se pudo obtener pnl real' not in rt.orphan_message('open', 'x'))
    check('H3: la marca manda sobre el texto (apertura aunque el detalle diga «no se pudo obtener pnl real»)',
          not rt.is_close_orphan({'error_message': rt.orphan_message('open', 'no se pudo obtener pnl real')}))
    # la huérfana de cierre con la marca nueva va por la liquidación (2a), no por la búsqueda de posición (2b)
    o = orphan(43, rt.orphan_message('close', 'Posicion cerrada en Bybit, sin closed-pnl (conciliacion)'))
    c = rr.RecClient(positions=[{'size': '1', 'avgPrice': '100', 'side': 'Buy'}])
    await run({'exec': []}, c, orphans=[o], settle=True)
    check('H4: huérfana de cierre con la marca nueva: se liquida con Bybit y no se busca la posición',
          c.checks == 0 and c.link_queries == [], (c.checks, c.link_queries))
    # todos los que marcan 'orphaned' usan la marca
    srcs = {f: (ROOT / 'python-engine' / f).read_text(encoding='utf-8')
            for f in ('trading/real_trader.py', 'api/v1/real_trading.py')}
    writers = sum(len(re.findall(r"status\s*=\s*'orphaned',\s*error_message\s*=\s*\$2", s)) for s in srcs.values())
    literal = sum(len(re.findall(r"status\s*=\s*'orphaned',\s*error_message\s*=\s*'", s)) for s in srcs.values())
    tagged = sum(s.count("orphan_message('close'") + s.count("orphan_message('open'") for s in srcs.values())
    check('H5: los 5 lugares que marcan una huérfana usan orphan_message (ninguno con texto fijo)',
          writers == 5 and literal == 0 and tagged == 5, (writers, literal, tagged))
    api_src = srcs['api/v1/real_trading.py']
    check('H6: la conciliación decide el tipo con is_close_orphan (no con el texto)',
          'if is_close_orphan(trade):' in api_src and "'no se pudo obtener pnl real' in" not in api_src)
    check("H7: ningún resultado de error se anota en 'ok' ni con setdefault",
          "'note': 'orphaned_api_error'})" in api_src and "results['ok'].append({'trade_id': trade['id'], 'symbol': symbol, 'note'" not in api_src
          and "results['ok'].append({'trade_id': tid, 'symbol': symbol, 'note'" not in api_src and "setdefault('errors'" not in api_src)


async def main():
    await part_response()
    await part_orphans()
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())

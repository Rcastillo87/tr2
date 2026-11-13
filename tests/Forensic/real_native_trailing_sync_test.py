"""
R-12 (auditoría 13-nov, INV-006): con trailing 'fixed' Real arma el trailing NATIVO de Bybit (activePrice + trailingStop).
Antes de activarse, Bybit informa en la orden TrailingProfit triggerPrice = activePrice ± trailingStop; el monitor lo
tomaba como SL vivo desde el primer minuto (sl ficticio en zona de ganancia + trailing_applied) y el circuit breaker
cerraba con ~0,4 % en contra (#86, #91 en demo). Ahora: solo se sincroniza un trailing ACTIVADO (el precio llegó al
activePrice), con un nivel que protege y mejora; un trailing_applied sin activación se repara al SL de Bybit; el
circuit breaker usa el SL vivo como referencia de trailing solo si está activado.
Casos con los precios reales de los trades #91 y #93 (ETHUSDT short). Sin base de datos ni Bybit.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_native_trailing_sync_test.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())                                   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))    # tests/Forensic/

import real_parity_test as rp  # noqa: E402  (pool/cliente simulados; anula las esperas)
from trading.real_trader import RealTrader  # noqa: E402

fails = 0
# Snapshot real de los trades #86/#91/#93 (VWAP Tendencia ETHUSDT H4), con el código de prueba de rp
SNAP = dict(sl_pct=1.5, tp_pct=3, be_pct=1.5, max_duration=0, regime_filter=False, commission_pct=0.055,
            slippage_pct=0.05, trailing_mode='fixed', trailing_distance_pct=1, trailing_activation_buffer_pct=1.8,
            strategy_code=rp.CODE)


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


def t93(sl=1959.97515, trailing=False, be_activated=False):
    """#93: short ETHUSDT @ 1931.01; activePrice 1896.25182, trailingStop 19.3101 (Bybit informó 1915.56)."""
    return {'id': 93, 'subscription_id': 94, 'strategy': 'VWAP Tendencia', 'symbol': 'ETHUSDT', 'interval': '240',
            'side': 'short', 'entry_price': 1931.01, 'sl': sl, 'tp': 1873.0797, 'tp2': None, 'tp3': None, 'tp4': None,
            'be_level': 1902.04485, 'be_activated': be_activated, 'size': 15.0, 'original_size': 15.0,
            'realized_pnl_partial': 0, 'entry_time': datetime.now(timezone.utc) - timedelta(minutes=30),
            'updated_at': None, 'order_id': 'A', 'balance_before': 49000.0, 'status': 'open',
            'trailing_applied': trailing, 'original_sl': 1959.97515, 'config_snapshot': dict(SNAP),
            'vol_widened': False}


def t91(sl=2039.87, trailing=True):
    """#91: short ETHUSDT @ 2056.33; activePrice 2019.31606, trailingStop 20.5633; SL real 2087.17495."""
    return {**t93(), 'id': 91, 'entry_price': 2056.33, 'sl': sl, 'tp': 1994.6401, 'be_level': 2025.48505,
            'original_sl': 2087.17495, 'trailing_applied': trailing}


class Client(rp.FakeClient):
    def __init__(self, native, ex_sl, tp, mark=None, **kw):
        pos = {'size': '15', 'avgPrice': '1931.01', 'stopLoss': str(ex_sl), 'takeProfit': str(tp)}
        if mark is not None:
            pos['markPrice'] = str(mark)
        super().__init__(position=pos, **kw)
        self.native = native

    async def get_native_trailing_level(self, symbol):
        return self.native


def updates(s, word):
    return [a for sql, a in s['exec'] if word in sql]


def audit_actions(s):
    return [e.get('action') for e in (s.get('audit') or [])]


async def monitor(tr, client, price, extremes):
    s = {'exec': [], 'audit': None, 'extremes': extremes}
    out = await RealTrader(rp.FakePool(s))._monitor_single_trade(tr, client, {'ETHUSDT': price}, 11)
    return out, s


async def breaker(tr, client, extremes):
    s = {'exec': [], 'audit': None, 'extremes': extremes}
    trader = RealTrader(rp.FakePool(s))
    closed = []

    async def _open(account_id):
        return [tr]

    async def _close(trade, reason, client, account_id, **k):
        closed.append(reason)
        return True
    trader.get_open_trades, trader.close_trade = _open, _close
    out = await trader.check_max_loss_circuit_breaker(11, client)
    return out, closed


async def main():
    # S1. #93 recién abierto: Bybit informa 1915.56 (activePrice + trailingStop) y el precio nunca llegó a 1896.25
    c = Client(1915.56, 1959.97515, 1873.0797)
    out, s = await monitor(t93(), c, 1931.0, {'hi': 1935.0, 'lo': 1925.0})
    check('S1 sin activación: NO se sincroniza el nivel nativo (sl y trailing_applied intactos)',
          not updates(s, 'trailing_applied=true') and not c.stops, (updates(s, 'trailing_applied=true'), c.stops))

    # S2. #93 tal como quedó en la base (sl ficticio 1915.56 + trailing_applied): se repara al SL de Bybit
    c = Client(1915.56, 1959.97515, 1873.0797)
    tr = t93(sl=1915.56, trailing=True)
    out, s = await monitor(tr, c, 1931.0, {'hi': 1935.0, 'lo': 1925.0})
    rep = updates(s, 'trailing_applied=false')
    check('S2 trailing_applied sin activación -> sl vuelve a 1959.97515 (el de Bybit) y trailing_applied=false',
          rep and abs(rep[0][0] - 1959.97515) < 1e-9, rep)
    check('S2 auditoría trailing_sync_repaired con el sl ficticio y el bueno',
          audit_actions(s) == ['trailing_sync_repaired'] and s['audit'][0]['data']['fake_sl'] == 1915.56, s.get('audit'))
    check('S2 no se envía nada a Bybit (su SL ya era el correcto)', not c.stops, c.stops)

    # S3. Reparado ANTES del BE: el precio tocó el BE (1902.04) sin llegar a la activación -> BE mueve el SL a la
    #     entrada en Bybit (con el sl ficticio se marcaba be_activated sin mover nada)
    c = Client(1915.56, 1959.97515, 1873.0797)
    out, s = await monitor(t93(sl=1915.56, trailing=True), c, 1905.0, {'hi': 1935.0, 'lo': 1900.0})
    check('S3 BE con sl ficticio heredado: se repara y el SL de Bybit pasa a la entrada 1931.01',
          c.stops and abs(c.stops[0][0] - 1931.01) < 1e-9 and out['be_activated'] == 1, (c.stops, out))

    # S4. Trailing ACTIVADO de verdad (mínimo 1890 <= 1896.25): Bybit informa 1909.31 (1890 + 19.31) -> se sincroniza
    c = Client(1909.31, 1959.97515, 1873.0797)
    out, s = await monitor(t93(), c, 1900.0, {'hi': 1935.0, 'lo': 1890.0})
    syn = updates(s, 'trailing_applied=true')
    check('S4 activado: se sincroniza 1909.31 con trailing_applied=true', syn and syn[0][0] == 1909.31, syn)

    # S5. Activado, pero el nivel informado no protege (precio 1915 ya por encima de 1909.31 en un short): se descarta
    c = Client(1909.31, 1959.97515, 1873.0797)
    out, s = await monitor(t93(), c, 1915.0, {'hi': 1935.0, 'lo': 1890.0})
    check('S5 nivel del lado equivocado del precio: descartado', not updates(s, 'trailing_applied=true'),
          updates(s, 'trailing_applied=true'))

    # S6. Activado, pero el nivel empeora el SL vigente (BE ya en 1931.01; nivel 1940): se descarta
    c = Client(1940.0, 1931.01, 1873.0797)
    out, s = await monitor(t93(sl=1931.01, be_activated=True), c, 1900.0, {'hi': 1935.0, 'lo': 1890.0})
    check('S6 nivel que empeora el SL vigente: descartado', not updates(s, 'trailing_applied=true'),
          updates(s, 'trailing_applied=true'))

    # C1. Circuit breaker con el estado real de #91 (sl ficticio 2039.87): con la marca a 2065.01 (+0,42 %) NO cierra
    c = Client(2039.87, 2087.17495, 1994.6401, mark=2065.01)
    out, closed = await breaker(t91(), c, {'hi': 2070.0, 'lo': 2030.0})
    check('C1 #91 sin activación: el circuit breaker NO cierra con +0,42 % (antes cerró: -174,82 USDT)',
          not closed, (closed, out))

    # C2. Mismo trade con el trailing activado de verdad (mínimo 2015 <= 2019.32) y la marca 1,23 % sobre el SL vivo:
    #     el circuit breaker sigue siendo la red de seguridad y cierra
    out, closed = await breaker(t91(), c, {'hi': 2070.0, 'lo': 2015.0})
    check('C2 activado y Bybit no disparó: el circuit breaker cierra (red de seguridad intacta)',
          closed == ['circuit_breaker_max_loss'], closed)

    # C3. Control sin trailing: más allá de 1,2x la distancia del SL original (marca 2126) cierra
    c = Client(None, 2087.17495, 1994.6401, mark=2126.0)
    out, closed = await breaker(t91(sl=2087.17495, trailing=False), c, {'hi': 2130.0, 'lo': 2050.0})
    check('C3 sin trailing, marca 2126 (> 1,2x el SL original): cierra', closed == ['circuit_breaker_max_loss'], closed)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(0 if fails == 0 else 1)


if __name__ == '__main__':
    asyncio.run(main())
